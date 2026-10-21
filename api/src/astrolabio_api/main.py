"""Entry point: builds the FastAPI app and wires the layers together.

uv run uvicorn astrolabio_api.main:app --reload
"""

from fastapi import FastAPI

from .config import Settings
from .routes import galaxy


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    # The site is public: the schema and interactive docs only exist in development.
    app = FastAPI(
        title="Astrolabio",
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )
    app.include_router(galaxy.router)
    return app


app = create_app()
