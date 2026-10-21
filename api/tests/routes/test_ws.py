"""`/ws` sends the galaxy on connect and only to the site's own origin."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from astrolabio_api.config import PUBLIC_ORIGIN, Settings
from astrolabio_api.contract.models import Galaxy
from astrolabio_api.main import create_app

PRODUCTION = Settings(environment="production", source="example")
DEVELOPMENT = Settings(environment="development", source="example")


def test_sends_the_galaxy_on_connect():
    client = TestClient(create_app(PRODUCTION))
    with client.websocket_connect("/ws", headers={"origin": PUBLIC_ORIGIN}) as ws:
        galaxy = Galaxy.model_validate_json(ws.receive_text())
    assert [c.id for c in galaxy.constellations] == ["hola", "cv", "astrolabio"]


@pytest.mark.parametrize("origin", [None, "https://evil.example", "http://localhost:5173"])
def test_rejects_other_origins_in_production(origin):
    client = TestClient(create_app(PRODUCTION))
    headers = {"origin": origin} if origin else {}
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect("/ws", headers=headers) as ws,
    ):
        ws.receive_text()
    assert closed.value.code == 1008


def test_local_dev_server_allowed_in_development():
    client = TestClient(create_app(DEVELOPMENT))
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        Galaxy.model_validate_json(ws.receive_text())


def test_client_messages_are_ignored():
    client = TestClient(create_app(PRODUCTION))
    with client.websocket_connect("/ws", headers={"origin": PUBLIC_ORIGIN}) as ws:
        ws.receive_text()
        ws.send_text("DELETE everything")  # read-only: nothing happens, nothing breaks
        ws.send_bytes(b"\x00" * 64)
