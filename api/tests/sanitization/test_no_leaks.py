"""Nothing forbidden leaves the API, whatever the cluster holds.

`find_leaks` walks a JSON document and reports raw Kubernetes keys, IPs,
versions, internal paths and the poisoned cluster's secrets. It runs on what
`GET /api/galaxy` serves today and on what `assembly/` builds from the poisoned
cluster.
"""

import re
from collections.abc import Iterator

from fastapi.testclient import TestClient
from poisoned_cluster import SECRETS, SHA, poisoned_cluster

from astrolabio_api.assembly import assemble_galaxy
from astrolabio_api.config import Settings
from astrolabio_api.kube.cluster import SNAPSHOT_KEYS
from astrolabio_api.main import create_app

# Keys of raw Kubernetes objects, or of data the contract never carries.
FORBIDDEN_KEYS = {
    "metadata", "spec", "status", "uid", "resourceversion", "managedfields",
    "labels", "annotations", "ownerreferences",
    "env", "envfrom", "volumes", "volumemounts", "containers", "image", "args", "command",
    "ports", "podip", "podips", "hostip", "hostips", "clusterip", "clusterips", "addresses",
    "nodename", "hostname", "nodeinfo", "repourl", "revision", "message", "involvedobject",
}  # fmt: skip
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
VERSION = re.compile(r"\bv?\d+\.\d+\.\d+\b")
INTERNAL_PATH = re.compile(r"(?<![\w.])/(?:var|etc|home|root|run|proc|opt|tmp|usr|srv|mnt)/")


def _walk(node: object, path: str = "$") -> Iterator[tuple[str, str, bool]]:
    """(path, text, is_key) for every key and string value in a JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, True
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node, False


def find_leaks(document: object) -> list[str]:
    leaks = []
    for path, text, is_key in _walk(document):
        if is_key and text.lower() in FORBIDDEN_KEYS:
            leaks.append(f"{path}: forbidden key {text!r}")
        if not is_key:
            for name, pattern in (("IP", IPV4), ("version", VERSION), ("path", INTERNAL_PATH)):
                if pattern.search(text):
                    leaks.append(f"{path}: {name} in {text!r}")
        leaks += [f"{path}: secret {s!r} in {text!r}" for s in SECRETS if s in text]
    return leaks


def test_scanner_catches_the_poisoned_cluster():
    # Guards against a scanner that silently finds nothing.
    leaks = "\n".join(find_leaks(poisoned_cluster()))
    for secret in SECRETS:
        assert repr(secret) in leaks, secret
    for kind in ("forbidden key", "IP in", "version in", "path in"):
        assert kind in leaks, kind


def test_served_galaxy_has_no_leaks():
    response = TestClient(create_app(Settings(environment="production", source="example"))).get(
        "/api/galaxy"
    )
    assert find_leaks(response.json()) == []


def test_assembled_galaxy_has_no_leaks():
    galaxy = assemble_galaxy(poisoned_cluster())
    assert find_leaks(galaxy.model_dump(mode="json")) == []
    # Allowed data survives: this is a filter, not a wipe.
    (cv,) = galaxy.constellations
    assert cv.id == "cv"
    assert [r.hostnames for r in cv.routes] == [["cv.fabiancienfuegos.com"]]
    assert cv.workloads[0].criticality is None  # unknown annotation value
    assert cv.workloads[0].commit and cv.workloads[0].commit.sha == SHA
    assert [p.name for p in cv.workloads[0].all_pods()] == ["cv-7d9f8b6c5-abcde"]
    # Metrics arrive as numbers only: 3141592n -> 3 millicores, 12288Ki -> 12 MiB.
    (pod,) = cv.workloads[0].all_pods()
    assert (pod.metrics.cpu_millicores, pod.metrics.memory_mib) == (3, 12)
    assert cv.workloads[0].metrics == pod.metrics
    # Traffic arrives as numbers only, on the visible project's route and Service.
    assert cv.routes[0].traffic.requests_per_second == 1.5
    assert cv.services[0].traffic.requests_per_second == 1.5


def test_metrics_reach_components_and_nodes():
    core = assemble_galaxy(poisoned_cluster()).core
    coredns = next(c for c in core.components if c.id == "coredns")
    assert (coredns.metrics.cpu_millicores, coredns.metrics.memory_mib) == (3, 24)
    nodes = {n.id: n.metrics for n in core.nodes}
    assert (nodes["control-plane"].cpu_millicores, nodes["control-plane"].memory_mib) == (412, 2048)
    assert nodes["worker-1"].cpu_millicores is None  # no sample: no number, never a guess


def test_core_publishes_only_catalog_components():
    core = assemble_galaxy(poisoned_cluster()).core
    components = {c.id: c for c in core.components}
    assert set(components) == {"coredns", "kube-apiserver", "calico-node"}  # no debug-shell
    # kube-dns is drawn, but without its name.
    assert [(s.id, s.name) for s in components["coredns"].services] == [
        ("core/coredns/service-1", None)
    ]
    assert [(n.id, n.pods) for n in core.nodes] == [
        ("control-plane", 2),
        ("worker-1", 1),
        ("worker-2", 1),
    ]


def test_poisoned_cluster_has_every_watched_resource():
    # The keys are the contract between kube/ and assembly/.
    assert set(poisoned_cluster()) == set(SNAPSHOT_KEYS)
