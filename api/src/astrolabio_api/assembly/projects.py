"""Visible projects: every namespace labeled `fabiancienfuegos.com/astrolabio: visible`
becomes a constellation with its workloads, active replica sets, pods, services and routes.

Pod names are published here because the project is shown on purpose. A namespace
whose data does not fit the contract is skipped and logged, so one bad annotation
can't take the whole galaxy down.
"""

import logging
import re
from dataclasses import dataclass

from pydantic import ValidationError

from ..contract.models import (
    ArgoHealth,
    ArgoStatus,
    ArgoSync,
    Commit,
    Constellation,
    Health,
    Metrics,
    NodeId,
    Pod,
    PodPhase,
    Replicas,
    ReplicaSet,
    Route,
    Service,
    Workload,
    WorkloadKind,
    is_public_host,
)
from . import annotations as ann
from .health import pod_health, ready_health, replicas_health, worst
from .metrics import PodKey, pod_key, pod_metrics, total
from .raw import (
    RawObject,
    Snapshot,
    annotations,
    controller,
    image_tag,
    in_namespace,
    labels,
    name,
    spec,
    status,
)

log = logging.getLogger(__name__)

ARGO_NAMESPACE = "argocd"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_POD_PHASES: set[PodPhase] = {"Pending", "Running", "Succeeded", "Failed", "Unknown"}
_ARGO_SYNC: set[ArgoSync] = {"Synced", "OutOfSync", "Unknown"}
_ARGO_HEALTH: set[ArgoHealth] = {
    "Healthy", "Progressing", "Degraded", "Suspended", "Missing", "Unknown",
}  # fmt: skip


def build_constellations(snapshot: Snapshot, node_ids: dict[str, NodeId]) -> list[Constellation]:
    constellations = []
    usage = pod_metrics(snapshot)
    for namespace in sorted(snapshot["namespaces"], key=name):
        if labels(namespace).get(ann.VISIBLE_LABEL) != "visible":
            continue
        try:
            constellations.append(_Project(snapshot, namespace, node_ids, usage).build())
        except ValidationError:
            log.exception("skipping namespace %s: it does not fit the contract", name(namespace))
    return constellations


def argo_status(application: RawObject | None) -> ArgoStatus | None:
    """Sync and health of an Argo CD Application (never its revision: private repo)."""
    if application is None:
        return None
    app_status = status(application)
    sync = (app_status.get("sync") or {}).get("status")
    health = (app_status.get("health") or {}).get("status")
    return ArgoStatus(
        sync=sync if sync in _ARGO_SYNC else "Unknown",
        health=health if health in _ARGO_HEALTH else "Unknown",
    )


def pod_ready(raw: RawObject) -> bool:
    return any(
        c.get("type") == "Ready" and c.get("status") == "True"
        for c in status(raw).get("conditions") or []
    )


def build_pod(
    raw: RawObject,
    id: str,
    pod_name: str | None,
    node_ids: dict[str, NodeId],
    metrics: Metrics | None = None,
) -> Pod:
    pod_status = status(raw)
    phase = pod_status.get("phase")
    phase = phase if phase in _POD_PHASES else "Unknown"
    ready = pod_ready(raw)
    return Pod(
        id=id,
        name=pod_name,
        phase=phase,
        ready=ready,
        restarts=sum(c.get("restartCount", 0) for c in pod_status.get("containerStatuses") or []),
        node=node_ids.get(spec(raw).get("nodeName", "")),
        health=pod_health(phase, ready),
        metrics=metrics or Metrics(),
    )


def workload_replicas(kind: WorkloadKind, raw: RawObject) -> Replicas:
    if kind == "DaemonSet":
        desired = status(raw).get("desiredNumberScheduled", 0)
        return Replicas(desired=desired, ready=status(raw).get("numberReady", 0))
    return Replicas(desired=spec(raw).get("replicas", 1), ready=status(raw).get("readyReplicas", 0))


@dataclass
class _Published:
    """A published pod and the labels services select it by."""

    pod: Pod
    labels: dict[str, str]


