"""A poisoned cluster: raw Kubernetes objects, shaped like the API's JSON, full of data
that must never reach the public galaxy.

Every forbidden value is listed in `SECRETS`, so the tests can check that none of
them survives assembly. Allowed data (visible project names, public hostnames,
the image SHA of a project) is mixed in on purpose, so assembly has something real
to keep.
"""

SHA = "3f9c2a7e1b4d8f6a0c5e9b2d7a1f4c8e6b3d0a9f"  # image tag of `cv`: public, allowed
GITOPS_SHA = "9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d"  # private GitOps commit: forbidden

# Every value here is forbidden in the output, wherever it appears.
SECRETS = [
    # env, volumes and config
    "s3cr3t-db-password",
    "DATABASE_URL",
    "cv-tls-cert",
    "/etc/coredns/Corefile",
    "/var/lib/kubelet/pods/0b1c2d3e/volumes",
    # IPs
    "10.244.1.23",
    "10.244.2.7",
    "10.96.0.10",
    "10.96.143.200",
    "192.168.0.41",
    "192.168.0.42",
    "192.168.0.43",
    # node hostnames
    "k8s-cp-01",
    "k8s-w-01",
    "k8s-w-02",
    # private GitOps repo
    "homelab-gitops",
    GITOPS_SHA,
    # versions and image tags of the platform
    "v1.12.0",
    "v3.29.1",
    "v1.35.0",
    "registry.k8s.io",
    "quay.io",
    # platform pod and service names
    "coredns-668d6bf9bc-x7k2p",
    "calico-node-4hq9z",
    "kube-dns",  # the static pod `kube-apiserver-k8s-cp-01` is covered by its hostname
    # outside the allowlist: hidden namespace, unknown platform workload, internal route
    "lab-privado",
    "proyecto-secreto",
    "debug-shell",
    "cv-admin.internal.lan",
    # annotations that are not ours, and an unknown annotation value
    "last-applied-configuration",
    "urgentisima",
    # Event messages
    "MountVolume.SetUp failed",
]


def _meta(name: str, namespace: str | None = None, **extra) -> dict:
    meta = {
        "name": name,
        "uid": "5b2f7a1e-0c3d-4e8f-9a6b-1d2c3e4f5a6b",
        "resourceVersion": "184467",
        "managedFields": [{"manager": "kubectl", "operation": "Apply"}],
        **extra,
    }
    if namespace:
        meta["namespace"] = namespace
    return meta


def _container(name: str, image: str, **extra) -> dict:
    return {
        "name": name,
        "image": image,
        "env": [
            {"name": "DATABASE_URL", "value": "postgres://cv:s3cr3t-db-password@10.96.143.200"}
        ],
        "volumeMounts": [{"name": "tls", "mountPath": "/var/lib/kubelet/pods/0b1c2d3e/volumes"}],
        "ports": [{"containerPort": 8080}],
        **extra,
    }


def _pod_spec(*containers: dict, node: str) -> dict:
    return {
        "nodeName": node,
        "containers": list(containers),
        "volumes": [{"name": "tls", "secret": {"secretName": "cv-tls-cert"}}],
    }


def _pod(name: str, namespace: str, owner: tuple[str, str], spec: dict, ip: str, host_ip: str):
    kind, owner_name = owner
    return {
        "metadata": _meta(
            name,
            namespace,
            labels={"app": owner_name},
            ownerReferences=[{"kind": kind, "name": owner_name, "controller": True}],
        ),
        "spec": spec,
        "status": {
            "phase": "Running",
            "podIP": ip,
            "podIPs": [{"ip": ip}],
            "hostIP": host_ip,
            "hostIPs": [{"ip": host_ip}],
            "conditions": [{"type": "Ready", "status": "True"}],
            "containerStatuses": [
                {"name": spec["containers"][0]["name"], "ready": True, "restartCount": 0}
            ],
        },
    }


