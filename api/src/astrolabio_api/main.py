"""Entry point: builds the FastAPI app and wires the layers together.

uv run uvicorn astrolabio_api.main:app --reload
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from .assembly import assemble_galaxy
from .config import Settings
from .contract.example import example_galaxy
from .kube.cluster import Cluster
from .live import Broadcaster
from .routes import galaxy, ws

# Every API response is data, never a page: nothing may sniff, frame, embed or cache it.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.source == "example":
            yield
            return
        # Informers start in the background; the galaxy answers 503 until they sync.
        cluster = await Cluster.connect(settings.prometheus_url)
        cluster.start()
        app.state.broadcaster = Broadcaster(
            lambda: assemble_galaxy(cluster.snapshot()) if cluster.synced else None,
            cluster.changed,
        )
        live = asyncio.create_task(app.state.broadcaster.run(), name="live-galaxy")
        try:
            yield
        finally:
            live.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await live
            await cluster.close()

    # The site is public: the schema and interactive docs only exist in development.
    app = FastAPI(
        title="Astrolabio",
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    # Without a cluster (ASTROLABIO_SOURCE=example) both endpoints serve the example,
    # and /ws never pushes a change.
    app.state.broadcaster = Broadcaster(example_galaxy, asyncio.Event())
    app.include_router(galaxy.router)
    app.include_router(ws.router)
    return app


app = create_app()
