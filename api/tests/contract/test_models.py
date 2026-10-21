"""The contract models only let allowed, public data through."""

import re

import pytest
from pydantic import ValidationError

from astrolabio_api.contract.example import example_galaxy
from astrolabio_api.contract.models import Commit, Constellation, Galaxy, InfraComponent

# Field names that must never exist in the public contract.
FORBIDDEN = re.compile(
    r"env|volume|ip$|^ip|ips|host|port|image|tag|version|repourl|token|secret"
    r"|label|annotation|pod_?name|args|command|message",
    re.IGNORECASE,
)
# The contract's own `version` is the only exception, and only at the root.
ALLOWED_AT_ROOT = {"version"}


def _properties(schema: dict) -> list[tuple[str, str]]:
    """(model, field) for every property in the schema, $defs included."""
    pairs = [("Galaxy", field) for field in schema.get("properties", {})]
    for model, definition in schema.get("$defs", {}).items():
        pairs += [(model, field) for field in definition.get("properties", {})]
    return pairs


def test_no_forbidden_field_in_schema():
    schema = Galaxy.model_json_schema(mode="serialization")
    suspicious = [
        f"{model}.{field}"
        for model, field in _properties(schema)
        if FORBIDDEN.search(field) and not (model == "Galaxy" and field in ALLOWED_AT_ROOT)
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
        Constellation(id="x", project="X", repo=repo, stars=[])


def test_commit_must_be_full_sha_of_public_repo():
    sha = "a" * 40
    Commit(sha=sha, url=f"https://github.com/FabianCienC/CV/commit/{sha}")
    with pytest.raises(ValidationError):
        Commit(sha="latest", url="https://github.com/FabianCienC/CV/commit/latest")
    with pytest.raises(ValidationError):
        Commit(sha=sha, url=f"https://github.com/FabianCienC/homelab-gitops/commit/{sha}")


def test_example_is_valid_and_covers_every_health():
    galaxy = Galaxy.model_validate_json(example_galaxy().model_dump_json())
    healths = {s.health for c in galaxy.constellations for s in c.stars}
    assert healths == {"ok", "degraded", "down", "unknown"}
    ids = [s.id for c in galaxy.constellations for s in c.stars]
    assert len(ids) == len(set(ids))
