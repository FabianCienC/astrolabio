"""`GET /api/galaxy`: the full sanitized snapshot of the cluster."""

from fastapi import APIRouter, HTTPException, Request, Response

from ..contract.models import Galaxy
from ..live import Broadcaster

router = APIRouter(prefix="/api")


@router.get("/galaxy", response_model=Galaxy)
async def get_galaxy(request: Request) -> Response:
    # The galaxy /ws pushes, already serialized: a request costs nothing to assemble.
    broadcaster: Broadcaster = request.app.state.broadcaster
    payload = broadcaster.current()
    if payload is None:
        raise HTTPException(status_code=503, detail="cluster cache is still syncing")
    return Response(payload, media_type="application/json")
