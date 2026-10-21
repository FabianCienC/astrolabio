"""The closed catalog of platform components shown in the galactic core.

One entry per platform workload. Only what is listed here is published, and the
text (name, purpose) lives here rather than in annotations, because static
control-plane pods and operator-made workloads can't be annotated through GitOps.
Anything in the platform namespaces that is not listed is dropped.

Backing workloads were taken from the cluster on 2026-10-21 (Calico >= 3.30
runs everything in `calico-system`). A listed workload that is missing from the
cluster is simply not shown.
"""

from dataclasses import dataclass
from typing import Literal

from ..contract.models import InfraCategory

BackingKind = Literal["Deployment", "StatefulSet", "DaemonSet", "StaticPod"]


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    purpose: str
    category: InfraCategory
    system: str  # groups the component in the core
    namespace: str
    kind: BackingKind
    workload: str  # workload name; for a static pod, its `component` label
    application: str | None = None  # the Argo CD Application that deploys it
    # Services without a selector that belong to it, as (namespace, name).
    services: tuple[tuple[str, str], ...] = ()


_K8S, _CALICO, _ARGO = "Kubernetes", "Calico", "Argo CD"

CATALOG: tuple[Entry, ...] = (
    # Kubernetes control plane (kubeadm static pods) and cluster add-ons.
    Entry(
        "kube-apiserver",
        "API server",
        "Punto de entrada al clúster: toda lectura y escritura pasa por aquí",
        "control",
        _K8S,
        "kube-system",
        "StaticPod",
        "kube-apiserver",
        services=(("default", "kubernetes"),),
    ),
    Entry(
        "etcd",
        "etcd",
        "Base de datos con el estado del clúster",
        "control",
        _K8S,
        "kube-system",
        "StaticPod",
        "etcd",
    ),
    Entry(
        "kube-controller-manager",
        "Controller manager",
        "Lleva el estado real hacia el deseado (réplicas, nodos, endpoints)",
        "control",
        _K8S,
        "kube-system",
        "StaticPod",
        "kube-controller-manager",
    ),
    Entry(
        "kube-scheduler",
        "Scheduler",
        "Decide en qué nodo corre cada pod",
        "control",
        _K8S,
        "kube-system",
        "StaticPod",
        "kube-scheduler",
    ),
    Entry(
        "coredns",
        "CoreDNS",
        "DNS interno: resuelve los nombres de los Services",
        "network",
        _K8S,
        "kube-system",
        "Deployment",
        "coredns",
    ),
    Entry(
        "kube-proxy",
        "kube-proxy",
        "Traduce Services a reglas de red en cada nodo",
        "network",
        _K8S,
        "kube-system",
        "DaemonSet",
        "kube-proxy",
    ),
    # Calico, installed and kept up to date by the Tigera operator.
    Entry(
        "tigera-operator",
        "Tigera operator",
        "Instala y actualiza Calico",
        "network",
        _CALICO,
        "tigera-operator",
        "Deployment",
        "tigera-operator",
    ),
    Entry(
        "calico-node",
        "Calico node",
        "Red de pods y NetworkPolicies en cada nodo",
        "network",
        _CALICO,
        "calico-system",
        "DaemonSet",
        "calico-node",
    ),
    Entry(
        "calico-typha",
        "Calico Typha",
        "Reparte los cambios de red a los nodos sin saturar el API server",
        "network",
        _CALICO,
        "calico-system",
        "Deployment",
        "calico-typha",
    ),
    Entry(
        "calico-kube-controllers",
        "Calico controllers",
        "Sincroniza Calico con los objetos de Kubernetes",
        "network",
        _CALICO,
        "calico-system",
        "Deployment",
        "calico-kube-controllers",
    ),
    Entry(
        "calico-apiserver",
        "Calico API server",
        "API de los recursos de Calico",
        "network",
        _CALICO,
        "calico-system",
        "Deployment",
        "calico-apiserver",
    ),
    Entry(
        "calico-csi",
        "Calico CSI",
        "Driver de volúmenes de Calico en cada nodo",
        "network",
        _CALICO,
        "calico-system",
        "DaemonSet",
        "csi-node-driver",
    ),
    Entry(
        "goldmane",
        "Goldmane",
        "Agrega los flujos de red que ve Calico",
        "network",
        _CALICO,
        "calico-system",
        "Deployment",
        "goldmane",
    ),
    Entry(
        "whisker",
        "Whisker",
        "Consola para observar los flujos de red de Calico",
        "network",
        _CALICO,
        "calico-system",
        "Deployment",
        "whisker",
    ),
    # Argo CD.
    Entry(
        "argocd-server",
        "Argo CD server",
        "API e interfaz web de Argo CD",
        "gitops",
        _ARGO,
        "argocd",
        "Deployment",
        "argocd-server",
    ),
    Entry(
        "argocd-repo-server",
        "Repo server",
        "Clona los repos de Git y genera los manifiestos",
        "gitops",
        _ARGO,
        "argocd",
        "Deployment",
        "argocd-repo-server",
    ),
    Entry(
        "argocd-application-controller",
        "Application controller",
        "Compara Git con el clúster y sincroniza las diferencias",
        "gitops",
        _ARGO,
        "argocd",
        "StatefulSet",
        "argocd-application-controller",
    ),
    Entry(
        "argocd-applicationset-controller",
        "ApplicationSet controller",
        "Genera Applications a partir de plantillas",
        "gitops",
        _ARGO,
        "argocd",
        "Deployment",
        "argocd-applicationset-controller",
    ),
    Entry(
        "argocd-notifications-controller",
        "Notifications controller",
        "Envía avisos de los eventos de Argo CD",
        "gitops",
        _ARGO,
        "argocd",
        "Deployment",
        "argocd-notifications-controller",
    ),
    Entry(
        "argocd-dex-server",
        "Dex",
        "Inicio de sesión (SSO) de Argo CD",
        "gitops",
        _ARGO,
        "argocd",
        "Deployment",
        "argocd-dex-server",
    ),
    Entry(
        "argocd-redis",
        "Redis",
        "Caché de Argo CD",
        "gitops",
        _ARGO,
        "argocd",
        "Deployment",
        "argocd-redis",
    ),
    # Ingress and secrets, deployed by Argo CD apps.
    Entry(
        "traefik",
        "Traefik",
        "Gateway API: enruta el tráfico de entrada a cada app",
        "ingress",
        "Traefik",
        "traefik",
        "Deployment",
        "traefik",
        application="traefik",
    ),
    Entry(
        "cloudflared",
        "Cloudflare Tunnel",
        "Publica el clúster en internet sin abrir puertos",
        "ingress",
        "Cloudflare",
        "cloudflared",
        "Deployment",
        "cloudflared",
        application="cloudflared",
    ),
    Entry(
        "sealed-secrets",
        "Sealed Secrets",
        "Descifra en el clúster los secretos que viven cifrados en Git",
        "security",
        "Sealed Secrets",
        "kube-system",
        "Deployment",
        "sealed-secrets-controller",
        application="sealed-secrets",
    ),
)