class _Project:
    def __init__(
        self,
        snapshot: Snapshot,
        namespace: RawObject,
        node_ids: dict[str, NodeId],
        usage: dict[PodKey, Metrics],
    ):
        self.ns = name(namespace)
        self.usage = usage
        self.namespace = namespace
        self.snapshot = snapshot
        self.node_ids = node_ids
        self.repo = ann.repo(annotations(namespace).get(ann.REPO))
        self.published: list[_Published] = []
        pods = in_namespace(snapshot["pods"], self.ns)
        self.pods_by_owner: dict[tuple[str, str], list[RawObject]] = {}
        for pod in pods:
            if owner := controller(pod):
                self.pods_by_owner.setdefault(owner, []).append(pod)

    def build(self) -> Constellation:
        notes = annotations(self.namespace)
        workloads = [
            *(self._workload("Deployment", d) for d in self._objects("deployments")),
            *(self._workload("StatefulSet", s) for s in self._objects("statefulsets")),
            *(self._workload("DaemonSet", d) for d in self._objects("daemonsets")),
        ]
        services = [self._service(s) for s in self._objects("services")]
        return Constellation(
            id=self.ns,
            project=ann.text(notes.get(ann.PROJECT)) or self.ns,
            description=ann.text(notes.get(ann.DESCRIPTION)),
            repo=self.repo,
            argo=argo_status(self._application()),
            health=worst(w.health for w in workloads),
            workloads=workloads,
            services=services,
            routes=[self._route(r, services) for r in self._objects("httproutes")],
        )

    def _objects(self, key: str) -> list[RawObject]:
        return in_namespace(self.snapshot[key], self.ns)

    def _id(self, kind: str, object_name: str) -> str:
        return f"{self.ns}/{kind}/{object_name}"

    def _pods(self, owner_kind: str, owner_name: str) -> list[Pod]:
        pods = []
        for raw in self.pods_by_owner.get((owner_kind, owner_name), []):
            pod = build_pod(
                raw,
                self._id("pod", name(raw)),
                name(raw),
                self.node_ids,
                self.usage.get(pod_key(raw)),
            )
            self.published.append(_Published(pod, labels(raw)))
            pods.append(pod)
        return pods

    def _workload(self, kind: WorkloadKind, raw: RawObject) -> Workload:
        notes = annotations(raw)
        replicas = workload_replicas(kind, raw)
        is_deployment = kind == "Deployment"
        replica_sets = self._replica_sets(name(raw)) if is_deployment else []
        pods = [] if is_deployment else self._pods(kind, name(raw))
        return Workload(
            id=self._id(kind.lower(), name(raw)),
            name=name(raw),
            kind=kind,
            description=ann.text(notes.get(ann.DESCRIPTION)),
            role=ann.role(notes.get(ann.ROLE)),
            criticality=ann.criticality(notes.get(ann.CRITICALITY)),
            replicas=replicas,
            health=replicas_health(replicas),
            commit=self._commit(raw),
            metrics=total(p.metrics for p in [*pods, *(p for rs in replica_sets for p in rs.pods)]),
            replica_sets=replica_sets,
            pods=pods,
        )

    def _replica_sets(self, deployment: str) -> list[ReplicaSet]:
        """Active replica sets only: the ones with pods (two during a rollout)."""
        replica_sets = []
        for raw in self._objects("replicasets"):
            if controller(raw) != ("Deployment", deployment):
                continue
            if (
                not spec(raw).get("replicas")
                and ("ReplicaSet", name(raw)) not in self.pods_by_owner
            ):
                continue
            replicas = Replicas(
                desired=spec(raw).get("replicas", 0), ready=status(raw).get("readyReplicas", 0)
            )
            replica_sets.append(
                ReplicaSet(
                    id=self._id("replicaset", name(raw)),
                    name=name(raw),
                    replicas=replicas,
                    health=replicas_health(replicas),
                    pods=self._pods("ReplicaSet", name(raw)),
                )
            )
        return replica_sets

    def _commit(self, raw: RawObject) -> Commit | None:
        """The image tag is the git SHA CI built it from; it links only with a public repo."""
        containers = (spec(raw).get("template") or {}).get("spec", {}).get("containers") or []
        tag = image_tag(containers[0].get("image", "")) if containers else None
        if not self.repo or not tag or not _SHA.match(tag):
            return None
        return Commit(sha=tag, url=f"{self.repo}/commit/{tag}")

    def _service(self, raw: RawObject) -> Service:
        selector = spec(raw).get("selector") or {}
        targets = [
            p.pod
            for p in self.published
            if selector and all(p.labels.get(k) == v for k, v in selector.items())
        ]
        return Service(
            id=self._id("service", name(raw)),
            name=name(raw),
            # Without a selector its endpoints are managed by hand: nothing to judge by.
            health=ready_health(sum(p.ready for p in targets), len(targets))
            if selector
            else "unknown",
            targets=[p.id for p in targets],
        )

    def _route(self, raw: RawObject, services: list[Service]) -> Route:
        service_ids = {s.name: s.id for s in services}
        backends = [
            ref
            for rule in spec(raw).get("rules") or []
            for ref in rule.get("backendRefs") or []
            if ref.get("kind", "Service") == "Service"
            and ref.get("group", "") == ""
            and ref.get("namespace", self.ns) == self.ns
        ]
        targets = list(
            dict.fromkeys(service_ids[r["name"]] for r in backends if r.get("name") in service_ids)
        )
        return Route(
            id=self._id("route", name(raw)),
            name=name(raw),
            hostnames=[h for h in spec(raw).get("hostnames") or [] if is_public_host(h)],
            health=_route_health(raw),
            services=targets,
        )

    def _application(self) -> RawObject | None:
        """The Argo CD Application deploying into this namespace; the one named after it first."""
        apps = [
            a
            for a in in_namespace(self.snapshot["applications"], ARGO_NAMESPACE)
            if (spec(a).get("destination") or {}).get("namespace") == self.ns
        ]
        return next((a for a in apps if name(a) == self.ns), apps[0] if apps else None)


def _route_health(raw: RawObject) -> Health:
    """From each parent Gateway's verdict: accepted, and its backends resolved."""
    parents = status(raw).get("parents") or []
    if not parents:
        return "unknown"

    def healthy(parent: dict) -> bool:
        conditions = {c.get("type"): c.get("status") for c in parent.get("conditions") or []}
        return (
            conditions.get("Accepted") == "True"
            and conditions.get("ResolvedRefs", "True") == "True"
        )

    return ready_health(sum(map(healthy, parents)), len(parents))
