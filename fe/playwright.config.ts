import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — tests boot Vite preview on :4173 (matches the
 * `preview` script in package.json) and run against the desktop entry.
 *
 * Set PLAYWRIGHT_BASE_URL when running against a hosted dev/staging
 * environment instead of the local preview server.
 */
export default defineConfig({
  testDir: "./tests/playwright",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:4173",
    headless: true,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run preview -- --port 4173",
    port: 4173,
    reuseExistingServer: true,
  },
});
