"""The metrics poller only signals real changes and survives metrics-server being down."""

import json

import pytest

from astrolabio_api.kube.metrics import MetricsPoller

pytestmark = pytest.mark.anyio


class Response:
    def __init__(self, items: list[dict], status: int = 200) -> None:
        self.status = status
        self.reason = "OK"
        # Like metrics-server: aggregated lists carry no resourceVersion.
        self.body = json.dumps({"kind": "PodMetricsList", "metadata": {}, "items": items}).encode()

    async def read(self) -> bytes:
        return self.body

    def release(self) -> None:
        pass


def _pod(cpu: str, window: str = "15s") -> dict:
    return {
        "metadata": {"name": "web-1", "namespace": "hola"},
        "window": window,
        "containers": [{"name": "web", "usage": {"cpu": cpu, "memory": "10Mi"}}],
    }


class Server:
    def __init__(self) -> None:
        self.pods = [_pod("1m")]
        self.down = False

    async def list_pods(self, **_):
        return Response([], status=503) if self.down else Response(self.pods)

    async def list_nodes(self, **_):
        return Response([], status=503) if self.down else Response([])


async def test_signals_only_when_usage_changes():
    server, changes = Server(), []
    poller = MetricsPoller(server.list_pods, server.list_nodes, on_change=lambda: changes.append(1))
    await poller.poll()
    assert len(changes) == 1
    server.pods = [_pod("1m", window="15.5s")]  # same numbers, new window: not a change
    await poller.poll()
    assert len(changes) == 1
    server.pods = [_pod("2m")]
    await poller.poll()
    assert len(changes) == 2
    assert poller.items("podmetrics")[0]["containers"][0]["usage"]["cpu"] == "2m"


async def test_keeps_last_numbers_while_metrics_server_is_down():
    server = Server()
    poller = MetricsPoller(server.list_pods, server.list_nodes)
    await poller.poll()
    server.down = True
    await poller.poll()
    assert len(poller.items("podmetrics")) == 1
