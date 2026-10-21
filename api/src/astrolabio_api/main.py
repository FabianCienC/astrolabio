"""Entry point: builds the FastAPI app and wires the layers together.

uv run uvicorn astrolabio_api.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .kube.cluster import Cluster
from .routes import galaxy


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.source == "example":
            yield
            return
        # Informers start in the background; the galaxy answers 503 until they sync.
        cluster = await Cluster.connect()
        cluster.start()
        app.state.cluster = cluster
        try:
            yield
        finally:
            await cluster.close()

    # The site is public: the schema and interactive docs only exist in development.
    app = FastAPI(
        title="Astrolabio",
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )
    app.state.cluster = None  # None serves the example galaxy
    app.include_router(galaxy.router)
    return app


app = create_app()
