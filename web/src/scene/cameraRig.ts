/**
 * Everything that moves the camera, so it always moves smoothly.
 *
 * OrbitControls handles rotate and pan (with damping) and touch gestures. On
 * top of it this rig adds:
 *   - wheel zoom that glides to a goal distance instead of jumping, and zooms
 *     toward the point under the cursor;
 *   - flights to an object, and back home, along an arc with an eased curve;
 *   - a pan limit, so the galaxy can't be dragged out of view.
 */

import { type PerspectiveCamera, Plane, Raycaster, Vector2, Vector3 } from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const HOME_TARGET = new Vector3(0, 0, 0);
/** Seen from above at an angle, like looking down at a galaxy disc. */
const HOME_OFFSET = new Vector3(0, 88, 64);
const MIN_DISTANCE = 4;
const MAX_DISTANCE = 220;
/** How far from the center the orbit target may be panned. */
const PAN_LIMIT = 80;
/** Wheel sensitivity: distance is multiplied by exp(deltaY * this). */
const WHEEL_SPEED = 0.0012;
/** Higher = the zoom catches up with its goal faster. */
const ZOOM_SMOOTHING = 7;
const AUTO_ROTATE_SPEED = 0.12;

type Flight = {
  fromTarget: Vector3;
  toTarget: Vector3;
  fromDirection: Vector3;
  toDirection: Vector3;
  fromDistance: number;
  toDistance: number;
  start: number;
  duration: number;
  /** Resume the slow auto-rotation when the flight ends (going home). */
  thenRotate: boolean;
};

