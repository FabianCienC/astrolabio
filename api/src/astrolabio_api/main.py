"""App FastAPI. Solo lectura: no hay endpoints que no sean GET.

uv run uvicorn astrolabio_api.main:app --reload
"""

import os

from fastapi import FastAPI

from .ejemplo import galaxia_de_ejemplo
from .modelos import Galaxia


def crear_app(*, desarrollo: bool | None = None) -> FastAPI:
    if desarrollo is None:
        desarrollo = os.environ.get("ASTROLABIO_ENTORNO") == "desarrollo"

    # /docs y /openapi.json solo existen en desarrollo; el sitio es público.
    app = FastAPI(
        title="Astrolabio",
        docs_url="/docs" if desarrollo else None,
        redoc_url=None,
        openapi_url="/openapi.json" if desarrollo else None,
    )

    @app.get("/api/galaxia", response_model=Galaxia)
    async def galaxia() -> Galaxia:
        # Provisional hasta los informers (E1.3–E1.5): sirve la galaxia de ejemplo.
        return galaxia_de_ejemplo()

    return app


app = crear_app()
