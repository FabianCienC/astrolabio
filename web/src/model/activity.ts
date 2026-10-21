/**
 * What changed between two galaxies, as short Spanish lines for the activity panel.
 *
 * Everything is derived in the browser from consecutive `/ws` galaxies: the API
 * publishes nothing extra for it. To log something new, add a rule to `RULES`: a
 * function that compares the previous and the next galaxy and returns entries.
 */

import type {
  Constellation,
  Galaxy,
  InfraComponent,
  Node,
  Pod,
  Workload,
} from "../contract/galaxy";
import { HEALTH_LABEL, type Health } from "./health";
import { componentId, namespaceId, nodeId } from "./ids";

export type Tone = "info" | "ok" | "warn" | "bad";

export type Activity = {
  id: number;
  at: Date;
  text: string;
  tone: Tone;
  /** Object to select when the entry is clicked. */
  targetId?: string;
};

export type Change = Omit<Activity, "id" | "at">;
type Rule = (previous: Galaxy, next: Galaxy) => Change[];

const TONE: Record<Health, Tone> = { ok: "ok", degraded: "warn", down: "bad", unknown: "info" };

function byId<T extends { id: string }>(items: T[]): Map<string, T> {
  return new Map(items.map((item) => [item.id, item]));
}

/** Every workload with its project, by workload id. */
function workloads(galaxy: Galaxy): Map<string, { workload: Workload; project: Constellation }> {
  return new Map(
    galaxy.constellations.flatMap((project) =>
      project.workloads.map((workload) => [workload.id, { workload, project }] as const),
    ),
  );
}

/** Every pod of a visible project (platform pods are anonymous and renumbered, so they
 * are followed through their component's replicas instead), by pod id. */
function projectPods(galaxy: Galaxy): Map<string, { pod: Pod; project: Constellation }> {
  return new Map(
    galaxy.constellations.flatMap((project) =>
      project.workloads.flatMap((w) =>
        [...w.pods, ...w.replica_sets.flatMap((rs) => rs.pods)].map(
          (pod) => [pod.id, { pod, project }] as const,
        ),
      ),
    ),
  );
}

/** Added and removed items of two maps keyed by id. */
function diff<T>(before: Map<string, T>, after: Map<string, T>) {
  return {
    added: [...after].filter(([id]) => !before.has(id)).map(([, v]) => v),
    removed: [...before].filter(([id]) => !after.has(id)).map(([, v]) => v),
    kept: [...after].flatMap(([id, v]) => (before.has(id) ? [[before.get(id)!, v] as const] : [])),
  };
}

const projects: Rule = (previous, next) => {
  const { added, removed } = diff(byId(previous.constellations), byId(next.constellations));
  return [
    ...added.map((c) => ({
      text: `Nuevo proyecto: ${c.project}`,
      tone: "info" as const,
      targetId: namespaceId(c.id),
    })),
    ...removed.map((c) => ({ text: `Proyecto retirado: ${c.project}`, tone: "warn" as const })),
  ];
};

const workloadChanges: Rule = (previous, next) => {
  const { added, removed, kept } = diff(workloads(previous), workloads(next));
  return [
    ...added.map(({ workload: w, project }) => ({
      text: `${project.project}: nuevo ${w.kind} ${w.name}`,
      tone: "info" as const,
      targetId: w.id,
    })),
    ...removed.map(({ workload: w, project }) => ({
      text: `${project.project}: ${w.kind} ${w.name} eliminado`,
      tone: "warn" as const,
    })),
    ...kept.flatMap(([{ workload: before }, { workload: w, project }]) => {
      const changes: Change[] = [];
      if (w.commit && w.commit.sha !== before.commit?.sha) {
        changes.push({
          text: `${project.project}: desplegando ${w.name} ${w.commit.sha.slice(0, 7)}`,
          tone: "info",
          targetId: w.id,
        });
      }
      if (
        w.replicas.ready !== before.replicas.ready ||
        w.replicas.desired !== before.replicas.desired
      ) {
        changes.push({
          text: `${w.name}: ${w.replicas.ready}/${w.replicas.desired} réplicas listas`,
          tone: TONE[w.health],
          targetId: w.id,
        });
      } else if (w.health !== before.health) {
        changes.push({
          text: `${w.name}: ${HEALTH_LABEL[w.health].toLowerCase()}`,
          tone: TONE[w.health],
          targetId: w.id,
        });
      }
      return changes;
    }),
  ];
};

