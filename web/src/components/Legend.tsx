import { type CSSProperties, type SyntheticEvent, useState } from "react";

import { NEBULA, OBJECT_KINDS, RELATION } from "../scene/symbology";
import { KindSymbol } from "./KindSymbol";

const STORAGE_KEY = "astrolabio.legend-open";

/** Whether this visitor left the legend open last time; closed by default. */
function rememberedOpen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false; // storage blocked (private mode, disabled site data)
  }
}

/**
 * What each color, shape and line means. Built from `scene/symbology.ts`, so it
 * always matches what the scene draws. It starts closed: open, it covers the
 * bottom-left of the scene, and the auto-rotation carries every project there.
 */
export function Legend() {
  const [open, setOpen] = useState(rememberedOpen);

  const onToggle = (event: SyntheticEvent<HTMLDetailsElement>) => {
    const next = event.currentTarget.open;
    setOpen(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // Not remembering is fine.
    }
  };

  return (
    <details className="legend" open={open} onToggle={onToggle}>
      <summary>Leyenda</summary>

      <h2>Objetos</h2>
      <ul>
        {OBJECT_KINDS.map((k) => (
          <li key={k.value}>
            <KindSymbol kind={k.value} />
            {k.label}
          </li>
        ))}
      </ul>

      <h2>Relaciones y áreas</h2>
      <ul>
        <li>
          <span className="symbol-slot" aria-hidden="true">
            <span
              className="legend-line"
              style={{ "--line": RELATION.color, opacity: RELATION.opacity * 2.5 } as CSSProperties}
            />
          </span>
          {RELATION.label}
        </li>
        <li>
          <span className="symbol-slot" aria-hidden="true">
            <span className="legend-nebula" style={{ "--nebula": NEBULA.palette[1] } as CSSProperties} />
          </span>
          {NEBULA.label}
        </li>
      </ul>
    </details>
  );
}
