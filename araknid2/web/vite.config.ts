import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // The demo build is served from a sub-path, so assets use relative URLs.
  base: mode === "demo" ? "./" : "/",
  build: mode === "demo" ? { outDir: "dist-demo" } : {},
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
}));
