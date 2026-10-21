# ⭐ Astrolabio: visualización 3D en tiempo real del homelab

**Prioridad:** Insignia (primero en construirse)
**Meta:** fases 1 a 3 funcionando y publicadas antes de fin de 2026, en paralelo con el curso del CKA.
**URL pública:** `https://astrolabio.fabiancienfuegos.com`

> Un astrolabio era el instrumento con el que los navegantes leían el cielo para orientarse. **Astrolabio** lee mi clúster de Kubernetes y lo dibuja como una galaxia viva.

## Qué es

Una aplicación web que **lee el clúster de Kubernetes en vivo** y lo dibuja en 3D como una galaxia:

- **Galaxia** = el clúster completo
- **Constelación** = un namespace (un proyecto del portafolio)
- **Estrella** = un workload (Deployment, StatefulSet…)
  - Brillo → uso de CPU / tráfico
  - Color → salud (ok, degradado, caído)
- **Líneas entre estrellas** = tráfico entre servicios
- Al hacer clic en una estrella se ve su ficha: qué es, responsable, repo, commit desplegado, estado de Argo CD

Misma línea visual de nodos-constelación de Elyx, pero sobre mi propia infraestructura.

## Identidad visual: tiene que verse galáctica

Es el requisito central del proyecto. Si se ve como un diagrama de cajas con efectos, falló. Tiene que sentirse como **mirar el espacio**.

**El frontend usa Three.js (WebGL), sin excepción.** Nada de SVG ni canvas 2D para la escena principal.

| Elemento | Cómo debe verse | Técnica en Three.js |
| --- | --- | --- |
| Fondo | Cielo profundo con miles de estrellas lejanas y un leve paralaje al mover la cámara | `Points` con un `BufferGeometry` de partículas, en capas a distintas profundidades |
| Estrellas (workloads) | Puntos de luz que **brillan y respiran**, no esferas sólidas. El halo crece con la CPU o el tráfico | Sprites o `Points` con shader propio + `UnrealBloomPass` (post-procesado) |
| Constelaciones (namespaces) | Grupos de estrellas unidos por **líneas finas y luminosas**, como en una carta astronómica, con una **nebulosa** de color detrás de cada proyecto | `Line` / `LineSegments` con material aditivo; nebulosa con planos de ruido (shader con *fbm*) y transparencia |
| Núcleo de infraestructura | Un centro galáctico brillante y difuso del que nacen los brazos donde viven los proyectos. Dentro, cada componente de plataforma (Traefik, Argo CD, Calico…) es una estrella con su propia ficha | Disco de partículas con rotación lenta y gradiente de color; componentes como `Points` con el mismo shader de las estrellas |
| Nodos del clúster | Tres "soles" en el corazón del núcleo (control plane y dos workers), con brillo según su CPU. Los workloads **no** orbitan alrededor de ellos: las constelaciones siguen agrupadas por proyecto | Sprites grandes con bloom; la ficha muestra salud, pods y CPU/RAM |
| Tráfico | Pulsos de luz que viajan por las líneas cuando hay peticiones | Partículas animadas a lo largo de curvas (`CatmullRomCurve3`) |
| Salud | Verde-azulado estable (ok), ámbar parpadeante (degradado), rojo apagándose (caído) | Uniforms del shader animados |
| Interacción | Cámara orbital suave; al hacer clic, vuelo hacia la estrella y se abre la ficha | `OrbitControls` + interpolación de cámara + `Raycaster` |

**Reglas técnicas para que funcione bien:**

- **Rendimiento:** `InstancedMesh` o `Points` para todo lo que se repite. Objetivo: 60 fps en laptop y 30+ fps en celular.
- **Celular:** si el dispositivo es lento, se reduce automáticamente la cantidad de partículas y la intensidad del bloom.
- **Accesibilidad:** respetar `prefers-reduced-motion` (sin pulsos ni rotación), y ofrecer una vista de lista con el mismo contenido para lectores de pantalla.
- **Coherencia con Elyx:** misma familia de nodos-constelación, pero con paleta y profundidad de espacio propias.

