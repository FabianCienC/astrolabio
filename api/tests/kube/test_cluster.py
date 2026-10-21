"""One informer per watched resource, built without touching the network."""

import pytest
from kubernetes_asyncio.client import ApiClient, Configuration

from astrolabio_api.kube.cluster import METRICS_KEYS, RESOURCES, Cluster

pytestmark = pytest.mark.anyio


async def test_one_informer_per_resource():
    cluster = Cluster(ApiClient(configuration=Configuration()))
    try:
        assert list(cluster.informers) == [r.key for r in RESOURCES]
        keys = [*(r.key for r in RESOURCES), *METRICS_KEYS]
        assert cluster.snapshot() == {key: [] for key in keys}
    finally:
        await cluster.close()


def test_resource_keys_are_unique():
    keys = [r.key for r in RESOURCES]
    assert len(keys) == len(set(keys))
