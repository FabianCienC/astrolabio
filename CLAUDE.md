# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This directory holds the design doc, `astrolabio.md` (in Spanish), which is the source of truth for scope, decisions and phases, and `PLAN.md`, the staged work plan (order and dependencies, no fixed dates). Read both before making changes. `api/` holds the API (contract done, informers next; see `api/README.md` for the module map); `web/` holds the 3D galaxy (visual spike stage); `anomalias/` doesn't exist yet.

## Commands

API (run from `api/`):

```
uv sync
uv run pytest                       # all tests; one: uv run pytest tests/contract/test_models.py::test_example_is_valid_and_ids_are_unique
uv run ruff check . && uv run ruff format --check .
uv run export-contract              # regenerate ../contract/ after changing contract/models.py or contract/example.py
ASTROLABIO_ENV=development uv run uvicorn astrolabio_api.main:app --reload                           # live cluster (kubeconfig)
ASTROLABIO_ENV=development ASTROLABIO_SOURCE=example uv run uvicorn astrolabio_api.main:app --reload  # example galaxy, no cluster
```

Web (run from `web/`; see `web/README.md` for the module map):

```
npm ci
npm run dev                         # http://localhost:5173, dev tuning panel; ?quality=low forces low quality
npm run typecheck
npm run build
npm run gen:contract                # regenerate src/contract/galaxy.ts after re-exporting the contract
```

The public contract of `GET /api/galaxy` is `api/src/astrolabio_api/contract/models.py` (Pydantic, `extra="forbid"`). `contract/galaxy.schema.json` and `contract/galaxy.example.json` are generated from it and committed (`contract/example.py` is a hand-made, sanitized snapshot of the real cluster taken 2026-10-21, not invented data; keep it faithful when the cluster changes); the web generates its TS types from the schema. Change the models first, then `uv run export-contract`, then `npm run gen:contract`.

## Language and workflow

- **All code is in English**: identifiers, comments, docstrings, JSON fields, API paths, CLI names, tests. The design docs (`astrolabio.md`, `PLAN.md`) stay in Spanish. Glossary from the docs to code: *galaxia* = galaxy (the cluster), *constelación* = constellation (a namespace), *estrella* = a workload (`Workload` in code; since every k8s object is drawn, scene code says "object", not "star"), *núcleo* = core (platform components + nodes), *ficha* = detail card. The `anomalias/` folder and image name `astrolabio-anomalias` are existing names and stay as is.
- **The site is in Spanish.** User-facing text (descriptions, infra catalog purposes, UI copy) is Spanish content; only code is English.
- **Annotations stay in Spanish** in `homelab-gitops` (keys `fabiancienfuegos.com/descripcion|rol|criticidad|proyecto|repo`, values like `alta|media|baja`, `datos`). `assembly/` maps them to the English contract values (`high|medium|low`, `data`); an unknown value becomes `None`, never passes through raw.
- **Never commit or push.** Make the changes, stop at a sensible checkpoint and summarize what changed and why; the user reviews and approves each commit. This also applies to `homelab-gitops`.

## What Astrolabio is

A public web app (`https://astrolabio.fabiancienfuegos.com`) that reads a homelab Kubernetes cluster live and renders it as a 3D galaxy. The cluster is kubeadm v1.35 with 3 nodes, Calico, Argo CD, Gateway API + Traefik and a Cloudflare Tunnel. Deployment follows the same GitOps pattern as the existing `hola` and `cv` apps.

## Planned layout (monorepo `FabianCienC/astrolabio`)

