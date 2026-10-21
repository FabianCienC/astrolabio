# Plan de trabajo de Astrolabio

Programa de etapas para construir Astrolabio. El alcance, las decisiones y los criterios de "listo" viven en [`astrolabio.md`](astrolabio.md); este archivo ordena el trabajo.

**Sin fechas estrictas.** La meta de fondo sigue siendo tener las fases 1 a 3 publicadas a fin de 2026, pero el plan marca **orden y dependencias**, no un calendario. Cada etapa termina con algo publicado y verificable.

## Idea central: contrato primero

Lo primero de la etapa 1 es fijar el **esquema de `GET /api/galaxy`** (modelos Pydantic) y exportarlo a `contract/` en la raíz del repo: `galaxy.schema.json` (JSON Schema, del que el frontend genera sus tipos) y `galaxy.example.json` (fixture). Con eso el frontend 3D avanza contra datos falsos sin esperar a que la API esté desplegada, y las etapas 1 y 2 pueden traslaparse.

```
E0 ──► E1.1 contrato ──┬──► resto de E1 (API) ──┐
                       └──► E2 (galaxia 3D) ────┴──► E3 (en vivo) ──► E4 ──► E5
```

## Decisión de frontend: React + TypeScript, Three.js directo

- **React** para la interfaz alrededor de la escena: ficha de la estrella, vista de lista accesible y controles. Funciona con Vite sin configuración extra y tiene el ecosistema más grande alrededor de Three.js.
- **La escena es un módulo TypeScript con Three.js puro** (`web/src/scene/`), sin React Three Fiber. React lo monta en un `<canvas>` y se comunica con él por una API pequeña: `load(galaxy)`, `applyDelta(delta)`, `focus(id)` y eventos de selección.
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

1. [x] **Contrato:** esqueleto de `api/` con **uv** (`uv init`, Python 3.13, `uv.lock`) (FastAPI, `/docs` y `/openapi.json` apagados en producción) con los modelos `Galaxy`, `Constellation`, `Star` y `Core`, organizado por capas (ver `api/README.md`). Exportar esquema y ejemplo a `contract/` con `uv run export-contract`; un test falla si quedan desactualizados. *Desbloquea E2.*
2. [x] **Tests de sanitización primero:** fallan si la respuesta contiene `env`, `volumes`, IPs de pods o nodos, el `repoURL` de `homelab-gitops` o mensajes de Events con rutas internas. Un "clúster envenenado" (`tests/sanitization/`) con objetos crudos llenos de datos prohibidos; la prueba sobre `assembly/` queda en `xfail` estricto hasta E1.5–E1.6.
3. [x] **Informer genérico** (`kube/informer.py`) list + watch con caché en memoria y re-list ante `410 Gone`, con su test. Trabaja sobre un `Source` (list + watch); el adaptador de `kubernetes_asyncio` llega con E1.4.
4. [x] Un informer por recurso (`kube/cluster.py`): Nodes, Namespaces, Pods, Services, Events, Deployments, ReplicaSets, StatefulSets, DaemonSets, `HTTPRoute`, `Application` (`argocd`). Adaptador propio sobre `kubernetes_asyncio` que lee el JSON crudo (`kube/source.py`).
5. [x] Ensamblado de la galaxia (`assembly/`, función pura: caché → `Galaxy`): anotaciones, commit desde el tag de imagen, sync/salud de Argo (sin revisión: es del repo privado) y allowlist por etiqueta. Conectado a `GET /api/galaxy` (503 hasta que sincronizan los informers; `ASTROLABIO_SOURCE=example` sirve el ejemplo sin clúster).
6. [x] **Catálogo de infraestructura** (`assembly/catalog.py`): componente → nombre, función y workload que lo respalda (CoreDNS, kube-proxy, API server, etcd, Calico, Traefik, Argo CD, cloudflared, Sealed Secrets…). Núcleo con sus componentes y los tres nodos (control plane, worker 1, worker 2). Test: nada fuera del catálogo aparece, y ningún componente de plataforma lleva versión ni tag.
7. [x] Prueba local: `uvicorn` contra el clúster con la identidad real de `astrolabio-api` (token corto) por túnel SSH vía `pve` (pasos en `CLAUDE.md`). 2026-10-21: los 11 informers sincronizan sin 403, `find_leaks` limpio sobre la respuesta real, los 24 componentes del catálogo presentes y el resultado igual a `contract/example.py`; los watches reflejan el reemplazo de pods sin recargar.
8. [x] Imagen (`api/Dockerfile`): `python:3.13-slim` fijada por digest, UID 10001, puerto 8080, dependencias con hash vía `uv sync --locked --no-dev --no-install-project` en una etapa de build; el proyecto corre desde `/app/src` sin construir wheel (nada fuera del lock se descarga). Sin Docker local: se construye por primera vez en CI (E1.9).
9. [x] CI (`.github/workflows/ci.yaml`): un job `changes` detecta con `git diff` qué carpetas cambiaron (el `paths` de GitHub filtra workflows completos); `api`: ruff, pytest, build, Trivy y, solo en push a `main`, push a ghcr y bump con `yq` en `homelab-gitops` (falla si falta la entrada `astrolabio-api` en `images`); `web`: tipos del contrato al día y build (su imagen llega con E2.9). Los PRs solo revisan. `dependabot.yml`: actions, docker, uv y npm.
10. [x] Manifiestos en `homelab-gitops/workloads/astrolabio/`: ServiceAccount (sin montar token por defecto), deployment ×1 (UID 10001, raíz de solo lectura, readiness en `/api/galaxy`, 50m/96Mi → 256Mi), service, `HTTPRoute` (`/api` → api; `/` → web llega con E2.9), *default deny* en el namespace, entrada solo desde Traefik y salida a `192.168.0.41:6443` + DNS. La imagen empieza con el tag `pending-first-build` hasta el primer bump del CI.

