"""CPU and memory from metrics-server (`metrics.k8s.io`), polled: it has no watch.

metrics-server refreshes every 15 s, so polling faster gains nothing. Without it
(not installed yet, or down) the galaxy simply has no metrics; nothing else waits
on this.
"""

import asyncio
import logging
from collections.abc import Callable

from .informer import RawObject
from .source import ApiSource, ListFunction

log = logging.getLogger(__name__)

POLL_SECONDS = 15.0


class MetricsPoller:
    def __init__(
        self,
        pods: ListFunction,
        nodes: ListFunction,
        *,
        on_change: Callable[[], None] = lambda: None,
        poll_seconds: float = POLL_SECONDS,
    ) -> None:
        self._lists = {"podmetrics": pods, "nodemetrics": nodes}
        self._on_change = on_change
        self._poll_seconds = poll_seconds
        self._items: dict[str, list[RawObject]] = {key: [] for key in self._lists}
        self._failing = False

    def items(self, key: str) -> list[RawObject]:
        return self._items[key]

    async def run(self) -> None:
        """Polls until cancelled."""
        while True:
            await self.poll()
            await asyncio.sleep(self._poll_seconds)

    async def poll(self) -> None:
        try:
            fresh = {key: (await ApiSource(fn).list())[0] for key, fn in self._lists.items()}
        except Exception:
            # Log the first failure of a streak, not one every 15 s.
            if not self._failing:
                log.warning("metrics-server unavailable; the galaxy goes without metrics")
            self._failing = True
            return
        if self._failing:
            log.info("metrics-server is back")
        self._failing = False
        if _usage(fresh) != _usage(self._items):
            self._items = fresh
            self._on_change()


def _usage(items: dict[str, list[RawObject]]) -> dict:
    """Only the numbers that matter: `timestamp` and `window` change on every poll."""
    return {
        key: {
            (o["metadata"].get("namespace"), o["metadata"]["name"]): (
                o.get("usage") or [c.get("usage") for c in o.get("containers") or []]
            )
            for o in objects
        }
        for key, objects in items.items()
    }
