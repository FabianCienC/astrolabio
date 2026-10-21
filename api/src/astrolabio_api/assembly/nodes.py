"""Nodes are published under generic ids: hostnames never leave the API."""

from ..contract.models import NodeId
from .raw import RawObject, labels, name

CONTROL_PLANE_LABEL = "node-role.kubernetes.io/control-plane"
_WORKER_IDS: tuple[NodeId, ...] = ("worker-1", "worker-2")


def node_ids(nodes: list[RawObject]) -> dict[str, NodeId]:
    """Hostname -> generic id: the control plane, then the workers in name order.

    Nodes beyond the contract's three get no id, so their pods show no node.
    """
    control_planes = sorted((n for n in nodes if CONTROL_PLANE_LABEL in labels(n)), key=name)
    workers = sorted((n for n in nodes if CONTROL_PLANE_LABEL not in labels(n)), key=name)
    ids: dict[str, NodeId] = {}
    if control_planes:
        ids[name(control_planes[0])] = "control-plane"
    for node, node_id in zip(workers, _WORKER_IDS, strict=False):
        ids[name(node)] = node_id
    return ids