**Listo cuando:** `curl https://astrolabio.fabiancienfuegos.com/api/galaxy` devuelve `hola`, `cv` y el núcleo, sin campos prohibidos. **Cumplido el 2026-10-21:** la API corre en el clúster (imagen `b00ac2b`) y la respuesta pública trae `hola`, `cv`, `astrolabio`, los 24 componentes y los 3 nodos, pasa el contrato y `find_leaks` no encuentra nada; `POST` responde 405.

## E2 · La galaxia en 3D (fase 2)

Puede empezar en cuanto exista el contrato (E1.1).

1. [x] Esqueleto de `web/`: Vite + React + TypeScript + Three.js, con la escena montada en un componente y cargando el fixture.
2. [x] **Spike visual (punto de decisión):** fondo negro, objetos como formas uniformes con bloom ceñido y leyenda abajo a la izquierda. Visto bueno del look el 2026-10-21.
3. [x] Objetos: cada objeto de Kubernetes con su nodo visible (namespace, workload, ReplicaSet activo, pod, Service, HTTPRoute), forma, tamaño y color por tipo (el estado vive en la barra lateral, no en la escena), propiedad por posición y líneas solo para relaciones reales. Contrato v2 en la API, con un ejemplo que es una foto real del clúster.
4. [x] Constelaciones: nebulosa con fbm por proyecto, en tonos fríos (sin líneas de agrupación), y nombre flotante de cada proyecto.
5. [x] Núcleo de infraestructura: los tres nodos al centro y un cúmulo por sistema de la plataforma (Kubernetes, Calico, Argo CD…) con su nebulosa y su nombre; cada workload de la plataforma con sus pods y Services, anónimos.
6. [x] Interacción: cámara siempre suave (`cameraRig.ts`: zoom que se desliza hacia el cursor, vuelos en arco, pan con límite, regreso a la vista inicial al deseleccionar), selección por clic o desde la barra lateral siempre visible, halo y atenuación del resto, mini tarjeta al pasar el cursor, ficha con estado, réplicas, commit, Argo CD y enlaces entre objetos relacionados.
7. [x] Accesibilidad: vista de lista con el mismo contenido (`ListView`: anidada por propiedad, tipo y salud como texto, selecciona igual que la escena), botón "Ver como lista", enlace para saltar a la lista con teclado, `?view=list` y caída automática a la lista sin WebGL. (`prefers-reduced-motion` ya está: sin rotación automática, transiciones siempre suaves.)
8. [x] Rendimiento: medir fps; en dispositivos lentos, bajar automáticamente la calidad. **Hecho:** tres niveles (alto, bajo, mínimo: pixel ratio e intensidad del bloom, que nunca se apaga) y `QualityGovernor`, que baja un nivel tras 3 s seguidos bajo el mínimo del nivel (40 y 28 fps), sin volver a subir; el bloom se desliza al nuevo valor. El usuario la vio bien en el sitio publicado; la prueba formal en celular se dio por buena.
9. [x] Conectar a `/api/galaxy` real (`useGalaxy`: reintenta mientras la API responde 503; en producción nunca cae al ejemplo). Imagen (`web/Dockerfile`, contexto la raíz del repo) con `nginx-unprivileged`, headers y CSP (`connect-src 'self' wss://astrolabio.fabiancienfuegos.com`), probada con el build de producción. Deployment ×2 sin token de SA, `/` → web en la `HTTPRoute` y entrada solo desde Traefik sobre el *default deny*. El CI construye, escanea, sube y hace el bump de las dos imágenes con `.github/scripts/bump-gitops.sh`.

