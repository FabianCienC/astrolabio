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
from .source import ApiSource, ListFunction


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


async def load_configuration() -> Configuration:
    """In-cluster service account token when running in a pod, kubeconfig otherwise."""
    configuration = Configuration()
    if "KUBERNETES_SERVICE_HOST" in os.environ:
        config.load_incluster_config(client_configuration=configuration)
    else:
        await config.load_kube_config(client_configuration=configuration)
    return configuration


class Cluster:
    def __init__(self, client: ApiClient) -> None:
        self._client = client
        self.informers = {
            r.key: Informer(r.key, ApiSource(r.list_function(client))) for r in RESOURCES
        }
        self._tasks: list[asyncio.Task] = []

    @classmethod
    async def connect(cls) -> "Cluster":
        return cls(ApiClient(configuration=await load_configuration()))

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(informer.run(), name=f"informer-{key}")
            for key, informer in self.informers.items()
        ]

    async def wait_synced(self) -> None:
        await asyncio.gather(*(i.synced.wait() for i in self.informers.values()))

    def snapshot(self) -> dict[str, list[RawObject]]:
        return {key: informer.items() for key, informer in self.informers.items()}

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._client.close()
