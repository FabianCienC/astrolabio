import type { CSSProperties } from "react";

import { NEBULA, OBJECT_KINDS, RELATION } from "../scene/symbology";
import { KindSymbol } from "./KindSymbol";

/**
 * What each color, shape and line means. Built from `scene/symbology.ts`, so it
 * always matches what the scene draws. Collapsible, so it gets out of the way on a phone.
 */
export function Legend() {
  return (
    <details className="legend" open>
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
