/**
 * Names floating in the scene: each project and each platform system, so the
 * groups read at a glance. They are HTML (CSS2DRenderer), crisp at any zoom,
 * never catch the pointer, and fade back together with the rest of the scene
 * while something is selected. With live updates they drift to their new place,
 * and fade in or out as projects and systems come and go.
 */

import { type Camera, type Scene, Vector3 } from "three";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";

import type { Label } from "./layout";

/** Opacity of the labels while something is selected (1 = untouched). */
const FOCUSED_OPACITY = 0.25;
/** How fast a label drifts to its new place and fades in or out (per second). */
const FOLLOW = 2.2;
const REDUCED_FOLLOW = 5;

type Floating = { object: CSS2DObject; goal: Vector3; visible: number; appear: number };

export class SceneLabels {
  private readonly renderer = new CSS2DRenderer();
  private readonly labels = new Map<string, Floating>();
  private focus = 0;

  constructor(
    private readonly scene: Scene,
    container: HTMLElement,
    private readonly reducedMotion = false,
  ) {
    const element = this.renderer.domElement;
    element.className = "scene-labels";
    container.appendChild(element);
  }

  /** Sets where each label should be; `animate` carries them there. */
  update(labels: Label[]) {
    const ids = new Set(labels.map((l) => l.id));
    for (const [id, label] of this.labels) if (!ids.has(id)) label.visible = 0;
    for (const label of labels) {
      const existing = this.labels.get(label.id);
      if (existing) {
        existing.goal.copy(label.position);
        existing.visible = 1;
        existing.object.element.textContent = label.text;
        continue;
      }
      const element = document.createElement("div");
      element.className = `scene-label scene-label-${label.kind}`;
      element.textContent = label.text;
      element.style.opacity = "0";
      const object = new CSS2DObject(element);
      object.position.copy(label.position);
      this.scene.add(object);
      this.labels.set(label.id, { object, goal: label.position.clone(), visible: 1, appear: 0 });
    }
  }

  /** Eases every label toward its place and visibility; call once per frame. */
  animate(deltaSeconds: number) {
    const k = 1 - Math.exp(-(this.reducedMotion ? REDUCED_FOLLOW : FOLLOW) * deltaSeconds);
    const focusOpacity = 1 - (1 - FOCUSED_OPACITY) * this.focus;
    for (const [id, label] of this.labels) {
      label.object.position.lerp(label.goal, k);
      label.appear += (label.visible - label.appear) * k;
      label.object.element.style.opacity = String(label.appear * focusOpacity);
      if (label.visible === 0 && label.appear < 0.005) {
        this.remove(label);
        this.labels.delete(id);
      }
    }
  }

  setSize(width: number, height: number) {
    this.renderer.setSize(width, height);
  }

  /** `focus` 0..1: how much a selection pushes the labels into the background. */
  setFocus(focus: number) {
    this.focus = focus;
  }

  render(camera: Camera) {
    this.renderer.render(this.scene, camera);
  }

  dispose() {
    for (const label of this.labels.values()) this.remove(label);
    this.labels.clear();
    this.renderer.domElement.remove();
  }

  private remove({ object }: Floating) {
    object.element.remove();
    this.scene.remove(object);
  }
}
