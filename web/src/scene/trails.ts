/**
 * A trail of light along each Traefik -> route line, as bright as the route's traffic:
 * visits read as a thick glowing path, with no motion at all (so also with reduced
 * motion, where the travelling pulses are off). Brightness eases between samples.
 */

import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  Points,
  ShaderMaterial,
  type Vector3,
} from "three";

import { TRAFFIC } from "./symbology";

/** One Traefik -> route line and its 0..1 traffic level. */
export type Trail = { from: Vector3; to: Vector3; level: number };

/** World units between two lights of a trail. */
const SPACING = 0.8;
/** Per second: how fast a trail brightens or fades toward its traffic. */
const FOLLOW = 1.5;

const vertexShader = /* glsl */ `
  uniform float uPixelRatio;
  attribute float aLevel;
  varying float vLevel;
  void main() {
    vLevel = aLevel;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = 10.0 * uPixelRatio;
  }
`;

const fragmentShader = /* glsl */ `
  uniform vec3 uColor;
  varying float vLevel;
  void main() {
    float r = length(gl_PointCoord - 0.5) * 2.0;
    float glow = pow(max(1.0 - r, 0.0), 1.6) * vLevel;
    if (glow < 0.004) discard;
    gl_FragColor = vec4(uColor * glow, 1.0);
  }
`;

export class TrafficTrails {
  readonly points: Points;
  private readonly geometry = new BufferGeometry();
  /** Per light: which trail it belongs to, so levels can ease per trail. */
  private owner: number[] = [];
  private current: number[] = [];
  private target: number[] = [];

  constructor(pixelRatio: number) {
    const material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uPixelRatio: { value: pixelRatio },
        uColor: { value: new Color(TRAFFIC.pulseColor) },
      },
      blending: AdditiveBlending,
      transparent: true,
      depthWrite: false,
    });
    this.points = new Points(this.geometry, material);
    this.points.frustumCulled = false;
  }

  /** Lays out the trails; each keeps the brightness it had if it already existed. */
  update(trails: Trail[]) {
    const positions: number[] = [];
    this.owner = [];
    trails.forEach((trail, i) => {
      const length = trail.from.distanceTo(trail.to);
      const count = Math.max(Math.floor(length / SPACING), 2);
      // Skip both ends: the lights run between Traefik and the route, not over them.
      for (let k = 1; k < count; k++) {
        const p = trail.from.clone().lerp(trail.to, k / count);
        positions.push(p.x, p.y, p.z);
        this.owner.push(i);
      }
    });
    this.current = trails.map((_, i) => this.current[i] ?? 0);
    this.target = trails.map((t) => t.level);
    this.geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
    this.geometry.setAttribute("aLevel", new Float32BufferAttribute(this.owner.length, 1));
    this.writeLevels();
  }

  /** Eases each trail toward its traffic; call once per frame. */
  animate(deltaSeconds: number) {
    const k = 1 - Math.exp(-FOLLOW * deltaSeconds);
    let moved = false;
    this.current = this.current.map((value, i) => {
      const next = value + (this.target[i]! - value) * k;
      moved ||= Math.abs(next - value) > 1e-4;
      return next;
    });
    if (moved) this.writeLevels();
  }

  dispose() {
    this.geometry.dispose();
    (this.points.material as ShaderMaterial).dispose();
  }

  private writeLevels() {
    const attribute = this.geometry.getAttribute("aLevel");
    if (!attribute) return;
    this.owner.forEach((trail, i) =>
      attribute.setX(i, this.current[trail]! * TRAFFIC.trailBrightness),
    );
    attribute.needsUpdate = true;
  }
}
