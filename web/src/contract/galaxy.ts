/* Generated from contract/galaxy.schema.json by npm run gen:contract. Do not edit. */

export interface Galaxy {
  version: 2;
  generated_at: string;
  constellations: Constellation[];
  core: Core;
}
/**
 * A namespace labeled `fabiancienfuegos.com/astrolabio: visible`.
 */
export interface Constellation {
  id: string;
  project: string;
  description: string | null;
  repo: string | null;
  argo: ArgoStatus | null;
  health: "ok" | "degraded" | "down" | "unknown";
  workloads: Workload[];
  services: Service[];
  routes: Route[];
}
/**
 * Sync and health of the Argo CD `Application`.
 *
 * No `revision`: it is a commit of the private GitOps repo.
 */
export interface ArgoStatus {
  sync: "Synced" | "OutOfSync" | "Unknown";
  health: "Healthy" | "Progressing" | "Degraded" | "Suspended" | "Missing" | "Unknown";
}
/**
 * A Deployment, StatefulSet or DaemonSet of a visible project.
 *
 * Deployments own pods through `replica_sets`; StatefulSets and DaemonSets own
 * them directly in `pods`.
 */
export interface Workload {
  id: string;
  name: string;
  kind: "Deployment" | "StatefulSet" | "DaemonSet";
  description: string | null;
  role: ("frontend" | "api" | "worker" | "data") | null;
  criticality: ("high" | "medium" | "low") | null;
  replicas: Replicas;
  health: "ok" | "degraded" | "down" | "unknown";
  commit: Commit | null;
  metrics: Metrics;
  replica_sets: ReplicaSet[];
  pods: Pod[];
}
export interface Replicas {
  desired: number;
  ready: number;
}
/**
 * Deployed commit, taken from the image tag (the SHA set by CI).
 */
export interface Commit {
  sha: string;
  url: string;
}
/**
 * CPU and memory (phase 3, metrics-server). `None` until there is data.
 */
export interface Metrics {
  cpu_millicores: number | null;
  memory_mib: number | null;
}
/**
 * The active replica set of a Deployment (two during a rollout). Old empty ones are not
 * published.
 */
export interface ReplicaSet {
  id: string;
  name: string;
  replicas: Replicas;
  health: "ok" | "degraded" | "down" | "unknown";
  pods: Pod[];
}
/**
 * A pod. `name` is `None` for platform pods, which are published anonymously.
 */
export interface Pod {
  id: string;
  name: string | null;
  phase: "Pending" | "Running" | "Succeeded" | "Failed" | "Unknown";
  ready: boolean;
  restarts: number;
  node: ("control-plane" | "worker-1" | "worker-2") | null;
  health: "ok" | "degraded" | "down" | "unknown";
  metrics: Metrics1;
}
/**
 * CPU and memory (phase 3, metrics-server). `None` until there is data.
 */
export interface Metrics1 {
  cpu_millicores: number | null;
  memory_mib: number | null;
}
/**
 * A Service. `targets` are the ids of the pods it selects. No ports or cluster IP.
 */
export interface Service {
  id: string;
  name: string | null;
  health: "ok" | "degraded" | "down" | "unknown";
  targets: string[];
  traffic: Traffic;
}
/**
 * Requests per second through Traefik (phase 4, Prometheus). `None` until there is data.
 */
export interface Traffic {
  requests_per_second: number | null;
}
/**
 * An `HTTPRoute`: the public entry into a project. Hostnames are public by nature.
 */
export interface Route {
  id: string;
  name: string;
  hostnames: string[];
  health: "ok" | "degraded" | "down" | "unknown";
  services: string[];
  traffic: Traffic1;
}
/**
 * Requests per second through Traefik (phase 4, Prometheus). `None` until there is data.
 */
export interface Traffic1 {
  requests_per_second: number | null;
}
/**
 * The galactic core: platform components and the cluster nodes.
 */
export interface Core {
  components: InfraComponent[];
  nodes: Node[];
}
/**
 * Platform component published from the API's closed catalog.
 *
 * Its pods and services are drawn, but anonymously: no names, versions, image
 * tags, IPs or configuration.
 */
export interface InfraComponent {
  id: string;
  name: string;
  purpose: string;
  category: "control" | "network" | "ingress" | "gitops" | "security";
  system: string;
  replicas: Replicas;
  health: "ok" | "degraded" | "down" | "unknown";
  argo: ArgoStatus | null;
  metrics: Metrics2;
  pods: Pod[];
  services: Service[];
}
/**
 * CPU and memory (phase 3, metrics-server). `None` until there is data.
 */
export interface Metrics2 {
  cpu_millicores: number | null;
  memory_mib: number | null;
}
/**
 * Cluster node, published under a generic name (no hostname or IP).
 */
export interface Node {
  id: "control-plane" | "worker-1" | "worker-2";
  name: "control plane" | "worker 1" | "worker 2";
  role: "control-plane" | "worker";
  health: "ok" | "degraded" | "down" | "unknown";
  pods: number;
  metrics: Metrics3;
}
/**
 * CPU and memory (phase 3, metrics-server). `None` until there is data.
 */
export interface Metrics3 {
  cpu_millicores: number | null;
  memory_mib: number | null;
}
