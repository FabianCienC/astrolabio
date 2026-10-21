import type { ReactNode } from "react";

import type { ArgoStatus, Commit, Metrics, Pod, Replicas } from "../contract/galaxy";
import type { Entry, GalaxyIndex } from "../model/galaxyIndex";
import { type Health, HEALTH_LABEL } from "../model/health";
import { componentId, namespaceId } from "../model/ids";
import { cpuGlow, KIND, type ObjectKind } from "../scene/symbology";
import { KindSymbol } from "./KindSymbol";

type Props = { entry: Entry; index: GalaxyIndex; onSelect: (id: string) => void };

const CATEGORY_LABEL = {
  control: "Plano de control",
  network: "Red",
  ingress: "Entrada",
  gitops: "GitOps",
  security: "Seguridad",
} as const;

const NODE_LABEL = { "control-plane": "control plane", "worker-1": "worker 1", "worker-2": "worker 2" };

/** Everything the sidebar knows about one selected object. */
export function ObjectDetails({ entry, index, onSelect }: Props) {
  const link = (id: string) => (
    <button type="button" className="link" onClick={() => onSelect(id)}>
      {index.label(id)}
    </button>
  );

  return (
    <article className="details">
      <header>
        <p className="details-kind">
          <KindSymbol kind={entry.kind} />
          {KIND[entry.kind].label}
        </p>
        <h2>{index.label(entry.id)}</h2>
        {"constellation" in entry && entry.constellation && entry.kind !== "namespace" && (
          <p className="details-context">en {link(namespaceId(entry.constellation.id))}</p>
        )}
        {(entry.kind === "pod" || entry.kind === "service") && entry.component && (
          <p className="details-context">de {link(componentId(entry.component.id))}</p>
        )}
      </header>
      <dl>{fields(entry, index, link)}</dl>
    </article>
  );
}

