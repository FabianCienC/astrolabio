/**
 * Lookup of every object in a galaxy by id, with the context the sidebar needs
 * (its owner, its project, what points to it). Pure data: no Three.js, no React.
 */

import type {
  Constellation,
  Galaxy,
  InfraComponent,
  Node,
  Pod,
  ReplicaSet,
  Route,
  Service,
  Workload,
} from "../contract/galaxy";
import type { Health } from "./health";
import { componentId, namespaceId, nodeId } from "./ids";

export type Entry =
  | { kind: "namespace"; id: string; constellation: Constellation }
  | { kind: "workload"; id: string; workload: Workload; constellation: Constellation }
  | {
      kind: "replicaset";
      id: string;
      replicaSet: ReplicaSet;
      workload: Workload;
      constellation: Constellation;
    }
  | {
      kind: "pod";
      id: string;
      pod: Pod;
      /** Id of the replica set, workload or component that owns it. */
      ownerId: string;
      constellation?: Constellation;
      component?: InfraComponent;
    }
  | {
      kind: "service";
      id: string;
      service: Service;
      constellation?: Constellation;
      component?: InfraComponent;
    }
  | { kind: "route"; id: string; route: Route; constellation: Constellation }
  | { kind: "component"; id: string; component: InfraComponent }
  | { kind: "node"; id: string; node: Node };

export class GalaxyIndex {
  private readonly entries = new Map<string, Entry>();
  /** pod id -> services that select it */
  private readonly servicesByPod = new Map<string, string[]>();
  /** service id -> routes that send traffic to it */
  private readonly routesByService = new Map<string, string[]>();

  constructor(readonly galaxy: Galaxy) {
    for (const constellation of galaxy.constellations) this.addConstellation(constellation);
    for (const component of galaxy.core.components) this.addComponent(component);
    for (const node of galaxy.core.nodes) {
      this.entries.set(nodeId(node.id), { kind: "node", id: nodeId(node.id), node });
    }
  }

  get(id: string): Entry | undefined {
    return this.entries.get(id);
  }

  servicesSelecting(podId: string): Service[] {
    return (this.servicesByPod.get(podId) ?? []).flatMap((id) => {
      const entry = this.entries.get(id);
      return entry?.kind === "service" ? [entry.service] : [];
    });
  }

  routesTo(serviceId: string): Route[] {
    return (this.routesByService.get(serviceId) ?? []).flatMap((id) => {
      const entry = this.entries.get(id);
      return entry?.kind === "route" ? [entry.route] : [];
    });
  }

  /** Health of any object (nodes, components and everything in a project have one). */
  health(id: string): Health | undefined {
    const entry = this.entries.get(id);
    if (!entry) return undefined;
    switch (entry.kind) {
      case "namespace":
        return entry.constellation.health;
      case "workload":
        return entry.workload.health;
      case "replicaset":
        return entry.replicaSet.health;
      case "pod":
        return entry.pod.health;
      case "service":
        return entry.service.health;
      case "route":
        return entry.route.health;
      case "component":
        return entry.component.health;
      case "node":
        return entry.node.health;
    }
  }

  /** Human label for any id: the object's name, or a description for anonymous ones. */
  label(id: string): string {
    const entry = this.entries.get(id);
    if (!entry) return id;
    switch (entry.kind) {
      case "namespace":
        return entry.constellation.project;
      case "workload":
        return entry.workload.name;
      case "replicaset":
        return entry.replicaSet.name;
      case "pod":
        return entry.pod.name ?? `Pod de ${entry.component?.name ?? "la plataforma"}`;
      case "service":
        return entry.service.name ?? `Service de ${entry.component?.name ?? "la plataforma"}`;
      case "route":
        return entry.route.name;
      case "component":
        return entry.component.name;
      case "node":
        return entry.node.name;
    }
  }

  private addConstellation(constellation: Constellation) {
    const id = namespaceId(constellation.id);
    this.entries.set(id, { kind: "namespace", id, constellation });

    for (const workload of constellation.workloads) {
      this.entries.set(workload.id, { kind: "workload", id: workload.id, workload, constellation });
      for (const pod of workload.pods) {
        this.entries.set(pod.id, { kind: "pod", id: pod.id, pod, ownerId: workload.id, constellation });
      }
      for (const replicaSet of workload.replica_sets) {
        this.entries.set(replicaSet.id, {
          kind: "replicaset",
          id: replicaSet.id,
          replicaSet,
          workload,
          constellation,
        });
        for (const pod of replicaSet.pods) {
          this.entries.set(pod.id, {
            kind: "pod",
            id: pod.id,
            pod,
            ownerId: replicaSet.id,
            constellation,
          });
        }
      }
    }
    for (const service of constellation.services) {
      this.entries.set(service.id, { kind: "service", id: service.id, service, constellation });
      this.indexService(service);
    }
    for (const route of constellation.routes) {
      this.entries.set(route.id, { kind: "route", id: route.id, route, constellation });
      for (const serviceId of route.services) push(this.routesByService, serviceId, route.id);
    }
  }

  private addComponent(component: InfraComponent) {
    const id = componentId(component.id);
    this.entries.set(id, { kind: "component", id, component });
    for (const pod of component.pods) {
      this.entries.set(pod.id, { kind: "pod", id: pod.id, pod, ownerId: id, component });
    }
    for (const service of component.services) {
      this.entries.set(service.id, { kind: "service", id: service.id, service, component });
      this.indexService(service);
    }
  }

  private indexService(service: Service) {
    for (const podId of service.targets) push(this.servicesByPod, podId, service.id);
  }
}

function push(map: Map<string, string[]>, key: string, value: string) {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}
