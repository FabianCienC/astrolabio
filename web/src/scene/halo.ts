/**
 * A glowing ring around the selected object, so it's obvious what is selected.
 *
 * It grows in when something is selected, glides to the new object when the
 * selection changes, fades out when it's cleared, and breathes slowly while
 * shown (not with reduced motion, which keeps it still).
 */

import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  Points,
  ShaderMaterial,
  Vector3,
} from "three";

import { SELECTED_GROWTH, SIZE_SCALE } from "./objects";

/** Halo diameter relative to the selected object's drawn size. */
const HALO_SCALE = 3.2;
/** Never smaller than this on screen, so far selections still read clearly. */
const MIN_HALO_PX = 34;
const FADE_SPEED = 2.5;
/** Higher = the halo catches up with a newly selected object faster. */
const FOLLOW_SMOOTHING = 9;
const WHITE = new Color("#ffffff");

const vertexShader = /* glsl */ `
  uniform float uPixelRatio;
  uniform float uWorldSize;
  uniform float uMinPx;
  uniform float uScale;
  varying float vPixels;

  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    float px = max(uWorldSize * (${SIZE_SCALE.toFixed(1)} / -mvPosition.z), uMinPx);
    gl_PointSize = px * uScale * uPixelRatio;
    vPixels = gl_PointSize;
  }
`;

const fragmentShader = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uBreath;
  varying float vPixels;

  void main() {
    float d = length(gl_PointCoord - 0.5);
    float radius = 0.34 + 0.02 * uBreath;
    // A crisp ring about two pixels wide, plus a soft glow just inside and outside it.
    float width = max(2.0 / vPixels, 0.012);
    float ring = exp(-pow((d - radius) / width, 2.0));
    float glow = exp(-pow((d - radius) / 0.09, 2.0)) * 0.22;
    float alpha = (ring + glow) * uOpacity * smoothstep(0.5, 0.44, d);
    if (alpha <= 0.002) discard;
    gl_FragColor = vec4(uColor * alpha * 0.8, 1.0);
  }
`;

export class SelectionHalo {
  readonly points: Points;
  readonly material: ShaderMaterial;
  private readonly position = new Vector3();
  private readonly goal = new Vector3();
  private amount = 0;
  private visible = false;

  constructor(
    pixelRatio: number,
    private readonly reducedMotion: boolean,
  ) {
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new Float32BufferAttribute([0, 0, 0], 3));
    this.material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uPixelRatio: { value: pixelRatio },
        uWorldSize: { value: 1 },
        uMinPx: { value: MIN_HALO_PX },
        uScale: { value: 0 },
        uColor: { value: new Color() },
        uOpacity: { value: 0 },
        uBreath: { value: 0 },
      },
      blending: AdditiveBlending,
      depthWrite: false,
      transparent: true,
    });
    this.points = new Points(geometry, this.material);
    this.points.frustumCulled = false;
  }

  /** Shows the halo around an object of relative `size` (as drawn) in `color`. */
  show(position: Vector3, size: number, color: Color) {
    this.goal.copy(position);
    if (!this.visible && this.amount === 0) this.position.copy(position); // appear in place
    this.visible = true;
    this.material.uniforms.uWorldSize!.value = size * (1 + SELECTED_GROWTH) * HALO_SCALE;
    this.material.uniforms.uColor!.value = color.clone().lerp(WHITE, 0.15);
  }

  hide() {
    this.visible = false;
  }

  animate(deltaSeconds: number, timeSeconds: number) {
    const step = deltaSeconds * FADE_SPEED;
    this.amount = this.visible ? Math.min(this.amount + step, 1) : Math.max(this.amount - step, 0);
    const eased = this.amount * this.amount * (3 - 2 * this.amount);

    this.position.lerp(this.goal, 1 - Math.exp(-FOLLOW_SMOOTHING * deltaSeconds));
    this.points.position.copy(this.position);

    const uniforms = this.material.uniforms;
    uniforms.uOpacity!.value = eased;
    // Grows in from 60% while fading in, and shrinks back while fading out.
    uniforms.uScale!.value = 0.6 + 0.4 * eased;
    uniforms.uBreath!.value = this.reducedMotion ? 0 : Math.sin(timeSeconds * 1.6);
  }

  dispose() {
    this.points.geometry.dispose();
    this.material.dispose();
  }
}
