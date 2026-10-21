import type { GalaxyIndex } from "../model/galaxyIndex";
import { HEALTH_LABEL } from "../model/health";
import type { Hover } from "../scene/GalaxyScene";
import { KIND } from "../scene/symbology";
import { KindSymbol } from "./KindSymbol";

type Props = { index: GalaxyIndex; hover: Hover | null };

/** Tiny preview next to the pointer: what the object is, before clicking it. */
export function HoverCard({ index, hover }: Props) {
  const entry = hover ? index.get(hover.id) : undefined;
  if (!hover || !entry) return null;
  const health = index.health(entry.id);

  return (
    // Keyed by id, so moving to another object replays the fade-in.
    <div key={entry.id} className="hover-card" style={{ left: hover.x, top: hover.y }} role="tooltip">
      <div className="hover-card-name">
        <KindSymbol kind={entry.kind} size={1} />
        <span>{index.label(entry.id)}</span>
      </div>
      <div className="hover-card-meta">
        <span>{KIND[entry.kind].label}</span>
        {entry.kind === "pod" && <span>· {entry.pod.phase}</span>}
        {health && <span className={`badge badge-${health}`}>{HEALTH_LABEL[health]}</span>}
      </div>
    </div>
  );
}
