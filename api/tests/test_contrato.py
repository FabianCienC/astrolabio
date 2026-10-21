import json
import re

import pytest
from pydantic import ValidationError

from astrolabio_api import contrato
from astrolabio_api.ejemplo import galaxia_de_ejemplo
from astrolabio_api.modelos import Commit, ComponenteInfra, Constelacion, Galaxia

# Nombres de campo que nunca deben existir en el contrato público.
PROHIBIDOS = re.compile(
    r"env|volume|ip$|^ip|ips|host|port|puerto|image|imagen|tag|version|repourl|token|secret"
    r"|label|annotation|pod_?name|args|command|mensaje|message",
    re.IGNORECASE,
)
# `version` del contrato es la única excepción, y solo en la raíz.
PERMITIDOS_EN_RAIZ = {"version"}


def _propiedades(esquema: dict) -> list[tuple[str, str]]:
    """(modelo, campo) de todas las propiedades del esquema, incluidas las $defs."""
    pares = [("Galaxia", campo) for campo in esquema.get("properties", {})]
    for modelo, definicion in esquema.get("$defs", {}).items():
        pares += [(modelo, campo) for campo in definicion.get("properties", {})]
    return pares


def test_ningun_campo_prohibido_en_el_esquema():
    esquema = Galaxia.model_json_schema(mode="serialization")
    sospechosos = [
        f"{modelo}.{campo}"
        for modelo, campo in _propiedades(esquema)
        if PROHIBIDOS.search(campo) and not (modelo == "Galaxia" and campo in PERMITIDOS_EN_RAIZ)
    ]
    assert sospechosos == []


def test_todos_los_modelos_rechazan_campos_extra():
    esquema = Galaxia.model_json_schema(mode="serialization")
    for nombre, definicion in esquema["$defs"].items():
        if definicion.get("type") == "object":
            assert definicion.get("additionalProperties") is False, nombre


def test_componente_de_infra_no_acepta_version():
    datos = galaxia_de_ejemplo().nucleo.componentes[0].model_dump()
    with pytest.raises(ValidationError):
        ComponenteInfra(**datos, version="v3.2.1")


@pytest.mark.parametrize(
    "repo",
    [
        "git@github.com:FabianCienC/homelab-gitops.git",
        "https://github.com/FabianCienC/homelab-gitops",
        "https://gitlab.interno/x/y",
        "file:///etc/passwd",
    ],
)
def test_repo_privado_o_no_github_se_rechaza(repo):
    with pytest.raises(ValidationError):
        Constelacion(id="x", proyecto="X", repo=repo, estrellas=[])


def test_commit_debe_ser_un_sha_completo_de_un_repo_publico():
    sha = "a" * 40
    Commit(sha=sha, url=f"https://github.com/FabianCienC/CV/commit/{sha}")
    with pytest.raises(ValidationError):
        Commit(sha="latest", url="https://github.com/FabianCienC/CV/commit/latest")
    with pytest.raises(ValidationError):
        Commit(sha=sha, url=f"https://github.com/FabianCienC/homelab-gitops/commit/{sha}")


def test_ejemplo_es_valido_y_cubre_todos_los_estados():
    galaxia = Galaxia.model_validate_json(galaxia_de_ejemplo().model_dump_json())
    saludes = {e.salud for c in galaxia.constelaciones for e in c.estrellas}
    assert saludes == {"ok", "degradado", "caido", "desconocido"}
    ids = [e.id for c in galaxia.constelaciones for e in c.estrellas]
    assert len(ids) == len(set(ids))


def test_archivos_del_contrato_al_dia():
    for nombre, contenido in contrato.archivos().items():
        ruta = contrato.DIRECTORIO / nombre
        assert ruta.exists(), f"falta {ruta}; corre `uv run exportar-contrato`"
        assert ruta.read_text(encoding="utf-8") == contenido, (
            f"{nombre} desactualizado; corre `uv run exportar-contrato`"
        )
    json.loads((contrato.DIRECTORIO / "galaxia.ejemplo.json").read_text(encoding="utf-8"))
