import { useMemo, useState } from "react";

import { HoverCard } from "./components/HoverCard";
import { Legend } from "./components/Legend";
import { ListView } from "./components/ListView";
import { SceneCanvas } from "./components/SceneCanvas";
import { Sidebar } from "./components/Sidebar";
import type { Galaxy } from "./contract/galaxy";
import { GalaxyIndex } from "./model/galaxyIndex";
import { useGalaxy } from "./model/useGalaxy";
import type { Hover } from "./scene/GalaxyScene";

type View = "galaxy" | "list";

export function App() {
  const state = useGalaxy();
  if (state.status !== "ready") {
    return (
      <div className="status-screen" role="status">
        <Title />
        <p className={state.status === "error" ? "status-error" : "status-loading"}>
          {state.status === "error"
            ? "No se pudo leer el clúster en este momento. Intenta recargar en un rato."
            : "Leyendo el clúster…"}
        </p>
      </div>
    );
  }
  return <GalaxyView galaxy={state.galaxy} example={state.example} />;
}

function Title() {
  return (
    <h1 className="title">
      Astrolabio
      <small>el homelab, en vivo</small>
    </h1>
  );
}

function GalaxyView({ galaxy, example }: { galaxy: Galaxy; example: boolean }) {
  const index = useMemo(() => new GalaxyIndex(galaxy), [galaxy]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  // `?view=list` opens the list directly (a link to the accessible view).
  const [view, setView] = useState<View>(() =>
    new URLSearchParams(window.location.search).get("view") === "list" ? "list" : "galaxy",
  );
  const [webgl, setWebgl] = useState(true);
  const showList = view === "list" || !webgl;

  return (
    <div className="layout">
      {webgl && (
        <button type="button" className="skip-link" onClick={() => setView("list")}>
          Ver el contenido como lista
        </button>
      )}
      <main className="stage">
        {/* The scene keeps running under the list, so returning to it never jumps. */}
        <SceneCanvas
          galaxy={galaxy}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onHover={setHover}
          onUnavailable={() => setWebgl(false)}
        />
        {!showList && <HoverCard index={index} hover={hover} />}
        <Title />
        {example && <p className="example-notice">Datos de ejemplo: no hay API local</p>}
        {webgl && (
          <button
            type="button"
            className="view-toggle"
            aria-pressed={showList}
            onClick={() => setView(showList ? "galaxy" : "list")}
          >
            {showList ? "Ver la galaxia" : "Ver como lista"}
          </button>
        )}
        {showList ? (
          <ListView
            index={index}
            selectedId={selectedId}
            onSelect={setSelectedId}
            notice={
              webgl
                ? undefined
                : "Este navegador no puede dibujar la galaxia en 3D (WebGL no está disponible). Aquí está el mismo contenido como lista."
            }
          />
        ) : (
          <Legend />
        )}
      </main>
      <Sidebar index={index} selectedId={selectedId} onSelect={setSelectedId} />
    </div>
  );
}
