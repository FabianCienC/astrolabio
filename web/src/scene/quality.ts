/**
 * How much the device can render (pixel ratio and bloom), picked on load and then
 * lowered automatically while the frame rate stays below what the level needs.
 */

export type QualityLevel = "high" | "low" | "minimal";

export type Quality = {
  level: QualityLevel;
  /** Cap on devicePixelRatio; the biggest lever on fill rate. */
  maxPixelRatio: number;
  /** Bloom stays at every level (it is part of the look); it only softens. */
  bloomStrength: number;
  /** Below this sustained fps the next level down is used. */
  minFps: number;
};

export const QUALITY: Record<QualityLevel, Quality> = {
  high: { level: "high", maxPixelRatio: 2, bloomStrength: 0.7, minFps: 40 },
  low: { level: "low", maxPixelRatio: 1.25, bloomStrength: 0.55, minFps: 28 },
  minimal: { level: "minimal", maxPixelRatio: 1, bloomStrength: 0.5, minFps: 0 },
};

const NEXT: Record<QualityLevel, QualityLevel | null> = { high: "low", low: "minimal", minimal: null };

/** `?quality=high|low|minimal` forces a level and turns adaptation off (to test on a laptop). */
export function forcedQuality(): Quality | null {
  const forced = new URLSearchParams(window.location.search).get("quality");
  return forced && forced in QUALITY ? QUALITY[forced as QualityLevel] : null;
}

/** Heuristic on first load, before any frame has been measured. */
export function detectQuality(): Quality {
  const touch = window.matchMedia("(pointer: coarse)").matches;
  const cores = navigator.hardwareConcurrency ?? 4;
  const memoryGb = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  return touch || cores <= 4 || memoryGb <= 4 ? QUALITY.low : QUALITY.high;
}

/**
 * Steps quality down when the measured fps stays under the level's minimum.
 * It never steps back up: oscillating between levels would look worse than
 * staying a notch lower.
 */
export class QualityGovernor {
  /** Load spikes (shader compiles, first layout) are not the device's real pace. */
  private static readonly WARMUP_MS = 4000;
  /** Consecutive one-second samples below the minimum before stepping down. */
  private static readonly SLOW_SAMPLES = 3;

  private slow = 0;
  private readonly startedAt = performance.now();

  constructor(private level: QualityLevel) {}

  /** Feed one fps sample (one per second); returns the new quality when it steps down. */
  sample(fps: number, nowMs: number): Quality | null {
    if (nowMs - this.startedAt < QualityGovernor.WARMUP_MS) return null;
    const next = NEXT[this.level];
    if (!next) return null;
    this.slow = fps < QUALITY[this.level].minFps ? this.slow + 1 : 0;
    if (this.slow < QualityGovernor.SLOW_SAMPLES) return null;
    this.slow = 0;
    this.level = next;
    return QUALITY[next];
  }
}
