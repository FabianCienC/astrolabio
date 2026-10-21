import example from "../../../contract/galaxy.example.json";
import type { Galaxy } from "./galaxy";

/** Example galaxy exported by the API (`uv run export-contract`). */
export const exampleGalaxy = example as Galaxy;
