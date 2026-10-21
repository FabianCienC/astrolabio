/**
 * Transition between two layouts when the live galaxy changes: objects that stay
 * glide to their new place, new ones grow in where they belong, gone ones shrink
 * away where they were, and relation lines fade in and out with them. Never
 * instant, not even with reduced motion (just shorter).
 *
 * A morph always starts from what is on screen right now (positions and how far
 * each object had grown), so an update arriving mid-transition never jumps.
 */

import type { Vector3 } from "three";

import type { PlacedObject, Relation } from "./layout";

/** An object as drawn this frame: `appear` 0..1 scales its size and brightness. */
export type DrawnObject = PlacedObject & { appear: number };
/** A relation line as drawn this frame: `weight` 0..1 fades it in or out. */
export type DrawnRelation = { from: string; to: string; weight: number };

const DURATION_MS = 1400;
const REDUCED_DURATION_MS = 600;

/** Starts and ends gently: nothing in the scene should lurch. */
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

type Line = { from: string; to: string; fade: "keep" | "in" | "out" };

export class Morph {
  private readonly start: Map<string, { position: Vector3; appear: number }>;
  private readonly leaving: DrawnObject[];
  private readonly lines: Line[];
  private readonly startMs: number;
  private readonly durationMs: number;

  /**
   * `next` is drawn first and in its order (so its indices stay valid for selection and
   * picking); objects that left are appended after it until they have shrunk away.
   */
  constructor(
    current: DrawnObject[],
    currentRelations: Relation[],
    private readonly next: PlacedObject[],
    nextRelations: Relation[],
    nowMs: number,
    reducedMotion: boolean,
  ) {
    this.start = new Map(
      current.map((o) => [o.id, { position: o.position.clone(), appear: o.appear }]),
    );
    const kept = new Set(next.map((o) => o.id));
    this.leaving = current.filter((o) => !kept.has(o.id) && o.appear > 0.001);

    const key = ([a, b]: Relation) => `${a}\u0000${b}`;
    const before = new Set(currentRelations.map(key));
    const after = new Set(nextRelations.map(key));
    this.lines = [
      ...nextRelations.map(([from, to]): Line => ({
        from,
        to,
        fade: before.has(key([from, to])) ? "keep" : "in",
      })),
      ...currentRelations
        .filter((r) => !after.has(key(r)))
        .map(([from, to]): Line => ({ from, to, fade: "out" })),
    ];
    this.startMs = nowMs;
    this.durationMs = reducedMotion ? REDUCED_DURATION_MS : DURATION_MS;
  }

  /** Objects and lines for this frame; `done` once everything has arrived. */
  frame(nowMs: number): { objects: DrawnObject[]; relations: DrawnRelation[]; done: boolean } {
    const t = Math.min(Math.max((nowMs - this.startMs) / this.durationMs, 0), 1);
    const e = ease(t);
    const objects: DrawnObject[] = this.next.map((o) => {
      const from = this.start.get(o.id);
      if (!from) return { ...o, appear: e }; // new: grows in where it belongs
      return {
        ...o,
        position: from.position.clone().lerp(o.position, e),
        appear: from.appear + (1 - from.appear) * e,
      };
    });
    for (const o of this.leaving) objects.push({ ...o, appear: o.appear * (1 - e) });

    const relations = this.lines.map(({ from, to, fade }) => ({
      from,
      to,
      weight: fade === "keep" ? 1 : fade === "in" ? e : 1 - e,
    }));
    return { objects, relations, done: t >= 1 };
  }
}
