"""`assemble_galaxy`: the informers' snapshot in, the public `Galaxy` out."""

from datetime import UTC, datetime

from ..contract.models import Galaxy
from .core import build_core
from .nodes import node_ids
from .projects import build_constellations
from .raw import Snapshot


def assemble_galaxy(snapshot: Snapshot, now: datetime | None = None) -> Galaxy:
    ids = node_ids(snapshot["nodes"])
    constellations = build_constellations(snapshot, ids)
    project_pods = [p for c in constellations for w in c.workloads for p in w.all_pods()]
    return Galaxy(
        generated_at=now or datetime.now(UTC),
        constellations=constellations,
        core=build_core(snapshot, ids, project_pods),
    )
