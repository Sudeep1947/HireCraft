import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // The interview video room signals over a WebSocket at
        // /api/v1/interview/:id/video. Without `ws: true` the dev proxy would
        // never forward the upgrade and the live call could not connect in
        // development. HTTP proxying is unaffected.
        ws: true,
      },
      "/uploads": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
    pool: "threads",
    fileParallelism: false,
  },
});