def _node(name: str, ip: str, control_plane: bool) -> dict:
    labels = {"kubernetes.io/hostname": name}
    if control_plane:
        labels["node-role.kubernetes.io/control-plane"] = ""
    return {
        "metadata": _meta(name, labels=labels),
        "status": {
            "addresses": [
                {"type": "InternalIP", "address": ip},
                {"type": "Hostname", "address": name},
            ],
            "conditions": [{"type": "Ready", "status": "True"}],
            "nodeInfo": {"kubeletVersion": "v1.35.0", "osImage": "Debian GNU/Linux 13"},
        },
    }


def _deployment(name: str, namespace: str, template: dict, annotations: dict | None = None):
    return {
        "metadata": _meta(name, namespace, annotations=annotations or {}),
        "spec": {"replicas": 1, "template": {"spec": template}},
        "status": {"replicas": 1, "readyReplicas": 1, "availableReplicas": 1},
    }


def poisoned_cluster() -> dict[str, list[dict]]:
    """Cache contents by resource, as the informers will hold them (raw API JSON)."""
    cv_image = f"ghcr.io/fabiancienc/cv:{SHA}"
    cv_pod_spec = _pod_spec(_container("cv", cv_image), node="k8s-w-01")
    coredns_spec = _pod_spec(
        _container(
            "coredns",
            "registry.k8s.io/coredns/coredns:v1.12.0",
            args=["-conf", "/etc/coredns/Corefile"],
        ),
        node="k8s-cp-01",
    )
    calico_spec = _pod_spec(
        _container("calico-node", "quay.io/calico/node:v3.29.1"), node="k8s-w-02"
    )
    apiserver_spec = _pod_spec(
        _container(
            "kube-apiserver",
            "registry.k8s.io/kube-apiserver:v1.35.0",
            command=["kube-apiserver", "--advertise-address=192.168.0.41"],
        ),
        node="k8s-cp-01",
    )

    return {
        "nodes": [
            _node("k8s-cp-01", "192.168.0.41", control_plane=True),
            _node("k8s-w-01", "192.168.0.42", control_plane=False),
            _node("k8s-w-02", "192.168.0.43", control_plane=False),
        ],
        "namespaces": [
            {
                "metadata": _meta(
                    "cv",
                    labels={"fabiancienfuegos.com/astrolabio": "visible"},
                    annotations={
                        "fabiancienfuegos.com/proyecto": "CV",
                        "fabiancienfuegos.com/descripcion": "Mi CV web en React",
                        "fabiancienfuegos.com/repo": "https://github.com/FabianCienC/CV",
                        "fabiancienfuegos.com/notas": "DATABASE_URL en homelab-gitops",
                    },
                )
            },
            # No visible label: nothing in it may be published.
            {"metadata": _meta("lab-privado")},
            {"metadata": _meta("kube-system")},
            {"metadata": _meta("calico-system")},
            {"metadata": _meta("argocd")},
        ],
        "deployments": [
            _deployment(
                "cv",
                "cv",
                cv_pod_spec,
                annotations={
                    "fabiancienfuegos.com/descripcion": "Frontend estático con nginx",
                    "fabiancienfuegos.com/rol": "frontend",
                    "fabiancienfuegos.com/criticidad": "urgentisima",
                    "kubectl.kubernetes.io/last-applied-configuration": (
                        '{"env":[{"name":"DATABASE_URL","value":"s3cr3t-db-password"}]}'
                    ),
                },
            ),
            _deployment("proyecto-secreto", "lab-privado", cv_pod_spec),
            _deployment("coredns", "kube-system", coredns_spec),
            # Not in the catalog: dropped.
            _deployment("debug-shell", "kube-system", coredns_spec),
        ],
        "replicasets": [
            {
                "metadata": _meta(
                    "cv-7d9f8b6c5",
                    "cv",
                    ownerReferences=[{"kind": "Deployment", "name": "cv", "controller": True}],
                ),
                "spec": {"replicas": 1, "template": {"spec": cv_pod_spec}},
                "status": {"replicas": 1, "readyReplicas": 1},
            },
            {
                "metadata": _meta(
                    "coredns-668d6bf9bc",
                    "kube-system",
                    ownerReferences=[{"kind": "Deployment", "name": "coredns", "controller": True}],
                ),
                "spec": {"replicas": 1, "template": {"spec": coredns_spec}},
                "status": {"replicas": 1, "readyReplicas": 1},
            },
        ],
        "statefulsets": [],
        "daemonsets": [
            {
                "metadata": _meta("calico-node", "calico-system"),
                "spec": {"template": {"spec": calico_spec}},
                "status": {"desiredNumberScheduled": 1, "numberReady": 1},
            }
        ],
        "pods": [
            _pod(
                "cv-7d9f8b6c5-abcde",
                "cv",
                ("ReplicaSet", "cv-7d9f8b6c5"),
                cv_pod_spec,
                "10.244.1.23",
                "192.168.0.42",
            ),
            _pod(
                "coredns-668d6bf9bc-x7k2p",
                "kube-system",
                ("ReplicaSet", "coredns-668d6bf9bc"),
                coredns_spec,
                "10.244.2.7",
                "192.168.0.41",
            ),
            _pod(
                "calico-node-4hq9z",
                "calico-system",
                ("DaemonSet", "calico-node"),
                calico_spec,
                "192.168.0.43",
                "192.168.0.43",
            ),
            # Static pod: owned by the node, named after its hostname.
            _pod(
                "kube-apiserver-k8s-cp-01",
                "kube-system",
                ("Node", "k8s-cp-01"),
                apiserver_spec,
                "192.168.0.41",
                "192.168.0.41",
            ),
        ],
        "services": [
            {
                "metadata": _meta("cv", "cv"),
                "spec": {
                    "selector": {"app": "cv"},
                    "clusterIP": "10.96.143.200",
                    "clusterIPs": ["10.96.143.200"],
                    "ports": [{"port": 80, "targetPort": 8080}],
                },
            },
            {
                "metadata": _meta("kube-dns", "kube-system"),
                "spec": {
                    "selector": {"app": "coredns"},
                    "clusterIP": "10.96.0.10",
                    "ports": [{"port": 53, "protocol": "UDP"}],
                },
            },
        ],
        "httproutes": [
            {
                "metadata": _meta("cv", "cv"),
                "spec": {
                    "hostnames": ["cv.fabiancienfuegos.com", "cv-admin.internal.lan"],
                    "rules": [{"backendRefs": [{"name": "cv", "port": 80}]}],
                },
                "status": {"parents": [{"conditions": [{"type": "Accepted", "status": "True"}]}]},
            }
        ],
        "applications": [
            {
                "metadata": _meta("cv", "argocd"),
                "spec": {
                    "source": {
                        "repoURL": "git@github.com:FabianCienC/homelab-gitops.git",
                        "path": "workloads/cv",
                    },
                    "destination": {"namespace": "cv"},
                },
                "status": {
                    "sync": {"status": "Synced", "revision": GITOPS_SHA},
                    "health": {"status": "Healthy"},
                    "operationState": {
                        "message": "successfully synced (homelab-gitops@" + GITOPS_SHA + ")"
                    },
                },
            }
        ],
        "events": [
            {
                "metadata": _meta("cv-7d9f8b6c5-abcde.17f2", "cv"),
                "involvedObject": {"kind": "Pod", "name": "cv-7d9f8b6c5-abcde"},
                "reason": "FailedMount",
                "type": "Warning",
                "message": (
                    "MountVolume.SetUp failed for volume tls: "
                    "/var/lib/kubelet/pods/0b1c2d3e/volumes not found"
                ),
            }
        ],
    }
