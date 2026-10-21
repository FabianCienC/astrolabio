/**
 * Dev-only panel to tune the look live (bloom, object size, relations, nebulae, rotation) and watch fps.
 * Loaded with a dynamic import under `import.meta.env.DEV`, so it never ships.
 */

import GUI from "lil-gui";

import type { GalaxyScene } from "./GalaxyScene";

export function attachDebugPanel(scene: GalaxyScene) {
  const gui = new GUI({ title: "Astrolabio (dev)" });
  const stats = { fps: 0, quality: scene.quality.level };
  gui.add(stats, "fps").listen().disable();
  gui.add(stats, "quality").disable();
  const timer = setInterval(() => (stats.fps = scene.fps), 500);

  const bloom = gui.addFolder("Bloom");
  bloom.add(scene.bloom, "strength", 0, 3, 0.01);
  bloom.add(scene.bloom, "radius", 0, 1.5, 0.01);
  bloom.add(scene.bloom, "threshold", 0, 1, 0.01);

  const objects = gui.addFolder("Objetos");
  objects.add(scene.objects.material.uniforms.uSize!, "value", 0.2, 4, 0.01).name("tamaño");

  const groups = gui.addFolder("Proyectos");
  groups.add(scene.relations, "baseOpacity", 0, 1, 0.01).name("relaciones");
  groups.add(scene.nebulae, "baseIntensity", 0, 1, 0.01).name("nebulosa");

  const camera = gui.addFolder("Cámara");
  camera.add(scene.rig.controls, "autoRotate").name("rotación");
  camera.add(scene.rig.controls, "autoRotateSpeed", 0, 1, 0.01).name("velocidad");

  return () => {
    clearInterval(timer);
    gui.destroy();
  };
}