## Qué esperamos lograr

- Una vitrina pública que demuestre que el portafolio **está corriendo de verdad** y no son solo capturas de pantalla.
- Evidencia práctica de Kubernetes (API, watch, RBAC, GitOps, observabilidad) que refuerza el CKA.
- Una capa de ML ligera: detectar comportamiento anómalo y explicarlo en lenguaje natural.

## Punto de partida: lo que ya existe en el clúster

Astrolabio no empieza de cero. Usa piezas que ya están funcionando:

| Ya existe | Cómo lo aprovecha Astrolabio |
| --- | --- |
| Clúster kubeadm v1.35, 3 nodos (2 workers de 5 GB) | Es el universo que se dibuja; el presupuesto de memoria está más abajo |
| Argo CD con *app of apps* y `AppProject portfolio` | Se despliega igual que `hola` y `cv`; además, la API **lee** los `Application` para mostrar sync, salud y commit |
| Gateway API + Traefik + Cloudflare Tunnel | Publicación en `astrolabio.fabiancienfuegos.com` con un `HTTPRoute`; WebSockets funcionan por el túnel |
| Sealed Secrets | Credenciales de AWS (Bedrock) cifradas en Git |
| Patrón CI de `hola` y `cv` (Trivy, SHA fijados, deploy key) | Mismo workflow, ahora con 2 o 3 imágenes |
| Apps reales: `hola`, `cv`, más la plataforma | Las primeras constelaciones con datos reales desde la fase 1 |
| Traefik ya expone métricas Prometheus (entryPoint `metrics`, :9100) | Fuente de tráfico por ruta para el brillo y las líneas |

Lo que **no** existe todavía y hay que agregar: `metrics-server`, Prometheus y las anotaciones en los manifiestos.

## Decisiones

| Tema | Decisión | Notas |
| --- | --- | --- |
| **Frontend (`astrolabio-web`)** | **Three.js + Vite, obligatorio.** Framework: **React + TypeScript** (decidido) | React para la UI (ficha, vista de lista, controles). La escena es un módulo TypeScript con **Three.js directo, sin React Three Fiber**, montado en un componente: casi todo es shader propio, y los deltas del WebSocket escriben directo en los buffers sin pasar por la reconciliación de React. Detalle en `PLAN.md`. Se sirve con `nginx-unprivileged`, igual que `hola` y `cv` |
| **Backend (`astrolabio-api`)** | **Python** con **FastAPI** + `kubernetes_asyncio` | Un solo *event loop*: los watchers de Kubernetes y los WebSockets conviven sin hilos. Mismo lenguaje que el worker de anomalías, así que se comparten modelos de datos y utilidades. Servido con `uvicorn` |
| Imagen de la API | `python:3.13-slim` con usuario sin root (UID 10001), dependencias fijadas con hash | Cumple PSA `restricted`. ~150 MB de imagen y ~80–120 MB de RAM |
| Tráfico entre servicios | **Traefik + NetworkPolicies**, no Hubble | El clúster usa **Calico**, y Hubble solo existe con Cilium. Las líneas salen del tráfico real de entrada por ruta (métricas de Traefik) y de las conexiones **permitidas** entre pods (NetworkPolicies). Migrar a Cilium queda como fase futura opcional |
| Métricas | `metrics-server` (fase 3) y Prometheus mínimo (fase 4) | `metrics-server` es ligero y da CPU/RAM por pod. Prometheus completo (kube-prometheus-stack) no cabe con holgura; se instala solo el servidor, con retención corta |
| Redis | **Fuera al inicio** | Con una sola réplica de la API no hace falta pub/sub. El worker de anomalías le avisa a la API por HTTP. Se agrega si un día hay varias réplicas |
| Base de datos | Ninguna al inicio | El estado vive en la caché en memoria de la API. Historial o *replay* → TimescaleDB más adelante |
| Prefijo de anotaciones | `fabiancienfuegos.com/…` | Kubernetes recomienda prefijos con un dominio propio |
| Exposición pública | `HTTPRoute` en el Gateway `public` + Cloudflare | Mismo camino que `cv`. Detalles en la sección de seguridad |

