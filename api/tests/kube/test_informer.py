"""The informer keeps its cache in sync through watch restarts, 410 Gone and errors."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from astrolabio_api.kube.informer import Gone, Informer, RawObject, WatchEvent, object_key

pytestmark = pytest.mark.anyio


def _obj(name: str, rv: str, namespace: str | None = "ns", **extra) -> RawObject:
    metadata = {"name": name, "resourceVersion": rv}
    if namespace:
        metadata["namespace"] = namespace
    return {"metadata": metadata, **extra}


class FakeSource:
    """Plays scripted lists and watches, then blocks once the script runs out.

    A watch script is a list of events; an exception in it is raised there, and
    `END` closes the stream normally (as the server does after its timeout).
    """

    END = object()

    def __init__(self, lists: list, watches: list[list]) -> None:
        self.lists = lists
        self.watches = watches
        self.list_calls = 0
        self.watch_calls: list[str] = []
        self.idle = asyncio.Event()

    async def list(self) -> tuple[list[RawObject], str]:
        self.list_calls += 1
        result = self.lists.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def watch(self, resource_version: str) -> AsyncIterator[WatchEvent]:
        self.watch_calls.append(resource_version)
        if not self.watches:
            self.idle.set()
            await asyncio.Event().wait()
        for step in self.watches.pop(0):
            if step is FakeSource.END:
                return
            if isinstance(step, Exception):
                raise step
            yield step
        self.idle.set()
        await asyncio.Event().wait()


async def _run_until_idle(informer: Informer, source: FakeSource) -> None:
    task = asyncio.create_task(informer.run())
    try:
        await asyncio.wait_for(source.idle.wait(), timeout=1)
    finally:
        task.cancel()


def _names(informer: Informer) -> set[str]:
    return {obj["metadata"]["name"] for obj in informer.items()}


async def test_list_then_apply_watch_events():
    source = FakeSource(
        lists=[([_obj("a", "1"), _obj("b", "2")], "10")],
        watches=[
            [
                WatchEvent("ADDED", _obj("c", "11")),
                WatchEvent("MODIFIED", _obj("a", "12", replicas=3)),
                WatchEvent("DELETED", _obj("b", "13")),
            ]
        ],
    )
    informer = Informer("test", source)
    await _run_until_idle(informer, source)

    assert informer.synced.is_set()
    assert source.watch_calls == ["10"]  # watches from the list's resourceVersion
    assert _names(informer) == {"a", "c"}
    assert next(o for o in informer.items() if o["metadata"]["name"] == "a")["replicas"] == 3


async def test_closed_watch_resumes_from_last_version_without_listing():
    source = FakeSource(
        lists=[([_obj("a", "1")], "10")],
        watches=[
            [WatchEvent("ADDED", _obj("b", "11")), FakeSource.END],
            [WatchEvent("BOOKMARK", {"metadata": {"resourceVersion": "20"}}), FakeSource.END],
            [],
        ],
    )
    informer = Informer("test", source)
    await _run_until_idle(informer, source)

    assert source.list_calls == 1
    assert source.watch_calls == ["10", "11", "20"]  # bookmarks advance the version too
    assert _names(informer) == {"a", "b"}


async def test_gone_lists_again_and_replaces_the_cache():
    source = FakeSource(
        lists=[([_obj("a", "1"), _obj("b", "2")], "10"), ([_obj("a", "30")], "31")],
        watches=[[Gone()], []],
    )
    informer = Informer("test", source)
    await _run_until_idle(informer, source)

    assert source.list_calls == 2
    assert source.watch_calls == ["10", "31"]
    assert _names(informer) == {"a"}  # `b` was deleted while the version was expired


async def test_errors_back_off_and_list_again():
    delays: list[float] = []

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    source = FakeSource(
        lists=[
            ConnectionError("api down"),
            ConnectionError("api down"),
            ([_obj("a", "1")], "10"),
            ([_obj("a", "1"), _obj("b", "2")], "20"),
        ],
        watches=[[ConnectionError("stream reset")], []],
    )
    informer = Informer("test", source, sleep=sleep)
    await _run_until_idle(informer, source)

    assert delays == [1.0, 2.0, 1.0]  # grows while failing, resets after a good list
    assert source.watch_calls == ["10", "20"]
    assert _names(informer) == {"a", "b"}


async def test_backoff_is_capped():
    delays: list[float] = []

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    source = FakeSource(lists=[*(ConnectionError() for _ in range(6)), ([], "1")], watches=[[]])
    informer = Informer("test", source, max_backoff=8.0, sleep=sleep)
    await _run_until_idle(informer, source)

    assert delays == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]
    assert not informer.items()


def test_cluster_scoped_objects_are_keyed_by_name():
    assert object_key(_obj("a", "1")) == "ns/a"
    assert object_key(_obj("worker", "1", namespace=None)) == "worker"
