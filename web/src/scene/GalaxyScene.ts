/**
 * The 3D scene, in plain Three.js. React mounts it and talks to it only through
 * this class: `load(galaxy)`, `select(id)`, `dispose()` and the `onSelect` callback.
 * Camera movement lives in `CameraRig`.
 */

import { NoToneMapping, PerspectiveCamera, Scene, Vector2, Vector3, WebGLRenderer } from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

import type { Galaxy } from "../contract/galaxy";
import { CameraRig } from "./cameraRig";
import { SceneLabels } from "./labels";
import { SelectionHalo } from "./halo";
import { layoutGalaxy, type PlacedObject } from "./layout";
import { Nebulae } from "./nebulae";
import { MIN_SIZE_PX, ObjectPoints, SIZE_SCALE } from "./objects";
import { detectQuality, type Quality } from "./quality";
import { RelationLines } from "./relations";
import { BACKGROUND, KIND_COLORS, type ObjectKind } from "./symbology";

export type SceneOptions = {
  /** `prefers-reduced-motion`: no auto-rotation. Transitions stay smooth, just shorter. */
  reducedMotion: boolean;
  /** Called when the user clicks an object (its id) or empty space (null). */
  onSelect: (id: string | null) => void;
  /** Called when the object under the pointer changes or the pointer moves over it. */
  onHover?: (hover: Hover | null) => void;
};

/** The object under the pointer and where the pointer is, in canvas pixels. */
export type Hover = { id: string; x: number; y: number };

/** How far the camera stays from each kind of object when flying to it. */
const FOCUS_DISTANCE: Record<ObjectKind, number> = {
  node: 16,
  namespace: 30,
  component: 14,
  workload: 14,
  replicaset: 10,
  pod: 8,
  service: 12,
  route: 14,
};
/** Extra pixels around each object that still count as a hit. */
const PICK_SLOP_PX = 4;
/** Pointer movement below this is a click; above it, the user is orbiting or panning. */
const CLICK_MAX_MOVE_PX = 5;

export class GalaxyScene {
  readonly quality: Quality;
  readonly renderer: WebGLRenderer;
  readonly camera: PerspectiveCamera;
  readonly rig: CameraRig;
  readonly bloom: UnrealBloomPass;
  readonly objects: ObjectPoints;
  readonly halo: SelectionHalo;
  readonly labels: SceneLabels;
  readonly relations = new RelationLines();
  readonly nebulae = new Nebulae();
  /** Last measured frames per second, for the debug panel. */
  fps = 0;

  private readonly scene = new Scene();
  private readonly composer: EffectComposer;
  private readonly resizeObserver: ResizeObserver;
  private readonly options: SceneOptions;
  private placed: PlacedObject[] = [];
  private indexById = new Map<string, number>();
  private selectedId: string | null = null;
  private pointerDown: { x: number; y: number } | null = null;
  private pointer: { x: number; y: number } | null = null;
  /** Last hover sent to `onHover`, to only notify on change. */
  private lastHover: Hover | null = null;
  private lastFrame = performance.now();
  private frames = 0;
  private fpsSince = performance.now();

