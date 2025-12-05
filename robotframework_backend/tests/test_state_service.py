import pytest

from src.api.state_service import set_ui_lock, sync_state, get_state, get_lock_info


@pytest.mark.asyncio
async def test_ui_lock_and_info():
    res = await set_ui_lock(True, owner="tester")
    assert res["locked"] is True and res["owner"] == "tester"

    info = await get_lock_info()
    assert info["locked"] is True and info["owner"] == "tester"

    res = await set_ui_lock(False, owner=None)
    assert res["locked"] is False and res["owner"] is None


@pytest.mark.asyncio
async def test_sync_and_get_state():
    st = await sync_state({"a": 1, "b": {"x": True}})
    assert st["a"] == 1 and st["b"]["x"] is True

    # merge more keys
    st = await sync_state({"b": {"y": 2}, "c": "v"})
    # naive merge updates top-level only; nested dict replace behavior is acceptable here
    assert "c" in st
    assert "b" in st
    gs = await get_state()
    assert gs == st
