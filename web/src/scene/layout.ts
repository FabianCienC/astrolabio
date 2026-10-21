/**
 * Where every object sits in space. Pure: galaxy in, positioned objects out.
 *
 * Position encodes ownership, so no line is needed for it:
 *   - each project (namespace) is a region around the core, with a ring at its center;
 *   - its workloads circle that ring, active replica sets sit just outside their
 *     workload, and pods circle their replica set (or workload, for StatefulSets);
 *   - services and routes sit on the side facing the core, since they are the way in.
 * The core holds the three cluster nodes; around them, each platform system
 * (Kubernetes, Calico, Argo CD...) is its own small cluster with its name.
 *
 * Non-ownership relations (Service -> Pod, Route -> Service) are returned as
 * pairs of ids and drawn as lines. Everything is deterministic: angles come from
 * list order and from hashing ids, so objects keep their place across reloads.
 */

import { Vector3 } from "three";

import type { Galaxy, InfraComponent, Pod, Route, Service, Workload } from "../contract/galaxy";
import { componentId, namespaceId, nodeId } from "../model/ids";
import { hashString, seededRandom } from "./random";
import { KIND, type ObjectKind, SHAPE } from "./symbology";

export type PlacedObject = {
  id: string;
  kind: ObjectKind;
  /** Constellation id for project objects, "core/<system>" for platform objects, "core" for nodes. */
  group: string;
  position: Vector3;
  size: number;
  shape: number;
  /** 0..1 brightness from CPU (`cpuGlow`); undefined without metrics. Set by the scene. */
  glow?: number;
};

export type Relation = [fromId: string, toId: string];

/** A name floating in the scene: a project or a platform system. */
export type Label = { id: string; text: string; kind: "project" | "system"; position: Vector3 };

export type Layout = { objects: PlacedObject[]; relations: Relation[]; labels: Label[] };

export const CORE_GROUP = "core";
/** Group of a platform system's objects: its own cluster (and nebula) inside the core. */
export const systemGroup = (system: string) => `core/${system}`;
export const isCoreGroup = (group: string) => group === CORE_GROUP || group.startsWith("core/");

const PROJECT_RING = 46;
const WORKLOAD_RADIUS = 4;
const REPLICASET_OFFSET = 1.6;
const POD_RADIUS = 0.75;
const ENTRY_DISTANCE = 6.5;
const ENTRY_SPACING = 1.8;
const NODE_RADIUS = 2.2;
const SYSTEM_RING = 16;
/** Empty angle (radians) between platform system clusters on the core ring. */
const SYSTEM_GAP_ANGLE = 0.35;

const UP = new Vector3(0, 1, 0);

/** Point on a circle in the horizontal plane around `center`. */
function around(center: Vector3, radius: number, angle: number, lift = 0): Vector3 {
  return new Vector3(
    center.x + Math.cos(angle) * radius,
    center.y + lift,
    center.z + Math.sin(angle) * radius,
  );
}

class Builder {
  readonly objects: PlacedObject[] = [];
  readonly relations: Relation[] = [];
  readonly labels: Label[] = [];

  add(id: string, kind: ObjectKind, group: string, position: Vector3) {
    const info = KIND[kind];
    this.objects.push({ id, kind, group, position, size: info.size, shape: SHAPE[info.shape] });
  }

  /** Pods evenly spaced on a small circle around their owner. */
  pods(pods: Pod[], owner: Vector3, group: string) {
    pods.forEach((pod, i) => {
      const angle = (i / pods.length) * Math.PI * 2 + 0.4;
      this.add(pod.id, "pod", group, around(owner, POD_RADIUS, angle, 0.15));
    });
  }

  /** Services then routes, in a row on the side of `center` that faces the core. */
  entries(center: Vector3, services: Service[], routes: Route[], group: string) {
    const inward = center.clone().setY(0).normalize().negate();
    const sideways = new Vector3().crossVectors(inward, UP).normalize();
    const row = (count: number, distance: number, index: number) =>
      center
        .clone()
        .addScaledVector(inward, distance)
        .addScaledVector(sideways, (index - (count - 1) / 2) * ENTRY_SPACING);

    services.forEach((service, i) => {
      this.add(service.id, "service", group, row(services.length, ENTRY_DISTANCE, i));
      for (const target of service.targets) this.relations.push([service.id, target]);
    });
    routes.forEach((route, i) => {
      this.add(route.id, "route", group, row(routes.length, ENTRY_DISTANCE + 2.5, i));
      for (const service of route.services) this.relations.push([route.id, service]);
    });
  }

