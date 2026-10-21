"""HTTP surface: the galaxy endpoint, docs disabled and read-only."""

import asyncio

from fastapi.testclient import TestClient

from astrolabio_api.assembly import assemble_galaxy
from astrolabio_api.config import Settings
from astrolabio_api.contract.models import Galaxy
from astrolabio_api.kube.cluster import METRICS_KEYS, RESOURCES
from astrolabio_api.live import Broadcaster
from astrolabio_api.main import create_app

PRODUCTION = Settings(environment="production", source="example")
DEVELOPMENT = Settings(environment="development", source="example")


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


def _snapshot() -> dict:
    """A cluster with one visible project, as the informers would hold it."""
    snapshot = {key: [] for key in [*(r.key for r in RESOURCES), *METRICS_KEYS]}
    snapshot["namespaces"] = [
        {"metadata": {"name": "hola", "labels": {"fabiancienfuegos.com/astrolabio": "visible"}}}
    ]
    return snapshot


def test_galaxy_is_unavailable_until_the_cache_syncs():
    app = create_app(PRODUCTION)
    app.state.broadcaster = Broadcaster(lambda: None, asyncio.Event())
    assert TestClient(app).get("/api/galaxy").status_code == 503


def test_galaxy_is_assembled_once_and_served_from_the_live_cache():
    app = create_app(PRODUCTION)
    assemblies = []

    def snapshot():
        assemblies.append(1)
        return assemble_galaxy(_snapshot())

    app.state.broadcaster = Broadcaster(snapshot, asyncio.Event())
    client = TestClient(app)
    for _ in range(3):
        galaxy = Galaxy.model_validate(client.get("/api/galaxy").json())
    assert [c.id for c in galaxy.constellations] == ["hola"]
    assert len(assemblies) == 1  # a burst of requests costs one assembly, not three


def test_every_api_response_carries_security_headers():
    client = TestClient(create_app(PRODUCTION))
    for path in ("/api/galaxy", "/api/nope"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
        assert headers["cache-control"] == "no-store"
