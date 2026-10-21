"""Nothing forbidden leaves the API, whatever the cluster holds.

`find_leaks` walks a JSON document and reports raw Kubernetes keys, IPs,
versions, internal paths and the poisoned cluster's secrets. It runs on what
`GET /api/galaxy` serves today and on what `assembly/` builds from the poisoned
cluster (written before `assembly/` exists: PLAN E1.2).
"""

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from poisoned_cluster import SECRETS, poisoned_cluster

from astrolabio_api.config import Settings
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
    response = TestClient(create_app(Settings(environment="production"))).get("/api/galaxy")
    assert find_leaks(response.json()) == []


@pytest.mark.xfail(
    raises=ModuleNotFoundError,
    strict=True,
    reason="assembly/ does not exist yet (PLAN E1.5-E1.6); drop this mark then",
)
def test_assembled_galaxy_has_no_leaks():
    from astrolabio_api.assembly import assemble_galaxy

    galaxy = assemble_galaxy(poisoned_cluster())
    assert find_leaks(galaxy.model_dump(mode="json")) == []
    # Allowed data survives: this is a filter, not a wipe.
    (cv,) = galaxy.constellations
    assert cv.id == "cv"
    assert [r.hostnames for r in cv.routes] == [["cv.fabiancienfuegos.com"]]
    assert cv.workloads[0].criticality is None  # unknown annotation value
    assert {c.id for c in galaxy.core.components} == {"coredns", "kube-apiserver", "calico-node"}
