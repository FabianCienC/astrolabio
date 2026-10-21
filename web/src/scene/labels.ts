/**
 * Names floating in the scene: each project and each platform system, so the
 * groups read at a glance. They are HTML (CSS2DRenderer), crisp at any zoom,
 * never catch the pointer, and fade back together with the rest of the scene
 * while something is selected.
 */

import type { Camera, Scene } from "three";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";

import type { Label } from "./layout";

/** Opacity of the labels while something is selected (1 = untouched). */
const FOCUSED_OPACITY = 0.25;

export class SceneLabels {
  private readonly renderer = new CSS2DRenderer();
  private objects: CSS2DObject[] = [];

  constructor(
    private readonly scene: Scene,
    container: HTMLElement,
  ) {
    const element = this.renderer.domElement;
    element.className = "scene-labels";
    container.appendChild(element);
  }

  update(labels: Label[]) {
    this.clear();
    this.objects = labels.map((label) => {
      const element = document.createElement("div");
      element.className = `scene-label scene-label-${label.kind}`;
      element.textContent = label.text;
      const object = new CSS2DObject(element);
      object.position.copy(label.position);
      this.scene.add(object);
      return object;
    });
  }

  setSize(width: number, height: number) {
    this.renderer.setSize(width, height);
  }

  /** `focus` 0..1: how much a selection pushes the labels into the background. */
  setFocus(focus: number) {
    const opacity = String(1 - (1 - FOCUSED_OPACITY) * focus);
    for (const object of this.objects) object.element.style.opacity = opacity;
  }

  render(camera: Camera) {
    this.renderer.render(this.scene, camera);
  }

  dispose() {
    this.clear();
    this.renderer.domElement.remove();
  }

  private clear() {
    for (const object of this.objects) {
      object.element.remove();
      this.scene.remove(object);
    }
    this.objects = [];
  }
}
