import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

// Pakai Chromium yang terpasang di lingkungan bila versi bawaan Playwright tidak tersedia.
const local = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome";
const executablePath = process.env.PW_CHROMIUM ?? (existsSync(local) ? local : undefined);

export default defineConfig({
  testDir: "tests",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    launchOptions: executablePath ? { executablePath } : {},
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      env: { DATA_SOURCE: "file" },
    },
    { command: "npx vite --host 127.0.0.1", url: "http://127.0.0.1:5173", reuseExistingServer: true },
  ],
});
