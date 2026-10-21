/**
 * What each visual means. The scene draws from these values and the legend
 * renders them, so adding a symbol here keeps both in sync.
 *
 * Color and shape identify the kind of object. Health is not drawn: the sidebar
 * shows it as text for the selected object.
 */

import { Color } from "three";

export const BACKGROUND = new Color("#000000");

/** Shapes the object shader can draw. The index is what the shader receives. */
export const SHAPE = { disc: 0, ring: 1, diamond: 2, triangle: 3 } as const;
export type Shape = keyof typeof SHAPE;

export type ObjectKind =
  | "node"
  | "namespace"
  | "component"
  | "workload"
  | "replicaset"
  | "pod"
  | "service"
  | "route";

/** Every Kubernetes object drawn in the scene: its look and its labels. */
export const OBJECT_KINDS: {
  value: ObjectKind;
  label: string;
  shape: Shape;
  size: number;
  color: string;
}[] = [
  { value: "node", label: "Nodo del clúster", shape: "disc", size: 2, color: "#ffe3a3" },
  { value: "namespace", label: "Proyecto (namespace)", shape: "ring", size: 2.4, color: "#ece8ff" },
  { value: "component", label: "Componente de infraestructura", shape: "disc", size: 1.1, color: "#c4a7ff" },
  { value: "workload", label: "Deployment / StatefulSet", shape: "disc", size: 1.2, color: "#7fe3ff" },
  { value: "replicaset", label: "ReplicaSet activo", shape: "ring", size: 0.85, color: "#5f9dff" },
  { value: "pod", label: "Pod", shape: "disc", size: 0.5, color: "#8df2c4" },
  { value: "service", label: "Service", shape: "diamond", size: 0.95, color: "#ff8fcf" },
  { value: "route", label: "HTTPRoute (entrada pública)", shape: "triangle", size: 1.1, color: "#ffad66" },
];

export const KIND = Object.fromEntries(OBJECT_KINDS.map((k) => [k.value, k])) as Record<
  ObjectKind,
  (typeof OBJECT_KINDS)[number]
>;

export const KIND_COLORS = Object.fromEntries(
  OBJECT_KINDS.map((k) => [k.value, new Color(k.color)]),
) as Record<ObjectKind, Color>;

/** Lines exist only for real relations (never just to group things). */
export const RELATION = {
  label: "Relación real (Service → Pod, ruta → Service)",
  color: "#9fb4ff",
  opacity: 0.28,
};

/** Nebula behind each project: cool, muted hues that stay in the background. */
export const NEBULA = {
  label: "Área de un proyecto o sistema",
  core: "#2c5aa8",
  /** One per platform system cluster in the core: blues, kept apart from project hues. */
  systems: ["#2c5aa8", "#2b6c98", "#3d4fae", "#2e7486", "#4a48a0", "#33608c"],
  palette: ["#3b4fd8", "#5a3fd1", "#2f62c9", "#7a3fb8", "#4656b0"],
  intensity: 0.3,
};

export function nebulaColor(isCore: boolean, hash: number): Color {
  const palette = isCore ? NEBULA.systems : NEBULA.palette;
  return new Color(palette[hash % palette.length]!);
}
