"""Minimal raw Kubernetes objects (API JSON shape) for assembly tests."""

from astrolabio_api.kube.cluster import METRICS_KEYS, RESOURCES

SHA = "eb8d8c0f9b206ddecb2dec958c851139503a3ea7"
REPO = "https://github.com/FabianCienC/CV"


def empty_snapshot() -> dict[str, list[dict]]:
    return {key: [] for key in [*(r.key for r in RESOURCES), *METRICS_KEYS]}


def meta(name, namespace=None, labels=None, annotations=None, owner=None) -> dict:
    metadata = {"name": name, "labels": labels or {}, "annotations": annotations or {}}
    if namespace:
        metadata["namespace"] = namespace
    if owner:
        metadata["ownerReferences"] = [{"kind": owner[0], "name": owner[1], "controller": True}]
    return metadata


def node(name, control_plane=False) -> dict:
    labels = {"node-role.kubernetes.io/control-plane": ""} if control_plane else {}
    return {"metadata": meta(name, labels=labels)}


def namespace(name, visible=True, **notes) -> dict:
    labels = {"fabiancienfuegos.com/astrolabio": "visible"} if visible else {}
    annotations = {f"fabiancienfuegos.com/{k}": v for k, v in notes.items()}
    return {"metadata": meta(name, labels=labels, annotations=annotations)}


def deployment(name, ns, replicas=2, ready=2, image=f"ghcr.io/fabiancienc/cv:{SHA}", **notes):
    annotations = {f"fabiancienfuegos.com/{k}": v for k, v in notes.items()}
    return {
        "metadata": meta(name, ns, annotations=annotations),
        "spec": {"replicas": replicas, "template": {"spec": {"containers": [{"image": image}]}}},
        "status": {"readyReplicas": ready},
    }


def replica_set(name, ns, deployment, replicas=2, ready=2) -> dict:
    return {
        "metadata": meta(name, ns, owner=("Deployment", deployment)),
        "spec": {"replicas": replicas},
        "status": {"readyReplicas": ready},
    }


def pod(name, ns, owner, node="w-a", phase="Running", ready=True, restarts=0, labels=None):
    return {
        "metadata": meta(name, ns, labels=labels or {"app": ns}, owner=owner),
        "spec": {"nodeName": node},
        "status": {
            "phase": phase,
            "conditions": [{"type": "Ready", "status": "True" if ready else "False"}],
            "containerStatuses": [{"restartCount": restarts}],
        },
    }


def service(name, ns, selector=None) -> dict:
    return {"metadata": meta(name, ns), "spec": {"selector": selector}}


def route(name, ns, hostnames, backends, parents=(("True", "True"),)) -> dict:
    return {
        "metadata": meta(name, ns),
        "spec": {"hostnames": hostnames, "rules": [{"backendRefs": backends}]},
        "status": {
            "parents": [
                {
                    "conditions": [
                        {"type": "Accepted", "status": accepted},
                        {"type": "ResolvedRefs", "status": resolved},
                    ]
                }
                for accepted, resolved in parents
            ]
        },
    }


def application(name, destination, sync="Synced", health="Healthy") -> dict:
    return {
        "metadata": meta(name, "argocd"),
        "spec": {"destination": {"namespace": destination}},
        "status": {"sync": {"status": sync}, "health": {"status": health}},
    }
