def test_health_and_db_info(app_client):
    r = app_client.get("/")
    assert r.status_code == 200
    assert r.json()["message"] == "Healthy"

    dbi = app_client.get("/db_info")
    assert dbi.status_code == 200
    assert "engine_url" in dbi.json()

    dbc = app_client.get("/db_check")
    assert dbc.status_code == 200
    assert dbc.json()["ok"] is True
