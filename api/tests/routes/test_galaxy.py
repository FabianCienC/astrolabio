"""HTTP surface: the galaxy endpoint, docs disabled and read-only."""

from fastapi.testclient import TestClient

from astrolabio_api.config import Settings
from astrolabio_api.contract.models import Galaxy
from astrolabio_api.kube.cluster import METRICS_KEYS, RESOURCES
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


class FakeCluster:
    def __init__(self, synced: bool) -> None:
        self.synced = synced

    def snapshot(self) -> dict:
        snapshot = {key: [] for key in [*(r.key for r in RESOURCES), *METRICS_KEYS]}
        snapshot["namespaces"] = [
            {"metadata": {"name": "hola", "labels": {"fabiancienfuegos.com/astrolabio": "visible"}}}
        ]
        return snapshot


def test_galaxy_is_unavailable_until_the_cache_syncs():
    app = create_app(PRODUCTION)
    app.state.cluster = FakeCluster(synced=False)
    assert TestClient(app).get("/api/galaxy").status_code == 503


def test_galaxy_is_assembled_from_the_cluster():
    app = create_app(PRODUCTION)
    app.state.cluster = FakeCluster(synced=True)
    galaxy = Galaxy.model_validate(TestClient(app).get("/api/galaxy").json())
    assert [c.id for c in galaxy.constellations] == ["hola"]
