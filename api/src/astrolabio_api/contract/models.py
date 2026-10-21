"""Models of `GET /api/galaxy`.

Every field here is allowed on purpose: Kubernetes objects are never forwarded
as-is. `extra="forbid"` makes adding an undeclared field an error instead of a
silent leak.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTRACT_VERSION = 1

Health = Literal["ok", "degraded", "down", "unknown"]
ArgoSync = Literal["Synced", "OutOfSync", "Unknown"]
ArgoHealth = Literal["Healthy", "Progressing", "Degraded", "Suspended", "Missing", "Unknown"]
Role = Literal["frontend", "api", "worker", "data"]
Criticality = Literal["high", "medium", "low"]
WorkloadKind = Literal["Deployment", "StatefulSet", "DaemonSet"]
InfraCategory = Literal["control", "network", "ingress", "gitops", "security"]

Text = Annotated[str, Field(min_length=1, max_length=200)]
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9./-]*[a-z0-9])?$", max_length=253)]

_PUBLIC_REPO = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _check_public_repo(url: str) -> str:
    # Defense in depth: the GitOps repo is private and must never leak.
    if not _PUBLIC_REPO.match(url) or "homelab-gitops" in url.lower():
        raise ValueError("only public GitHub repos are published")
    return url


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class Star(Model):
    """A workload of a visible project."""

    id: Identifier  # "<namespace>/<name>", stable for the phase 3 deltas
    name: Identifier
    kind: WorkloadKind
    description: Text | None = None
    role: Role | None = None
    criticality: Criticality | None = None
    replicas: Replicas
    health: Health
    commit: Commit | None = None
    metrics: Metrics = Metrics()


class Constellation(Model):
    """A namespace labeled `fabiancienfuegos.com/astrolabio: visible`."""

    id: Identifier  # namespace name
    project: Text
    description: Text | None = None
    repo: str | None = None
    argo: ArgoStatus | None = None
    stars: list[Star]

    @field_validator("repo")
    @classmethod
    def _public_repo(cls, repo: str | None) -> str | None:
        return None if repo is None else _check_public_repo(repo)


class InfraComponent(Model):
    """Platform component published from the API's closed catalog.

    No version, image tag, pod names, IPs or configuration.
    """

    id: Identifier
    name: Text
    purpose: Text
    category: InfraCategory
    replicas: Replicas
    health: Health
    argo: ArgoStatus | None = None
    metrics: Metrics = Metrics()


class Node(Model):
    """Cluster node, published under a generic name (no hostname or IP)."""

    id: Literal["control-plane", "worker-1", "worker-2"]
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
    version: Literal[1] = CONTRACT_VERSION
    generated_at: datetime
    constellations: list[Constellation]
    core: Core
