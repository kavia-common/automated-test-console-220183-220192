from src.core.settings import settings


def test_logs_sse_headers_reflect_origin(app_client, monkeypatch):
    monkeypatch.setattr(settings, "USE_SSE", True, raising=False)
    # Send an Origin header; our SSE response should echo it in Access-Control-Allow-Origin
    origin = "http://localhost:3000"
    resp = app_client.get("/logs", headers={"Origin": origin})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert resp.headers.get("access-control-allow-origin") == origin
