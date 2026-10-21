"""The traffic poller only signals real changes and survives Prometheus being down."""

import pytest

from astrolabio_api.kube.traffic import TrafficPoller

pytestmark = pytest.mark.anyio


class Response:
    def __init__(self, body: dict | None) -> None:
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def raise_for_status(self) -> None:
        if self.body is None:
            raise RuntimeError("503")

    async def json(self) -> dict:
        return self.body


class Session:
    def __init__(self) -> None:
        self.rps = "1"
        self.down = False

    def get(self, url, params):
        assert url.endswith("/api/v1/query") and "traefik_service_requests_total" in params["query"]
        if self.down:
            return Response(None)
        result = [{"metric": {"service": "s@kubernetesgateway"}, "value": [1.0, self.rps]}]
        return Response({"status": "success", "data": {"result": result}})


async def test_signals_only_when_the_numbers_change():
    session, changes = Session(), []
    poller = TrafficPoller("http://prometheus", on_change=lambda: changes.append(1))
    await poller.poll(session)
    await poller.poll(session)
    assert len(changes) == 1
    session.rps = "1.001"  # float noise below the rounding
    await poller.poll(session)
    assert len(changes) == 1
    session.rps = "4"
    await poller.poll(session)
    assert len(changes) == 2


async def test_keeps_last_numbers_while_prometheus_is_down():
    session = Session()
    poller = TrafficPoller("http://prometheus")
    await poller.poll(session)
    session.down = True
    await poller.poll(session)
    assert poller.items()[0]["value"][1] == "1"
