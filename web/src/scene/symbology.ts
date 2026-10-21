/**
 * What each visual means. The scene draws from these values and the legend
 * renders them, so adding a symbol here keeps both in sync.
 *
 * Color and shape identify the kind of object. Health is not drawn: the sidebar
 * shows it as text for the selected object.
 */

import { Color } from "three";

/** Deep navy, like the night sky in the references; the stage adds a vignette in CSS. */
export const BACKGROUND = new Color("#060a14");

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
  /** Thin additive lines: where many cross, they add up to a glow. */
  opacity: 0.4,
  /** One color per relation, keyed by the kind it starts from. */
  kinds: [
    { from: "service", label: "Service → los pods que selecciona", color: "#3fd8c6" },
    { from: "route", label: "Ruta → los Services a los que envía tráfico", color: "#9b87ff" },
  ] as { from: ObjectKind; label: string; color: string }[],
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

/**
 * CPU (metrics-server) makes each object a brighter, bigger star: an idle one is a
 * small dim point, a busy one a white-hot core with a wide halo in its kind color.
 * On a log scale, so 2m and 200m read far apart, up to a reference per kind (a
 * node naturally uses far more than a pod). Objects without metrics sit at
 * NEUTRAL_GLOW, a modest star.
 */
export const CPU_GLOW = {
  label: "Halo: uso de CPU (más CPU, estrella más grande y brillante)",
  /** Millicores that count as full glow, per kind. */
  reference: { pod: 100, workload: 200, component: 200, node: 1000 } as Partial<
    Record<ObjectKind, number>
  >,
  /** Halo radius, as a multiple of the core radius, at zero and full glow. */
  haloMin: 0.5,
  haloMax: 11,
  /** Halo intensity at zero and full glow. */
  haloDim: 0.04,
  haloBright: 1.5,
  /** Core brightness at zero and full glow (the core also turns whiter). */
  coreDim: 0.35,
  coreBright: 1.9,
};

/** 0..1 glow of an object from its CPU, or undefined when it has no metrics. */
export function cpuGlow(
  kind: ObjectKind,
  cpuMillicores: number | null | undefined,
): number | undefined {
  const reference = CPU_GLOW.reference[kind];
  if (reference === undefined || cpuMillicores === null || cpuMillicores === undefined) {
    return undefined;
  }
  return Math.min(Math.log10(1 + cpuMillicores) / Math.log10(1 + reference), 1);
}

/** Glow of objects without metrics (Services, routes, or no metrics-server): a modest star. */
export const NEUTRAL_GLOW = 0.35;
