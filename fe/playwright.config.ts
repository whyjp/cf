import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — tests boot Vite preview on :4173 (matches the
 * `preview` script in package.json) and run against the desktop entry.
 *
 * Set PLAYWRIGHT_BASE_URL when running against a hosted dev/staging
 * environment instead of the local preview server.
 *
 * Projects:
 *   - chromium  : default desktop entry (index.html), Desktop Chrome viewport
 *   - mobile    : iPhone 12 device — verifies UA-aware "/" redirect (BFF
 *                 only; Vite preview itself doesn't UA-sniff) AND mobile
 *                 bundle smoke (m.html). Tests scope themselves with
 *                 testMatch so chromium doesn't run mobile.spec.ts and
 *                 vice versa.
 */
export default defineConfig({
  testDir: "./tests/playwright",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:4173",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /desktop\.spec\.ts$/,
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 12"] },
      testMatch: /mobile\.spec\.ts$/,
    },
  ],
  webServer: {
    command: "npm run preview -- --port 4173",
    port: 4173,
    reuseExistingServer: true,
  },
});
