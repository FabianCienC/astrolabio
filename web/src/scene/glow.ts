/** CPU of every object that has metrics, as the 0..1 glow the shader draws. */

import type { Galaxy } from "../contract/galaxy";
import { componentId, nodeId } from "../model/ids";
import { cpuGlow } from "./symbology";

export function glowById(galaxy: Galaxy): Map<string, number> {
  const glow = new Map<string, number>();
  const set = (id: string, value: number | undefined) => {
    if (value !== undefined) glow.set(id, value);
  };
  for (const c of galaxy.constellations) {
    for (const w of c.workloads) {
      set(w.id, cpuGlow("workload", w.metrics.cpu_millicores));
      for (const p of [...w.pods, ...w.replica_sets.flatMap((rs) => rs.pods)]) {
        set(p.id, cpuGlow("pod", p.metrics.cpu_millicores));
      }
    }
  }
  for (const c of galaxy.core.components) {
    set(componentId(c.id), cpuGlow("component", c.metrics.cpu_millicores));
    for (const p of c.pods) set(p.id, cpuGlow("pod", p.metrics.cpu_millicores));
  }
  for (const n of galaxy.core.nodes) set(nodeId(n.id), cpuGlow("node", n.metrics.cpu_millicores));
  return glow;
}
