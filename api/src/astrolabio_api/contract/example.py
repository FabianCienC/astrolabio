"""Example galaxy: feeds the web fixture and the API until the informers exist.

It deliberately covers every state the scene must be able to draw
(ok, degraded, down, unknown, OutOfSync, missing metrics).
"""

from datetime import UTC, datetime

from .models import (
    ArgoStatus,
    Commit,
    Constellation,
    Core,
    Galaxy,
    InfraCategory,
    InfraComponent,
    Metrics,
    Node,
    Replicas,
    Star,
)

_SYNCED = ArgoStatus(sync="Synced", health="Healthy")


def _commit(repo: str, sha: str) -> Commit:
    return Commit(sha=sha, url=f"{repo}/commit/{sha}")


def _component(
    id: str,
    name: str,
    purpose: str,
    category: InfraCategory,
    replicas: int,
    *,
    argo: bool = True,
    cpu: int | None = None,
) -> InfraComponent:
    return InfraComponent(
        id=id,
        name=name,
        purpose=purpose,
        category=category,
        replicas=Replicas(desired=replicas, ready=replicas),
        health="ok",
        argo=_SYNCED if argo else None,
        metrics=Metrics(cpu_millicores=cpu),
    )


def example_galaxy() -> Galaxy:
    hola_repo = "https://github.com/FabianCienC/hola-homelab"
    cv_repo = "https://github.com/FabianCienC/CV"
    astrolabio_repo = "https://github.com/FabianCienC/astrolabio"

    constellations = [
        Constellation(
            id="hola",
            project="Hola",
            description="App de prueba del homelab",
            repo=hola_repo,
            argo=_SYNCED,
            stars=[
                Star(
                    id="hola/hola",
                    name="hola",
                    kind="Deployment",
                    description="Página estática servida con nginx",
                    role="frontend",
                    criticality="low",
                    replicas=Replicas(desired=2, ready=2),
                    health="ok",
                    commit=_commit(hola_repo, "91b7466c2f0e4d8a9b1c3e5f7a9b0c2d4e6f8a1b"),
                    metrics=Metrics(cpu_millicores=2, memory_mib=11),
                ),
            ],
        ),
        Constellation(
            id="cv",
            project="CV",
            description="Mi CV web en React",
            repo=cv_repo,
            argo=ArgoStatus(sync="OutOfSync", health="Progressing"),
            stars=[
                Star(
                    id="cv/cv",
                    name="cv",
                    kind="Deployment",
                    description="Frontend estático con nginx",
                    role="frontend",
                    criticality="medium",
                    replicas=Replicas(desired=2, ready=1),
                    health="degraded",
                    commit=_commit(cv_repo, "eb8d8c0a3f1b2c4d5e6f708192a3b4c5d6e7f809"),
                    metrics=Metrics(cpu_millicores=5, memory_mib=18),
                ),
            ],
        ),
        Constellation(
            id="astrolabio",
            project="Astrolabio",
            description="Visualización 3D en tiempo real del homelab",
            repo=astrolabio_repo,
            argo=ArgoStatus(sync="Synced", health="Degraded"),
            stars=[
                Star(
                    id="astrolabio/astrolabio-web",
                    name="astrolabio-web",
                    kind="Deployment",
                    description="Galaxia 3D con Three.js servida por nginx",
                    role="frontend",
                    criticality="medium",
                    replicas=Replicas(desired=2, ready=2),
                    health="ok",
                    commit=_commit(astrolabio_repo, "4af9b5c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6"),
                ),
                Star(
                    id="astrolabio/astrolabio-api",
                    name="astrolabio-api",
                    kind="Deployment",
                    description="Watchers de Kubernetes, REST y WebSocket",
                    role="api",
                    criticality="high",
                    replicas=Replicas(desired=1, ready=0),
                    health="down",
                    commit=_commit(astrolabio_repo, "e3a2add1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"),
                ),
                Star(
                    id="astrolabio/astrolabio-anomalias",
                    name="astrolabio-anomalias",
                    kind="Deployment",
                    role="worker",
                    replicas=Replicas(desired=1, ready=1),
                    health="unknown",
                ),
            ],
        ),
    ]

    components = [
        _component(
            "api-server",
            "API server",
            "Punto de entrada al clúster",
            "control",
            1,
            argo=False,
            cpu=180,
        ),
        _component(
            "etcd", "etcd", "Base de datos del estado del clúster", "control", 1, argo=False, cpu=60
        ),
        _component(
            "coredns", "CoreDNS", "DNS interno de servicios", "network", 2, argo=False, cpu=4
        ),
        _component(
            "kube-proxy",
            "kube-proxy",
            "Reglas de red de los Services",
            "network",
            3,
            argo=False,
            cpu=2,
        ),
        _component(
            "calico", "Calico", "Red de pods y NetworkPolicies", "network", 3, argo=False, cpu=25
        ),
        _component(
            "traefik", "Traefik", "Gateway API: enruta el tráfico de entrada", "ingress", 1, cpu=8
        ),
        _component(
            "cloudflared",
            "Cloudflare Tunnel",
            "Publica el clúster sin abrir puertos",
            "ingress",
            2,
            cpu=3,
        ),
        _component(
            "argocd",
            "Argo CD",
            "GitOps: sincroniza el clúster con Git",
            "gitops",
            1,
            argo=False,
            cpu=40,
        ),
        _component(
            "sealed-secrets", "Sealed Secrets", "Secretos cifrados en Git", "security", 1, cpu=1
        ),
    ]

    nodes = [
        Node(
            id="control-plane",
            name="control plane",
            role="control-plane",
            health="ok",
            pods=14,
            metrics=Metrics(cpu_millicores=420, memory_mib=1650),
        ),
        Node(
            id="worker-1",
            name="worker 1",
            role="worker",
            health="ok",
            pods=11,
            metrics=Metrics(cpu_millicores=160, memory_mib=1320),
        ),
        Node(id="worker-2", name="worker 2", role="worker", health="ok", pods=9),
    ]

    return Galaxy(
        generated_at=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        constellations=constellations,
        core=Core(components=components, nodes=nodes),
    )
