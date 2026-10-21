/**
 * Light pulses travelling the incoming-traffic paths: along the Traefik -> route line,
 * then on to the route's Service. The busier the path, the more pulses; none with
 * reduced motion (the lines' brightness carries the same news without moving).
 */

import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  CurvePath,
  Float32BufferAttribute,
  LineCurve3,
  Points,
  ShaderMaterial,
  Vector3,
} from "three";

import { TRAFFIC } from "./symbology";

/** One path requests take, and how many per second. */
export type Flow = { from: Vector3; route: Vector3; service: Vector3; rps: number };

const MAX_PULSES = 256;

const vertexShader = /* glsl */ `
  uniform float uPixelRatio;
  attribute float aLife;
  varying float vLife;
  void main() {
    vLife = aLife;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = 9.0 * uPixelRatio;
  }
`;

const fragmentShader = /* glsl */ `
  uniform vec3 uColor;
  varying float vLife;
  void main() {
    float r = length(gl_PointCoord - 0.5) * 2.0;
    // A bright head with a soft edge; fades in at Traefik and out at the Service.
    float glow = pow(max(1.0 - r, 0.0), 2.0);
    float fade = smoothstep(0.0, 0.08, vLife) * (1.0 - smoothstep(0.85, 1.0, vLife));
    if (glow * fade < 0.003) discard;
    gl_FragColor = vec4(uColor * glow * fade, 1.0);
  }
`;

type Path = { curve: CurvePath<Vector3>; rate: number; due: number };

export class TrafficPulses {
  readonly points: Points;
  private readonly geometry = new BufferGeometry();
  private readonly positions = new Float32Array(MAX_PULSES * 3);
  private readonly lives = new Float32Array(MAX_PULSES);
  private paths: Path[] = [];
  /** Each live pulse: its path and how far along it is (0..1). */
  private pulses: { path: Path; t: number }[] = [];

  constructor(
    pixelRatio: number,
    private readonly reducedMotion: boolean,
  ) {
    this.geometry.setAttribute("position", new Float32BufferAttribute(this.positions, 3));
    this.geometry.setAttribute("aLife", new Float32BufferAttribute(this.lives, 1));
    this.geometry.setDrawRange(0, 0);
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

  /** The paths requests take now; pulses already in flight finish their trip. */
  setFlows(flows: Flow[]) {
    if (this.reducedMotion) return;
    this.paths = flows
      .filter((f) => f.rps > 0)
      .map((f) => {
        // Along the drawn line to the route, then on to the Service: a polyline, so pulses
        // ride exactly on the lines instead of cutting across.
        const curve = new CurvePath<Vector3>();
        curve.add(new LineCurve3(f.from, f.route));
        curve.add(new LineCurve3(f.route, f.service));
        return { curve, rate: Math.min(f.rps, TRAFFIC.maxRate), due: Math.random() };
      });
  }

  /** Spawns, moves and retires pulses; call once per frame. */
  animate(deltaSeconds: number) {
    if (this.reducedMotion) return;
    for (const path of this.paths) {
      path.due -= deltaSeconds * path.rate;
      while (path.due <= 0 && this.pulses.length < MAX_PULSES) {
        this.pulses.push({ path, t: 0 });
        path.due += 1;
      }
    }
    const step = deltaSeconds / TRAFFIC.travelSeconds;
    this.pulses = this.pulses.filter((p) => (p.t += step) < 1);

    const point = new Vector3();
    this.pulses.forEach((p, i) => {
      p.path.curve.getPointAt(p.t, point);
      point.toArray(this.positions, i * 3);
      this.lives[i] = p.t;
    });
    this.geometry.attributes.position!.needsUpdate = true;
    this.geometry.attributes.aLife!.needsUpdate = true;
    this.geometry.setDrawRange(0, this.pulses.length);
  }

  dispose() {
    this.geometry.dispose();
    (this.points.material as ShaderMaterial).dispose();
  }
}
