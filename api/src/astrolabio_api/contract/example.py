"""Example galaxy: a snapshot of the real cluster, sanitized by the contract.

Taken by hand from `kubectl get` on 2026-10-21 (no metrics-server yet, so no
CPU or memory). It feeds the web fixture and the API until the informers exist,
which will produce this same shape live. Platform pods and services are
anonymous and nodes use their generic names, exactly as the API will publish them.
"""

from datetime import UTC, datetime

from .models import (
    ArgoStatus,
    Commit,
    Constellation,
    Core,
    Criticality,
    Galaxy,
    InfraCategory,
    InfraComponent,
    Node,
    NodeId,
    Pod,
    Replicas,
    ReplicaSet,
    Route,
    Service,
    Workload,
)

_SYNCED = ArgoStatus(sync="Synced", health="Healthy")
CP: NodeId = "control-plane"
W1: NodeId = "worker-1"
W2: NodeId = "worker-2"


def _commit(repo: str, sha: str) -> Commit:
    return Commit(sha=sha, url=f"{repo}/commit/{sha}")


def _pod(namespace: str, name: str, node: NodeId, restarts: int) -> Pod:
    return Pod(
        id=f"{namespace}/pod/{name}",
        name=name,
        phase="Running",
        ready=True,
        restarts=restarts,
        node=node,
        health="ok",
    )


def _web_project(
    namespace: str,
    project: str,
    description: str,
    repo: str,
    sha: str,
    replica_set: str,
    pods: list[Pod],
    workload_description: str,
    criticality: Criticality,
) -> Constellation:
    """A project with one Deployment, its Service and its public HTTPRoute (hola and cv)."""
    replicas = Replicas(desired=len(pods), ready=len(pods))
    workload = Workload(
        id=f"{namespace}/deployment/{namespace}",
        name=namespace,
        kind="Deployment",
        description=workload_description,
        role="frontend",
        criticality=criticality,
        replicas=replicas,
        health="ok",
        commit=_commit(repo, sha),
        replica_sets=[
            ReplicaSet(
                id=f"{namespace}/replicaset/{replica_set}",
                name=replica_set,
                replicas=replicas,
                health="ok",
                pods=pods,
            )
        ],
    )
    service = Service(
        id=f"{namespace}/service/{namespace}",
        name=namespace,
        health="ok",
        targets=[p.id for p in pods],
    )
    route = Route(
        id=f"{namespace}/route/{namespace}",
        name=namespace,
        hostnames=[f"{namespace}.fabiancienfuegos.com"],
        health="ok",
        services=[service.id],
    )
    return Constellation(
        id=namespace,
        project=project,
        description=description,
        repo=repo,
        argo=_SYNCED,
        health="ok",
        workloads=[workload],
        services=[service],
        routes=[route],
    )


def _projects() -> list[Constellation]:
    hola = _web_project(
        "hola",
        "Hola",
        "App de prueba del homelab",
        "https://github.com/FabianCienC/hola-homelab",
        "91b74663060424c6c3b8485735f291fd53a0d3d3",
        "hola-7cddc9f88c",
        [
            _pod("hola", "hola-7cddc9f88c-dkvxn", W1, 1),
            _pod("hola", "hola-7cddc9f88c-lgzzd", W1, 1),
        ],
        "Página estática servida con nginx",
        "low",
    )
    cv = _web_project(
        "cv",
        "CV",
        "Mi CV web en React",
        "https://github.com/FabianCienC/CV",
        "eb8d8c0f9b206ddecb2dec958c851139503a3ea7",
        "cv-78ff77987",
        [_pod("cv", "cv-78ff77987-gx9hx", W1, 1), _pod("cv", "cv-78ff77987-lhggf", W1, 1)],
        "Frontend estático con nginx",
        "medium",
    )
    # Namespace and Argo CD app exist, but nothing is deployed yet.
    astrolabio = Constellation(
        id="astrolabio",
        project="Astrolabio",
        description="Visualización 3D en tiempo real del homelab",
        repo="https://github.com/FabianCienC/astrolabio",
        argo=_SYNCED,
        health="unknown",
        workloads=[],
    )
    return [hola, cv, astrolabio]


def _component(
    id: str,
    name: str,
    purpose: str,
    category: InfraCategory,
    system: str,
    pods: list[tuple[NodeId, int]],
    *,
    services: int = 0,
    argo: bool = False,
) -> InfraComponent:
    """A platform workload. `pods` is (node, restarts) per pod; every service selects all pods."""
    published = [
        Pod(
            id=f"core/{id}/pod-{i + 1}",
            name=None,
            phase="Running",
            ready=True,
            restarts=restarts,
            node=node,
            health="ok",
        )
        for i, (node, restarts) in enumerate(pods)
    ]
    return InfraComponent(
        id=id,
        name=name,
        purpose=purpose,
        category=category,
        system=system,
        replicas=Replicas(desired=len(pods), ready=len(pods)),
        health="ok",
        argo=_SYNCED if argo else None,
        pods=published,
        services=[
            Service(
                id=f"core/{id}/service-{n + 1}",
                name=None,
                health="ok",
                targets=[p.id for p in published],
            )
            for n in range(services)
        ],
    )


