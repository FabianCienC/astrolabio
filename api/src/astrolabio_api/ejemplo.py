"""Galaxia de ejemplo: alimenta el fixture del frontend y la API en desarrollo.

Cubre a propósito todos los estados que la escena debe saber dibujar
(ok, degradado, caído, desconocido, OutOfSync, sin métricas).
"""

from datetime import UTC, datetime

from .modelos import (
    Commit,
    ComponenteInfra,
    Constelacion,
    EstadoArgo,
    Estrella,
    Galaxia,
    Metricas,
    Nodo,
    Nucleo,
    Replicas,
)

_SINCRONIZADA = EstadoArgo(sync="Synced", salud="Healthy")


def _commit(repo: str, sha: str) -> Commit:
    return Commit(sha=sha, url=f"{repo}/commit/{sha}")


def _componente(
    id: str,
    nombre: str,
    funcion: str,
    categoria: str,
    replicas: int,
    *,
    argo: bool = True,
    cpu: int | None = None,
) -> ComponenteInfra:
    return ComponenteInfra(
        id=id,
        nombre=nombre,
        funcion=funcion,
        categoria=categoria,
        replicas=Replicas(deseadas=replicas, listas=replicas),
        salud="ok",
        argo=_SINCRONIZADA if argo else None,
        metricas=Metricas(cpu_milicores=cpu),
    )


def galaxia_de_ejemplo() -> Galaxia:
    repo_hola = "https://github.com/FabianCienC/hola-homelab"
    repo_cv = "https://github.com/FabianCienC/CV"
    repo_astrolabio = "https://github.com/FabianCienC/astrolabio"

    constelaciones = [
        Constelacion(
            id="hola",
            proyecto="Hola",
            descripcion="App de prueba del homelab",
            repo=repo_hola,
            argo=_SINCRONIZADA,
            estrellas=[
                Estrella(
                    id="hola/hola",
                    nombre="hola",
                    tipo="Deployment",
                    descripcion="Página estática servida con nginx",
                    rol="frontend",
                    criticidad="baja",
                    replicas=Replicas(deseadas=2, listas=2),
                    salud="ok",
                    commit=_commit(repo_hola, "91b7466c2f0e4d8a9b1c3e5f7a9b0c2d4e6f8a1b"),
                    metricas=Metricas(cpu_milicores=2, memoria_mib=11),
                ),
            ],
        ),
        Constelacion(
            id="cv",
            proyecto="CV",
            descripcion="Mi CV web en React",
            repo=repo_cv,
            argo=EstadoArgo(sync="OutOfSync", salud="Progressing"),
            estrellas=[
                Estrella(
                    id="cv/cv",
                    nombre="cv",
                    tipo="Deployment",
                    descripcion="Frontend estático con nginx",
                    rol="frontend",
                    criticidad="media",
                    replicas=Replicas(deseadas=2, listas=1),
                    salud="degradado",
                    commit=_commit(repo_cv, "eb8d8c0a3f1b2c4d5e6f708192a3b4c5d6e7f809"),
                    metricas=Metricas(cpu_milicores=5, memoria_mib=18),
                ),
            ],
        ),
        Constelacion(
            id="astrolabio",
            proyecto="Astrolabio",
            descripcion="Visualización 3D en tiempo real del homelab",
            repo=repo_astrolabio,
            argo=EstadoArgo(sync="Synced", salud="Degraded"),
            estrellas=[
                Estrella(
                    id="astrolabio/astrolabio-web",
                    nombre="astrolabio-web",
                    tipo="Deployment",
                    descripcion="Galaxia 3D con Three.js servida por nginx",
                    rol="frontend",
                    criticidad="media",
                    replicas=Replicas(deseadas=2, listas=2),
                    salud="ok",
                    commit=_commit(repo_astrolabio, "4af9b5c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6"),
                ),
                Estrella(
                    id="astrolabio/astrolabio-api",
                    nombre="astrolabio-api",
                    tipo="Deployment",
                    descripcion="Watchers de Kubernetes, REST y WebSocket",
                    rol="api",
                    criticidad="alta",
                    replicas=Replicas(deseadas=1, listas=0),
                    salud="caido",
                    commit=_commit(repo_astrolabio, "e3a2add1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"),
                ),
                Estrella(
                    id="astrolabio/astrolabio-anomalias",
                    nombre="astrolabio-anomalias",
                    tipo="Deployment",
                    rol="worker",
                    replicas=Replicas(deseadas=1, listas=1),
                    salud="desconocido",
                ),
            ],
        ),
    ]

    componentes = [
        _componente(
            "api-server",
            "API server",
            "Punto de entrada al clúster",
            "control",
            1,
            argo=False,
            cpu=180,
        ),
        _componente(
            "etcd", "etcd", "Base de datos del estado del clúster", "control", 1, argo=False, cpu=60
        ),
        _componente("coredns", "CoreDNS", "DNS interno de servicios", "red", 2, argo=False, cpu=4),
        _componente(
            "kube-proxy", "kube-proxy", "Reglas de red de los Services", "red", 3, argo=False, cpu=2
        ),
        _componente(
            "calico", "Calico", "Red de pods y NetworkPolicies", "red", 3, argo=False, cpu=25
        ),
        _componente(
            "traefik", "Traefik", "Gateway API: enruta el tráfico de entrada", "ingreso", 1, cpu=8
        ),
        _componente(
            "cloudflared",
            "Cloudflare Tunnel",
            "Publica el clúster sin abrir puertos",
            "ingreso",
            2,
            cpu=3,
        ),
        _componente(
            "argocd",
            "Argo CD",
            "GitOps: sincroniza el clúster con Git",
            "gitops",
            1,
            argo=False,
            cpu=40,
        ),
        _componente(
            "sealed-secrets", "Sealed Secrets", "Secretos cifrados en Git", "seguridad", 1, cpu=1
        ),
    ]

    nodos = [
        Nodo(
            id="control-plane",
            nombre="control plane",
            rol="control-plane",
            salud="ok",
            pods=14,
            metricas=Metricas(cpu_milicores=420, memoria_mib=1650),
        ),
        Nodo(
            id="worker-1",
            nombre="worker 1",
            rol="worker",
            salud="ok",
            pods=11,
            metricas=Metricas(cpu_milicores=160, memoria_mib=1320),
        ),
        Nodo(id="worker-2", nombre="worker 2", rol="worker", salud="ok", pods=9),
    ]

    return Galaxia(
        generada=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        constelaciones=constelaciones,
        nucleo=Nucleo(componentes=componentes, nodos=nodos),
    )
