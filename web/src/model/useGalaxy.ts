import { useEffect, useState } from "react";

import type { Galaxy } from "../contract/galaxy";

export type GalaxyState =
  | { status: "loading"; galaxy: null }
  | { status: "ready"; galaxy: Galaxy; example: boolean }
  | { status: "error"; galaxy: null };

/** While the API's informers sync it answers 503; it is worth waiting a little. */
const RETRY_MS = 2000;
const MAX_RETRIES = 15;

/**
 * Loads the cluster from `GET /api/galaxy` (same origin). Production never falls
 * back to the example: showing it as the live cluster would be misleading. In dev,
 * without a local API, the example is used and the page says so.
 */
export function useGalaxy(): GalaxyState {
  const [state, setState] = useState<GalaxyState>({ status: "loading", galaxy: null });

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;

    const load = async (attempt: number): Promise<void> => {
      try {
        const response = await fetch("/api/galaxy", { signal: controller.signal });
        if (response.status === 503 && attempt < MAX_RETRIES) {
          timer = window.setTimeout(() => void load(attempt + 1), RETRY_MS);
          return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setState({ status: "ready", galaxy: (await response.json()) as Galaxy, example: false });
      } catch (error) {
        if (controller.signal.aborted) return;
        if (import.meta.env.DEV) {
          const { exampleGalaxy } = await import("../contract/fixture");
          setState({ status: "ready", galaxy: exampleGalaxy, example: true });
          return;
        }
        console.error("could not load /api/galaxy", error);
        setState({ status: "error", galaxy: null });
      }
    };

    void load(0);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, []);

  return state;
}
