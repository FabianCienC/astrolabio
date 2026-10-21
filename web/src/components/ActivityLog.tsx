import { type SyntheticEvent, useState } from "react";

import type { Activity } from "../model/activity";

const STORAGE_KEY = "astrolabio.activity-open";

function rememberedOpen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false; // storage blocked (private mode, disabled site data)
  }
}

const time = new Intl.DateTimeFormat("es", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

type Props = { entries: Activity[]; onSelect: (id: string) => void };

/**
 * Bottom-right activity panel: what the live galaxy just did. Closed, it is a pill
 * showing only the latest entry, so live status is always visible without covering
 * the scene; open, it lists the recent history. Entries with an object select it.
 */
export function ActivityLog({ entries, onSelect }: Props) {
  const [open, setOpen] = useState(rememberedOpen);
  const latest = entries[0];

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
    <details className="activity" open={open} onToggle={onToggle}>
      <summary>
        <span className="activity-title">Actividad</span>
        {!open && latest && (
          // Keyed by entry, so each new one fades in.
          <span key={latest.id} className={`activity-latest tone-${latest.tone} fade-in`}>
            {latest.text}
          </span>
        )}
      </summary>
      <ol className="activity-list" aria-live="polite">
        {entries.map((entry) => (
          <li key={entry.id} className={`tone-${entry.tone} fade-in`}>
            <time dateTime={entry.at.toISOString()}>{time.format(entry.at)}</time>
            {entry.targetId ? (
              <button type="button" onClick={() => onSelect(entry.targetId!)}>
                {entry.text}
              </button>
            ) : (
              <span>{entry.text}</span>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}
