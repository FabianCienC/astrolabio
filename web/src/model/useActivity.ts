import { useEffect, useRef, useState } from "react";

import type { Galaxy } from "../contract/galaxy";
import { type Activity, type Change, describeChanges, describeGalaxy } from "./activity";

/** The panel keeps only the latest entries. */
const MAX_ENTRIES = 50;

/**
 * The activity log: what each new galaxy changed, plus the live connection coming
 * and going. Newest first.
 */
export function useActivity(galaxy: Galaxy, live: boolean, example: boolean): Activity[] {
  const [entries, setEntries] = useState<Activity[]>([]);
  const previous = useRef<Galaxy | null>(null);
  /** Whether /ws has connected at least once: a later drop is worth logging. */
  const everLive = useRef(false);
  const nextId = useRef(0);

  const push = (changes: Change[]) => {
    if (changes.length === 0) return;
    const at = new Date();
    const added = changes.map((change) => ({ ...change, id: nextId.current++, at }));
    setEntries((current) => [...added.reverse(), ...current].slice(0, MAX_ENTRIES));
  };

  useEffect(() => {
    push(previous.current ? describeChanges(previous.current, galaxy) : [describeGalaxy(galaxy)]);
    previous.current = galaxy;
  }, [galaxy]);

  useEffect(() => {
    if (example) return; // no live stream in dev without an API
    if (live) {
      push([
        {
          text: everLive.current ? "En vivo: conexión recuperada" : "En vivo: conectado",
          tone: "ok",
        },
      ]);
      everLive.current = true;
    } else if (everLive.current) {
      push([{ text: "Conexión perdida, reconectando…", tone: "warn" }]);
    }
  }, [live, example]);

  return entries;
}
