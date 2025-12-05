from datetime import datetime, timedelta

from src.db.repositories import (
    create_test_run,
    finalize_test_run,
    add_case_result,
    add_batch_log,
    add_fail_log,
    get_recent_runs,
    get_run_stats,
    count_case_status,
)
from src.db import models


def test_create_and_finalize_run(db_session):
    run = create_test_run(db_session, project="proj", suite_name="suite1", total_cases=5, logs_path="/tmp/logs/run1")
    assert run.id > 0
    assert run.status == "running"
    assert run.project == "proj"
    assert run.total_cases == 5
    assert run.logs_path.endswith("/tmp/logs/run1")

    updated = finalize_test_run(db_session, run.id, status="passed", passed=5, failed=0)
    assert updated is not None
    assert updated.status == "passed"
    assert updated.passed == 5
    assert updated.failed == 0
    assert updated.end_time is not None

    # get_run_stats reflects finalized values
    stats = get_run_stats(db_session, run.id)
    assert stats == (5, 5, 0)


def test_case_results_and_counts(db_session):
    run = create_test_run(db_session, project=None, suite_name=None, total_cases=0)
    # Add case results
    add_case_result(db_session, run_id=run.id, case_name="Case A", status="passed", duration_sec=0.5, suite_name="S1")
    add_case_result(db_session, run_id=run.id, case_name="Case B", status="failed", duration_sec=0.2, suite_name="S1")
    add_case_result(db_session, run_id=run.id, case_name="Case C", status="passed", duration_sec=0.3, suite_name="S2")

    p, f, t = count_case_status(db_session, run.id)
    assert (p, f, t) == (2, 1, 3)

    # finalize should not break
    finalize_test_run(db_session, run.id, status="failed", passed=p, failed=f)
    stats = get_run_stats(db_session, run.id)
    assert stats == (0, 2, 1)  # total_cases is the TestRun.total_cases field, left 0 intentionally


def test_logs_and_recent_runs(db_session):
    # Prepare two runs with logs
    r1 = create_test_run(db_session, project="A", suite_name="S", total_cases=0)
    r2 = create_test_run(db_session, project="B", suite_name="S", total_cases=0)

    # Add logs with time ordering
    past = datetime.utcnow() - timedelta(minutes=5)
    add_batch_log(db_session, r1.id, "started r1", timestamp=past)
    add_batch_log(db_session, r2.id, "started r2")

    add_fail_log(db_session, r2.id, "failure happened", error_type="RobotFailure")

    # Recent runs should include both
    recent = get_recent_runs(db_session, limit=10)
    assert isinstance(recent, list)
    assert set([rc.id for rc in recent]) >= {r1.id, r2.id}

    # Ensure fail log relation exists
    flogs = db_session.query(models.FailLog).filter(models.FailLog.test_run_id == r2.id).all()
    assert len(flogs) == 1
    assert flogs[0].error_type == "RobotFailure"
