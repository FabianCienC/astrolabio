import { useEffect, useState } from "react";

import type { Galaxy } from "../contract/galaxy";

export type GalaxyState =
  | { status: "loading"; galaxy: null }
  | { status: "ready"; galaxy: Galaxy; example: boolean; live: boolean }
  | { status: "error"; galaxy: null };

/** While the API's informers sync it answers 503; it is worth waiting a little. */
const RETRY_MS = 2000;
const MAX_RETRIES = 15;
/** Reconnect delays of the live stream: doubles from 1 s up to 30 s, reset once it delivers. */
const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

/**
 * Loads the cluster from `GET /api/galaxy` (same origin), then keeps it live through
 * `/ws`, which sends the whole galaxy again on every change (and on every reconnect).
 * Production never falls back to the example: showing it as the live cluster would be
 * misleading. In dev, without a local API, the example is used and the page says so.
 */
export function useGalaxy(): GalaxyState {
  const [state, setState] = useState<GalaxyState>({ status: "loading", galaxy: null });

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    let socket: WebSocket | null = null;
    let reconnectMs = RECONNECT_MIN_MS;

    const setLive = (live: boolean) =>
      setState((s) => (s.status === "ready" && s.live !== live ? { ...s, live } : s));

    const connect = () => {
      if (controller.signal.aborted) return;
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws`);
      socket.onmessage = (event: MessageEvent<string>) => {
        reconnectMs = RECONNECT_MIN_MS;
        const galaxy = JSON.parse(event.data) as Galaxy;
        setState({ status: "ready", galaxy, example: false, live: true });
      };
      socket.onclose = () => {
        setLive(false);
        if (controller.signal.aborted) return;
        timer = window.setTimeout(connect, reconnectMs);
        reconnectMs = Math.min(reconnectMs * 2, RECONNECT_MAX_MS);
      };
    };

    const load = async (attempt: number): Promise<void> => {
      try {
        const response = await fetch("/api/galaxy", { signal: controller.signal });
        if (response.status === 503 && attempt < MAX_RETRIES) {
          timer = window.setTimeout(() => void load(attempt + 1), RETRY_MS);
          return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const galaxy = (await response.json()) as Galaxy;
        setState({ status: "ready", galaxy, example: false, live: false });
        connect();
      } catch (error) {
        if (controller.signal.aborted) return;
        if (import.meta.env.DEV) {
          const { exampleGalaxy } = await import("../contract/fixture");
          setState({ status: "ready", galaxy: exampleGalaxy, example: true, live: false });
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
      socket?.close();
    };
  }, []);

  return state;
}
