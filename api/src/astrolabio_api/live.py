"""Live galaxy for `/ws`: re-assembles on cluster changes and pushes it to every client.

Every message is the full sanitized `Galaxy`, the same model as `GET /api/galaxy`,
so nothing leaves the API without passing through the contract. Changes are
batched (one assembly per second at most) and only sent when the galaxy really
changed: Events churn constantly but rarely change what is drawn.
"""

import asyncio
import logging
from collections.abc import Callable

from .contract.models import Galaxy

log = logging.getLogger(__name__)

# How long to gather changes before assembling; a rollout touches many objects at once.
BATCH_SECONDS = 1.0
# Beyond this, new clients are turned away: each one costs a queue and a socket.
MAX_CLIENTS = 200
# Connections one visitor (one IP) may hold, so a single client can't take every slot.
MAX_PER_VISITOR = 4


class Broadcaster:
    def __init__(
        self,
        snapshot: Callable[[], Galaxy | None],
        changed: asyncio.Event,
        *,
        batch_seconds: float = BATCH_SECONDS,
        max_clients: int = MAX_CLIENTS,
        max_per_visitor: int = MAX_PER_VISITOR,
    ) -> None:
        """`snapshot` builds the current galaxy (None while the cache syncs); `changed` is set
        by the informers on any change."""
        self._snapshot = snapshot
        self._changed = changed
        self._batch_seconds = batch_seconds
        self._max_clients = max_clients
        self._max_per_visitor = max_per_visitor
        # One slot per client: a slow client gets the newest galaxy, never a backlog.
        self._clients: dict[asyncio.Queue[str], str | None] = {}  # queue -> visitor
        self._last_payload: str | None = None
        self._last_key: str | None = None

    @property
    def clients(self) -> int:
        return len(self._clients)

    def current(self) -> str | None:
        """The latest galaxy as JSON: assembled once per change, not once per request.
        None while the cache syncs."""
        if self._last_payload is None:
            self._refresh()
        return self._last_payload

    def subscribe(self, visitor: str | None = None) -> asyncio.Queue[str] | None:
        """A queue that starts with the current galaxy; None when full (overall or for this
        visitor) or not synced yet."""
        if len(self._clients) >= self._max_clients:
            return None
        if visitor is not None and self._held_by(visitor) >= self._max_per_visitor:
            return None
        if self._last_payload is None and not self._refresh():
            return None
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        queue.put_nowait(self._last_payload)  # type: ignore[arg-type]
        self._clients[queue] = visitor
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._clients.pop(queue, None)

    def _held_by(self, visitor: str) -> int:
        return sum(v == visitor for v in self._clients.values())

    async def run(self) -> None:
        """Pushes every real change until cancelled."""
        while True:
            await self._changed.wait()
            await asyncio.sleep(self._batch_seconds)
            self._changed.clear()
            try:
                if self._refresh():
                    self._publish()
            except Exception:
                log.exception("could not assemble the live galaxy")

    def _refresh(self) -> bool:
        """Assembles the galaxy; True when it differs from the last one."""
        galaxy = self._snapshot()
        if galaxy is None:
            return False
        # generated_at changes every time; it doesn't make the galaxy different.
        key = galaxy.model_dump_json(exclude={"generated_at"})
        if key == self._last_key:
            return False
        self._last_key = key
        self._last_payload = galaxy.model_dump_json()
        return True

    def _publish(self) -> None:
        for queue in self._clients:
            if queue.full():
                queue.get_nowait()  # drop the stale one this client hasn't sent yet
            queue.put_nowait(self._last_payload)  # type: ignore[arg-type]
