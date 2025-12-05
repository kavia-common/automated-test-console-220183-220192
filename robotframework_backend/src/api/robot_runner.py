from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, AsyncGenerator

from robot import run_cli

from sqlalchemy.orm import Session

from src.core.settings import settings
from src.db.repositories import (
    create_test_run,
    finalize_test_run,
    add_batch_log,
    add_fail_log,
    count_case_status,
)
from src.db.database import SessionLocal


class RobotRunController:
    """Controls a single Robot Framework run and its process lifecycle."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._proc_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._current_run_id: Optional[int] = None
        self._current_log_file: Optional[str] = None
        self._expected_total: int = 0
        self._current_case: Dict[str, Any] = {}

    # PUBLIC_INTERFACE
    async def run(
        self,
        project: Optional[str] = None,
        suite: Optional[str] = None,
        tests: Optional[List[str]] = None,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        variables: Optional[Dict[str, Any]] = None,
        loop: int = 1,
        dry_run: bool = False,
        batch: bool = False,
    ) -> Dict[str, Any]:
        """Schedule and execute Robot run asynchronously. Returns metadata about the scheduled run."""
        async with self._lock:
            if self._proc_task and not self._proc_task.done():
                raise RuntimeError("A run is already in progress")
            os.makedirs(settings.LOG_DIR, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            log_dir = os.path.join(settings.LOG_DIR, f"run_{timestamp}")
            os.makedirs(log_dir, exist_ok=True)
            run_log_path = os.path.join(log_dir, "runner.log")
            self._current_log_file = run_log_path

            # Persist run record
            with SessionLocal() as db:
                run = create_test_run(
                    db=db,
                    project=project,
                    suite_name=suite,
                    total_cases=0,
                    logs_path=log_dir,
                )
                self._current_run_id = run.id

            # Spawn background execution task
            self._stop_event.clear()
            self._proc_task = asyncio.create_task(
                self._execute_robot(
                    log_dir=log_dir,
                    project=project,
                    suite=suite,
                    tests=tests,
                    include_tags=include_tags,
                    exclude_tags=exclude_tags,
                    variables=variables,
                    loop=loop,
                    dry_run=dry_run,
                    batch=batch,
                )
            )
            return {"run_id": self._current_run_id, "status": "running", "logs_path": log_dir}

    async def _execute_robot(
        self,
        log_dir: str,
        project: Optional[str],
        suite: Optional[str],
        tests: Optional[List[str]],
        include_tags: Optional[List[str]],
        exclude_tags: Optional[List[str]],
        variables: Optional[Dict[str, Any]],
        loop: int,
        dry_run: bool,
        batch: bool,
    ) -> None:
        """Internal: execute Robot with the given parameters, update DB/logs, handle loop/batch."""
        run_id = self._current_run_id
        if not run_id:
            return

        # Build CLI arguments for Robot Framework
        def build_args() -> List[str]:
            args: List[str] = [
                "--outputdir", os.path.join(log_dir, "robot"),
                "--log", "log.html",
                "--report", "report.html",
                "--xunit", "xunit.xml",
            ]
            if dry_run:
                args += ["--dryrun"]
            if include_tags:
                for it in include_tags:
                    args += ["-i", it]
            if exclude_tags:
                for et in exclude_tags:
                    args += ["-e", et]
            if variables:
                for k, v in variables.items():
                    args += ["--variable", f"{k}:{v}"]
            if suite:
                args += ["--suite", suite]
            # Test selection
            if tests:
                for t in tests:
                    args += ["--test", t]
            # Root path
            args.append(settings.ROBOT_PROJECT_ROOT)
            return args

        os.makedirs(log_dir, exist_ok=True)
        runner_log_file = os.path.join(log_dir, "runner.log")

        # Basic file logger
        def write_line(msg: str) -> None:
            ts = datetime.utcnow().isoformat()
            with open(runner_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")

        passed_total, failed_total = 0, 0
        try:
            for i in range(loop or 1):
                if self._stop_event.is_set():
                    write_line("Stop requested; breaking the loop.")
                    break
                write_line(f"Starting Robot execution, loop {i+1}/{loop}")
                args = build_args()
                # Call Robot in-process using run_cli to avoid managing external subprocess
                start_time = time.time()
                rc = await asyncio.to_thread(run_cli, args)
                elapsed = time.time() - start_time
                write_line(f"Robot finished with rc={rc} in {elapsed:.2f}s")

                # Update DB with counts and synthetic logs (We don't parse output.xml here)
                with SessionLocal() as db:
                    # We compute counts from recorded case results if any; otherwise fallback to rc
                    p, f, total = count_case_status(db, run_id)
                    # If nothing recorded, infer some outcome from rc
                    if total == 0:
                        if rc == 0:
                            p, f, total = 1, 0, 1
                        else:
                            p, f, total = 0, 1, 1
                    passed_total += p
                    failed_total += f
                    add_batch_log(db, run_id, f"Loop {i+1} completed: passed={p}, failed={f}, rc={rc}")
                    if f > 0:
                        add_fail_log(
                            db,
                            run_id,
                            message=f"{f} failures detected in loop {i+1}",
                            error_type="RobotFailure",
                        )

                if batch and i < (loop - 1):
                    write_line("Batch mode: short delay before next loop.")
                    await asyncio.sleep(1.0)

            # Finalize
            final_status = "stopped" if self._stop_event.is_set() else ("failed" if failed_total > 0 else "passed")
            with SessionLocal() as db:
                finalize_test_run(db, run_id, status=final_status, passed=passed_total, failed=failed_total)
                add_batch_log(
                    db,
                    run_id,
                    (
                        f"Run finalized with status={final_status}, "
                        f"passed={passed_total}, failed={failed_total}"
                    ),
                )
        except Exception as ex:
            with SessionLocal() as db:
                add_fail_log(Session(db.connection()), run_id, message=str(ex), error_type="RunnerError")
            write_line(f"Exception during execution: {ex!r}")
            with SessionLocal() as db:
                finalize_test_run(db, run_id, status="error", passed=passed_total, failed=failed_total)
        finally:
            # Clear current pointers
            self._current_run_id = None

    # PUBLIC_INTERFACE
    async def stop(self) -> Dict[str, Any]:
        """Signal the running task to stop; returns whether a task was running."""
        async with self._lock:
            if self._proc_task and not self._proc_task.done():
                self._stop_event.set()
                return {"stopped": True, "run_id": self._current_run_id}
            return {"stopped": False, "run_id": self._current_run_id}

    # PUBLIC_INTERFACE
    def get_current_run(self) -> Optional[int]:
        """Return current run id if running."""
        if self._proc_task and not self._proc_task.done():
            return self._current_run_id
        return None

    # PUBLIC_INTERFACE
    def get_log_file(self) -> Optional[str]:
        """Return current runner log file if running."""
        return self._current_log_file

    # PUBLIC_INTERFACE
    def set_expected_total(self, total: int) -> None:
        """Set expected total test cases for the current run."""
        self._expected_total = max(0, int(total or 0))

    # PUBLIC_INTERFACE
    def get_expected_total(self) -> int:
        """Get expected total test cases for the current run."""
        return self._expected_total

    # PUBLIC_INTERFACE
    def get_current_case_info(self) -> Dict[str, Any]:
        """Get information about the currently running case (best effort placeholder)."""
        return dict(self._current_case)

    # PUBLIC_INTERFACE
    async def stream_log(self) -> AsyncGenerator[str, None]:
        """Async generator that tails the current runner log file for SSE."""
        log_file = self._current_log_file
        if not log_file or not os.path.exists(log_file):
            # Yield a minimal message to avoid empty stream
            yield "event: message\ndata: No log available\n\n"
            return
        # Tail-like behavior
        with open(log_file, "r", encoding="utf-8") as f:
            # Seek to end initially
            f.seek(0, os.SEEK_END)
            while True:
                # When stop event is set and process is done, break after draining
                line = f.readline()
                if not line:
                    if self._stop_event.is_set() and (not self._proc_task or self._proc_task.done()):
                        break
                    await asyncio.sleep(0.5)
                    continue
                yield f"event: message\ndata: {line.rstrip()}\n\n"


# Singleton controller
controller = RobotRunController()
