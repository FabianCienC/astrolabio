import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // The fixture lives in ../contract, outside the web root.
    fs: { allow: [".", "../contract"] },
    // In dev, /api goes to a local uvicorn (same origin as in production).
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