function fields(entry: Entry, index: GalaxyIndex, link: (id: string) => ReactNode): ReactNode {
  switch (entry.kind) {
    case "namespace": {
      const c = entry.constellation;
      const pods = c.workloads.flatMap((w) => [...w.pods, ...w.replica_sets.flatMap((r) => r.pods)]);
      return (
        <>
          <Row label="Estado"><HealthBadge health={c.health} /></Row>
          {c.description && <Row label="Descripción">{c.description}</Row>}
          <Row label="Namespace"><code>{c.id}</code></Row>
          {c.repo && <Row label="Repositorio"><External href={c.repo}>{repoName(c.repo)}</External></Row>}
          {c.argo && <Row label="Argo CD"><Argo argo={c.argo} /></Row>}
          <Row label="Workloads"><List ids={c.workloads.map((w) => w.id)} link={link} /></Row>
          <Row label="Pods">{pods.length}</Row>
          {c.routes.length > 0 && (
            <Row label="Entradas"><List ids={c.routes.map((r) => r.id)} link={link} /></Row>
          )}
        </>
      );
    }
    case "workload": {
      const w = entry.workload;
      return (
        <>
          <Row label="Estado"><HealthBadge health={w.health} /></Row>
          <Row label="Tipo">{w.kind}</Row>
          {w.description && <Row label="Descripción">{w.description}</Row>}
          {w.role && <Row label="Rol">{w.role}</Row>}
          {w.criticality && <Row label="Criticidad">{w.criticality}</Row>}
          <Row label="Réplicas"><ReplicaCount replicas={w.replicas} /></Row>
          {w.commit && <Row label="Commit"><CommitLink commit={w.commit} /></Row>}
          <MetricsRows metrics={w.metrics} kind="workload" />
          {w.replica_sets.length > 0 && (
            <Row label="ReplicaSets"><List ids={w.replica_sets.map((r) => r.id)} link={link} /></Row>
          )}
          {w.pods.length > 0 && <Row label="Pods"><List ids={w.pods.map((p) => p.id)} link={link} /></Row>}
        </>
      );
    }
    case "replicaset": {
      const rs = entry.replicaSet;
      return (
        <>
          <Row label="Estado"><HealthBadge health={rs.health} /></Row>
          <Row label="Deployment">{link(entry.workload.id)}</Row>
          <Row label="Réplicas"><ReplicaCount replicas={rs.replicas} /></Row>
          {entry.workload.replica_sets.length > 1 && (
            <Row label="Rollout">En curso: este Deployment tiene {entry.workload.replica_sets.length} ReplicaSets activos</Row>
          )}
          <Row label="Pods"><List ids={rs.pods.map((p) => p.id)} link={link} /></Row>
        </>
      );
    }
    case "pod": {
      const services = index.servicesSelecting(entry.pod.id);
      return (
        <>
          <Row label="Estado"><HealthBadge health={entry.pod.health} /></Row>
          <PodRows pod={entry.pod} />
          <Row label="Dueño">{link(entry.ownerId)}</Row>
          {services.length > 0 && <Row label="Recibe tráfico de"><List ids={services.map((s) => s.id)} link={link} /></Row>}
        </>
      );
    }
    case "service": {
      const routes = index.routesTo(entry.service.id);
      return (
        <>
          <Row label="Estado"><HealthBadge health={entry.service.health} /></Row>
          <Row label="Envía tráfico a"><List ids={entry.service.targets} link={link} /></Row>
          {routes.length > 0 && <Row label="Expuesto por"><List ids={routes.map((r) => r.id)} link={link} /></Row>}
        </>
      );
    }
    case "route":
      return (
        <>
          <Row label="Estado"><HealthBadge health={entry.route.health} /></Row>
          <Row label="Dirección">
            <ul className="plain">
              {entry.route.hostnames.map((host) => (
                <li key={host}><External href={`https://${host}`}>{host}</External></li>
              ))}
            </ul>
          </Row>
          <Row label="Services"><List ids={entry.route.services} link={link} /></Row>
        </>
      );
    case "component": {
      const c = entry.component;
      return (
        <>
          <Row label="Estado"><HealthBadge health={c.health} /></Row>
          <Row label="Función">{c.purpose}</Row>
          <Row label="Sistema">{c.system}</Row>
          <Row label="Categoría">{CATEGORY_LABEL[c.category]}</Row>
          <Row label="Réplicas"><ReplicaCount replicas={c.replicas} /></Row>
          {c.argo && <Row label="Argo CD"><Argo argo={c.argo} /></Row>}
          <MetricsRows metrics={c.metrics} kind="component" />
          {c.pods.length > 0 && <Row label="Pods"><List ids={c.pods.map((p) => p.id)} link={link} /></Row>}
          <p className="note">Los objetos de la plataforma se muestran sin nombres ni versiones.</p>
        </>
      );
    }
    case "node": {
      const n = entry.node;
      return (
        <>
          <Row label="Estado"><HealthBadge health={n.health} /></Row>
          <Row label="Rol">{n.role === "control-plane" ? "Plano de control" : "Worker"}</Row>
          <Row label="Pods">{n.pods}</Row>
          <MetricsRows metrics={n.metrics} kind="node" />
        </>
      );
    }
  }
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function HealthBadge({ health }: { health: Health }) {
  return <span className={`badge badge-${health}`}>{HEALTH_LABEL[health]}</span>;
}

function ReplicaCount({ replicas }: { replicas: Replicas }) {
  return (
    <>
      {replicas.ready} de {replicas.desired} listas
    </>
  );
}

function PodRows({ pod }: { pod: Pod }) {
  return (
    <>
      <Row label="Fase">{pod.phase}</Row>
      <Row label="Listo">{pod.ready ? "Sí" : "No"}</Row>
      <Row label="Reinicios">{pod.restarts}</Row>
      {pod.node && <Row label="Nodo">{NODE_LABEL[pod.node]}</Row>}
      <MetricsRows metrics={pod.metrics} kind="pod" />
    </>
  );
}

function MetricsRows({ metrics, kind }: { metrics: Metrics; kind: ObjectKind }) {
  return (
    <>
      {metrics.cpu_millicores !== null && (
        <Row label="CPU">
          <CpuMeter kind={kind} cpu={metrics.cpu_millicores} />
        </Row>
      )}
      {metrics.memory_mib !== null && <Row label="Memoria">{metrics.memory_mib} MiB</Row>}
    </>
  );
}

function Argo({ argo }: { argo: ArgoStatus }) {
  return (
    <>
      {argo.sync} · {argo.health}
    </>
  );
}

function CommitLink({ commit }: { commit: Commit }) {
  return (
    <External href={commit.url}>
      <code>{commit.sha.slice(0, 7)}</code>
    </External>
  );
}

function List({ ids, link }: { ids: string[]; link: (id: string) => ReactNode }) {
  return (
    <ul className="plain">
      {ids.map((id) => (
        <li key={id}>{link(id)}</li>
      ))}
    </ul>
  );
}

function External({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  );
}

function repoName(url: string) {
  return url.replace("https://github.com/", "");
}

/** CPU as a bar on the scene's own scale: a full bar is a star at full glow. */
export function CpuMeter({ kind, cpu }: { kind: ObjectKind; cpu: number }) {
  const glow = cpuGlow(kind, cpu) ?? 0;
  return (
    <span className="cpu-meter">
      <span
        className="cpu-meter-bar"
        role="meter"
        aria-label="Uso de CPU"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={glow}
      >
        <span style={{ width: `${Math.round(glow * 100)}%` }} />
      </span>
      {cpu} m
    </span>
  );
}
