/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        desktop: resolve(__dirname, "index.html"),
        // mobile: resolve(__dirname, "m.html"),  // C1 에서 활성화
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/sites": "http://localhost:8070",
      "/facets": "http://localhost:8070",
      "/concepts": "http://localhost:8070",
      "/themes": "http://localhost:8070",
      "/marks": "http://localhost:8070",
      "/featured-axes": "http://localhost:8070",
      "/eta": "http://localhost:8070",
    },
  },
  test: {
    // Playwright tests live under tests/playwright/ and run via
    // `npm run test:e2e`. Keep vitest scoped to the unit tests under
    // tests/shared/ (and any future src/__tests__).
    exclude: ["node_modules/**", "dist/**", "tests/playwright/**"],
  },
});
