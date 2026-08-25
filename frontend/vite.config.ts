/// <reference types="vitest" />

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backendPort = process.env.BACKEND_PORT || "8000";
const frontendPort = Number(process.env.FRONTEND_PORT || "5174");

export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
    proxy: {
      "/api": `http://127.0.0.1:${backendPort}`,
    },
  },
  test: {
    environment: "jsdom",
    pool: "threads",
    setupFiles: "./src/setupTests.ts",
  },
});
