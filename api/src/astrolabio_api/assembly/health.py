"""Health rules. The scene never draws health; the sidebar shows it as text."""

from collections.abc import Iterable

from ..contract.models import Health, PodPhase, Replicas

_SEVERITY: dict[Health, int] = {"ok": 0, "unknown": 1, "degraded": 2, "down": 3}


def worst(healths: Iterable[Health]) -> Health:
    """The most severe health; unknown when there is none."""
    return max(healths, key=_SEVERITY.__getitem__, default="unknown")


def replicas_health(replicas: Replicas) -> Health:
    # Scaled to zero serves nothing, so it reads as down, not unknown.
    if replicas.ready == 0:
        return "down"
    return "ok" if replicas.ready >= replicas.desired else "degraded"


def pod_health(phase: PodPhase, ready: bool) -> Health:
    match phase:
        case "Running":
            return "ok" if ready else "degraded"
        case "Succeeded":
            return "ok"
        case "Pending":
            return "degraded"
        case "Failed":
            return "down"
        case _:
            return "unknown"


def ready_health(ready: int, total: int) -> Health:
    """Health of something that depends on `total` backends, `ready` of them up."""
    if total == 0 or ready == 0:
        return "down"
    return "ok" if ready == total else "degraded"