const pods: Rule = (previous, next) => {
  const { added, removed, kept } = diff(projectPods(previous), projectPods(next));
  return [
    ...added.map(({ pod, project }) => ({
      text: `${project.project}: pod ${pod.name} creado`,
      tone: "info" as const,
      targetId: pod.id,
    })),
    ...removed.map(({ pod, project }) => ({
      text: `${project.project}: pod ${pod.name} eliminado`,
      tone: "info" as const,
    })),
    ...kept
      .filter(([before, after]) => after.pod.restarts > before.pod.restarts)
      .map(([, { pod, project }]) => ({
        text: `${project.project}: pod ${pod.name} se reinició (${pod.restarts})`,
        tone: "warn" as const,
        targetId: pod.id,
      })),
  ];
};

const argo: Rule = (previous, next) => {
  const before = byId(previous.constellations);
  return next.constellations.flatMap((c) => {
    const old = before.get(c.id)?.argo;
    if (!c.argo || !old || (old.sync === c.argo.sync && old.health === c.argo.health)) return [];
    const tone: Tone = c.argo.sync === "Synced" && c.argo.health === "Healthy" ? "ok" : "warn";
    return [
      {
        text: `${c.project}: Argo CD ${c.argo.sync} / ${c.argo.health}`,
        tone,
        targetId: namespaceId(c.id),
      },
    ];
  });
};

/** Platform components and nodes: replicas and health. */
const core: Rule = (previous, next) => {
  const components = diff(byId(previous.core.components), byId(next.core.components));
  const nodes = diff(byId(previous.core.nodes), byId(next.core.nodes));
  const component = ([before, c]: readonly [InfraComponent, InfraComponent]): Change[] => {
    if (
      c.replicas.ready !== before.replicas.ready ||
      c.replicas.desired !== before.replicas.desired
    ) {
      return [
        {
          text: `${c.name}: ${c.replicas.ready}/${c.replicas.desired} réplicas listas`,
          tone: TONE[c.health],
          targetId: componentId(c.id),
        },
      ];
    }
    if (c.health === before.health) return [];
    return [
      {
        text: `${c.name}: ${HEALTH_LABEL[c.health].toLowerCase()}`,
        tone: TONE[c.health],
        targetId: componentId(c.id),
      },
    ];
  };
  const node = ([before, n]: readonly [Node, Node]): Change[] =>
    n.health === before.health
      ? []
      : [
          {
            text: `Nodo ${n.name}: ${HEALTH_LABEL[n.health].toLowerCase()}`,
            tone: TONE[n.health],
            targetId: nodeId(n.id),
          },
        ];
  return [...components.kept.flatMap(component), ...nodes.kept.flatMap(node)];
};

/** Add a rule here to log something new. */
export const RULES: Rule[] = [projects, workloadChanges, pods, argo, core];

export function describeChanges(previous: Galaxy, next: Galaxy): Change[] {
  return RULES.flatMap((rule) => rule(previous, next));
}

/** First line of the log: what was found on connecting. */
export function describeGalaxy(galaxy: Galaxy): Change {
  const pods =
    galaxy.constellations.flatMap((c) =>
      c.workloads.flatMap((w) => [...w.pods, ...w.replica_sets.flatMap((rs) => rs.pods)]),
    ).length + galaxy.core.components.reduce((sum, c) => sum + c.pods.length, 0);
  return {
    text: `Clúster leído: ${galaxy.constellations.length} proyectos, ${galaxy.core.nodes.length} nodos, ${pods} pods`,
    tone: "ok",
  };
}
