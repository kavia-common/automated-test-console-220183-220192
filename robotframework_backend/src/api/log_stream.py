from typing import AsyncGenerator

from sse_starlette.sse import EventSourceResponse

from src.api.robot_runner import controller


# PUBLIC_INTERFACE
async def get_log_sse() -> EventSourceResponse:
    """Return an SSE response streaming current run log, or an empty stream."""
    async def gen() -> AsyncGenerator[str, None]:
        async for chunk in controller.stream_log():
            yield chunk
    return EventSourceResponse(gen(), ping=10000)
