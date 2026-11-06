import { defineConfig } from "vite";

const api = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  server: { port: 5173, strictPort: true, proxy: { "/api": api } },
  preview: { port: 4173, strictPort: true, proxy: { "/api": api } },
  build: { target: "es2022", sourcemap: true },
});
