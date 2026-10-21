"""The contract models only let allowed, public data through."""

import re

import pytest
from pydantic import ValidationError

from astrolabio_api.contract.example import example_galaxy
from astrolabio_api.contract.models import (
    Commit,
    Constellation,
    Galaxy,
    InfraComponent,
    Pod,
    Route,
    Service,
)

# Field names that must never exist in the public contract.
FORBIDDEN = re.compile(
    r"env|volume|ip$|^ip|ips|host|port|image|tag|version|repourl|token|secret"
    r"|label|annotation|args|command|message|log",
    re.IGNORECASE,
)
# Deliberate exceptions: the contract's own version, and public route hostnames.
ALLOWED = {("Galaxy", "version"), ("Route", "hostnames")}


def _properties(schema: dict) -> list[tuple[str, str]]:
    """(model, field) for every property in the schema, $defs included."""
    pairs = [("Galaxy", field) for field in schema.get("properties", {})]
    for model, definition in schema.get("$defs", {}).items():
        pairs += [(model, field) for field in definition.get("properties", {})]
    return pairs


def _pod(name: str | None = "web-1", id: str = "ns/pod/web-1") -> Pod:
    return Pod(
        id=id, name=name, phase="Running", ready=True, restarts=0, node="worker-1", health="ok"
    )


def test_no_forbidden_field_in_schema():
    schema = Galaxy.model_json_schema(mode="serialization")
    suspicious = [
        f"{model}.{field}"
        for model, field in _properties(schema)
        if FORBIDDEN.search(field) and (model, field) not in ALLOWED
    ]
    assert suspicious == []


def test_every_model_rejects_extra_fields():
    schema = Galaxy.model_json_schema(mode="serialization")
    for name, definition in schema["$defs"].items():
        if definition.get("type") == "object":
            assert definition.get("additionalProperties") is False, name


def test_infra_component_rejects_version():
    data = example_galaxy().core.components[0].model_dump()
    with pytest.raises(ValidationError):
        InfraComponent(**data, version="v3.2.1")


def test_platform_pods_and_services_must_be_anonymous():
    base = dict(
        id="coredns",
        name="CoreDNS",
        purpose="DNS",
        category="network",
        system="Kubernetes",
        replicas={"desired": 1, "ready": 1},
        health="ok",
    )
    InfraComponent(**base, pods=[_pod(name=None, id="core/coredns/pod-1")])
    with pytest.raises(ValidationError, match="without names"):
        InfraComponent(**base, pods=[_pod(name="coredns-5d78c9869d-abcde")])
    with pytest.raises(ValidationError, match="without names"):
        InfraComponent(
            **base,
            services=[
                Service(id="core/coredns/service-1", name="kube-dns", health="ok", targets=[])
            ],
        )


def test_relations_must_point_inside_the_constellation():
    with pytest.raises(ValidationError, match="unknown pods"):
        Constellation(
            id="x",
            project="X",
            health="ok",
            workloads=[],
            services=[Service(id="x/service/a", name="a", health="ok", targets=["x/pod/ghost"])],
        )
    with pytest.raises(ValidationError, match="unknown services"):
        Constellation(
            id="x",
            project="X",
            health="ok",
            workloads=[],
            routes=[
                Route(
                    id="x/route/a",
                    name="a",
                    hostnames=[],
                    health="ok",
                    services=["x/service/ghost"],
                )
            ],
        )


@pytest.mark.parametrize(
    "host", ["internal.lan", "10.0.0.5", "evil.com", "fabiancienfuegos.com.evil.io"]
)
def test_route_only_publishes_public_hostnames(host):
    with pytest.raises(ValidationError):
        Route(id="x/route/a", name="a", hostnames=[host], health="ok", services=[])


@pytest.mark.parametrize(
    "repo",
    [
        "git@github.com:FabianCienC/homelab-gitops.git",
        "https://github.com/FabianCienC/homelab-gitops",
        "https://gitlab.internal/x/y",
        "file:///etc/passwd",
    ],
)
def test_private_or_non_github_repo_is_rejected(repo):
    with pytest.raises(ValidationError):
        Constellation(id="x", project="X", repo=repo, health="ok", workloads=[])


def test_commit_must_be_full_sha_of_public_repo():
    sha = "a" * 40
    Commit(sha=sha, url=f"https://github.com/FabianCienC/CV/commit/{sha}")
    with pytest.raises(ValidationError):
        Commit(sha="latest", url="https://github.com/FabianCienC/CV/commit/latest")
    with pytest.raises(ValidationError):
        Commit(sha=sha, url=f"https://github.com/FabianCienC/homelab-gitops/commit/{sha}")


def test_example_is_valid_and_ids_are_unique():
    galaxy = Galaxy.model_validate_json(example_galaxy().model_dump_json())
    workloads = [w for c in galaxy.constellations for w in c.workloads]
    pods = [p for w in workloads for p in w.all_pods()]

    ids = [
        *(c.id for c in galaxy.constellations),
        *(w.id for w in workloads),
        *(rs.id for w in workloads for rs in w.replica_sets),
        *(p.id for p in pods),
        *(s.id for c in galaxy.constellations for s in c.services),
        *(r.id for c in galaxy.constellations for r in c.routes),
        *(p.id for comp in galaxy.core.components for p in comp.pods),
        *(s.id for comp in galaxy.core.components for s in comp.services),
    ]
    assert len(ids) == len(set(ids))


def test_example_node_pod_counts_match_published_pods():
    galaxy = example_galaxy()
    pods = [
        *(p for c in galaxy.constellations for w in c.workloads for p in w.all_pods()),
        *(p for comp in galaxy.core.components for p in comp.pods),
    ]
    for node in galaxy.core.nodes:
        assert node.pods == sum(p.node == node.id for p in pods), node.id