  workload(workload: Workload, position: Vector3, outward: Vector3, group: string) {
    this.add(workload.id, "workload", group, position);
    this.pods(workload.pods, position, group);

    workload.replica_sets.forEach((rs, i) => {
      // Two replica sets (a rollout) fan out to both sides of the outward direction.
      const spread = (i - (workload.replica_sets.length - 1) / 2) * 0.9;
      const direction = outward.clone().applyAxisAngle(UP, spread);
      const rsPosition = position.clone().addScaledVector(direction, REPLICASET_OFFSET);
      this.add(rs.id, "replicaset", group, rsPosition);
      this.pods(rs.pods, rsPosition, group);
    });
  }
}

export function layoutGalaxy(galaxy: Galaxy): Layout {
  const build = new Builder();
  const count = galaxy.constellations.length;

  galaxy.constellations.forEach((constellation, i) => {
    const rand = seededRandom(hashString(constellation.id));
    const angle = (i / Math.max(count, 1)) * Math.PI * 2 + rand() * 0.4;
    const radius = PROJECT_RING + (rand() - 0.5) * 6;
    const center = around(new Vector3(), radius, angle, (rand() - 0.5) * 6);
    const group = constellation.id;

    build.add(namespaceId(group), "namespace", group, center);
    build.labels.push({ id: group, text: constellation.project, kind: "project", position: center });

    // Workloads fill the half circle away from the core; services and routes use the other.
    const span = Math.PI * 1.1;
    const awayFromCore = Math.atan2(center.z, center.x);
    constellation.workloads.forEach((workload, w) => {
      const step = (span * (w + 0.5)) / constellation.workloads.length;
      const position = around(center, WORKLOAD_RADIUS, awayFromCore - span / 2 + step);
      const outward = position.clone().sub(center).setY(0).normalize();
      build.workload(workload, position, outward, group);
    });

    build.entries(center, constellation.services, constellation.routes, group);
  });

  const origin = new Vector3();
  galaxy.core.nodes.forEach((node, i) => {
    const angle = (i / galaxy.core.nodes.length) * Math.PI * 2;
    build.add(nodeId(node.id), "node", CORE_GROUP, around(origin, NODE_RADIUS, angle));
  });

  // Each platform system (Kubernetes, Calico, Argo CD...) is its own cluster on the core
  // ring: a sector sized by how many components it has, with a gap between systems.
  const systems = new Map<string, InfraComponent[]>();
  for (const c of galaxy.core.components) systems.set(c.system, [...(systems.get(c.system) ?? []), c]);
  const total = galaxy.core.components.length;
  const usable = Math.PI * 2 - systems.size * SYSTEM_GAP_ANGLE;
  let start = 0;
  for (const [system, components] of systems) {
    const sector = (usable * components.length) / Math.max(total, 1);
    const angle = start + sector / 2;
    start += sector + SYSTEM_GAP_ANGLE;
    const center = around(origin, SYSTEM_RING, angle);
    const radius = components.length === 1 ? 0 : 1.4 + 0.45 * components.length;
    const group = systemGroup(system);

    components.forEach((component, i) => {
      // Members on a small circle around the cluster's center, starting on its outer side.
      const a = angle + (i / components.length) * Math.PI * 2;
      const position = around(center, radius, a, i % 2 ? 0.4 : -0.4);
      build.add(componentId(component.id), "component", group, position);
      build.pods(component.pods, position, group);
      const towardNodes = position.clone().setY(0).normalize().negate();
      const sideways = new Vector3().crossVectors(towardNodes, UP);
      component.services.forEach((service, n) => {
        // Platform services sit just inside their component, toward the nodes, side by side.
        const offset = (n - (component.services.length - 1) / 2) * 0.7;
        const inside = position
          .clone()
          .addScaledVector(towardNodes, 1.3)
          .addScaledVector(sideways, offset);
        build.add(service.id, "service", group, inside);
        for (const target of service.targets) build.relations.push([service.id, target]);
      });
    });

    // The name floats just outside the cluster, away from the nodes.
    build.labels.push({
      id: group,
      text: system,
      kind: "system",
      position: around(origin, SYSTEM_RING + radius + 2.6, angle),
    });
  }

  return { objects: build.objects, relations: build.relations, labels: build.labels };
}

/** Objects by group, in layout order. */
export function groupObjects(objects: PlacedObject[]): Map<string, PlacedObject[]> {
  const groups = new Map<string, PlacedObject[]>();
  for (const object of objects) {
    const members = groups.get(object.group);
    if (members) members.push(object);
    else groups.set(object.group, [object]);
  }
  return groups;
}
