"""`Source` backed by kubernetes_asyncio, reading raw JSON straight off the wire.

It reads the HTTP response itself (`_preload_content=False`) instead of using
`kubernetes_asyncio.watch.Watch`, which turns objects into models and retries
410 on its own: the informer wants raw dicts and must see every 410.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .informer import Gone, RawObject, WatchEvent

# A list call of the generated client, e.g. `CoreV1Api(client).list_pod_for_all_namespaces`.
ListFunction = Callable[..., Awaitable[Any]]

# The server closes each watch after this; the informer resumes it from the last version.
# It stays below aiohttp's default 300 s total timeout, which `_request_timeout` lifts.
WATCH_TIMEOUT_SECONDS = 240

_LAST_APPLIED = "kubectl.kubernetes.io/last-applied-configuration"
_EVENT_TYPES = {"ADDED", "MODIFIED", "DELETED", "BOOKMARK"}


class ApiError(Exception):
    """The API server answered with an error other than 410."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status}: {reason}")
        self.status = status


class ApiSource:
    def __init__(self, list_function: ListFunction) -> None:
        self._list = list_function

    async def list(self) -> tuple[list[RawObject], str]:
        response = await self._list(_preload_content=False)
        try:
            await _check_status(response)
            body = json.loads(await response.read())
        finally:
            response.release()
        return [_trim(obj) for obj in body["items"]], body["metadata"]["resourceVersion"]

    async def watch(self, resource_version: str) -> AsyncIterator[WatchEvent]:
        response = await self._list(
            watch=True,
            resource_version=resource_version,
            allow_watch_bookmarks=True,
            timeout_seconds=WATCH_TIMEOUT_SECONDS,
            _request_timeout=WATCH_TIMEOUT_SECONDS + 30,
            _preload_content=False,
        )
        try:
            await _check_status(response)
            # One JSON event per line. Lines are split by hand: aiohttp's readline
            # rejects lines over its buffer limit, and an Argo Application can be big.
            buffer = b""
            async for chunk in response.content.iter_any():
                *lines, buffer = (buffer + chunk).split(b"\n")
                for line in lines:
                    if line.strip():
                        yield _event(json.loads(line))
        finally:
            response.release()


async def _check_status(response: Any) -> None:
    if response.status == 410:
        raise Gone()
    if not 200 <= response.status <= 299:
        raise ApiError(response.status, response.reason or "")


def _event(data: dict) -> WatchEvent:
    obj = data["object"]
    if data["type"] == "ERROR":
        # A watch from a too old resourceVersion answers 200 and then this event.
        if obj.get("code") == 410:
            raise Gone()
        raise ApiError(obj.get("code", 0), obj.get("reason", ""))
    if data["type"] not in _EVENT_TYPES:
        raise ApiError(0, f"unknown watch event type {data['type']!r}")
    return WatchEvent(data["type"], _trim(obj))


def _trim(obj: RawObject) -> RawObject:
    """Drops bulky metadata nothing reads, so the cache stays small."""
    metadata = obj.get("metadata", {})
    metadata.pop("managedFields", None)
    metadata.get("annotations", {}).pop(_LAST_APPLIED, None)
    return obj
