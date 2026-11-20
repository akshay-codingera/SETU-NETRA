"""
telemetry.py: Server-Sent Events (SSE) streaming endpoint (/api/v1/events/stream).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Header, Request
from starlette.responses import StreamingResponse

from setu_netra.api.event_bus import get_event_bus

router = APIRouter(prefix="/events", tags=["Telemetry & Events"])


@router.get("/stream")
async def stream_events(
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """
    Real-time Server-Sent Events (SSE) telemetry stream.
    
    Features:
    - 2048-event historical replay if Last-Event-ID is provided.
    - 15-second heartbeat ping comments (: ping\\n\\n).
    - Monotonically increasing event IDs and correlation IDs.
    - Automatic slow-client frame dropping with backpressure alerts.
    """
    event_bus = get_event_bus()
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    
    parsed_last_id: Optional[int] = None
    if last_event_id and last_event_id.isdigit():
        parsed_last_id = int(last_event_id)

    async def _event_generator():
        try:
            async for sse_chunk in event_bus.subscribe(sub_id=sub_id, last_event_id=parsed_last_id):
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                yield sse_chunk
        except Exception:
            pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
