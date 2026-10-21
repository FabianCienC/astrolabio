"""Models of `GET /api/galaxy`.

Every field here is allowed on purpose: Kubernetes objects are never forwarded
as-is. `extra="forbid"` makes adding an undeclared field an error instead of a
silent leak.

Every Kubernetes object the scene draws has its own model, nested the way it is
owned (namespace > workload > replica set > pod). Relations that are not
ownership (Service -> Pods, Route -> Services) are lists of ids, and validators
check that every id points to an object in the same constellation.

Ids are unique across the galaxy and shaped `<namespace>/<kind>/<name>`, or
`core/<component>/<kind>-<n>` for anonymous platform objects.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = 2

Health = Literal["ok", "degraded", "down", "unknown"]
ArgoSync = Literal["Synced", "OutOfSync", "Unknown"]
ArgoHealth = Literal["Healthy", "Progressing", "Degraded", "Suspended", "Missing", "Unknown"]
Role = Literal["frontend", "api", "worker", "data"]
Criticality = Literal["high", "medium", "low"]
WorkloadKind = Literal["Deployment", "StatefulSet", "DaemonSet"]
InfraCategory = Literal["control", "network", "ingress", "gitops", "security"]
PodPhase = Literal["Pending", "Running", "Succeeded", "Failed", "Unknown"]
NodeId = Literal["control-plane", "worker-1", "worker-2"]

Text = Annotated[str, Field(min_length=1, max_length=200)]
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9./-]*[a-z0-9])?$", max_length=253)]

_PUBLIC_REPO = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_PUBLIC_HOST = re.compile(r"^([a-z0-9-]+\.)*fabiancienfuegos\.com$")


def is_public_repo(url: str) -> bool:
    # Defense in depth: the GitOps repo is private and must never leak.
    return bool(_PUBLIC_REPO.match(url)) and "homelab-gitops" not in url.lower()


def is_public_host(host: str) -> bool:
    return bool(_PUBLIC_HOST.match(host))


def _check_public_repo(url: str) -> str:
    if not is_public_repo(url):
        raise ValueError("only public GitHub repos are published")
    return url


class Model(BaseModel):
    # Fields with defaults are always serialized, so the schema marks them required
    # and the web types don't make them optional.
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )


class Replicas(Model):
    desired: int = Field(ge=0)
    ready: int = Field(ge=0)


class ArgoStatus(Model):
    """Sync and health of the Argo CD `Application`.

    No `revision`: it is a commit of the private GitOps repo.
    """

    sync: ArgoSync
    health: ArgoHealth


class Commit(Model):
    """Deployed commit, taken from the image tag (the SHA set by CI)."""

    sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    url: str

    @field_validator("url")
    @classmethod
    def _public_url(cls, url: str) -> str:
        repo, sep, sha = url.rpartition("/commit/")
        if not sep or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("url must point to a commit")
        _check_public_repo(repo)
        return url


class Metrics(Model):
    """CPU and memory (phase 3, metrics-server). `None` until there is data."""

    cpu_millicores: int | None = Field(default=None, ge=0)
    memory_mib: int | None = Field(default=None, ge=0)


class Pod(Model):
    """A pod. `name` is `None` for platform pods, which are published anonymously."""

    id: Identifier
    name: Identifier | None
    phase: PodPhase
    ready: bool
    restarts: int = Field(ge=0)
    node: NodeId | None  # generic node name, never a hostname
    health: Health
    metrics: Metrics = Metrics()


class ReplicaSet(Model):
    """The active replica set of a Deployment (two during a rollout). Old empty ones are not
    published."""

    id: Identifier
    name: Identifier
    replicas: Replicas
    health: Health
    pods: list[Pod]


class Workload(Model):
    """A Deployment, StatefulSet or DaemonSet of a visible project.

    Deployments own pods through `replica_sets`; StatefulSets and DaemonSets own
    them directly in `pods`.
    """

    id: Identifier
    name: Identifier
    kind: WorkloadKind
    description: Text | None = None
    role: Role | None = None
    criticality: Criticality | None = None
    replicas: Replicas
    health: Health
    commit: Commit | None = None
    metrics: Metrics = Metrics()
    replica_sets: list[ReplicaSet] = []
    pods: list[Pod] = []

    def all_pods(self) -> list[Pod]:
        return [*self.pods, *(p for rs in self.replica_sets for p in rs.pods)]


class Service(Model):
    """A Service. `targets` are the ids of the pods it selects. No ports or cluster IP."""

    id: Identifier
    name: Identifier | None
    health: Health
    targets: list[Identifier]


class Route(Model):
    """An `HTTPRoute`: the public entry into a project. Hostnames are public by nature."""

    id: Identifier
    name: Identifier
    hostnames: list[str]
    health: Health
    services: list[Identifier]

    @field_validator("hostnames")
    @classmethod
    def _public_hostnames(cls, hostnames: list[str]) -> list[str]:
        for host in hostnames:
            if not is_public_host(host):
                raise ValueError("only public fabiancienfuegos.com hostnames are published")
        return hostnames


class Constellation(Model):
    """A namespace labeled `fabiancienfuegos.com/astrolabio: visible`."""

    id: Identifier  # namespace name
    project: Text
    description: Text | None = None
    repo: str | None = None
    argo: ArgoStatus | None = None
    health: Health  # worst health among its workloads; unknown when it has none
    workloads: list[Workload]
    services: list[Service] = []
    routes: list[Route] = []

    @field_validator("repo")
    @classmethod
    def _public_repo(cls, repo: str | None) -> str | None:
        return None if repo is None else _check_public_repo(repo)

    @model_validator(mode="after")
    def _relations_point_inside(self) -> "Constellation":
        pod_ids = {p.id for w in self.workloads for p in w.all_pods()}
        service_ids = {s.id for s in self.services}
        for service in self.services:
            if missing := set(service.targets) - pod_ids:
                raise ValueError(f"{service.id} targets unknown pods: {sorted(missing)}")
        for route in self.routes:
            if missing := set(route.services) - service_ids:
                raise ValueError(f"{route.id} points to unknown services: {sorted(missing)}")
        return self


class InfraComponent(Model):
    """Platform component published from the API's closed catalog.

    Its pods and services are drawn, but anonymously: no names, versions, image
    tags, IPs or configuration.
    """

    id: Identifier
    name: Text
    purpose: Text
    category: InfraCategory
    system: Text  # the platform it belongs to (Argo CD, Calico...), to group it in the core
    replicas: Replicas
    health: Health
    argo: ArgoStatus | None = None
    metrics: Metrics = Metrics()
    pods: list[Pod] = []
    services: list[Service] = []

    @model_validator(mode="after")
    def _anonymous(self) -> "InfraComponent":
        if any(p.name is not None for p in self.pods) or any(
            s.name is not None for s in self.services
        ):
            raise ValueError("platform pods and services are published without names")
        pod_ids = {p.id for p in self.pods}
        for service in self.services:
            if missing := set(service.targets) - pod_ids:
                raise ValueError(f"{service.id} targets unknown pods: {sorted(missing)}")
        return self


class Node(Model):
    """Cluster node, published under a generic name (no hostname or IP)."""

    id: NodeId
    name: Literal["control plane", "worker 1", "worker 2"]
    role: Literal["control-plane", "worker"]
    health: Health
    pods: int = Field(ge=0)
    metrics: Metrics = Metrics()


class Core(Model):
    """The galactic core: platform components and the cluster nodes."""

    components: list[InfraComponent]
    nodes: list[Node]


class Galaxy(Model):
    version: Literal[2] = CONTRACT_VERSION
    generated_at: datetime
    constellations: list[Constellation]
    core: Core