## Cómo identifica cada cosa

1. **API de Kubernetes con watch** (sin polling). Para cada tipo de recurso, la API hace `list` una vez, guarda el resultado en memoria y luego mantiene un `watch` abierto que aplica cada cambio. Es el mismo patrón *list + watch* que usan los controladores de Kubernetes, también llamado *informer*. Recursos vigilados: Namespaces, Deployments, StatefulSets, Pods, Services, Events, `HTTPRoute` y `Application` de Argo CD.
   - Si el watch responde **`410 Gone`** (la versión que pedía ya expiró), se vuelve a hacer `list` y se reanuda. Es el error más común al escribir watchers a mano.
2. **Anotaciones propias**, en dos niveles:

   En el **Namespace**, que es la constelación (`platform/namespaces/<app>.yaml`):

   ```yaml
   metadata:
     labels:
       fabiancienfuegos.com/astrolabio: "visible"   # solo los namespaces con esta etiqueta se dibujan con detalle
     annotations:
       fabiancienfuegos.com/proyecto: "CV"
       fabiancienfuegos.com/descripcion: "Mi CV web en React"
       fabiancienfuegos.com/repo: "https://github.com/FabianCienC/CV"
   ```

   En cada **Deployment**, que es la estrella (`workloads/<app>/deployment.yaml`):

   ```yaml
   metadata:
     annotations:
       fabiancienfuegos.com/descripcion: "Frontend estático con nginx"
       fabiancienfuegos.com/rol: "frontend"            # frontend | api | worker | datos
       fabiancienfuegos.com/criticidad: "alta"         # alta | media | baja
   ```

   Lo que se puede deducir no se anota. El commit sale del **tag de la imagen**, que ya es el SHA del commit gracias al CI, y el estado de despliegue sale del `Application` de Argo CD.
3. **Argo CD**: la API lee los objetos `Application` del namespace `argocd` (`status.sync.status`, `status.health.status`, `status.sync.revision`). Así la ficha muestra "Synced · Healthy · commit a1b2c3d" con enlace al commit en GitHub.
4. **Métricas**: `metrics-server` para CPU y memoria por pod (fase 3); Prometheus para series de tiempo y el tráfico de Traefik (fases 4 y 5).
5. **Líneas de tráfico**: `HTTPRoute` (Traefik → servicio) más NetworkPolicies (qué pod puede hablar con cuál), con el grosor según las peticiones por segundo que reporta Traefik.

## Machine learning

- **Detección de anomalías** sobre series de tiempo de Prometheus: primero un modelo estadístico (z-score móvil o STL) y después, si aporta, un autoencoder sencillo. La estrella "parpadea" cuando algo se sale de lo normal.
- **Resumen con LLM** (Bedrock): ante una anomalía, toma los Events y el estado recientes del workload y redacta en lenguaje natural qué pasó.
  - Usuario IAM **propio** de Astrolabio, con permiso solo para `bedrock:InvokeModel` sobre un modelo específico, y alerta de presupuesto en AWS.
  - Credenciales como `SealedSecret` en `homelab-gitops`.
  - **No se mandan logs crudos al LLM** al inicio: solo Events y estados, que ya están sanitizados. Así se evita filtrar datos por accidente.

## Estructura en Kubernetes

Namespace: `astrolabio` (PSA `restricted`, `gateway-access: public`, `fabiancienfuegos.com/astrolabio: visible`).

