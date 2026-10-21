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

import type { Layout } from "./layout";
import { RELATION } from "./symbology";

export class RelationLines {
  /** Opacity with nothing selected (the debug panel tunes this). */
  baseOpacity = RELATION.opacity;
  readonly material = new LineBasicMaterial({
    color: new Color(RELATION.color),
    opacity: RELATION.opacity,
    transparent: true,
    blending: AdditiveBlending,
    depthWrite: false,
  });
  readonly object = new LineSegments(new BufferGeometry(), this.material);

  update({ objects, relations }: Layout) {
    const byId = new Map(objects.map((o) => [o.id, o.position]));
    const positions: number[] = [];
    for (const [from, to] of relations) {
      const a = byId.get(from);
      const b = byId.get(to);
      if (a && b) positions.push(a.x, a.y, a.z, b.x, b.y, b.z);
    }
    this.object.geometry.dispose();
    this.object.geometry = new BufferGeometry();
    this.object.geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
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
