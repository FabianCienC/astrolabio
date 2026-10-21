import { useMemo, useState } from "react";

import { HoverCard } from "./components/HoverCard";
import { Legend } from "./components/Legend";
import { SceneCanvas } from "./components/SceneCanvas";
import { Sidebar } from "./components/Sidebar";
import { exampleGalaxy } from "./contract/fixture";
import { GalaxyIndex } from "./model/galaxyIndex";
import type { Hover } from "./scene/GalaxyScene";

export function App() {
  // The scene renders the contract fixture until the real /api/galaxy is wired (E2.9).
  const galaxy = exampleGalaxy;
  const index = useMemo(() => new GalaxyIndex(galaxy), [galaxy]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  return (
    <div className="layout">
      <main className="stage">
        <SceneCanvas
          galaxy={galaxy}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onHover={setHover}
        />
        <HoverCard index={index} hover={hover} />
        <h1 className="title">
          Astrolabio
          <small>el homelab, en vivo</small>
        </h1>
        <Legend />
      </main>
      <Sidebar index={index} selectedId={selectedId} onSelect={setSelectedId} />
    </div>
  );
}
