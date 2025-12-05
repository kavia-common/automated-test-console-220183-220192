from typing import AsyncGenerator, Optional

from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from src.api.robot_runner import controller


# PUBLIC_INTERFACE
async def get_log_sse(request: Optional[Request] = None) -> EventSourceResponse:
    """Return an SSE response streaming current run log, or an empty stream.

    Ensures proper SSE/CORS headers for consumption by browsers.
    """
    async def gen() -> AsyncGenerator[str, None]:
        async for chunk in controller.stream_log():
            yield chunk

    # Derive origin header for CORS echo if available
    origin = None
    if request is not None:
        origin = request.headers.get("origin")

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # for proxies like nginx
    }
    # When origin is present, reflect it back to satisfy CORS for credential-less SSE
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    else:
        # As a safe default in dev, allow localhost frontend
        headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
    headers["Access-Control-Allow-Credentials"] = "true"

    return EventSourceResponse(gen(), ping=10000, headers=headers)
