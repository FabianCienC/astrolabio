# Plan de trabajo de Astrolabio

Programa de etapas para construir Astrolabio. El alcance, las decisiones y los criterios de "listo" viven en [`astrolabio.md`](astrolabio.md); este archivo ordena el trabajo.

**Sin fechas estrictas.** La meta de fondo sigue siendo tener las fases 1 a 3 publicadas a fin de 2026, pero el plan marca **orden y dependencias**, no un calendario. Cada etapa termina con algo publicado y verificable.

## Idea central: contrato primero

Lo primero de la etapa 1 es fijar el **esquema de `GET /api/galaxia`** (modelos Pydantic) y exportarlo a `contrato/` en la raíz del repo: `galaxia.schema.json` (JSON Schema, del que el frontend genera sus tipos) y `galaxia.ejemplo.json` (fixture). Con eso el frontend 3D avanza contra datos falsos sin esperar a que la API esté desplegada, y las etapas 1 y 2 pueden traslaparse.

```
E0 ──► E1.1 contrato ──┬──► resto de E1 (API) ──┐
                       └──► E2 (galaxia 3D) ────┴──► E3 (en vivo) ──► E4 ──► E5
```

## Decisión de frontend: React + TypeScript, Three.js directo

- **React** para la interfaz alrededor de la escena: ficha de la estrella, vista de lista accesible y controles. Funciona con Vite sin configuración extra y tiene el ecosistema más grande alrededor de Three.js.
- **La escena es un módulo TypeScript con Three.js puro** (`web/src/escena/`), sin React Three Fiber. React lo monta en un `<canvas>` y se comunica con él por una API pequeña: `cargar(galaxia)`, `aplicarDelta(delta)`, `enfocar(id)` y eventos de selección.
- **Por qué sin R3F:** casi todo es shader propio, `Points` e `InstancedMesh`, y los deltas del WebSocket (fase 3) deben escribir directo en los buffers sin pasar por la reconciliación de React. Además, la técnica del diseño (`EffectComposer` + `UnrealBloomPass`) se usa tal cual. Si más adelante R3F conviene para algo, se puede adoptar sin rehacer la UI.

## E0 · Preparar el terreno (fase 0)

- [x] Rama principal `main` y remoto `FabianCienC/astrolabio` (público).
- [x] Deploy key `astrolabio-ci` (escritura) en `homelab-gitops`; su privada como secreto `GITOPS_DEPLOY_KEY`.
- [x] `homelab-gitops`: `platform/namespaces/astrolabio.yaml` (PSA `restricted`, `gateway-access: public`, etiqueta visible).
- [x] `homelab-gitops`: `platform/rbac/astrolabio-reader.yaml` + `apps/rbac.yaml`.
- [x] `homelab-gitops`: namespace `astrolabio` y kind `ServiceAccount` en el `AppProject portfolio`; `apps/astrolabio.yaml`.
- [x] Anotaciones `fabiancienfuegos.com/*` en los namespaces y deployments de `hola` y `cv`.
- [x] Decidir cuánta infraestructura se muestra y si aparecen los nodos: **componentes con detalle desde un catálogo cerrado en la API, sin versiones; nodos como tres soles en el núcleo, sin órbitas** (ver Seguridad en `astrolabio.md`).

**Listo cuando:** los tres `k auth can-i` dan lo esperado y Argo CD muestra `astrolabio` en `Synced`.

## E1 · Contrato + API (fase 1)

1. [x] **Contrato:** esqueleto de `api/` con **uv** (`uv init`, Python 3.13, `uv.lock`) (FastAPI, `/docs` y `/openapi.json` apagados en producción) con los modelos `Galaxia`, `Constelacion`, `Estrella` y `Nucleo`. Exportar esquema y ejemplo a `contrato/` con `uv run exportar-contrato`; un test falla si quedan desactualizados. *Desbloquea E2.*
2. [ ] **Tests de sanitización primero:** fallan si la respuesta contiene `env`, `volumes`, IPs de pods o nodos, el `repoURL` de `homelab-gitops` o mensajes de Events con rutas internas.
3. [ ] **Informer genérico** list + watch con caché en memoria y re-list ante `410 Gone`, con su test.
4. [ ] Un informer por recurso: Namespaces, Deployments, StatefulSets, Pods, Services, Events, `HTTPRoute`, `Application` (`argocd`).
5. [ ] Ensamblado de la galaxia: anotaciones, commit desde el tag de imagen, sync/salud/revisión de Argo y allowlist por etiqueta.
6. [ ] **Catálogo de infraestructura** (`api/.../catalogo.py`): componente → nombre, función y workload que lo respalda (CoreDNS, kube-proxy, API server, etcd, Calico, Traefik, Argo CD, cloudflared, Sealed Secrets…). Núcleo con sus componentes y los tres nodos (control plane, worker 1, worker 2). Test: nada fuera del catálogo aparece, y ningún componente de plataforma lleva versión ni tag.
7. [ ] Prueba local: `uvicorn` contra el clúster con kubeconfig por túnel SSH.
8. [ ] Imagen: `python:3.13-slim`, UID 10001, dependencias con hash vía `uv sync --locked` (o `uv export --hashes`) en una etapa de build.
9. [ ] CI (`.github/workflows/ci.yaml`): job por carpeta con `paths`, Trivy, push a ghcr y bump con `yq` en `homelab-gitops`. `dependabot.yml`.
10. [ ] Manifiestos en `homelab-gitops/workloads/astrolabio/`: deployment, SA, service, `HTTPRoute` y NetworkPolicy de salida a `192.168.0.41:6443` + DNS.

