# Astrolabio: nota para el portafolio

**Astrolabio** es una visualización en vivo de mi homelab de Kubernetes: cada proyecto,
pod, Service y componente de la infraestructura aparece como una estrella en una galaxia
3D que cambia sola cuando el clúster cambia. Lo que más trabaja brilla más, y un
despliegue se ve como pods que nacen y se apagan.

Lo construí de punta a punta:

- **Backend en Python (FastAPI, asyncio)** que vigila la API de Kubernetes con el mismo
  patrón de *informers* que usan los controladores, sin base de datos, y empuja cada
  cambio por WebSocket.
- **Frontend en React + Three.js** con shaders propios, transiciones que nunca saltan,
  modo accesible en lista y calidad que se adapta al dispositivo.
- **Seguridad pensada para algo público**: un contrato con lista blanca de campos y
  pruebas que fallan si se filtra un dato interno, RBAC de solo lectura, pods sin
  privilegios, NetworkPolicies y Cloudflare delante.
- **Entrega con GitOps**: CI con Trivy, imágenes fijadas por digest y despliegue
  automático con Argo CD.

Sitio: [astrolabio.fabiancienfuegos.com](https://astrolabio.fabiancienfuegos.com) ·
Código: [github.com/FabianCienC/astrolabio](https://github.com/FabianCienC/astrolabio)
