"""HTTP surface: the galaxy endpoint, docs disabled and read-only."""

from fastapi.testclient import TestClient

from astrolabio_api.config import Settings
from astrolabio_api.contract.models import Galaxy
from astrolabio_api.main import create_app

PRODUCTION = Settings(environment="production")
DEVELOPMENT = Settings(environment="development")


def test_galaxy_matches_contract():
    response = TestClient(create_app(PRODUCTION)).get("/api/galaxy")
    assert response.status_code == 200
    Galaxy.model_validate(response.json())


def test_docs_disabled_in_production():
    client = TestClient(create_app(PRODUCTION))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_read_only():
    app = create_app(DEVELOPMENT)
    methods = {m for route in app.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD"}
