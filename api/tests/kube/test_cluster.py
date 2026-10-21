"""One informer per watched resource, built without touching the network."""

import pytest
from kubernetes_asyncio.client import ApiClient, Configuration

from astrolabio_api.kube.cluster import RESOURCES, Cluster

pytestmark = pytest.mark.anyio


async def test_one_informer_per_resource():
    cluster = Cluster(ApiClient(configuration=Configuration()))
    try:
        assert list(cluster.informers) == [r.key for r in RESOURCES]
        assert cluster.snapshot() == {r.key: [] for r in RESOURCES}
    finally:
        await cluster.close()


def test_resource_keys_are_unique():
    keys = [r.key for r in RESOURCES]
    assert len(keys) == len(set(keys))