  constructor(
    private readonly canvas: HTMLCanvasElement,
    options: SceneOptions,
  ) {
    this.options = options;
    this.quality = detectQuality();
    const pixelRatio = Math.min(window.devicePixelRatio, this.quality.maxPixelRatio);

    this.renderer = new WebGLRenderer({ canvas, antialias: false, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(pixelRatio);
    // No tone mapping: filmic curves push bright colors to white, and shapes must keep their hue.
    this.renderer.toneMapping = NoToneMapping;
    this.scene.background = BACKGROUND;

    this.camera = new PerspectiveCamera(55, 1, 0.1, 2000);
    this.rig = new CameraRig(this.camera, canvas, options.reducedMotion);

    this.objects = new ObjectPoints(pixelRatio);
    this.halo = new SelectionHalo(pixelRatio, options.reducedMotion);
    this.labels = new SceneLabels(this.scene, canvas.parentElement!);
    this.scene.add(
      this.nebulae.object,
      this.relations.object,
      this.halo.points,
      this.objects.points,
    );

    this.composer = new EffectComposer(this.renderer);
    this.composer.setPixelRatio(pixelRatio);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new Vector2(1, 1), this.quality.bloomStrength, 0, 0.1);
    // Tight glow hugging each shape: keep the sharp mips, drop the wide ones that
    // add up to a haze over the whole core. (Index 0 is the sharpest of the 5 mips.)
    this.bloom.compositeMaterial.uniforms.bloomFactors!.value = [1, 0.7, 0.25, 0, 0];
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointerup", this.onPointerUp);
    canvas.addEventListener("pointermove", this.onPointerMove);
    canvas.addEventListener("pointerleave", this.onPointerLeave);
    canvas.addEventListener("contextmenu", this.onContextMenu);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this.resize();

    this.renderer.setAnimationLoop((time) => this.frame(time));
  }

  load(galaxy: Galaxy) {
    const layout = layoutGalaxy(galaxy);
    this.placed = layout.objects;
    this.indexById = new Map(layout.objects.map((o, i) => [o.id, i]));
    this.objects.update(layout.objects);
    this.relations.update(layout);
    this.nebulae.update(layout.objects);
    this.labels.update(layout.labels);
    this.objects.setSelected(this.indexOf(this.selectedId));
    this.updateHalo();
  }

  /** Highlights an object and flies to it; `null` clears the selection and flies home. */
  select(id: string | null) {
    const hadSelection = this.selectedId !== null;
    this.selectedId = id;
    const index = this.indexOf(id);
    this.objects.setSelected(index);
    this.updateHalo();
    if (index >= 0) {
      const object = this.placed[index]!;
      this.rig.flyTo(object.position, FOCUS_DISTANCE[object.kind]);
    } else if (hadSelection) {
      this.rig.home();
    }
  }

  dispose() {
    this.renderer.setAnimationLoop(null);
    this.canvas.removeEventListener("pointerdown", this.onPointerDown);
    this.canvas.removeEventListener("pointerup", this.onPointerUp);
    this.canvas.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("pointerleave", this.onPointerLeave);
    this.canvas.removeEventListener("contextmenu", this.onContextMenu);
    this.resizeObserver.disconnect();
    this.rig.dispose();
    this.objects.dispose();
    this.halo.dispose();
    this.labels.dispose();
    this.relations.dispose();
    this.nebulae.dispose();
    this.composer.dispose();
    this.renderer.dispose();
  }

  private updateHalo() {
    const object = this.placed[this.indexOf(this.selectedId)];
    if (object) this.halo.show(object.position, object.size, KIND_COLORS[object.kind]);
    else this.halo.hide();
  }

  private notifyHover(index: number) {
    const next: Hover | null =
      index >= 0 && this.pointer
        ? { id: this.placed[index]!.id, x: this.pointer.x, y: this.pointer.y }
        : null;
    const last = this.lastHover;
    const same =
      next === last ||
      (next !== null && last !== null && next.id === last.id && next.x === last.x && next.y === last.y);
    if (same) return;
    this.lastHover = next;
    this.options.onHover?.(next);
  }

  private indexOf(id: string | null): number {
    return id === null ? -1 : (this.indexById.get(id) ?? -1);
  }

  /**
   * The object under a canvas point, or -1. Projects every object to the screen
   * and checks its drawn radius (same formula as the vertex shader, highlights
   * included), so small far objects stay clickable. Nearest to the camera wins.
   */
  private pick(x: number, y: number): number {
    const { clientWidth: width, clientHeight: height } = this.canvas;
    const uSize = this.objects.material.uniforms.uSize!.value as number;
    const projected = new Vector3();
    const view = new Vector3();
    let best = -1;
    let bestDepth = Infinity;
    this.placed.forEach((object, i) => {
      view.copy(object.position).applyMatrix4(this.camera.matrixWorldInverse);
      const depth = -view.z;
      if (depth <= 0) return;
      projected.copy(object.position).project(this.camera);
      const sx = ((projected.x + 1) / 2) * width;
      const sy = ((1 - projected.y) / 2) * height;
      const size = uSize * object.size * this.objects.growth(i);
      const radius = Math.max((size * SIZE_SCALE) / depth, MIN_SIZE_PX) / 2;
      if (Math.hypot(sx - x, sy - y) <= radius + PICK_SLOP_PX && depth < bestDepth) {
        best = i;
        bestDepth = depth;
      }
    });
    return best;
  }

  private onPointerDown = (event: PointerEvent) => {
    this.pointerDown = { x: event.offsetX, y: event.offsetY };
  };

  private onPointerUp = (event: PointerEvent) => {
    const down = this.pointerDown;
    this.pointerDown = null;
    // Only a left click without movement selects; drags orbit, right/shift drags pan.
    if (event.button !== 0 || event.shiftKey || !down) return;
    if (Math.hypot(event.offsetX - down.x, event.offsetY - down.y) > CLICK_MAX_MOVE_PX) return;
    const index = this.pick(event.offsetX, event.offsetY);
    this.options.onSelect(index < 0 ? null : this.placed[index]!.id);
  };

  private onPointerMove = (event: PointerEvent) => {
    this.pointer = { x: event.offsetX, y: event.offsetY };
  };

  private onPointerLeave = () => {
    this.pointer = null;
  };

  /** Right-drag pans; don't open the browser menu over the scene. */
  private onContextMenu = (event: Event) => {
    event.preventDefault();
  };

  private resize() {
    const { clientWidth: width, clientHeight: height } = this.canvas;
    if (width === 0 || height === 0) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
    this.composer.setSize(width, height);
    this.labels.setSize(width, height);
  }

  private frame(nowMs: number) {
    // Clamp the step so a backgrounded tab doesn't jump on return.
    const delta = Math.min((nowMs - this.lastFrame) / 1000, 0.1);
    this.lastFrame = nowMs;

    this.rig.update(nowMs, delta);
    this.nebulae.faceCamera(this.camera);

    // Hover: only while no button is held, so orbiting doesn't flicker the highlight.
    const hovered =
      this.pointer && !this.pointerDown ? this.pick(this.pointer.x, this.pointer.y) : -1;
    this.objects.setHovered(hovered);
    this.notifyHover(hovered);
    this.objects.animate(delta);
    this.halo.animate(delta, nowMs / 1000);
    // The rest of the scene steps back together with the objects while something is selected.
    this.relations.setFocus(this.objects.focus);
    this.nebulae.setFocus(this.objects.focus);
    this.labels.setFocus(this.objects.focus);
    this.canvas.style.cursor = hovered >= 0 ? "pointer" : "";

    this.composer.render();
    this.labels.render(this.camera);

    this.frames++;
    if (nowMs - this.fpsSince >= 1000) {
      this.fps = Math.round((this.frames * 1000) / (nowMs - this.fpsSince));
      this.frames = 0;
      this.fpsSince = nowMs;
    }
  }
}