const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export class CameraRig {
  readonly controls: OrbitControls;
  private flight: Flight | null = null;
  private distanceGoal: number | null = null;
  private targetGoal: Vector3 | null = null;
  private readonly ground = new Plane(new Vector3(0, 1, 0), 0);
  private readonly raycaster = new Raycaster();

  constructor(
    private readonly camera: PerspectiveCamera,
    private readonly canvas: HTMLCanvasElement,
    private readonly reducedMotion: boolean,
  ) {
    camera.position.copy(HOME_TARGET).add(HOME_OFFSET);

    this.controls = new OrbitControls(camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.rotateSpeed = 0.6;
    this.controls.enablePan = true;
    // Pan slides along the galaxy plane instead of the screen plane.
    this.controls.screenSpacePanning = false;
    this.controls.panSpeed = 0.8;
    this.controls.minDistance = MIN_DISTANCE;
    this.controls.maxDistance = MAX_DISTANCE;
    // Never edge-on: projects are laid out on the disc plane and would collapse into lines.
    this.controls.maxPolarAngle = 1.1;
    this.controls.autoRotate = !reducedMotion;
    this.controls.autoRotateSpeed = AUTO_ROTATE_SPEED;
    this.controls.addEventListener("start", this.onUserStart);

    // Capture phase, so this runs before OrbitControls' own (instant) wheel zoom and replaces it.
    canvas.addEventListener("wheel", this.onWheel, { capture: true, passive: false });
  }

  /** Flies to look at `target` from `distance`, keeping roughly the current viewing angle. */
  flyTo(target: Vector3, distance: number) {
    this.controls.autoRotate = false;
    this.startFlight(target, this.direction(), distance, false);
  }

  /** Flies back to the initial view and resumes the slow rotation. */
  home() {
    this.startFlight(HOME_TARGET, HOME_OFFSET.clone().normalize(), HOME_OFFSET.length(), true);
  }

  update(nowMs: number, deltaSeconds: number) {
    if (this.flight) {
      this.stepFlight(nowMs);
    } else if (this.distanceGoal !== null || this.targetGoal !== null) {
      this.stepZoom(deltaSeconds);
    }
    // Past the pan limit, pull target and camera back together so the view doesn't tilt.
    const before = this.controls.target.clone();
    this.clampTarget(this.controls.target);
    this.camera.position.add(this.controls.target.clone().sub(before));
    this.controls.update(deltaSeconds);
  }

  dispose() {
    this.canvas.removeEventListener("wheel", this.onWheel, { capture: true });
    this.controls.removeEventListener("start", this.onUserStart);
    this.controls.dispose();
  }

  private startFlight(target: Vector3, direction: Vector3, distance: number, thenRotate: boolean) {
    this.distanceGoal = null;
    this.targetGoal = null;
    const toDistance = Math.min(Math.max(distance, MIN_DISTANCE), MAX_DISTANCE);
    const fromDistance = this.distance();
    const fromCamera = this.camera.position.clone();
    const toCamera = target.clone().addScaledVector(direction, toDistance);
    // Longer trips take longer, within limits, so short hops stay snappy and big ones calm.
    const travel = fromCamera.distanceTo(toCamera);
    this.flight = {
      fromTarget: this.controls.target.clone(),
      toTarget: target.clone(),
      fromDirection: this.direction(),
      toDirection: direction.clone().normalize(),
      fromDistance,
      toDistance,
      start: performance.now(),
      // Always animated; with reduced motion, shorter so it reads as a transition, not a ride.
      duration: Math.min(Math.max(0.7 + travel / 90, 0.9), this.reducedMotion ? 1 : 1.8) * 1000,
      thenRotate,
    };
  }

  private stepFlight(nowMs: number) {
    const f = this.flight!;
    const t = Math.min((nowMs - f.start) / f.duration, 1);
    const e = easeInOutCubic(t);
    const target = new Vector3().lerpVectors(f.fromTarget, f.toTarget, e);
    // Direction and distance are blended separately, so the camera swings along an arc
    // around the target instead of cutting straight through the scene.
    const direction = new Vector3().lerpVectors(f.fromDirection, f.toDirection, e).normalize();
    // Geometric blend: zooming from 90 to 9 feels as even as zooming from 9 to 0.9.
    const distance = f.fromDistance * Math.pow(f.toDistance / f.fromDistance, e);
    this.place(target, direction, distance);
    if (t >= 1) {
      this.flight = null;
      if (f.thenRotate && !this.reducedMotion) this.controls.autoRotate = true;
    }
  }

  private stepZoom(deltaSeconds: number) {
    // Exponential smoothing: frame-rate independent, eases out naturally.
    const k = 1 - Math.exp(-ZOOM_SMOOTHING * deltaSeconds);
    const target = this.controls.target.clone();
    if (this.targetGoal) target.lerp(this.targetGoal, k);
    const current = this.distance();
    const goal = this.distanceGoal ?? current;
    const distance = current + (goal - current) * k;
    this.place(target, this.direction(), distance);

    const settled =
      Math.abs(goal - distance) < 0.01 &&
      (!this.targetGoal || target.distanceTo(this.targetGoal) < 0.01);
    if (settled) {
      this.distanceGoal = null;
      this.targetGoal = null;
    }
  }

  private onWheel = (event: WheelEvent) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    this.flight = null;
    this.controls.autoRotate = false;

    // Lines (Firefox) and pages are much bigger units than pixels.
    const unit = event.deltaMode === 1 ? 33 : event.deltaMode === 2 ? 800 : 1;
    const factor = Math.exp(event.deltaY * unit * WHEEL_SPEED);
    const from = this.distanceGoal ?? this.distance();
    const to = Math.min(Math.max(from * factor, MIN_DISTANCE), MAX_DISTANCE);
    this.distanceGoal = to;

    // Zooming in drifts the view toward the point under the cursor, like a map.
    if (to < from) {
      const point = this.groundPointAt(event.offsetX, event.offsetY);
      if (point) {
        const goal = this.targetGoal ?? this.controls.target.clone();
        goal.lerp(point, 1 - to / from);
        this.clampTarget(goal);
        this.targetGoal = goal;
      }
    }
  };

  /** The user grabbed the camera: they're in charge until they select something again. */
  private onUserStart = () => {
    this.flight = null;
    this.targetGoal = null;
    this.controls.autoRotate = false;
  };

  private groundPointAt(x: number, y: number): Vector3 | null {
    const ndc = new Vector2(
      (x / this.canvas.clientWidth) * 2 - 1,
      -(y / this.canvas.clientHeight) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    return this.raycaster.ray.intersectPlane(this.ground, new Vector3());
  }

  private place(target: Vector3, direction: Vector3, distance: number) {
    this.controls.target.copy(target);
    this.camera.position.copy(target).addScaledVector(direction, distance);
  }

  private direction(): Vector3 {
    return this.camera.position.clone().sub(this.controls.target).normalize();
  }

  private distance(): number {
    return this.camera.position.distanceTo(this.controls.target);
  }

  private clampTarget(target: Vector3) {
    const flat = Math.hypot(target.x, target.z);
    if (flat > PAN_LIMIT) {
      target.x *= PAN_LIMIT / flat;
      target.z *= PAN_LIMIT / flat;
    }
  }
}
