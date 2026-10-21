/**
 * Lines for real, non-ownership relations: a Service to each pod it selects, a
 * route to each Service it sends traffic to. Ownership (pod -> replica set ->
 * workload -> namespace) is shown by position instead, so it needs no line.
 */

import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  LineBasicMaterial,
  LineSegments,
} from "three";

import type { DrawnObject, DrawnRelation } from "./morph";
import { RELATION } from "./symbology";

const COLORS = new Map(RELATION.kinds.map((k) => [k.from, new Color(k.color)]));
const FALLBACK = new Color("#9b87ff");

export class RelationLines {
  /** Opacity with nothing selected (the debug panel tunes this). */
  baseOpacity = RELATION.opacity;
  readonly material = new LineBasicMaterial({
    color: new Color("#ffffff"), // each line carries its own color
    opacity: RELATION.opacity,
    transparent: true,
    blending: AdditiveBlending,
    depthWrite: false,
    // Per-vertex color: the relation's color, scaled by its fade (additive: darker is fainter).
    vertexColors: true,
  });
  readonly object = new LineSegments(new BufferGeometry(), this.material);

  /**
   * Draws each line between its two objects. A line fades with its `weight` and with
   * the less visible of its two ends, so it grows and shrinks along with them.
   */
  update(objects: DrawnObject[], relations: DrawnRelation[]) {
    const byId = new Map(objects.map((o) => [o.id, o]));
    const positions: number[] = [];
    const shades: number[] = [];
    for (const { from, to, weight } of relations) {
      const a = byId.get(from);
      const b = byId.get(to);
      if (!a || !b) continue;
      const shade = weight * Math.min(a.appear, b.appear);
      if (shade <= 0.001) continue;
      positions.push(
        a.position.x,
        a.position.y,
        a.position.z,
        b.position.x,
        b.position.y,
        b.position.z,
      );
      const color = (COLORS.get(a.kind) ?? FALLBACK).clone().multiplyScalar(shade).toArray();
      shades.push(...color, ...color);
    }
    this.object.geometry.dispose();
    this.object.geometry = new BufferGeometry();
    this.object.geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
    this.object.geometry.setAttribute("color", new Float32BufferAttribute(shades, 3));
  }

  /** `focus` 0..1: how much a selection pushes the lines into the background. */
  setFocus(focus: number) {
    this.material.opacity = this.baseOpacity * (1 - 0.65 * focus);
  }

  dispose() {
    this.object.geometry.dispose();
    this.material.dispose();
  }
}