- `web/`: `astrolabio-web`. Vite + **Three.js (WebGL), mandatory**. No SVG or 2D canvas for the main scene. **React + TypeScript** for the UI; the scene is a plain Three.js TS module (`web/src/scene/`, no React Three Fiber) mounted by a component. It is served by `nginx-unprivileged`.
- `api/`: `astrolabio-api`. Python 3.13, FastAPI + `kubernetes_asyncio`, served by `uvicorn`. Tooling is **uv** (`pyproject.toml` + `uv.lock`; the lock's hashes satisfy "pinned by hash"). There is no system Python on the dev machine, so use `uv run` / `uv sync`, never bare `python` or `pip`. Everything runs on one asyncio event loop with no threads.
- `anomalias/`: `astrolabio-anomalias` (phase 5). Python. It reads Prometheus, runs a z-score/STL check and notifies the API over HTTP. It also produces a Bedrock LLM summary built only from Events and state, never raw logs.
- `.github/workflows/ci.yaml`: builds only the image whose folder changed (per-job `paths` filters), scans it with Trivy and pushes it to `ghcr.io/fabiancienc/astrolabio-*`. It then bumps the tag in the separate `homelab-gitops` repo with `yq` (`select(.name == "astrolabio-api")).newTag = strenv(GITHUB_SHA)`) using the `GITOPS_DEPLOY_KEY` secret.

Kubernetes manifests do **not** live here. They go in `homelab-gitops` under `workloads/astrolabio/`, `platform/namespaces/` and `platform/rbac/`.

## API architecture (the part that spans many files)

- **Informer pattern:** for each resource the API does one `list`, caches the result in memory, then keeps a `watch` open from that resourceVersion. On **`410 Gone`** it re-lists and resumes. Watched resources (`kube/cluster.py`): Nodes, Namespaces, Deployments, ReplicaSets, StatefulSets, DaemonSets, Pods, Services, Events, `HTTPRoute`, and Argo CD `Application` (in `argocd`).
- **No DB, no Redis.** All state is the in-memory cache, and there is a single API replica.
- **Endpoints:** `GET /api/galaxy` returns a full sanitized snapshot. `/ws` is a WebSocket that pushes watcher deltas (phase 3).
- **Metadata sources:** custom annotations on the Namespace (`fabiancienfuegos.com/proyecto|descripcion|repo`) and on Deployments (`fabiancienfuegos.com/descripcion|rol|criticidad`). A namespace is drawn in detail only if it has the label `fabiancienfuegos.com/astrolabio: visible`. The commit comes from the image tag, which is the git SHA. Sync and health come from `Application.status` (not `revision`: it is a commit of the private GitOps repo). Don't add annotations for data that can be derived.
- **Platform namespaces** (`kube-system`, `argocd`, `traefik`, `cloudflared`, `calico-system`, `tigera-operator`, plus the `kubernetes` Service in `default`) form the "infrastructure" galactic core and **do** show their components, as a showcase of the infra. Only components in a closed **catalog inside the API** are published (name, purpose, `system`, backing workload), **one component per platform workload** (argocd-server, calico-typha, coredns...; static control-plane pods included), grouped by `system` (Kubernetes, Calico, Argo CD, Traefik, Cloudflare, Sealed Secrets); anything not in the catalog is dropped. Publish name, purpose, health, ready/desired replicas, Argo sync/health and (phase 3) CPU/RAM. Their pods and services are drawn but **anonymous** (`name: None`, ids like `core/coredns/pod-1`; a validator enforces it). Never publish platform pod/service names, IPs, ports, **versions or image tags**, args or config.
- **Every Kubernetes object is its own drawn object** (contract v2): namespace, workload, *active* ReplicaSets (the ones with pods; two during a rollout), pods, Services and HTTPRoutes. Ownership nests in the contract (constellation > workload > replica set > pod); non-ownership relations are id lists (`Service.targets` = pod ids, `Route.services` = service ids) and validators check they point inside the same constellation.
- **Nodes** are three "suns" in the core, published only as "control plane", "worker 1", "worker 2" (no hostname or IP), with health, pod count and CPU/RAM. Pods reference them by that generic id.

## Security invariants (the site is public)

- **Never forward raw k8s objects.** Convert them to Pydantic models with an allowlist of fields: name, namespace, replicas, status, `fabiancienfuegos.com/*` annotations and image tag. Pod names are published **only for visible projects** (with phase, ready, restarts, generic node); route hostnames only if they are under `fabiancienfuegos.com`. Never expose `env`, `volumes`, pod/node IPs, the private `homelab-gitops` `repoURL`, or Event messages that contain internal paths.
- The app is read-only end to end, so there are no `POST`, `PUT` or `DELETE` endpoints. FastAPI `/docs` and `/openapi.json` are disabled in production.
- Web and API share one origin (`/` → web, `/api` and `/ws` → api), so there is no CORS. The CSP needs `connect-src 'self' wss://astrolabio.fabiancienfuegos.com`.
- RBAC (`astrolabio-reader`) lists every resource explicitly. Never use `*`, because it would grant secrets and configmaps. There is no `pods/log`. Only `astrolabio-api` mounts a SA token. Every other pod sets `automountServiceAccountToken: false`.
- API egress NetworkPolicy targets the real control-plane IP **`192.168.0.41:6443`**, not `10.96.0.1:443`, because of Calico post-DNAT. It also allows DNS to kube-dns.
- Images run as non-root (API: UID 10001, PSA `restricted`), with dependencies pinned by hash.

## Frontend rendering rules

- **Clean look:** plain black background (no starfield), every object is a uniform flat shape with a tight bloom (no spikes, no halos). **Color, shape and size identify the kind** (disc: node/workload/component/pod, ring: namespace/replica set, diamond: Service, triangle: HTTPRoute; each kind has its own color). **Health is never drawn in the scene**: it lives in the right sidebar as text badges. Ownership is shown by position (pods circle their replica set, which sits by its workload, around the namespace ring); services and routes sit on the side facing the core. No grouping lines: lines only ever mean a real relation (Service → Pod, route → Service) or traffic. The core groups platform components by `system`: each system is its own cluster on the core ring (sector sized by member count, gaps between systems) with its own nebula (group `core/<system>`), around the three nodes. Projects and systems carry a small floating name (`scene/labels.ts`, CSS2DRenderer, no pointer events, fades with the selection). Camera looks down at the disc and can't go edge-on (`maxPolarAngle`).
- **Selection:** click an object (screen-space picking with the same size formula as the shader) or pick it in the always-visible right sidebar; the camera flies to it and the sidebar shows what it is, its health and links to related objects. The selected object brightens and gets a ring halo in its kind color (`scene/halo.ts`, breathes slowly, glides between selections) while every other object, relation line and nebula fades to the background (`ObjectPoints.focus`); objects rest slightly dim so the selection stands out. Hovering an object shows a tiny card by the pointer (`components/HoverCard.tsx`: shape, name, kind, health; the scene only reports hover changes). With no selection the sidebar shows a cluster overview; deselecting flies back home and resumes auto-rotation.
- **Camera motion is always smooth** and lives in `scene/cameraRig.ts`: wheel zoom glides to a goal distance (exponential smoothing) toward the point under the cursor, replacing OrbitControls' instant zoom; flights use eased arcs (direction and distance blended separately, duration by travel); pan (right/shift drag) slides on the galaxy plane within a limit; highlights fade in/out in the shader. Don't add camera moves that jump. `model/galaxyIndex.ts` resolves ids to objects and reverse relations.
- **Nebulae and legend:** a cool-toned nebula (indigo to violet) behind each project and the core helps find it. Every visual symbol is defined in `web/src/scene/symbology.ts` and shown in the bottom-left legend (`components/Legend.tsx`); add new symbols there so scene and legend stay in sync.
- Use `Points`/`InstancedMesh` for anything repeated. Stars use custom shaders + `UnrealBloomPass`. Nebulae use fbm noise shaders. Lines use additive materials. Traffic pulses travel along `CatmullRomCurve3`. Interaction uses `OrbitControls` + camera fly-to + screen-space picking.
- Targets are 60 fps on a laptop and 30+ fps on a phone. Lower the particle count and bloom on slow devices.
- `prefers-reduced-motion` only removes continuous motion the user didn't trigger (auto-rotation, pulses). **Transitions are never instant**, not even then: flights, highlights and sidebar fades stay animated, just shorter. The user's own Windows has animations off, so test with reduced motion emulated too. Provide an accessible list view with the same content.
- The core requirement is that the scene feels like looking at space, not a box diagram with effects, while staying clean. The user signs off on the look before any web commit.

## Phases

0 repo/RBAC/namespace setup → 1 watchers + `GET /api/galaxy` → 2 3D galaxy → 3 WebSocket + metrics-server (CPU → brightness) → 4 Prometheus + Traefik traffic lines → 5 anomalies + Bedrock. Each phase has a concrete "listo cuando" (done-when) check in `astrolabio.md`.

For local API development, run `uvicorn` against the cluster with a kubeconfig over an SSH tunnel. Use `k auth can-i ... --as=system:serviceaccount:astrolabio:astrolabio-api` to verify RBAC.
