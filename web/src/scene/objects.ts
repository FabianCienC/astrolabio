/**
 * Every Kubernetes object in the scene, drawn as one `Points`.
 *
 * Each object is a flat, uniform shape (disc, ring, diamond or triangle) in its
 * kind's color; the bloom pass gives it its glow. The selected object grows and
 * brightens and the one under the pointer grows a little; both ease in and out.
 */

import {
  AdditiveBlending,
  BufferGeometry,
  Float32BufferAttribute,
  Points,
  ShaderMaterial,
} from "three";

import type { PlacedObject } from "./layout";
import { KIND_COLORS } from "./symbology";

/** Must match the 420.0 and 5.0 in the vertex shader: picking uses the same size. */
export const SIZE_SCALE = 420;
export const MIN_SIZE_PX = 5;
/** Extra size at full highlight; picking uses these too. */
export const SELECTED_GROWTH = 0.7;
export const HOVERED_GROWTH = 0.3;
/** Resting brightness of every object (1 = its full kind color). */
const BASE_BRIGHTNESS = 0.72;
/** Brightness factor of everything else while something is selected. */
export const DIMMED = 0.3;
const SELECTED_BRIGHTNESS = 1.2;
/** Selections per second for the dim-the-rest fade. */
const FOCUS_SPEED = 2.5;

const vertexShader = /* glsl */ `
  uniform float uPixelRatio;
  uniform float uSize;
  // Index and 0..1 amount for the current and the fading-out previous highlight.
  uniform vec4 uSelected;  // (index, amount, previous index, previous amount)
  uniform vec4 uHovered;
  // 0..1: how much a selection dims everything else.
  uniform float uFocus;
  attribute float aSize;
  attribute float aShape;
  attribute float aIndex;
  // 0..1 while an object grows in or shrinks away during a live update (see morph.ts).
  attribute float aAppear;
  attribute vec3 aColor;
  varying vec3 vColor;
  varying float vShape;
  varying float vPixels;

  float amount(vec4 h) {
    return (1.0 - step(0.5, abs(aIndex - h.x))) * h.y + (1.0 - step(0.5, abs(aIndex - h.z))) * h.w;
  }

  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    float selected = amount(uSelected);
    float hovered = amount(uHovered) * (1.0 - selected);

    // Everything rests a little dim; with a selection the rest dims further (hover lifts it
    // back) and the selected object outshines it all, tinted toward white.
    float rest = ${BASE_BRIGHTNESS.toFixed(2)} * mix(1.0, ${DIMMED.toFixed(2)}, uFocus);
    float brightness = mix(mix(rest, ${BASE_BRIGHTNESS.toFixed(2)}, hovered), ${SELECTED_BRIGHTNESS.toFixed(2)}, selected);
    vColor = mix(aColor, vec3(1.0), 0.12 * selected) * brightness * aAppear;
    vShape = aShape;
    float size = uSize * aSize * (1.0 + ${SELECTED_GROWTH.toFixed(2)} * selected + ${HOVERED_GROWTH.toFixed(2)} * hovered);
    gl_PointSize = max(size * uPixelRatio * (420.0 / -mvPosition.z), 5.0 * uPixelRatio) * aAppear;
    vPixels = gl_PointSize;
  }
`;

const fragmentShader = /* glsl */ `
  varying vec3 vColor;
  varying float vShape;
  varying float vPixels;

  // Signed distance (negative inside) of an equilateral triangle, in sprite space.
  float sdTriangle(vec2 p, float r) {
    const float k = 1.7320508;
    p.x = abs(p.x) - r;
    p.y = p.y + r / k;
    if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
    p.x -= clamp(p.x, -2.0 * r, 0.0);
    return -length(p) * sign(p.y);
  }

  void main() {
    vec2 p = gl_PointCoord - 0.5;
    p.y = -p.y;
    int shape = int(vShape + 0.5);
    float d;
    if (shape == 0) {
      d = length(p) - 0.42;                         // disc
    } else if (shape == 1) {
      d = abs(length(p) - 0.36) - 0.06;             // ring
    } else if (shape == 2) {
      d = (abs(p.x) + abs(p.y)) - 0.42;             // diamond
    } else {
      d = sdTriangle(p - vec2(0.0, -0.06), 0.4);    // triangle, pointing up
    }
    // Antialias over about one screen pixel, whatever the sprite size.
    float edge = 1.0 / max(vPixels, 1.0);
    float alpha = 1.0 - smoothstep(-edge, edge, d);
    if (alpha <= 0.0) discard;
    gl_FragColor = vec4(vColor * alpha, 1.0);
  }
`;

