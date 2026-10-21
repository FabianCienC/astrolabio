"""Assembly layer: turns the informers' raw objects into a public `Galaxy`.

- `galaxy.py`: `assemble_galaxy(snapshot)`, the only entry point. Pure: cache in, `Galaxy` out.
- `core.py`: the core: catalog components (anonymous pods and services) and the node suns.
- `catalog.py`: the closed catalog of platform components and their backing workloads.
- `projects.py`: visible namespaces as constellations (workloads, replica sets, pods,
  services, routes, Argo CD status).
- `nodes.py`: hostnames to generic node ids (`control-plane`, `worker-1`, `worker-2`).
- `annotations.py`: our Spanish `fabiancienfuegos.com/*` annotations to contract values.
- `health.py`: health rules.
- `raw.py`: safe readers for raw API JSON.

This is the only place that reads raw Kubernetes objects and builds contract
models, and it reads only allowlisted fields.
"""

from .galaxy import assemble_galaxy

__all__ = ["assemble_galaxy"]
