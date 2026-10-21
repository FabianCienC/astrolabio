"""`GET /api/galaxy`: the full sanitized snapshot of the cluster."""

from fastapi import APIRouter

from ..contract.example import example_galaxy
from ..contract.models import Galaxy

router = APIRouter(prefix="/api")


@router.get("/galaxy", response_model=Galaxy)
async def get_galaxy() -> Galaxy:
    # Temporary until the informers exist (PLAN E1.3-E1.5): serves the example galaxy.
    return example_galaxy()
