"""Contrato público de `GET /api/galaxia`.

Estos modelos son la única forma en que los datos del clúster salen de la API.
Cada campo está permitido a propósito: los objetos de Kubernetes nunca se
reenvían tal cual. `extra="forbid"` hace que agregar un campo sin declararlo
aquí sea un error, no una fuga silenciosa.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSION_CONTRATO = 1

Salud = Literal["ok", "degradado", "caido", "desconocido"]
SyncArgo = Literal["Synced", "OutOfSync", "Unknown"]
SaludArgo = Literal["Healthy", "Progressing", "Degraded", "Suspended", "Missing", "Unknown"]
Rol = Literal["frontend", "api", "worker", "datos"]
Criticidad = Literal["alta", "media", "baja"]
TipoWorkload = Literal["Deployment", "StatefulSet", "DaemonSet"]
CategoriaInfra = Literal["control", "red", "ingreso", "gitops", "seguridad"]

Texto = Annotated[str, Field(min_length=1, max_length=200)]
Identificador = Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9./-]*[a-z0-9])?$", max_length=253)]

_REPO_PUBLICO = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _validar_repo_publico(url: str) -> str:
    # Defensa en profundidad: el repo de GitOps es privado y nunca debe salir.
    if not _REPO_PUBLICO.match(url) or "homelab-gitops" in url.lower():
        raise ValueError("solo se publican repos públicos de GitHub")
    return url


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Replicas(Modelo):
    deseadas: int = Field(ge=0)
    listas: int = Field(ge=0)


class EstadoArgo(Modelo):
    """Sync y salud del `Application`. Sin `revision`: es un commit del repo privado."""

    sync: SyncArgo
    salud: SaludArgo


class Commit(Modelo):
    """Commit desplegado, deducido del tag de la imagen (el SHA que pone el CI)."""

    sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    url: str

    @field_validator("url")
    @classmethod
    def _url_publica(cls, url: str) -> str:
        repo, sep, sha = url.rpartition("/commit/")
        if not sep or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("la url debe apuntar a un commit")
        _validar_repo_publico(repo)
        return url


class Metricas(Modelo):
    """CPU y memoria (fase 3, metrics-server). `None` mientras no haya datos."""

    cpu_milicores: int | None = Field(default=None, ge=0)
    memoria_mib: int | None = Field(default=None, ge=0)


class Estrella(Modelo):
    """Un workload de un proyecto visible."""

    id: Identificador  # "<namespace>/<nombre>", estable para los deltas de la fase 3
    nombre: Identificador
    tipo: TipoWorkload
    descripcion: Texto | None = None
    rol: Rol | None = None
    criticidad: Criticidad | None = None
    replicas: Replicas
    salud: Salud
    commit: Commit | None = None
    metricas: Metricas = Metricas()


class Constelacion(Modelo):
    """Un namespace con la etiqueta `fabiancienfuegos.com/astrolabio: visible`."""

    id: Identificador  # nombre del namespace
    proyecto: Texto
    descripcion: Texto | None = None
    repo: str | None = None
    argo: EstadoArgo | None = None
    estrellas: list[Estrella]

    @field_validator("repo")
    @classmethod
    def _repo_publico(cls, repo: str | None) -> str | None:
        return None if repo is None else _validar_repo_publico(repo)


class ComponenteInfra(Modelo):
    """Componente de plataforma publicado desde el catálogo cerrado de la API.

    Sin versión, tag de imagen, nombres de pods, IPs ni configuración.
    """

    id: Identificador
    nombre: Texto
    funcion: Texto
    categoria: CategoriaInfra
    replicas: Replicas
    salud: Salud
    argo: EstadoArgo | None = None
    metricas: Metricas = Metricas()


class Nodo(Modelo):
    """Nodo del clúster, publicado con un nombre genérico (sin hostname ni IP)."""

    id: Literal["control-plane", "worker-1", "worker-2"]
    nombre: Literal["control plane", "worker 1", "worker 2"]
    rol: Literal["control-plane", "worker"]
    salud: Salud
    pods: int = Field(ge=0)
    metricas: Metricas = Metricas()


class Nucleo(Modelo):
    componentes: list[ComponenteInfra]
    nodos: list[Nodo]


class Galaxia(Modelo):
    version: Literal[1] = VERSION_CONTRATO
    generada: datetime
    constelaciones: list[Constelacion]
    nucleo: Nucleo
