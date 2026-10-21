"""The core publishes only catalog components, anonymously, and the nodes as suns."""

import k8s_objects as k

from astrolabio_api.assembly import assemble_galaxy
from astrolabio_api.assembly.catalog import CATALOG
from astrolabio_api.contract.example import example_galaxy


def _platform_snapshot() -> dict:
    s = k.empty_snapshot()
    s["nodes"] = [k.node("cp", control_plane=True), k.node("w-a"), k.node("w-b")]
    s["nodes"][2]["status"] = {"conditions": [{"type": "Ready", "status": "False"}]}
    s["nodes"][0]["status"] = {"conditions": [{"type": "Ready", "status": "True"}]}
    s["deployments"] = [
        k.deployment("coredns", "kube-system", replicas=2, ready=2),
        k.deployment("traefik", "traefik", replicas=1, ready=1),
        k.deployment("metrics-hack", "kube-system"),  # not in the catalog
    ]
    s["replicasets"] = [k.replica_set("coredns-abc", "kube-system", "coredns")]
    s["pods"] = [
        k.pod(
            "coredns-abc-1",
            "kube-system",
            ("ReplicaSet", "coredns-abc"),
            "cp",
            labels={"k8s-app": "kube-dns"},
        ),
        k.pod(
            "coredns-abc-2",
            "kube-system",
            ("ReplicaSet", "coredns-abc"),
            "w-a",
            labels={"k8s-app": "kube-dns"},
        ),
        k.pod(
            "kube-apiserver-cp",
            "kube-system",
            ("Node", "cp"),
            "cp",
            labels={"component": "kube-apiserver", "tier": "control-plane"},
        ),
        k.pod("metrics-hack-1", "kube-system", ("ReplicaSet", "metrics-hack-x"), "w-b"),
    ]
    s["services"] = [
        k.service("kube-dns", "kube-system", {"k8s-app": "kube-dns"}),
        k.service("kubernetes", "default"),  # selectorless: listed in the catalog entry
    ]
    s["applications"] = [k.application("traefik", "traefik", sync="OutOfSync")]
    return s


def test_example_components_match_the_catalog():
    # The example is a real snapshot: each of its components must be its catalog entry,
    # in catalog order. The catalog may list more (absent when the snapshot was taken).
    entries = {e.id: e for e in CATALOG}
    order = list(entries)
    components = example_galaxy().core.components
    for c in components:
        e = entries.get(c.id)
        assert e, f"{c.id} is not in the catalog"
        assert (c.name, c.purpose, c.category, c.system, c.argo is not None) == (
            e.name,
            e.purpose,
            e.category,
            e.system,
            e.application is not None,
        ), c.id
    assert [c.id for c in components] == sorted((c.id for c in components), key=order.index)


def test_only_catalog_components_present_in_the_cluster_are_published():
    core = assemble_galaxy(_platform_snapshot()).core
    assert [c.id for c in core.components] == ["kube-apiserver", "coredns", "traefik"]


def test_component_pods_and_services_are_anonymous():
    components = {c.id: c for c in assemble_galaxy(_platform_snapshot()).core.components}
    coredns = components["coredns"]
    assert [(p.id, p.name, p.node) for p in coredns.pods] == [
        ("core/coredns/pod-1", None, "control-plane"),
        ("core/coredns/pod-2", None, "worker-1"),
    ]
    assert [(s.id, s.name, s.targets) for s in coredns.services] == [
        ("core/coredns/service-1", None, ["core/coredns/pod-1", "core/coredns/pod-2"])
    ]


def test_static_pod_and_selectorless_service():
    components = {c.id: c for c in assemble_galaxy(_platform_snapshot()).core.components}
    apiserver = components["kube-apiserver"]
    assert (apiserver.replicas.desired, apiserver.replicas.ready, apiserver.health) == (1, 1, "ok")
    assert [s.targets for s in apiserver.services] == [["core/kube-apiserver/pod-1"]]


def test_argo_status_only_for_components_deployed_by_an_application():
    components = {c.id: c for c in assemble_galaxy(_platform_snapshot()).core.components}
    assert components["traefik"].argo.sync == "OutOfSync"
    assert components["coredns"].argo is None


def test_nodes_are_generic_suns_counting_published_pods():
    nodes = assemble_galaxy(_platform_snapshot()).core.nodes
    assert [(n.id, n.name, n.role, n.health, n.pods) for n in nodes] == [
        ("control-plane", "control plane", "control-plane", "ok", 2),
        ("worker-1", "worker 1", "worker", "unknown", 1),
        ("worker-2", "worker 2", "worker", "down", 0),  # metrics-hack is not published
    ]
