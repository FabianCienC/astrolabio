"""The broadcaster pushes the full galaxy, only when it really changed, newest first."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from astrolabio_api.contract.example import example_galaxy
from astrolabio_api.contract.models import Galaxy
from astrolabio_api.live import Broadcaster

pytestmark = pytest.mark.anyio


class Cluster:
    """A galaxy that tests change by hand, and the event informers would set."""

    def __init__(self) -> None:
        self.galaxy: Galaxy | None = example_galaxy()
        self.changed = asyncio.Event()
        self.assemblies = 0

    def snapshot(self) -> Galaxy | None:
        self.assemblies += 1
        return self.galaxy

    def touch(self, **update) -> None:
        assert self.galaxy
        self.galaxy = self.galaxy.model_copy(update=update)
        self.changed.set()


def _projects(payload: str) -> list[str]:
    return [c["id"] for c in json.loads(payload)["constellations"]]


async def _round(broadcaster: Broadcaster) -> None:
    """Lets the run loop handle what is pending (its batch window is 0 in tests)."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_subscriber_starts_with_the_current_galaxy():
    cluster = Cluster()
    queue = Broadcaster(cluster.snapshot, cluster.changed).subscribe()
    assert queue is not None
    assert _projects(queue.get_nowait()) == ["hola", "cv", "astrolabio"]


async def test_nothing_before_the_cache_syncs():
    cluster = Cluster()
    cluster.galaxy = None
    assert Broadcaster(cluster.snapshot, cluster.changed).subscribe() is None


async def test_pushes_real_changes_and_skips_noise():
    cluster = Cluster()
    broadcaster = Broadcaster(cluster.snapshot, cluster.changed, batch_seconds=0)
    queue = broadcaster.subscribe()
    queue.get_nowait()
    task = asyncio.create_task(broadcaster.run())
    try:
        # Only generated_at moves (an Event churned): nothing to send.
        cluster.touch(generated_at=datetime.now(UTC) + timedelta(minutes=1))
        await _round(broadcaster)
        assert queue.empty()

        # A project disappears: everyone gets the new galaxy.
        cluster.touch(constellations=cluster.galaxy.constellations[:1])
        await _round(broadcaster)
        assert _projects(queue.get_nowait()) == ["hola"]
    finally:
        task.cancel()


async def test_slow_client_gets_the_newest_galaxy_not_a_backlog():
    cluster = Cluster()
    broadcaster = Broadcaster(cluster.snapshot, cluster.changed, batch_seconds=0)
    queue = broadcaster.subscribe()  # its first galaxy is never read
    task = asyncio.create_task(broadcaster.run())
    try:
        cluster.touch(constellations=cluster.galaxy.constellations[:2])
        await _round(broadcaster)
        cluster.touch(constellations=cluster.galaxy.constellations[:1])
        await _round(broadcaster)
        assert queue.qsize() == 1
        assert _projects(queue.get_nowait()) == ["hola"]
    finally:
        task.cancel()


async def test_changes_are_batched():
    cluster = Cluster()
    broadcaster = Broadcaster(cluster.snapshot, cluster.changed, batch_seconds=0.2)
    broadcaster.subscribe()
    before = cluster.assemblies
    task = asyncio.create_task(broadcaster.run())
    try:
        for _ in range(10):  # a rollout touching many objects at once
            cluster.changed.set()
            await asyncio.sleep(0)  # yields without a timer (coarse on Windows)
        await asyncio.sleep(0.4)
        assert cluster.assemblies - before == 1
    finally:
        task.cancel()


async def test_turns_clients_away_when_full():
    cluster = Cluster()
    broadcaster = Broadcaster(cluster.snapshot, cluster.changed, max_clients=2)
    first, second = broadcaster.subscribe(), broadcaster.subscribe()
    assert broadcaster.subscribe() is None
    broadcaster.unsubscribe(first)
    assert broadcaster.subscribe() is not None
    assert second is not None
