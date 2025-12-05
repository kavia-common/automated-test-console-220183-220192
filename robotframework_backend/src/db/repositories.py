from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case as sa_case

from src.db import models


# PUBLIC_INTERFACE
def create_test_run(
    db: Session,
    project: Optional[str] = None,
    suite_name: Optional[str] = None,
    total_cases: int = 0,
    logs_path: Optional[str] = None,
) -> models.TestRun:
    """Create and persist a new TestRun with 'running' status."""
    run = models.TestRun(
        project=project,
        suite_name=suite_name,
        start_time=datetime.utcnow(),
        status="running",
        total_cases=total_cases,
        logs_path=logs_path,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# PUBLIC_INTERFACE
def finalize_test_run(
    db: Session, run_id: int, status: str, passed: int, failed: int
) -> Optional[models.TestRun]:
    """Mark a TestRun as finished, updating counts and status."""
    run = db.get(models.TestRun, run_id)
    if not run:
        return None
    run.end_time = datetime.utcnow()
    run.status = status
    run.passed = passed
    run.failed = failed
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# PUBLIC_INTERFACE
def add_case_result(
    db: Session,
    run_id: int,
    case_name: str,
    status: str,
    duration_sec: Optional[float] = None,
    message: Optional[str] = None,
    suite_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    tags: Optional[str] = None,
) -> models.TestCaseResult:
    """Create and persist a TestCaseResult for a given run."""
    rec = models.TestCaseResult(
        test_run_id=run_id,
        case_name=case_name,
        status=status,
        duration_sec=duration_sec,
        message=message,
        suite_name=suite_name,
        start_time=start_time,
        end_time=end_time,
        tags=tags,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# PUBLIC_INTERFACE
def add_batch_log(
    db: Session,
    run_id: int,
    message: str,
    level: str = "INFO",
    timestamp: Optional[datetime] = None,
) -> models.BatchLog:
    """Append a batch log line for a run."""
    entry = models.BatchLog(
        test_run_id=run_id,
        message=message,
        level=level,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# PUBLIC_INTERFACE
def add_fail_log(
    db: Session,
    run_id: int,
    message: str,
    error_type: Optional[str] = None,
    case_result_id: Optional[int] = None,
    details: Optional[str] = None,
) -> models.FailLog:
    """Append a failure log entry for a run (optionally tied to a case result)."""
    entry = models.FailLog(
        test_run_id=run_id,
        case_result_id=case_result_id,
        message=message,
        error_type=error_type,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# PUBLIC_INTERFACE
def get_recent_runs(db: Session, limit: int = 20) -> List[models.TestRun]:
    """Return most recent test runs by start_time."""
    stmt = select(models.TestRun).order_by(desc(models.TestRun.start_time)).limit(limit)
    return list(db.scalars(stmt))


# PUBLIC_INTERFACE
def get_run_stats(db: Session, run_id: int) -> Optional[Tuple[int, int, int]]:
    """Return tuple (total_cases, passed, failed) for a run."""
    run = db.get(models.TestRun, run_id)
    if not run:
        return None
    return (run.total_cases, run.passed, run.failed)


# PUBLIC_INTERFACE
def count_case_status(db: Session, run_id: int) -> Tuple[int, int, int]:
    """Compute counts for passed/failed/other from case results."""
    # Use sqlalchemy.case and func.sum for SQLAlchemy 2.x compatibility
    passed_case = sa_case((models.TestCaseResult.status == "passed", 1), else_=0)
    failed_case = sa_case((models.TestCaseResult.status == "failed", 1), else_=0)

    stmt = (
        select(
            func.sum(passed_case).label("passed"),
            func.sum(failed_case).label("failed"),
            func.count().label("total"),
        )
        .where(models.TestCaseResult.test_run_id == run_id)
    )
    passed, failed, total = db.execute(stmt).one()
    return int(passed or 0), int(failed or 0), int(total or 0)