/**
 * One highlighted object that eases in, while the previous one eases out.
 * `speed` is how many full transitions per second.
 */
class Highlight {
  index = -1;
  amount = 0;
  private previous = -1;
  private previousAmount = 0;

  constructor(private readonly speed: number) {}

  set(index: number) {
    if (index === this.index) return;
    this.previous = this.index;
    this.previousAmount = this.amount;
    this.index = index;
    this.amount = 0;
  }

  /** Advances the fades and returns the shader uniform (index, amount, prev index, prev amount). */
  step(deltaSeconds: number): [number, number, number, number] {
    const delta = deltaSeconds * this.speed;
    this.amount = Math.min(this.amount + delta, 1);
    this.previousAmount = Math.max(this.previousAmount - delta, 0);
    // Smoothstep, so growth starts and ends gently.
    const ease = (t: number) => t * t * (3 - 2 * t);
    return [this.index, ease(this.amount), this.previous, ease(this.previousAmount)];
  }

  /** Current 0..1 amount for an object, for picking. */
  amountFor(index: number): number {
    if (index === this.index) return this.amount;
    if (index === this.previous) return this.previousAmount;
    return 0;
  }
}

export class ObjectPoints {
  readonly points: Points;
  readonly material: ShaderMaterial;
  private readonly geometry = new BufferGeometry();
  private readonly selected = new Highlight(3);
  private readonly hovered = new Highlight(6);
  private focusAmount = 0;

  constructor(pixelRatio: number) {
    this.material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uPixelRatio: { value: pixelRatio },
        uSize: { value: 1 },
        uSelected: { value: [-1, 0, -1, 0] },
        uHovered: { value: [-1, 0, -1, 0] },
        uFocus: { value: 0 },
      },
      blending: AdditiveBlending,
      depthWrite: false,
      transparent: true,
    });
    this.points = new Points(this.geometry, this.material);
    this.points.frustumCulled = false;
  }

  /** Replaces every object. Cheap at this scale (a few hundred points at most), so a live
   * update can call it every frame while objects move. */
  update(objects: (PlacedObject & { appear?: number })[]) {
    const attribute = (values: number[], size = 1) => new Float32BufferAttribute(values, size);
    const positions = objects.flatMap((o) => [o.position.x, o.position.y, o.position.z]);
    const colors = objects.flatMap((o) => KIND_COLORS[o.kind].toArray());
    this.geometry.setAttribute("position", attribute(positions, 3));
    this.geometry.setAttribute("aColor", attribute(colors, 3));
    this.geometry.setAttribute("aSize", attribute(objects.map((o) => o.size)));
    this.geometry.setAttribute("aShape", attribute(objects.map((o) => o.shape)));
    this.geometry.setAttribute("aIndex", attribute(objects.map((_, i) => i)));
    this.geometry.setAttribute("aAppear", attribute(objects.map((o) => o.appear ?? 1)));
  }

  /** Index into the last `update` list, or -1 for none. */
  setSelected(index: number) {
    this.selected.set(index);
  }

  setHovered(index: number) {
    this.hovered.set(index);
  }

  /** Current size multiplier of an object from its highlights, so picking matches what is drawn. */
  growth(index: number): number {
    const selected = this.selected.amountFor(index);
    return 1 + SELECTED_GROWTH * selected + HOVERED_GROWTH * this.hovered.amountFor(index) * (1 - selected);
  }

  /**
   * 0..1, eased: how much the current selection dims the rest of the scene. Lines and
   * nebulae follow it too, so the whole scene steps back together.
   */
  get focus(): number {
    return this.focusAmount * this.focusAmount * (3 - 2 * this.focusAmount);
  }

  /** Advances highlight fades; call once per frame. */
  animate(deltaSeconds: number) {
    const towards = this.selected.index >= 0 ? 1 : 0;
    const step = deltaSeconds * FOCUS_SPEED;
    this.focusAmount =
      towards > this.focusAmount
        ? Math.min(this.focusAmount + step, 1)
        : Math.max(this.focusAmount - step, 0);
    this.material.uniforms.uFocus!.value = this.focus;
    this.material.uniforms.uSelected!.value = this.selected.step(deltaSeconds);
    this.material.uniforms.uHovered!.value = this.hovered.step(deltaSeconds);
  }

  dispose() {
    this.geometry.dispose();
    this.material.dispose();
  }
}
