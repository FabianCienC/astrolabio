"""`GET /api/galaxy`: the full sanitized snapshot of the cluster."""

from fastapi import APIRouter, HTTPException, Request

from ..assembly import assemble_galaxy
from ..contract.example import example_galaxy
from ..contract.models import Galaxy

router = APIRouter(prefix="/api")


@router.get("/galaxy", response_model=Galaxy)
async def get_galaxy(request: Request) -> Galaxy:
    cluster = request.app.state.cluster
    if cluster is None:  # ASTROLABIO_SOURCE=example
        return example_galaxy()
    if not cluster.synced:
        raise HTTPException(status_code=503, detail="cluster cache is still syncing")
    return assemble_galaxy(cluster.snapshot())
