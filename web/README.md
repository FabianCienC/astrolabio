# astrolabio-web

The galaxy: React for the UI around the scene, plain Three.js for the scene itself.

## Commands

```
npm ci                    # install exact versions from package-lock.json
npm run dev               # http://localhost:5173 (dev panel top right; ?quality=high|low|minimal forces a level; ?view=list opens the list)
npm run typecheck
npm run build             # typecheck + production bundle in dist/
npm run gen:contract      # regenerate src/contract/galaxy.ts after the API contract changes
```

`/api` is proxied to `http://127.0.0.1:8000` in dev, so a local uvicorn works on the same origin; without it the page shows the contract example with a notice.

## Image

`Dockerfile`, built from the repo root (`docker build -f web/Dockerfile .`) because the types read `../contract`: `npm ci` (integrity hashes from `package-lock.json`) and `npm run build` on `node:24-alpine`, then `dist/` on `nginx-unprivileged`, both pinned by digest.

- `nginx/default.conf` serves the app: fingerprinted `/assets/` cached for good, `index.html` always revalidated so a deploy shows up on reload.
- `nginx/security-headers.conf` holds the CSP (`'self'` only, plus `wss://astrolabio.fabiancienfuegos.com` for phase 3) and the other security headers. It is included in every `location`, because an `add_header` inside a location drops the inherited ones.



## How the code is organized

```
contract/galaxy.schema.json ──► src/contract/galaxy.ts (generated types)
contract/galaxy.example.json ─► src/contract/fixture.ts
                                        │
React: App ─┬► components/SceneCanvas ─► scene/GalaxyScene ─► layout ─► objects, relations, nebulae
            └► components/Legend              (bloom, controls)
                        ▲                              ▲
                        └──── scene/symbology ─────────┘  (one source for colors, sizes, labels)
```

| Module | Responsibility |
| --- | --- |
| `src/App.tsx` | Page: the scene plus the UI overlay (title, legend, view toggle, skip link), and the list view instead of the scene when chosen (`?view=list`) or without WebGL. |
| `src/components/ListView.tsx` | Accessible list view: the same content as the scene as nested lists (ownership = nesting), with kind and health as text; picking an item selects it like a click in the scene. |
| `src/components/Legend.tsx` | Bottom-left legend. Rendered from `scene/symbology.ts`, so it always matches the scene. Starts closed (open, it covers the projects the rotation brings to that corner) and remembers the visitor's choice in `localStorage`. |
| `src/components/Sidebar.tsx` | Always-visible right panel: cluster overview, or the selected object. |
| `src/components/ObjectDetails.tsx` | Detail of each kind of object (health lives here, as text), with links to related objects. |
| `src/components/KindSymbol.tsx` | CSS copy of a scene shape, shared by legend and sidebar. |
| `src/components/HoverCard.tsx` | Tiny preview by the pointer while hovering an object: shape, name, kind, health. |
| `src/model/galaxyIndex.ts` | id → object, its owner and project, and reverse relations (who selects this pod, which routes reach this service). |
| `src/model/ids.ts`, `src/model/health.ts` | Ids for namespaces, components and nodes; health labels. |
| `src/components/SceneCanvas.tsx` | Mounts `GalaxyScene` on a `<canvas>` and owns its lifecycle; reports `onUnavailable` when there is no WebGL. React never touches Three.js objects. |
| `src/contract/galaxy.ts` | Types generated from the API's JSON Schema. **Do not edit.** |
| `src/contract/fixture.ts` | The example galaxy, typed. Dev only: used when there is no local API (and the page says so); never in the production bundle. |
| `src/model/useGalaxy.ts` | Loads `GET /api/galaxy` (same origin), retrying while the API answers 503 (informers syncing). Production never falls back to the example. |
| `src/scene/GalaxyScene.ts` | The scene's public API (`load`, `select`, `dispose`, `onSelect`): renderer, picking, highlights, bloom, render loop. |
| `src/scene/cameraRig.ts` | All camera movement, always smooth: gliding wheel zoom toward the cursor, eased flights (to an object and back home), damped orbit, pan on the galaxy plane with a limit. |
| `src/scene/halo.ts` | Ring halo around the selected object: grows in, follows the selection, breathes slowly, fades out. |
| `src/scene/labels.ts` | Floating names of projects and platform systems (CSS2DRenderer over the canvas). |
| `src/scene/layout.ts` | Pure: galaxy → positioned objects + relations. Position encodes ownership (pods around their replica set, by their workload, around the namespace ring). Deterministic. |
| `src/scene/objects.ts` | Every k8s object as one `Points`: flat shapes by kind, color by kind; selected brightens, hovered grows, the rest dims while something is selected. |
| `src/scene/relations.ts` | Lines for real relations only: Service → pods it selects, route → services. |
| `src/scene/nebulae.ts` | Soft fbm nebula behind each group, camera-facing, from the cool nebula palette. |
| `src/scene/symbology.ts` | What every visual means: object kinds (shape, size, color, label), relation line and nebula styles, background. **Add new symbols here.** |
| `src/scene/quality.ts` | Quality levels (high, low, minimal: pixel ratio and bloom strength; bloom never turns off). Picked on load, then `QualityGovernor` steps down while fps stays under the level's minimum (never back up). `?quality=` forces a level. |
| `src/scene/random.ts` | Seeded PRNG and string hash for deterministic layout. |
| `src/scene/debug.ts` | Dev-only tuning panel (lil-gui); never shipped in the build. |

User-facing text is Spanish; code is English.
