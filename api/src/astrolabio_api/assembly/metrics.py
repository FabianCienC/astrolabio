"""CPU and memory from metrics-server, as contract `Metrics` (millicores and MiB).

Only the usage numbers are read; names are used to match pods and nodes, never
published. With no metrics (metrics-server missing), everything is `Metrics()`.
"""

import re
from collections.abc import Iterable

from ..contract.models import Metrics, NodeId
from .raw import RawObject, Snapshot, name, namespace

_QUANTITY = re.compile(r"^(\d+(?:\.\d+)?)([a-zA-Z]*)$")
_CPU_TO_MILLI = {"n": 1e-6, "u": 1e-3, "m": 1.0, "": 1000.0}
_BYTES = {
    "": 1, "k": 1e3, "M": 1e6, "G": 1e9, "Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40,
}  # fmt: skip

PodKey = tuple[str | None, str]


def cpu_millicores(quantity: str) -> float | None:
    match = _QUANTITY.match(quantity or "")
    if not match or match[2] not in _CPU_TO_MILLI:
        return None
    return float(match[1]) * _CPU_TO_MILLI[match[2]]


def memory_mib(quantity: str) -> float | None:
    match = _QUANTITY.match(quantity or "")
    if not match or match[2] not in _BYTES:
        return None
    return float(match[1]) * _BYTES[match[2]] / 2**20


def _metrics(usages: Iterable[dict]) -> Metrics:
    cpu = mem = 0.0
    seen = False
    for usage in usages:
        c, m = cpu_millicores(usage.get("cpu", "")), memory_mib(usage.get("memory", ""))
        if c is None or m is None:
            continue
        cpu, mem, seen = cpu + c, mem + m, True
    return Metrics(cpu_millicores=round(cpu), memory_mib=round(mem)) if seen else Metrics()


def pod_metrics(snapshot: Snapshot) -> dict[PodKey, Metrics]:
    """Per pod (namespace, name): the sum of its containers."""
    return {
        (namespace(o), name(o)): _metrics(c.get("usage") or {} for c in o.get("containers") or [])
        for o in snapshot["podmetrics"]
    }


def node_metrics(snapshot: Snapshot, node_ids: dict[str, NodeId]) -> dict[NodeId, Metrics]:
    """Per generic node id; hostnames are only used to match."""
    return {
        node_ids[name(o)]: _metrics([o.get("usage") or {}])
        for o in snapshot["nodemetrics"]
        if name(o) in node_ids
    }


def pod_key(raw: RawObject) -> PodKey:
    return namespace(raw), name(raw)


def total(metrics: Iterable[Metrics]) -> Metrics:
    """The sum of several objects' metrics; empty if none of them has any."""
    known = [m for m in metrics if m.cpu_millicores is not None]
    if not known:
        return Metrics()
    return Metrics(
        cpu_millicores=sum(m.cpu_millicores or 0 for m in known),
        memory_mib=sum(m.memory_mib or 0 for m in known),
    )
