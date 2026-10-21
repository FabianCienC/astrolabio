"""Generic informer: list once, cache in memory, then watch from that resourceVersion.

The same list + watch pattern Kubernetes controllers use. A watch closed by the
server (normal after its timeout) resumes from the last resourceVersion seen.
On `410 Gone` the version is too old for the API server, so the informer lists
again, replacing the cache (objects deleted during the gap disappear), and
resumes. Any other error backs off and lists again.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

log = logging.getLogger(__name__)

RawObject = dict[str, Any]  # an object as the API's JSON returns it


class Gone(Exception):
    """The watch's resourceVersion expired (HTTP 410): list again."""


@dataclass(frozen=True)
class WatchEvent:
    type: Literal["ADDED", "MODIFIED", "DELETED", "BOOKMARK"]
    object: RawObject


class Source(Protocol):
    """How an informer reaches one resource type."""

    async def list(self) -> tuple[list[RawObject], str]:
        """Every object, and the list's resourceVersion."""
        ...

    def watch(self, resource_version: str) -> AsyncIterator[WatchEvent]:
        """Changes after `resource_version`. Raises `Gone` on 410."""
        ...


def object_key(obj: RawObject) -> str:
    """`namespace/name`, or `name` for cluster-scoped objects."""
    metadata = obj["metadata"]
    namespace = metadata.get("namespace")
    return f"{namespace}/{metadata['name']}" if namespace else metadata["name"]


class Informer:
    def __init__(
        self,
        name: str,
        source: Source,
        *,
        max_backoff: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.name = name
        self.synced = asyncio.Event()  # set after the first successful list
        self._source = source
        self._max_backoff = max_backoff
        self._sleep = sleep
        self._cache: dict[str, RawObject] = {}
        self._resource_version = ""

    def items(self) -> list[RawObject]:
        return list(self._cache.values())

    async def run(self) -> None:
        """Keeps the cache in sync until cancelled."""
        failures = 0
        while True:
            try:
                await self._list()
                failures = 0
                await self._watch_until_gone()
            except Exception:
                failures += 1
                delay = min(self._max_backoff, 2.0 ** (failures - 1))
                log.exception("%s: list/watch failed, listing again in %.0fs", self.name, delay)
                await self._sleep(delay)

    async def _list(self) -> None:
        items, resource_version = await self._source.list()
        self._cache = {object_key(obj): obj for obj in items}
        self._resource_version = resource_version
        self.synced.set()

    async def _watch_until_gone(self) -> None:
        while True:
            try:
                async for event in self._source.watch(self._resource_version):
                    self._apply(event)
            except Gone:
                log.info("%s: resourceVersion expired, listing again", self.name)
                return

    def _apply(self, event: WatchEvent) -> None:
        if resource_version := event.object.get("metadata", {}).get("resourceVersion"):
            self._resource_version = resource_version
        if event.type == "BOOKMARK":
            return
        key = object_key(event.object)
        if event.type == "DELETED":
            self._cache.pop(key, None)
        else:
            self._cache[key] = event.object
