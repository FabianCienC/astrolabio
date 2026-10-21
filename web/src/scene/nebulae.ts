/**
 * A soft nebula behind each group, so a project reads as one region of space.
 *
 * Each nebula is a camera-facing plane with an fbm noise shader, sized to its
 * group and tinted from the cool nebula palette.
 */

import {
  AdditiveBlending,
  type Camera,
  DoubleSide,
  Group,
  Mesh,
  PlaneGeometry,
  ShaderMaterial,
  Vector3,
} from "three";

import { groupObjects, isCoreGroup, type PlacedObject } from "./layout";
import { hashString } from "./random";
import { NEBULA, nebulaColor } from "./symbology";

const MIN_RADIUS = 8;
/** Platform system clusters are small and close together: tighter nebulae. */
const MIN_CORE_RADIUS = 4.5;
/** How far the nebula reaches past its farthest object. */
const SPREAD = 1.5;

const vertexShader = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  uniform vec3 uColor;
  uniform float uSeed;
  uniform float uIntensity;
  varying vec2 vUv;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
      mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
      u.y
    );
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 5; i++) {
      value += amplitude * noise(p);
      p *= 2.0;
      amplitude *= 0.5;
    }
    return value;
  }

  void main() {
    vec2 p = vUv - 0.5;
    float falloff = pow(smoothstep(0.5, 0.0, length(p)), 1.6);
    float density = falloff * smoothstep(0.3, 0.85, fbm(p * 3.5 + uSeed));
    gl_FragColor = vec4(uColor * density * uIntensity, 1.0);
  }
`;

export class Nebulae {
  readonly object = new Group();
  /** Intensity with nothing selected (the debug panel tunes this). */
  baseIntensity = NEBULA.intensity;
  /** Shared uniform of every nebula, so they all change together. */
  private readonly intensity = { value: NEBULA.intensity };

  update(objects: PlacedObject[]) {
    this.clear();
    for (const [group, members] of groupObjects(objects)) {
      const center = members
        .reduce((sum, m) => sum.add(m.position), new Vector3())
        .divideScalar(members.length);
      const core = isCoreGroup(group);
      const radius = Math.max(
        core ? MIN_CORE_RADIUS : MIN_RADIUS,
        ...members.map((m) => m.position.distanceTo(center) * SPREAD),
      );
      const hash = hashString(group);
      const mesh = new Mesh(
        new PlaneGeometry(radius * 2, radius * 2),
        new ShaderMaterial({
          vertexShader,
          fragmentShader,
          uniforms: {
            uColor: { value: nebulaColor(core, hash) },
            uSeed: { value: (hash % 1000) / 37 },
            uIntensity: this.intensity,
          },
          blending: AdditiveBlending,
          transparent: true,
          depthWrite: false,
          side: DoubleSide,
        }),
      );
      mesh.position.copy(center);
      mesh.renderOrder = -1; // behind objects and lines
      this.object.add(mesh);
    }
  }

  /** `focus` 0..1: how much a selection pushes the nebulae into the background. */
  setFocus(focus: number) {
    this.intensity.value = this.baseIntensity * (1 - 0.5 * focus);
  }

  /** Billboards: every nebula turns to face the camera. Call once per frame. */
  faceCamera(camera: Camera) {
    for (const mesh of this.object.children) mesh.quaternion.copy(camera.quaternion);
  }

  dispose() {
    this.clear();
  }

  private clear() {
    for (const mesh of this.object.children as Mesh[]) {
      mesh.geometry.dispose();
      (mesh.material as ShaderMaterial).dispose();
    }
    this.object.clear();
  }
}