**Listo cuando:** `curl https://astrolabio.fabiancienfuegos.com/api/galaxia` devuelve `hola`, `cv` y el núcleo, sin campos prohibidos.

## E2 · La galaxia en 3D (fase 2)

Puede empezar en cuanto exista el contrato (E1.1).

1. [ ] Esqueleto de `web/`: Vite + React + TypeScript + Three.js, con la escena montada en un componente y cargando el fixture.
2. [ ] **Spike visual (punto de decisión):** fondo de partículas en capas con paralaje + una estrella con shader propio y `UnrealBloomPass`. Se itera hasta que **se sienta como mirar el espacio** antes de seguir.
3. [ ] Estrellas: `Points` con shader, brillo que respira, color y animación según la salud (ok / degradado / caído).
4. [ ] Constelaciones: líneas finas con material aditivo y una nebulosa con fbm por proyecto.
5. [ ] Núcleo de infraestructura: disco de partículas con rotación lenta, componentes como estrellas con ficha y los tres nodos como soles.
6. [ ] Interacción: `OrbitControls`, `Raycaster`, vuelo de cámara y ficha en React (qué es, rol, repo, commit con enlace y estado de Argo).
7. [ ] Accesibilidad: vista de lista con el mismo contenido y `prefers-reduced-motion` (sin pulsos ni rotación).
8. [ ] Rendimiento: medir fps; en dispositivos lentos, bajar automáticamente las partículas y el bloom. Probar en celular real.
9. [ ] Conectar a `/api/galaxia` real. Imagen con `nginx-unprivileged`, headers y CSP (`connect-src 'self' wss://astrolabio.fabiancienfuegos.com`), deployment ×2 sin token de SA y *default deny*.

**Listo cuando:** se ve fluida en el celular y `k -n hola scale deploy hola --replicas=0` (y de regreso) se refleja al recargar.

## E3 · En vivo (fase 3)

- [ ] Probar temprano que el WebSocket pasa por Gateway + Traefik + Cloudflare Tunnel.
- [ ] `/ws`: la API empuja los deltas de los watchers (sanitizados con los mismos modelos).
- [ ] Cliente: snapshot inicial + deltas aplicados directo a la escena; reconexión con nuevo snapshot.
- [ ] `metrics-server` por Helm; CPU por pod → brillo de la estrella.

**Listo cuando:** un push a `hola` cambia su estrella en vivo, sin recargar, mientras Argo CD despliega.

## Endurecimiento (antes de difundir la URL)

- [ ] Cloudflare: *rate limiting* en `/api` y `/ws`, WAF administrado.
- [ ] Revisión de seguridad completa contra las invariantes de `CLAUDE.md`.
- [ ] README del repo y nota de portafolio.

## E4 · Líneas de tráfico (fase 4)

- [ ] Prometheus mínimo por Helm (solo el servidor, retención de 3 días).
- [ ] Scrape de las métricas de Traefik (`:9100`); peticiones por `HTTPRoute`.
- [ ] Líneas Traefik → servicio con pulsos en `CatmullRomCurve3` según rps; conexiones permitidas por NetworkPolicy como líneas tenues.

**Listo cuando:** abrir el CV varias veces ilumina su línea.

## E5 · Anomalías + LLM (fase 5)

- [ ] `anomalias/`: z-score móvil (luego STL) sobre CPU, memoria y peticiones desde Prometheus; aviso a la API por HTTP.
- [ ] Usuario IAM exclusivo (`bedrock:InvokeModel` sobre un modelo), alerta de presupuesto y credenciales como `SealedSecret`.
- [ ] Resumen con Bedrock solo con Events y estado, nunca logs crudos.
- [ ] Estrella que parpadea + explicación en la ficha.

**Listo cuando:** un pod que consume CPU a propósito en un namespace de pruebas hace parpadear su estrella y aparece la explicación.

## Futuro (después del CKA)

- Migración de Calico a Cilium + Hubble para tener flujos reales entre pods, documentada como ejercicio.
- Historial o *replay* con TimescaleDB, si hace falta.
