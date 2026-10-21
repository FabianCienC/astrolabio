/**
 * Health labels for the sidebar. Health is not drawn in the scene (colors there
 * identify object kinds); it is shown as text where the object is described.
 */

import type { Workload } from "../contract/galaxy";

export type Health = Workload["health"];

export const HEALTH_LABEL: Record<Health, string> = {
  ok: "Sano",
  degraded: "Degradado",
  down: "Caído",
  unknown: "Desconocido",
};
