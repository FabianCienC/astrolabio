"""The galactic core: catalog components and the three node suns.

Platform pods and services are published anonymously (`core/<component>/pod-<n>`,
no names); nodes only by their generic ids. Nothing else from the platform
namespaces is read.
"""

from ..contract.models import (
    Core,
    Health,
    InfraComponent,
    Metrics,
    Node,
    NodeId,
    Pod,
    Replicas,
    Service,
)
from .catalog import CATALOG, Entry
from .health import ready_health, replicas_health
from .metrics import PodKey, node_metrics, pod_key, pod_metrics, total
from .projects import ARGO_NAMESPACE, argo_status, build_pod, pod_ready, workload_replicas
from .raw import RawObject, Snapshot, controller, in_namespace, labels, name, spec, status

_RESOURCE_KEYS = {
    "Deployment": "deployments",
    "StatefulSet": "statefulsets",
    "DaemonSet": "daemonsets",
}
_NODES: dict[NodeId, tuple[str, str]] = {
    "control-plane": ("control plane", "control-plane"),
    "worker-1": ("worker 1", "worker"),
    "worker-2": ("worker 2", "worker"),
}


def build_core(snapshot: Snapshot, node_ids: dict[str, NodeId], project_pods: list[Pod]) -> Core:
    usage = pod_metrics(snapshot)
    components = [c for entry in CATALOG if (c := _component(snapshot, entry, node_ids, usage))]
    published = [*project_pods, *(p for c in components for p in c.pods)]
    nodes = _nodes(snapshot["nodes"], node_ids, published, node_metrics(snapshot, node_ids))
    return Core(components=components, nodes=nodes)


def _component(
    snapshot: Snapshot,
    entry: Entry,
    node_ids: dict[str, NodeId],
    usage: dict[PodKey, Metrics],
) -> InfraComponent | None:
    backing = _backing(snapshot, entry)
    if backing is None:
        return None
    replicas, raw_pods = backing
    pods = [
        build_pod(raw, f"core/{entry.id}/pod-{i + 1}", None, node_ids, usage.get(pod_key(raw)))
        for i, raw in enumerate(raw_pods)
    ]
    application = next(
        (
            a
            for a in in_namespace(snapshot["applications"], ARGO_NAMESPACE)
            if name(a) == entry.application
        ),
        None,
    )
    return InfraComponent(
        id=entry.id,
        name=entry.name,
        purpose=entry.purpose,
        category=entry.category,
        system=entry.system,
        replicas=replicas,
        health=replicas_health(replicas),
        argo=argo_status(application),
        metrics=total(p.metrics for p in pods),
        pods=pods,
        services=_services(snapshot, entry, raw_pods, pods),
    )


def _backing(snapshot: Snapshot, entry: Entry) -> tuple[Replicas, list[RawObject]] | None:
    """The component's replicas and raw pods (sorted, so ids are stable); None if absent."""
    pods = in_namespace(snapshot["pods"], entry.namespace)
    if entry.kind == "StaticPod":
        mine = [p for p in pods if labels(p).get("component") == entry.workload]
        if not mine:
            return None
        return Replicas(desired=len(mine), ready=sum(map(pod_ready, mine))), mine

    workloads = in_namespace(snapshot[_RESOURCE_KEYS[entry.kind]], entry.namespace)
    workload = next((w for w in workloads if name(w) == entry.workload), None)
    if workload is None:
        return None
    owners = {(entry.kind, entry.workload)}
    if entry.kind == "Deployment":
        owners = {
            ("ReplicaSet", name(rs))
            for rs in in_namespace(snapshot["replicasets"], entry.namespace)
            if controller(rs) == ("Deployment", entry.workload)
        }
    return workload_replicas(entry.kind, workload), [p for p in pods if controller(p) in owners]


def _services(
    snapshot: Snapshot, entry: Entry, raw_pods: list[RawObject], pods: list[Pod]
) -> list[Service]:
    """Services that select the component's pods, plus its listed selectorless ones."""
    matched: list[list[Pod]] = []
    for raw in in_namespace(snapshot["services"], entry.namespace):
        selector = spec(raw).get("selector") or {}
        targets = [
            pod
            for pod, raw_pod in zip(pods, raw_pods, strict=True)
            if selector and all(labels(raw_pod).get(k) == v for k, v in selector.items())
        ]
        if targets:
            matched.append(targets)
    for namespace, service_name in entry.services:
        if any(name(s) == service_name for s in in_namespace(snapshot["services"], namespace)):
            matched.append(pods)
    return [
        Service(
            id=f"core/{entry.id}/service-{n + 1}",
            name=None,
            health=ready_health(sum(p.ready for p in targets), len(targets)),
            targets=[p.id for p in targets],
        )
        for n, targets in enumerate(matched)
    ]


def _nodes(
    nodes: list[RawObject],
    node_ids: dict[str, NodeId],
    pods: list[Pod],
    usage: dict[NodeId, Metrics],
) -> list[Node]:
    published = []
    for raw in nodes:
        node_id = node_ids.get(name(raw))
        if node_id is None:
            continue
        display_name, role = _NODES[node_id]
        published.append(
            Node(
                id=node_id,
                name=display_name,
                role=role,
                health=_node_health(raw),
                pods=sum(p.node == node_id for p in pods),
                metrics=usage.get(node_id, Metrics()),
            )
        )
    return sorted(published, key=lambda n: list(_NODES).index(n.id))


def _node_health(raw: RawObject) -> Health:
    ready = next(
        (c.get("status") for c in status(raw).get("conditions") or [] if c.get("type") == "Ready"),
        None,
    )
    return {"True": "ok", "False": "down"}.get(ready, "unknown")
