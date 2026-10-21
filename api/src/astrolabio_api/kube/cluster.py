"""Every informer the API needs, one per watched resource, sharing one API client.

`snapshot()` is what `assembly/` reads: raw objects by resource key. The keys
are the contract between the two layers (the poisoned cluster in
`tests/sanitization/` uses the same ones).
"""

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from kubernetes_asyncio import config
from kubernetes_asyncio.client import (
    ApiClient,
    AppsV1Api,
    Configuration,
    CoreV1Api,
    CustomObjectsApi,
)

from .informer import Informer, RawObject
from .metrics import MetricsPoller
from .source import ApiSource, ListFunction
from .traffic import TrafficPoller


@dataclass(frozen=True)
class Resource:
    key: str
    list_function: Callable[[ApiClient], ListFunction]


def _custom(group: str, version: str, plural: str, namespace: str | None = None):
    def build(client: ApiClient) -> ListFunction:
        api = CustomObjectsApi(client)
        if namespace:
            return partial(api.list_namespaced_custom_object, group, version, namespace, plural)
        return partial(api.list_cluster_custom_object, group, version, plural)

    return build


# Each one must be granted (get, list, watch) by the `astrolabio-reader` ClusterRole.
RESOURCES = (
    Resource("nodes", lambda c: CoreV1Api(c).list_node),
    Resource("namespaces", lambda c: CoreV1Api(c).list_namespace),
    Resource("pods", lambda c: CoreV1Api(c).list_pod_for_all_namespaces),
    Resource("services", lambda c: CoreV1Api(c).list_service_for_all_namespaces),
    Resource("events", lambda c: CoreV1Api(c).list_event_for_all_namespaces),
    Resource("deployments", lambda c: AppsV1Api(c).list_deployment_for_all_namespaces),
    Resource("replicasets", lambda c: AppsV1Api(c).list_replica_set_for_all_namespaces),
    Resource("statefulsets", lambda c: AppsV1Api(c).list_stateful_set_for_all_namespaces),
    Resource("daemonsets", lambda c: AppsV1Api(c).list_daemon_set_for_all_namespaces),
    Resource("httproutes", _custom("gateway.networking.k8s.io", "v1", "httproutes")),
    Resource("applications", _custom("argoproj.io", "v1alpha1", "applications", "argocd")),
)

# Snapshot keys filled by the metrics poller (polled, not watched; empty without metrics-server).
METRICS_KEYS = ("podmetrics", "nodemetrics")
# Snapshot key filled by the traffic poller (Prometheus; empty without it).
TRAFFIC_KEY = "traffic"
# Every key of `Cluster.snapshot()`: the contract between kube/ and assembly/.
SNAPSHOT_KEYS = (*(r.key for r in RESOURCES), *METRICS_KEYS, TRAFFIC_KEY)


async def load_configuration() -> Configuration:
    """In-cluster service account token when running in a pod, kubeconfig otherwise."""
    configuration = Configuration()
    if "KUBERNETES_SERVICE_HOST" in os.environ:
        config.load_incluster_config(client_configuration=configuration)
    else:
        await config.load_kube_config(client_configuration=configuration)
    return configuration


class Cluster:
    def __init__(self, client: ApiClient, prometheus_url: str = "") -> None:
        self._client = client
        # Set by any informer on any change; `live.py` waits on it to push the galaxy.
        self.changed = asyncio.Event()
        self.informers = {
            r.key: Informer(r.key, ApiSource(r.list_function(client)), on_change=self.changed.set)
            for r in RESOURCES
        }
        # CPU and memory (metrics-server): polled, and optional.
        metrics = CustomObjectsApi(client)
        self.metrics = MetricsPoller(
            partial(metrics.list_cluster_custom_object, "metrics.k8s.io", "v1beta1", "pods"),
            partial(metrics.list_cluster_custom_object, "metrics.k8s.io", "v1beta1", "nodes"),
            on_change=self.changed.set,
        )
        # Requests per second through Traefik (Prometheus): polled, and optional.
        self.traffic = TrafficPoller(prometheus_url, on_change=self.changed.set)
        self._prometheus = bool(prometheus_url)
        self._tasks: list[asyncio.Task] = []

    @classmethod
    async def connect(cls, prometheus_url: str = "") -> "Cluster":
        return cls(ApiClient(configuration=await load_configuration()), prometheus_url)

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(informer.run(), name=f"informer-{key}")
            for key, informer in self.informers.items()
        ] + [asyncio.create_task(self.metrics.run(), name="metrics")]
        if self._prometheus:
            self._tasks.append(asyncio.create_task(self.traffic.run(), name="traffic"))

    @property
    def synced(self) -> bool:
        """Every informer has listed at least once."""
        return all(i.synced.is_set() for i in self.informers.values())

    async def wait_synced(self) -> None:
        await asyncio.gather(*(i.synced.wait() for i in self.informers.values()))

    def snapshot(self) -> dict[str, list[RawObject]]:
        return {
            **{key: informer.items() for key, informer in self.informers.items()},
            **{key: self.metrics.items(key) for key in METRICS_KEYS},
            TRAFFIC_KEY: self.traffic.items(),
        }

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._client.close()