| Componente | Tipo | Imagen | requests → limits | Notas |
| --- | --- | --- | --- | --- |
| `astrolabio-web` | Deployment ×2 | `ghcr.io/fabiancienc/astrolabio-web` | 10m/32Mi → 96Mi | Build de Vite servido por nginx sin root; sin salida a ningún lado |
| `astrolabio-api` | Deployment ×1 | `ghcr.io/fabiancienc/astrolabio-api` | 50m/96Mi → 256Mi | FastAPI: watchers + REST + WebSocket. **Única** con token de ServiceAccount |
| `astrolabio-anomalias` | Deployment ×1 (fase 5) | `ghcr.io/fabiancienc/astrolabio-anomalias` | 50m/128Mi → 384Mi | Python; lee Prometheus y avisa a la API |
| `astrolabio-api` | ServiceAccount | — | — | Ligada al ClusterRole de solo lectura |
| `astrolabio` | `HTTPRoute` | — | — | `/` → web, `/api` y `/ws` → api |
| Prometheus | Helm (fase 4) | chart `prometheus-community/prometheus` | ~300–500 Mi | Solo el servidor; sin Alertmanager ni Pushgateway; retención 3 días |
| metrics-server | Helm (fase 3) | chart oficial | ~50 Mi | Necesita `--kubelet-insecure-tls` o certificados de kubelet firmados |

**Presupuesto total:** ~1.2 GB en la fase 5. Cabe en los dos workers de 5 GB junto a `hola`, `cv` y la plataforma.

## Cómo se acomoda en GitOps (mismo patrón que `hola` y `cv`)

### Repo de la app: `FabianCienC/astrolabio` (público, monorepo)

```
astrolabio/
├── web/                  # React + TypeScript + Vite + Three.js, Dockerfile con nginx-unprivileged
├── api/                  # Python (FastAPI + kubernetes_asyncio), Dockerfile sin root
├── anomalias/            # Python (fase 5)
└── .github/
    ├── workflows/ci.yaml # construye, escanea con Trivy, sube y actualiza homelab-gitops
    └── dependabot.yml    # github-actions, docker, npm y pip
```

El CI construye **solo** la imagen de la carpeta que cambió (filtros `paths` por job) y actualiza su tag en `homelab-gitops` con `yq` por nombre:

```bash
yq -i '(.images[] | select(.name == "astrolabio-api")).newTag = strenv(GITHUB_SHA)' workloads/astrolabio/kustomization.yaml
```

Deploy key propia: **`astrolabio-ci`** (escritura) en `homelab-gitops`, y su privada como secreto `GITOPS_DEPLOY_KEY` en el repo `astrolabio`.

### En `homelab-gitops`

```
platform/
├── namespaces/astrolabio.yaml       # namespace con PSA, gateway-access y etiqueta de Astrolabio
└── rbac/astrolabio-reader.yaml      # ClusterRole + ClusterRoleBinding de solo lectura (lo controla la plataforma)
workloads/astrolabio/
├── kustomization.yaml               # images: astrolabio-web, astrolabio-api, astrolabio-anomalias
├── web-deployment.yaml
├── api-deployment.yaml
├── api-serviceaccount.yaml
├── services.yaml
├── httproute.yaml
└── networkpolicy.yaml
apps/
├── astrolabio.yaml                  # Application, project: portfolio
├── rbac.yaml                        # Application → platform/rbac/ (project: default)
└── project-portfolio.yaml           # + namespace astrolabio y kind ServiceAccount en el whitelist
```

**Decisión de seguridad:** el `ClusterRole` vive en `platform/`, no en `workloads/`. El `AppProject portfolio` sigue sin permitir recursos de clúster, así que la app **no puede darse permisos a sí misma**. Esos permisos los decide la plataforma.

