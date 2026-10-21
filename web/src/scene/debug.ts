/**
 * Dev-only panel to tune the look live (bloom, object size, relations, nebulae, rotation) and watch fps.
 * Loaded with a dynamic import under `import.meta.env.DEV`, so it never ships.
 */

import GUI from "lil-gui";

import type { GalaxyScene } from "./GalaxyScene";
import { CPU_GLOW } from "./symbology";

export function attachDebugPanel(scene: GalaxyScene) {
  const gui = new GUI({ title: "Astrolabio (dev)" });
  const stats = { fps: 0, quality: scene.quality.level };
  gui.add(stats, "fps").listen().disable();
  gui.add(stats, "quality").listen().disable();
  const timer = setInterval(() => {
    stats.fps = scene.fps;
    stats.quality = scene.quality.level;  // lowered live by the governor
  }, 500);

  const bloom = gui.addFolder("Bloom");
  bloom.add(scene.bloom, "strength", 0, 3, 0.01);
  bloom.add(scene.bloom, "radius", 0, 1.5, 0.01);
  bloom.add(scene.bloom, "threshold", 0, 1, 0.01);

  const objects = gui.addFolder("Objetos");
  objects.add(scene.objects.material.uniforms.uSize!, "value", 0.2, 4, 0.01).name("tamaño");

  // Tune here, then copy the values into CPU_GLOW (symbology.ts).
  const glow = gui.addFolder("Halo de CPU");
  const u = scene.objects.material.uniforms;
  glow.add(u.uHaloMax!, "value", 0, 15, 0.1).name("radio máx.");
  glow.add(u.uHaloMaxPx!, "value", 0, 200, 1).name("halo máx. (px)");
  glow.add(u.uHaloBright!, "value", 0, 3, 0.01).name("intensidad máx.");
  glow.add(u.uInnerGlow!, "value", 0, 2, 0.01).name("resplandor interior");
  glow.add(u.uCoreDim!, "value", 0, 2, 0.01).name("núcleo en reposo");
  glow.add(u.uCoreBright!, "value", 0, 3, 0.01).name("núcleo máx.");
  glow.add(u.uWhiten!, "value", 0, 1, 0.01).name("blanqueo");
  for (const kind of ["node", "component", "workload", "pod"] as const) {
    const shares = CPU_GLOW.haloShare;
    const value = { [kind]: shares[kind] ?? 1 };
    glow
      .add(value, kind, 0, 1, 0.01)
      .name(`halo ${kind}`)
      .onChange((v: number) => {
        shares[kind] = v;
        scene.objects.refresh();
      });
  }
  glow
    .add(CPU_GLOW, "platformPodShare", 0, 1, 0.01)
    .name("halo pod plataforma")
    .onChange(() => scene.objects.refresh());

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
