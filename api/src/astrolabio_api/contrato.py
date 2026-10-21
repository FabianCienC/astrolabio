"""Exporta el contrato a `contrato/` en la raíz del repo, para el frontend.

uv run exportar-contrato           # escribe los archivos
uv run exportar-contrato --check   # falla si están desactualizados (CI)
"""

import argparse
import json
import sys
from pathlib import Path

from .ejemplo import galaxia_de_ejemplo
from .modelos import Galaxia

DIRECTORIO = Path(__file__).resolve().parents[3] / "contrato"


def archivos() -> dict[str, str]:
    esquema = Galaxia.model_json_schema(mode="serialization")
    return {
        "galaxia.schema.json": json.dumps(esquema, indent=2, ensure_ascii=False) + "\n",
        "galaxia.ejemplo.json": galaxia_de_ejemplo().model_dump_json(indent=2) + "\n",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    desactualizados = []
    for nombre, contenido in archivos().items():
        ruta = DIRECTORIO / nombre
        actual = ruta.read_text(encoding="utf-8") if ruta.exists() else None
        if actual == contenido:
            continue
        if args.check:
            desactualizados.append(nombre)
        else:
            DIRECTORIO.mkdir(exist_ok=True)
            ruta.write_text(contenido, encoding="utf-8", newline="\n")
            print(f"escrito {ruta}")

    if desactualizados:
        print(
            f"contrato desactualizado: {', '.join(desactualizados)}; corre `uv run "
            "exportar-contrato`",
            file=sys.stderr,
        )
        sys.exit(1)