def _platform() -> list[InfraComponent]:
    k8s, calico, argocd = "Kubernetes", "Calico", "Argo CD"
    return [
        # Kubernetes control plane (static pods on the control plane) and cluster add-ons.
        _component(
            "kube-apiserver",
            "API server",
            "Punto de entrada al clúster: toda lectura y escritura pasa por aquí",
            "control",
            k8s,
            [(CP, 2)],
            services=1,
        ),
        _component(
            "etcd", "etcd", "Base de datos con el estado del clúster", "control", k8s, [(CP, 4)]
        ),
        _component(
            "kube-controller-manager",
            "Controller manager",
            "Lleva el estado real hacia el deseado (réplicas, nodos, endpoints)",
            "control",
            k8s,
            [(CP, 5)],
        ),
        _component(
            "kube-scheduler",
            "Scheduler",
            "Decide en qué nodo corre cada pod",
            "control",
            k8s,
            [(CP, 5)],
        ),
        _component(
            "coredns",
            "CoreDNS",
            "DNS interno: resuelve los nombres de los Services",
            "network",
            k8s,
            [(CP, 4), (CP, 4)],
            services=1,
        ),
        _component(
            "kube-proxy",
            "kube-proxy",
            "Traduce Services a reglas de red en cada nodo",
            "network",
            k8s,
            [(W1, 5), (CP, 4), (W2, 5)],
        ),
        # Calico, installed and kept up to date by the Tigera operator.
        _component(
            "tigera-operator",
            "Tigera operator",
            "Instala y actualiza Calico",
            "network",
            calico,
            [(CP, 5)],
        ),
        _component(
            "calico-node",
            "Calico node",
            "Red de pods y NetworkPolicies en cada nodo",
            "network",
            calico,
            [(W2, 5), (CP, 4), (W1, 5)],
        ),
        _component(
            "calico-typha",
            "Calico Typha",
            "Reparte los cambios de red a los nodos sin saturar el API server",
            "network",
            calico,
            [(W2, 1), (CP, 4)],
            services=1,
        ),
        _component(
            "calico-kube-controllers",
            "Calico controllers",
            "Sincroniza Calico con los objetos de Kubernetes",
            "network",
            calico,
            [(CP, 4)],
            services=1,
        ),
        _component(
            "calico-apiserver",
            "Calico API server",
            "API de los recursos de Calico",
            "network",
            calico,
            [(CP, 4), (CP, 4)],
            services=1,
        ),
        _component(
            "calico-csi",
            "Calico CSI",
            "Driver de volúmenes de Calico en cada nodo",
            "network",
            calico,
            [(W2, 10), (W1, 10), (CP, 8)],
        ),
        _component(
            "goldmane",
            "Goldmane",
            "Agrega los flujos de red que ve Calico",
            "network",
            calico,
            [(CP, 4)],
            services=1,
        ),
        _component(
            "whisker",
            "Whisker",
            "Consola para observar los flujos de red de Calico",
            "network",
            calico,
            [(CP, 8)],
            services=1,
        ),
        # Argo CD: all of it runs on worker 1.
        _component(
            "argocd-server",
            "Argo CD server",
            "API e interfaz web de Argo CD",
            "gitops",
            argocd,
            [(W1, 1)],
            services=2,
        ),
        _component(
            "argocd-repo-server",
            "Repo server",
            "Clona los repos de Git y genera los manifiestos",
            "gitops",
            argocd,
            [(W1, 1)],
            services=1,
        ),
        _component(
            "argocd-application-controller",
            "Application controller",
            "Compara Git con el clúster y sincroniza las diferencias",
            "gitops",
            argocd,
            [(W1, 1)],
            services=1,
        ),
        _component(
            "argocd-applicationset-controller",
            "ApplicationSet controller",
            "Genera Applications a partir de plantillas",
            "gitops",
            argocd,
            [(W1, 1)],
            services=1,
        ),
        _component(
            "argocd-notifications-controller",
            "Notifications controller",
            "Envía avisos de los eventos de Argo CD",
            "gitops",
            argocd,
            [(W1, 1)],
            services=1,
        ),
        _component(
            "argocd-dex-server",
            "Dex",
            "Inicio de sesión (SSO) de Argo CD",
            "gitops",
            argocd,
            [(W1, 1)],
            services=1,
        ),
        _component(
            "argocd-redis", "Redis", "Caché de Argo CD", "gitops", argocd, [(W1, 1)], services=1
        ),
        # Ingress and secrets, deployed by Argo CD apps.
        _component(
            "traefik",
            "Traefik",
            "Gateway API: enruta el tráfico de entrada a cada app",
            "ingress",
            "Traefik",
            [(W1, 1)],
            services=1,
            argo=True,
        ),
        _component(
            "cloudflared",
            "Cloudflare Tunnel",
            "Publica el clúster en internet sin abrir puertos",
            "ingress",
            "Cloudflare",
            [(W1, 1), (W1, 1)],
            argo=True,
        ),
        _component(
            "sealed-secrets",
            "Sealed Secrets",
            "Descifra en el clúster los secretos que viven cifrados en Git",
            "security",
            "Sealed Secrets",
            [(W1, 1)],
            services=2,
            argo=True,
        ),
    ]


def example_galaxy() -> Galaxy:
    return Galaxy(
        generated_at=datetime(2026, 10, 21, 18, 0, tzinfo=UTC),
        constellations=_projects(),
        core=Core(
            components=_platform(),
            nodes=[
                Node(id=CP, name="control plane", role="control-plane", health="ok", pods=16),
                Node(id=W1, name="worker 1", role="worker", health="ok", pods=18),
                Node(id=W2, name="worker 2", role="worker", health="ok", pods=4),
            ],
        ),
    )