**Listo cuando:** se ve fluida en el celular y `k -n hola scale deploy hola --replicas=0` (y de regreso) se refleja al recargar. (Argo CD tiene `selfHeal` en `hola`: hay que pausar la sincronización automática para la prueba, o revierte el escalado en segundos.) **2026-10-21:** desplegada en `https://astrolabio.fabiancienfuegos.com` leyendo el clúster real, con la CSP y los headers en producción; visto bueno del sitio publicado. **Falta:** la prueba de escalar `hola` a 0 y de regreso. La leyenda empieza cerrada, así que ya no tapa a CV (ni a ningún proyecto que la rotación lleve a esa esquina). **Cerrada el 2026-10-21 por decisión del usuario**, sin la prueba manual de escalar `hola` a 0: los watches ya mostraron en vivo el reemplazo de pods.

## E3 · En vivo (fase 3)

- [x] Probar temprano que el WebSocket pasa por Gateway + Traefik + Cloudflare Tunnel. 2026-10-21: `wss://astrolabio.fabiancienfuegos.com/ws` entrega la galaxia, sigue abierto pasados 120 s (los pings de uvicorn le ganan al corte de 100 s de Cloudflare) y rechaza otros orígenes con 403.
- [x] `/ws`: la API empuja la **galaxia completa** sanitizada (los mismos modelos que `GET /api/galaxy`) cada vez que cambia, agrupando los cambios en ventanas de 1 s y omitiendo los que no cambian nada (decidido el 2026-10-21: más simple y robusto que deltas por objeto, sin protocolo nuevo ni riesgo de desincronizarse; `live.py`, `routes/ws.py`). Solo el origen del sitio, máx. 200 clientes, mensajes entrantes descartados.
- [x] Cliente: galaxia inicial por `GET /api/galaxy` y luego `/ws`; la escena anima solo lo que cambió; reconexión con espera creciente (al reconectar llega la galaxia actual). transición sin saltos (`morph.ts`: objetos, líneas, nebulosas y nombres), indicador "conectado", panel de actividad abajo a la derecha (`model/activity.ts`, reglas fáciles de extender).
- [x] `metrics-server` por Helm; CPU por pod → brillo de la estrella. metrics-server corre en el clúster (app de Argo, chart 3.14.0, también en el catálogo del núcleo) y la API publica CPU y memoria. Cada objeto es una estrella que **se calienta** con la CPU (halo hacia ámbar, núcleo blanco cálido), crece, destella al subir y late (sin movimiento reducido); fondo azul marino, líneas verde azuladas y violetas, medidor de CPU y "Más activos" en la barra lateral. Estética de `inspiration/`, visto bueno el 2026-10-21.

**Listo cuando:** un push a `hola` cambia su estrella en vivo, sin recargar, mientras Argo CD despliega. **Cerrada el 2026-10-21 por decisión del usuario**, sin la prueba manual del push: el WebSocket se verificó de punta a punta en producción (galaxia completa, conexión estable más de 120 s, otros orígenes rechazados) y las transiciones con datos simulados.

## Endurecimiento (antes de difundir la URL)

- [x] Cloudflare (verificado el 2026-10-21): *rate limiting* gratuito en `/api/galaxy` y `/ws` (30 peticiones en 10 s por IP, bloqueo de 10 s con 429; el plan gratuito solo permite filtrar por ruta), "Always Use HTTPS" (301) y HSTS de 6 meses con includeSubDomains. El WAF administrado se omitió: aporta poco a una app de solo lectura sin entradas de usuario.
- [x] Revisión de seguridad completa contra las invariantes de `CLAUDE.md` (2026-10-21), verificada contra producción. **Bien:** sin docs ni esquema de FastAPI, solo GET (POST/PUT/DELETE/PATCH/OPTIONS → 405), sin CORS, CSP en la web, RBAC explícito sin secrets ni configmaps, solo la API con token, raíz de solo lectura y sin capabilities en ambos pods, nada de dev ni source maps en el build, sin secretos en el historial, y `find_leaks` limpio sobre la foto real. **Corregido:** cualquier ruta devolvía la página con 200 (ahora 404 real); la API no mandaba headers de seguridad (ahora `nosniff`, CSP `default-src 'none'`, `no-store`); cada `GET /api/galaxy` ensamblaba la galaxia (ahora sale de la caché del broadcaster: una ráfaga cuesta un ensamblado); un solo visitante podía ocupar los 200 lugares de `/ws` (ahora máx. 4 por IP según `CF-Connecting-IP`).
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
