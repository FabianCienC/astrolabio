"""`/ws`: the live galaxy. The current one on connect, then each change.

Read-only like the rest of the API: whatever a client sends is read only to notice
the disconnect, and discarded.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..live import Broadcaster

router = APIRouter()

# Close codes (RFC 6455): policy violation, and "try again later".
POLICY_VIOLATION = 1008
TRY_AGAIN_LATER = 1013


@router.websocket("/ws")
async def galaxy_stream(websocket: WebSocket) -> None:
    if not websocket.app.state.settings.allows_origin(websocket.headers.get("origin")):
        await websocket.close(code=POLICY_VIOLATION)
        return
    broadcaster: Broadcaster = websocket.app.state.broadcaster
    # Cloudflare names the visitor (traffic only reaches us through its tunnel).
    queue = broadcaster.subscribe(websocket.headers.get("cf-connecting-ip"))
    if queue is None:  # too many clients (or from this visitor), or still syncing
        await websocket.close(code=TRY_AGAIN_LATER)
        return

    await websocket.accept()
    sender = asyncio.create_task(_send(websocket, queue))
    try:
        while (await websocket.receive())["type"] != "websocket.disconnect":
            pass  # clients have nothing to say: discard
    finally:
        broadcaster.unsubscribe(queue)
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender


async def _send(websocket: WebSocket, queue: asyncio.Queue[str]) -> None:
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):
        while True:
            await websocket.send_text(await queue.get())
