from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.schemas import (
    RunRequest,
    RunResponse,
    StopResponse,
    StatsResponse,
    CaseStatusResponse,
    ProgressResponse,
    CurrentCaseInfo,
    ConfigPayload,
    ConfigListResponse,
    UILockRequest,
    SyncStateRequest,
    GetStateResponse,
    ExpectedTotalResponse,
)
from src.api.robot_runner import controller
from src.api.config_service import read_config, write_config, list_config_folders
from src.api.state_service import set_ui_lock, sync_state, get_state
from src.api.log_stream import get_log_sse
from src.db.database import get_db
from src.db.repositories import get_run_stats, count_case_status
from src.core.settings import settings


router = APIRouter(tags=["robot"])


# PUBLIC_INTERFACE
@router.post(
    "/run",
    response_model=RunResponse,
    summary="Start Robot run",
    description="Start a Robot Framework run with specified options.",
)
async def start_run(payload: RunRequest) -> RunResponse:
    """Start a background robot run and return its run id and initial status."""
    try:
        result = await controller.run(
            project=payload.project,
            suite=payload.suite,
            tests=payload.tests,
            include_tags=payload.include_tags,
            exclude_tags=payload.exclude_tags,
            variables=payload.variables,
            loop=payload.loop or 1,
            dry_run=payload.dry_run or False,
            batch=payload.batch or False,
        )
        return RunResponse(run_id=result["run_id"], status=result["status"], logs_path=result.get("logs_path"))
    except RuntimeError as re:
        raise HTTPException(status_code=409, detail=str(re))


# PUBLIC_INTERFACE
@router.post(
    "/stop",
    response_model=StopResponse,
    summary="Stop run",
    description="Stop the currently running Robot process if any.",
)
async def stop_run() -> StopResponse:
    """Attempt to stop the currently running robot run."""
    res = await controller.stop()
    return StopResponse(run_id=res.get("run_id"), stopped=res.get("stopped", False))


# PUBLIC_INTERFACE
@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Run stats",
    description="Get aggregated statistics for a run.",
)
def stats(
    run_id: int = Query(..., description="Run id"),
    db: Session = Depends(get_db),
) -> StatsResponse:
    """Return aggregated statistics for a run."""
    tup = get_run_stats(db, run_id)
    if not tup:
        raise HTTPException(status_code=404, detail="Run not found")
    total, passed, failed = tup
    # Lookup status
    from src.db import models
    run = db.get(models.TestRun, run_id)
    status = run.status if run else "unknown"
    return StatsResponse(run_id=run_id, total=total, passed=passed, failed=failed, status=status)


# PUBLIC_INTERFACE
@router.get(
    "/case_status",
    response_model=CaseStatusResponse,
    summary="Case status counts",
    description="Return counts for passed/failed/recorded cases.",
)
def case_status(
    run_id: int = Query(..., description="Run id"),
    db: Session = Depends(get_db),
) -> CaseStatusResponse:
    """Return per-case status summary for a run."""
    passed, failed, total = count_case_status(db, run_id)
    return CaseStatusResponse(run_id=run_id, passed=passed, failed=failed, total_recorded=total)


# PUBLIC_INTERFACE
@router.get(
    "/progress",
    response_model=ProgressResponse,
    summary="Run progress",
    description="Return computed progress for a run from expected total.",
)
def progress(
    run_id: int = Query(..., description="Run id"),
    db: Session = Depends(get_db),
) -> ProgressResponse:
    """Compute progress as (completed/expected_total)*100 using expected_total from controller."""
    expected = controller.get_expected_total()
    p, f, total = count_case_status(db, run_id)
    completed = p + f if expected == 0 else min(expected, p + f)
    percent = 0.0 if expected == 0 else round(100.0 * completed / float(expected), 2)
    return ProgressResponse(run_id=run_id, completed=completed, total=expected, percent=percent)


# PUBLIC_INTERFACE
@router.get(
    "/current_case_info",
    response_model=CurrentCaseInfo,
    summary="Current case info",
    description="Get information about the currently executing test case.",
)
def current_case_info(
    run_id: int = Query(..., description="Run id"),
) -> CurrentCaseInfo:
    """Return best-effort info about currently running case."""
    info = controller.get_current_case_info()
    return CurrentCaseInfo(
        run_id=run_id,
        case_name=info.get("case_name"),
        suite_name=info.get("suite_name"),
        start_time=info.get("start_time"),
    )


# PUBLIC_INTERFACE
@router.get(
    "/logs",
    summary="Stream logs (SSE)",
    description="Stream the current run logs via Server-Sent Events if enabled.",
)
async def logs():
    """Return SSE stream for current run logs if USE_SSE is true, else 400."""
    if not settings.USE_SSE:
        raise HTTPException(status_code=400, detail="SSE disabled; use batch_log polling.")
    return await get_log_sse()


