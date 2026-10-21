import { useEffect, useRef } from "react";

import type { Galaxy } from "../contract/galaxy";
import { GalaxyScene, type Hover } from "../scene/GalaxyScene";

type Props = {
  galaxy: Galaxy;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (hover: Hover | null) => void;
  /** The device can't create a WebGL context: the page falls back to the list view. */
  onUnavailable: () => void;
};

/** Mounts the Three.js scene on a canvas. React only owns its lifecycle and the selection. */
export function SceneCanvas({ galaxy, selectedId, onSelect, onHover, onUnavailable }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<GalaxyScene | null>(null);
  // The scene keeps its callbacks for its whole life; these refs always point to the latest.
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onHoverRef = useRef(onHover);
  onHoverRef.current = onHover;

  useEffect(() => {
    let scene: GalaxyScene;
    try {
      scene = new GalaxyScene(canvasRef.current!, {
        reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        onSelect: (id) => onSelectRef.current(id),
        onHover: (hover) => onHoverRef.current(hover),
      });
    } catch {
      // Three.js throws when the browser has no WebGL (disabled, blocklisted GPU...).
      onUnavailable();
      return;
    }
    sceneRef.current = scene;

    // StrictMode mounts twice in dev: only attach the panel if this scene is still alive.
    let disposed = false;
    let detachDebug: (() => void) | undefined;
    if (import.meta.env.DEV) {
      void import("../scene/debug").then(({ attachDebugPanel }) => {
        if (!disposed) detachDebug = attachDebugPanel(scene);
      });
    }
    return () => {
      disposed = true;
      detachDebug?.();
      scene.dispose();
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    sceneRef.current?.load(galaxy);
  }, [galaxy]);

  useEffect(() => {
    sceneRef.current?.select(selectedId);
  }, [selectedId]);

  return <canvas ref={canvasRef} className="scene" aria-hidden="true" />;
}
