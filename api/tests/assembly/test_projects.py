"""Visible namespaces become constellations built only from allowlisted fields."""

import k8s_objects as k
import pytest

from astrolabio_api.assembly import assemble_galaxy
from astrolabio_api.assembly.annotations import text
from astrolabio_api.assembly.health import replicas_health, worst
from astrolabio_api.assembly.nodes import node_ids
from astrolabio_api.assembly.raw import image_tag
from astrolabio_api.contract.models import Replicas


def _cv_snapshot() -> dict:
    """`cv` mid-rollout: an old and a new replica set, a service and a public route."""
    s = k.empty_snapshot()
    s["nodes"] = [k.node("cp", control_plane=True), k.node("w-b"), k.node("w-a")]
    s["namespaces"] = [
        k.namespace("cv", proyecto="CV", descripcion="Mi CV web en React", repo=k.REPO),
        k.namespace("hidden", visible=False),
    ]
    s["deployments"] = [
        k.deployment("cv", "cv", replicas=2, ready=1, rol="datos", criticidad="Media"),
        k.deployment("secret", "hidden"),
    ]
    s["replicasets"] = [
        k.replica_set("cv-new", "cv", "cv", replicas=1, ready=0),
        k.replica_set("cv-old", "cv", "cv", replicas=1, ready=1),
        k.replica_set("cv-ancient", "cv", "cv", replicas=0, ready=0),  # no pods: not active
    ]
    s["pods"] = [
        k.pod("cv-new-1", "cv", ("ReplicaSet", "cv-new"), phase="Pending", ready=False),
        k.pod("cv-old-1", "cv", ("ReplicaSet", "cv-old"), node="w-b", restarts=3),
        k.pod("job-1", "cv", ("Job", "migrate"), labels={"app": "cv"}),  # not drawn
    ]
    s["services"] = [k.service("cv", "cv", {"app": "cv"}), k.service("manual", "cv")]
    s["httproutes"] = [
        k.route(
            "cv",
            "cv",
            ["cv.fabiancienfuegos.com", "cv.lan"],
            [{"name": "cv", "port": 80}, {"name": "other", "namespace": "hidden"}],
        )
    ]
    s["applications"] = [
        k.application("cv-extra", "cv", sync="OutOfSync"),
        k.application("cv", "cv", health="Weird"),
    ]
    return s


def test_only_visible_namespaces_are_published():
    galaxy = assemble_galaxy(_cv_snapshot())
    assert [c.id for c in galaxy.constellations] == ["cv"]


def test_constellation_from_namespace_annotations_and_argo():
    (cv,) = assemble_galaxy(_cv_snapshot()).constellations
    assert (cv.project, cv.description, cv.repo) == ("CV", "Mi CV web en React", k.REPO)
    # The Application named after the namespace wins; unknown values read as Unknown.
    assert (cv.argo.sync, cv.argo.health) == ("Synced", "Unknown")
    assert cv.health == "degraded"


def test_workload_maps_spanish_annotations_and_commit():
    (cv,) = assemble_galaxy(_cv_snapshot()).constellations
    (workload,) = cv.workloads
    assert (workload.id, workload.kind) == ("cv/deployment/cv", "Deployment")
    assert (workload.role, workload.criticality) == ("data", "medium")
    assert workload.commit.url == f"{k.REPO}/commit/{k.SHA}"
    assert (workload.replicas.desired, workload.replicas.ready, workload.health) == (
        2,
        1,
        "degraded",
    )


def test_rollout_keeps_both_active_replica_sets_with_their_pods():
    (cv,) = assemble_galaxy(_cv_snapshot()).constellations
    replica_sets = {rs.name: rs for rs in cv.workloads[0].replica_sets}
    assert set(replica_sets) == {"cv-new", "cv-old"}
    (new_pod,) = replica_sets["cv-new"].pods
    (old_pod,) = replica_sets["cv-old"].pods
    assert (new_pod.id, new_pod.phase, new_pod.health) == ("cv/pod/cv-new-1", "Pending", "degraded")
    assert (old_pod.node, old_pod.restarts, old_pod.health) == ("worker-2", 3, "ok")


def test_service_targets_only_published_pods():
    (cv,) = assemble_galaxy(_cv_snapshot()).constellations
    services = {s.name: s for s in cv.services}
    # The Job pod matches the selector but is not drawn, so it is not a target.
    assert services["cv"].targets == ["cv/pod/cv-new-1", "cv/pod/cv-old-1"]
    assert services["cv"].health == "degraded"
    assert (services["manual"].targets, services["manual"].health) == ([], "unknown")


def test_route_keeps_public_hostnames_and_same_namespace_backends():
    (cv,) = assemble_galaxy(_cv_snapshot()).constellations
    (route,) = cv.routes
    assert route.hostnames == ["cv.fabiancienfuegos.com"]
    assert route.services == ["cv/service/cv"]
    assert route.health == "ok"


def test_bad_annotations_never_break_the_galaxy():
    s = k.empty_snapshot()
    s["namespaces"] = [
        k.namespace(
            "x",
            proyecto="   ",
            descripcion="a" * 500,
            repo="https://github.com/FabianCienC/homelab-gitops",
        )
    ]
    s["deployments"] = [k.deployment("x", "x", image="nginx:latest", rol="jefe")]
    (x,) = assemble_galaxy(s).constellations
    assert x.project == "x"  # falls back to the namespace name
    assert len(x.description) == 200
    assert x.repo is None
    assert x.workloads[0].commit is None
    assert x.workloads[0].role is None


def test_namespace_without_workloads_is_unknown():
    s = k.empty_snapshot()
    s["namespaces"] = [k.namespace("empty")]
    (empty,) = assemble_galaxy(s).constellations
    assert (empty.workloads, empty.health, empty.argo) == ([], "unknown", None)


def test_node_ids_are_generic():
    nodes = [k.node("zeta"), k.node("cp", control_plane=True), k.node("alpha"), k.node("extra")]
    assert node_ids(nodes) == {"cp": "control-plane", "alpha": "worker-1", "extra": "worker-2"}


@pytest.mark.parametrize(
    ("image", "tag"),
    [
        ("ghcr.io/fabiancienc/cv:abc", "abc"),
        ("localhost:5000/cv", None),
        ("nginx", None),
        ("ghcr.io/x/cv:abc@sha256:123", "abc"),
        ("ghcr.io/x/cv@sha256:123", None),
    ],
)
def test_image_tag(image, tag):
    assert image_tag(image) == tag


@pytest.mark.parametrize(
    ("desired", "ready", "health"),
    [(2, 2, "ok"), (2, 1, "degraded"), (2, 0, "down"), (0, 0, "down"), (1, 2, "ok")],
)
def test_replicas_health(desired, ready, health):
    assert replicas_health(Replicas(desired=desired, ready=ready)) == health


def test_worst_and_text():
    assert worst(["ok", "unknown", "degraded"]) == "degraded"
    assert worst([]) == "unknown"
    assert text("  ") is None
    assert text(" hola ") == "hola"
