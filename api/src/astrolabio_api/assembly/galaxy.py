"""`assemble_galaxy`: the informers' snapshot in, the public `Galaxy` out."""

from datetime import UTC, datetime

from ..contract.models import Core, Galaxy
from .nodes import node_ids
from .projects import build_constellations
from .raw import Snapshot


def assemble_galaxy(snapshot: Snapshot, now: datetime | None = None) -> Galaxy:
    ids = node_ids(snapshot["nodes"])
    return Galaxy(
        generated_at=now or datetime.now(UTC),
        constellations=build_constellations(snapshot, ids),
        # The infra catalog and the node suns come with PLAN E1.6.
        core=Core(components=[], nodes=[]),
    )
