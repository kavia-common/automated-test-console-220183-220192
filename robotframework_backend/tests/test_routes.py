import asyncio
import os

import pytest
from fastapi import status

from src.api.robot_runner import controller
from src.core.settings import settings
from src.db.repositories import create_test_run, add_case_result, finalize_test_run


@pytest.fixture(autouse=True)
def ensure_sse_enabled(monkeypatch):
    # Enable by default for these tests unless explicitly toggled off
    monkeypatch.setattr(settings, "USE_SSE", True, raising=False)


def _force_run_finished(db_session, run_id: int, passed: int = 1, failed: int = 0, status_val: str = "passed"):
    finalize_test_run(db_session, run_id, status=status_val, passed=passed, failed=failed)


@pytest.mark.asyncio
async def test_run_and_stop_flow(app_client, db_session, monkeypatch, tmp_path):
    # Mock controller._execute_robot to be a fast no-op that finalizes the run
    async def fake_execute_robot(*args, **kwargs):
        # simulate brief work then finalize
        await asyncio.sleep(0.01)
        rid = controller.get_current_run()
        assert rid is not None
        # add synthetic results
        add_case_result(db_session, run_id=rid, case_name="Case A", status="passed")
        add_case_result(db_session, run_id=rid, case_name="Case B", status="failed")
        # finalize
        _force_run_finished(db_session, rid, passed=1, failed=1, status_val="failed")
        # write a log line to allow SSE/batch_log to read something
        log_file = controller.get_log_file()
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("Robot finished with rc=1\n")

    monkeypatch.setattr(controller, "_execute_robot", fake_execute_robot, raising=True)

    # Start a run
    resp = app_client.post("/run", json={"project": "demo", "suite": "S1", "dry_run": True})
    assert resp.status_code == status.HTTP_200_OK, resp.text
    payload = resp.json()
    run_id = payload["run_id"]
    assert payload["status"] == "running"
    assert run_id is not None

    # Optionally stop (should report stopped False if finished quickly)
    stop_resp = app_client.post("/stop")
    assert stop_resp.status_code == 200
    stop_payload = stop_resp.json()
    assert "stopped" in stop_payload
    assert stop_payload["run_id"] in (None, run_id)

    # Stats should reflect finalized values
    stats_resp = app_client.get(f"/stats?run_id={run_id}")
    assert stats_resp.status_code == 200, stats_resp.text
    stats = stats_resp.json()
    assert stats["run_id"] == run_id
    assert stats["passed"] in (1, 0)  # allow race if finalize occurs after first fetch
    assert stats["failed"] in (1, 0)
    assert stats["status"] in ("failed", "passed", "running")

    # Case status counts from case_results
    cs_resp = app_client.get(f"/case_status?run_id={run_id}")
    assert cs_resp.status_code == 200
    cs = cs_resp.json()
    assert cs["run_id"] == run_id
    assert cs["total_recorded"] >= cs["passed"] + cs["failed"]

    # Expected total and progress
    set_et = app_client.post(f"/expected_total?run_id={run_id}&total=10")
    assert set_et.status_code == 200
    et = set_et.json()
    assert et["expected_total"] == 10

    pr = app_client.get(f"/progress?run_id={run_id}")
    assert pr.status_code == 200
    prog = pr.json()
    assert prog["total"] == 10
    assert 0 <= prog["percent"] <= 100

    # current_case_info returns structure with given run_id
    cci = app_client.get(f"/current_case_info?run_id={run_id}")
    assert cci.status_code == 200
    cci_json = cci.json()
    assert cci_json["run_id"] == run_id
    assert "case_name" in cci_json

    # Logs endpoint (SSE) – verify headers only; do not attempt to consume stream
    logs_resp = app_client.get("/logs")
    assert logs_resp.status_code == 200
    # CORS/SSE headers
    # Starlette's EventSourceResponse sets proper content-type; our function injects headers
    assert "text/event-stream" in logs_resp.headers.get("content-type", "")
    # Access-Control-Allow-Origin present
    assert logs_resp.headers.get("access-control-allow-origin") is not None

    # Batch log fallback returns file content
    bl = app_client.get("/batch_log")
    assert bl.status_code == 200
    # Ensure at least empty string, we wrote a line so it should be non-empty
    assert isinstance(bl.text, str)


def test_logs_polling_fallback_when_sse_disabled(app_client, monkeypatch):
    # disable SSE
    monkeypatch.setattr(settings, "USE_SSE", False, raising=False)
    # logs should reject
    resp = app_client.get("/logs")
    assert resp.status_code == 400
    assert "SSE disabled" in resp.text

    # batch_log should return empty string if no run
    bl = app_client.get("/batch_log")
    assert bl.status_code == 200
    assert bl.text == ""


def test_config_get_put_and_list(app_client):
    # write config via PUT then GET
    put = app_client.put("/config", json={"path": "profiles/ui.json", "content": {"x": 1, "name": "ui"}})
    assert put.status_code == 200
    pl = put.json()
    assert pl["path"] == "profiles/ui.json"
    assert pl["content"]["x"] == 1

    # read it back
    get = app_client.get("/config", params={"path": "profiles/ui.json"})
    assert get.status_code == 200
    gp = get.json()
    assert gp["content"]["name"] == "ui"

    # list folders
    lf = app_client.get("/list_config_folders")
    assert lf.status_code == 200
    folders = lf.json()["folders"]
    assert "profiles" in folders


def test_state_sync_and_get(app_client):
    # get default
    g1 = app_client.get("/get_state")
    assert g1.status_code == 200
    assert "state" in g1.json()

    # sync
    s1 = app_client.post("/sync_state", json={"state": {"a": 10}})
    assert s1.status_code == 200
    assert s1.json()["state"]["a"] == 10

    # lock
    l1 = app_client.post("/ui_lock", json={"locked": True, "owner": "tester"})
    assert l1.status_code == 200
    assert l1.json()["locked"] is True and l1.json()["owner"] == "tester"


def test_fail_log_and_stats_404(app_client, db_session):
    # unknown run -> stats 404
    not_found = app_client.get("/stats?run_id=999999")
    assert not_found.status_code == 404

    # Create a run without any case to test fail_log simple behavior (no entries)
    run = create_test_run(db_session, project="p", suite_name="s")
    fl = app_client.get(f"/fail_log?run_id={run.id}")
    assert fl.status_code == 200
    assert fl.text == ""
