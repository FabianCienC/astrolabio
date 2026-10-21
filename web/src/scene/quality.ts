/** Picks how much the device can render: pixel ratio and bloom. */

export type Quality = {
  level: "high" | "low";
  /** Cap on devicePixelRatio; the biggest lever on fill rate. */
  maxPixelRatio: number;
  bloomStrength: number;
};

const HIGH: Quality = { level: "high", maxPixelRatio: 2, bloomStrength: 0.7 };
const LOW: Quality = { level: "low", maxPixelRatio: 1.25, bloomStrength: 0.55 };

/** Heuristic on first load. `?quality=low|high` forces a level (handy to test on a laptop). */
export function detectQuality(): Quality {
  const forced = new URLSearchParams(window.location.search).get("quality");
  if (forced === "low") return LOW;
  if (forced === "high") return HIGH;

  const touch = window.matchMedia("(pointer: coarse)").matches;
  const cores = navigator.hardwareConcurrency ?? 4;
  const memoryGb = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  return touch || cores <= 4 || memoryGb <= 4 ? LOW : HIGH;
}