# PUBLIC_INTERFACE
@router.get(
    "/batch_log",
    summary="Batch log",
    description="Return current batch log contents for polling fallback.",
)
def batch_log():
    """Return entire current runner log file as text for polling fallback."""
    from starlette.responses import PlainTextResponse
    log_file = controller.get_log_file()
    if not log_file:
        return PlainTextResponse("")
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            return PlainTextResponse(content)
    except FileNotFoundError:
        return PlainTextResponse("")


# PUBLIC_INTERFACE
@router.get(
    "/fail_log",
    summary="Fail log",
    description="Return a simple joined fail log messages for current run.",
)
def fail_log(
    run_id: int = Query(..., description="Run id"),
    db: Session = Depends(get_db),
):
    """Return a text aggregation of failure logs for the run."""
    from starlette.responses import PlainTextResponse
    from src.db import models
    from sqlalchemy import select
    stmt = select(models.FailLog).where(models.FailLog.test_run_id == run_id).order_by(models.FailLog.timestamp)
    lines = []
    for row in db.scalars(stmt):
        lines.append(f"[{row.timestamp.isoformat()}] {row.error_type or 'Failure'}: {row.message}")
    # When there are no lines, return an explicit empty string
    if not lines:
        return PlainTextResponse("")
    return PlainTextResponse("\n".join(lines))


# PUBLIC_INTERFACE
@router.get(
    "/config",
    response_model=ConfigPayload,
    summary="Read config",
    description="Read YAML/JSON config content from CONFIG_DIR.",
)
def get_config(
    path: str = Query(..., description="Relative config path from CONFIG_DIR"),
) -> ConfigPayload:
    """Read a config file from CONFIG_DIR."""
    content = read_config(path)
    return ConfigPayload(path=path, content=content)


# PUBLIC_INTERFACE
@router.put(
    "/config",
    response_model=ConfigPayload,
    summary="Write config",
    description="Write YAML/JSON config content to CONFIG_DIR.",
)
def put_config(payload: ConfigPayload) -> ConfigPayload:
    """Write a config file to CONFIG_DIR."""
    written = write_config(payload.path, payload.content)
    return ConfigPayload(path=payload.path, content=written)


# PUBLIC_INTERFACE
@router.get(
    "/list_config_folders",
    response_model=ConfigListResponse,
    summary="List config folders",
    description="List folders under CONFIG_DIR.",
)
def list_configs() -> ConfigListResponse:
    """List available config folders under CONFIG_DIR."""
    return ConfigListResponse(folders=list_config_folders())


# PUBLIC_INTERFACE
@router.post(
    "/ui_lock",
    summary="Set UI lock",
    description="Set or clear UI lock to prevent concurrent actions.",
)
async def ui_lock(payload: UILockRequest):
    """Set or clear the UI lock state."""
    return await set_ui_lock(payload.locked, owner=payload.owner)


# PUBLIC_INTERFACE
@router.post(
    "/sync_state",
    response_model=GetStateResponse,
    summary="Sync state",
    description="Merge provided state into stored UI/app state.",
)
async def sync_state_route(payload: SyncStateRequest) -> GetStateResponse:
    """Merge provided state into store and return updated state."""
    state = await sync_state(payload.state or {})
    return GetStateResponse(state=state)


# PUBLIC_INTERFACE
@router.get(
    "/get_state",
    response_model=GetStateResponse,
    summary="Get state",
    description="Return stored UI/app state.",
)
async def get_state_route() -> GetStateResponse:
    """Return current UI/app state."""
    state = await get_state()
    return GetStateResponse(state=state)


# PUBLIC_INTERFACE
@router.get(
    "/expected_total",
    response_model=ExpectedTotalResponse,
    summary="Get expected total",
    description="Get expected total test cases for current run.",
)
async def get_expected_total(
    run_id: int = Query(..., description="Run id"),
) -> ExpectedTotalResponse:
    """Return expected total from the controller."""
    return ExpectedTotalResponse(run_id=run_id, expected_total=controller.get_expected_total())


# PUBLIC_INTERFACE
@router.post(
    "/expected_total",
    response_model=ExpectedTotalResponse,
    summary="Set expected total",
    description="Set expected total test cases for current run.",
)
async def set_expected_total(
    run_id: int = Query(..., description="Run id"),
    total: int = Query(..., description="Expected total"),
) -> ExpectedTotalResponse:
    """Set expected total in the controller and return the value."""
    controller.set_expected_total(total)
    return ExpectedTotalResponse(run_id=run_id, expected_total=controller.get_expected_total())