### RBAC de solo lectura (`platform/rbac/astrolabio-reader.yaml`)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: astrolabio-reader
rules:
  - apiGroups: [""]
    resources: ["namespaces", "pods", "services", "events", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets", "daemonsets", "replicasets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["gateway.networking.k8s.io"]
    resources: ["httproutes", "gateways"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["networkpolicies"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["argoproj.io"]
    resources: ["applications"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["pods", "nodes"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: astrolabio-reader
subjects:
  - kind: ServiceAccount
    name: astrolabio-api
    namespace: astrolabio
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: astrolabio-reader
```

Cada recurso va **listado uno por uno**: nunca `*`, porque un comodín incluiría `secrets` y `configmaps`. Tampoco hay permiso de `pods/log`. Para comprobarlo:

```bash
k auth can-i list secrets --as=system:serviceaccount:astrolabio:astrolabio-api        # no
k auth can-i watch deployments --as=system:serviceaccount:astrolabio:astrolabio-api   # yes
k auth can-i delete pods --as=system:serviceaccount:astrolabio:astrolabio-api         # no
```

### NetworkPolicy: la trampa del API server

`astrolabio-api` es el primer pod del portafolio que necesita **salir**: hacia el API server. Para Calico, el destino no es la IP del Service `kubernetes` (`10.96.0.1:443`) sino la IP real del control plane después de la traducción, **`192.168.0.41:6443`**. Por eso la regla de salida apunta ahí:

```yaml
  egress:
    - to:
        - ipBlock: { cidr: 192.168.0.41/32 }
      ports:
        - { port: 6443, protocol: TCP }
    - to:                                   # DNS
        - namespaceSelector:
            matchLabels: { kubernetes.io/metadata.name: kube-system }
          podSelector:
            matchLabels: { k8s-app: kube-dns }
      ports:
        - { port: 53, protocol: UDP }
        - { port: 53, protocol: TCP }
```

`astrolabio-web` conserva el *default deny* total, como `hola`. El firewall de Proxmox ya permite este tráfico, porque la red de pods `10.244.0.0/16` está en el ipset `k8s-internal`.

## Seguridad (importante por ser público)

- **Modelo sanitizado.** La API nunca reenvía objetos de Kubernetes tal cual: los convierte a modelos de Pydantic con una lista de campos permitidos (nombre, namespace, réplicas, estado, anotaciones `fabiancienfuegos.com/*`, tag de imagen). Nunca expone `env`, `volumes`, IPs de pods o nodos, `repoURL` del repo privado `homelab-gitops`, ni mensajes de Events que contengan rutas internas.
- **Namespaces visibles por allowlist.** Solo los que tienen `fabiancienfuegos.com/astrolabio: visible` se dibujan con detalle.
- **Infraestructura como vitrina, con catálogo cerrado.** La plataforma (`kube-system`, `argocd`, `traefik`, `cloudflared`, `calico-system`) forma el núcleo galáctico y sí muestra sus componentes, para presentar la infraestructura que se mantiene. Solo aparecen los componentes listados en un **catálogo dentro de la API** (nombre, función, workload que lo respalda); lo que no está en el catálogo no se publica. Las descripciones viven en el catálogo, no en anotaciones, porque varios componentes son pods estáticos de kubeadm o los crea un operador y no se pueden anotar por GitOps.
  - **Se muestra:** nombre, función, salud, réplicas listas/deseadas, sync y salud de Argo CD (si aplica) y, desde la fase 3, CPU/RAM.
  - **No se muestra:** nombres de pods, IPs, puertos, **versiones o tags de imagen** (darían a cualquiera la lista exacta de CVE a probar), argumentos, configuración ni `repoURL`.
  - **Nodos:** se publican como "control plane", "worker 1" y "worker 2", sin hostname ni IP.
- **Solo lectura de punta a punta.** RBAC sin verbos de escritura, y API sin endpoints `POST`, `PUT` ni `DELETE`. La documentación automática de FastAPI (`/docs`, `/openapi.json`) queda **desactivada** en producción.
- **Cloudflare como escudo:** una regla de *rate limiting* en `/api` y `/ws` (el plan gratuito incluye una), WAF administrado activado y el tráfico solo por el túnel.
- **Headers de seguridad** en el `HTTPRoute`, como en `cv`. La CSP debe permitir `connect-src 'self' wss://astrolabio.fabiancienfuegos.com` para el WebSocket. Si los shaders se compilan en tiempo de ejecución, no hace falta `unsafe-eval`: Three.js no lo usa.
- **Un solo origen.** Web y API en el mismo host (`/` y `/api`), así que no hace falta CORS.
- **Token de ServiceAccount solo en `astrolabio-api`**; los demás pods llevan `automountServiceAccountToken: false`.
- **Credenciales de AWS** como `SealedSecret`, en un usuario IAM exclusivo con permiso mínimo.

## Fases

Cada fase termina con algo publicado y un criterio claro de "listo".

### Fase 0: preparar el terreno (1 sesión)

- Crear el repo `astrolabio` y su deploy key `astrolabio-ci`.
- En `homelab-gitops`: namespace `astrolabio`, `platform/rbac/`, `apps/rbac.yaml`, y `astrolabio` + `ServiceAccount` en el `AppProject`.
- Agregar las anotaciones `fabiancienfuegos.com/*` a `hola` y `cv`, para tener constelaciones reales desde el día uno.
- DNS: `astrolabio.fabiancienfuegos.com` ya lo cubre el comodín del túnel `homelab-k8s`.

**Listo cuando:** `k auth can-i` da los tres resultados esperados y Argo CD muestra `astrolabio` en `Synced`, aunque todavía esté vacía.

### Fase 1: watchers + API

- `astrolabio-api` en Python con FastAPI y `kubernetes_asyncio`: un watcher *list + watch* por recurso, con caché en memoria y manejo de `410 Gone`.
- Expone `GET /api/galaxia`, un JSON sanitizado con constelaciones (namespaces), estrellas (workloads), anotaciones, estado de Argo CD y commit.
- Probar primero en local (`uvicorn`, con kubeconfig por túnel SSH) y luego en el clúster.

**Listo cuando:** `curl https://astrolabio.fabiancienfuegos.com/api/galaxia` devuelve `hola`, `cv` y el núcleo de infraestructura, sin ningún campo prohibido.

### Fase 2: la galaxia en 3D

- `astrolabio-web` con Vite + Three.js: fondo de estrellas, constelaciones con líneas luminosas y nebulosas, estrellas con bloom y color por salud, vuelo de cámara y ficha al hacer clic.
- Es la fase donde se juega la identidad visual: **se itera hasta que se vea galáctico**, antes de pasar a lo demás.

**Listo cuando:** la galaxia se ve fluida en el celular, y al hacer `k -n hola scale deploy hola --replicas=0` (y regresar), el cambio aparece al recargar la página.

### Fase 3: en vivo

- WebSocket `/ws`: la API empuja cada cambio que reciben los watchers.
- Instalar `metrics-server`; el brillo de cada estrella sigue a su CPU.

**Listo cuando:** un push a `hola` hace que su estrella cambie de estado **en vivo**, sin recargar, mientras Argo CD despliega.

### Fase 4: líneas de tráfico

- Instalar Prometheus mínimo y leer las métricas de Traefik (peticiones por `HTTPRoute`).
- Dibujar las líneas Traefik → servicio con pulsos de luz según el tráfico, y las conexiones permitidas por NetworkPolicy como líneas tenues.

**Listo cuando:** abrir el CV varias veces hace que su línea se ilumine.

### Fase 5: anomalías + LLM

- `astrolabio-anomalias` en Python: z-score sobre CPU, memoria y peticiones, y aviso a la API.
- Resumen con Bedrock a partir de Events y estado.

**Listo cuando:** provocar una anomalía (por ejemplo, un pod que consume CPU a propósito en un namespace de pruebas) hace parpadear su estrella y aparece una explicación en la ficha.

### Fase futura (opcional): Cilium + Hubble

Reemplazar Calico por Cilium para tener flujos reales entre pods. Exige reconstruir la red del clúster, así que conviene hacerlo **después del CKA** y como ejercicio de migración documentado.

## Relación con el CKA

| Tema del examen | Dónde aparece en Astrolabio |
| --- | --- |
| RBAC (ClusterRole, binding, `auth can-i`) | `astrolabio-reader` |
| ServiceAccounts y tokens | Solo `astrolabio-api` monta token |
| NetworkPolicies | La salida exacta al API server |
| Workloads y escalado | Las pruebas de cada fase |
| CRDs y operadores | Leer `Application` de Argo CD y `HTTPRoute`; el patrón *list + watch* es el corazón de cualquier controlador |
| Helm | metrics-server y Prometheus |
| Troubleshooting | Events y estados que Astrolabio muestra |

## Pendiente de platicar

- Paleta final, interacción en celular y la vista accesible de lista.
