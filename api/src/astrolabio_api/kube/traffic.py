"""Requests per second through Traefik, from Prometheus (phase 4), polled.

Prometheus scrapes Traefik every 15 s, so polling faster gains nothing. Without
it (not installed, unreachable from a laptop, down) the galaxy simply has no
traffic; nothing else waits on this.
"""

import asyncio
import logging
from collections.abc import Callable

import aiohttp

log = logging.getLogger(__name__)

POLL_SECONDS = 15.0
# Requests per second of each Traefik service over the last minute.
QUERY = "sum by (service) (rate(traefik_service_requests_total[1m]))"


class TrafficPoller:
    def __init__(
        self,
        prometheus_url: str,
        *,
        on_change: Callable[[], None] = lambda: None,
        poll_seconds: float = POLL_SECONDS,
    ) -> None:
        self._url = prometheus_url.rstrip("/") + "/api/v1/query"
        self._on_change = on_change
        self._poll_seconds = poll_seconds
        self._results: list[dict] = []
        self._failing = False

    def items(self) -> list[dict]:
        """Raw Prometheus results: `{"metric": {"service": ...}, "value": [ts, "rps"]}`."""
        return self._results

    async def run(self) -> None:
        """Polls until cancelled."""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            while True:
                await self.poll(session)
                await asyncio.sleep(self._poll_seconds)

    async def poll(self, session: aiohttp.ClientSession) -> None:
        try:
            async with session.get(self._url, params={"query": QUERY}) as response:
                response.raise_for_status()
                body = await response.json()
            results = body["data"]["result"]
        except Exception as error:
            # Log the first failure of a streak, not one every 15 s.
            if not self._failing:
                log.warning("Prometheus unavailable (%r); the galaxy goes without traffic", error)
            self._failing = True
            return
        if self._failing:
            log.info("Prometheus is back")
        self._failing = False
        if _rates(results) != _rates(self._results):
            self._results = results
            self._on_change()


def _rates(results: list[dict]) -> dict[str, float]:
    """Only the numbers that matter (rounded: tiny float noise is not a change)."""
    return {
        r.get("metric", {}).get("service", ""): round(float(r.get("value", [0, "0"])[1]), 2)
        for r in results
    }
