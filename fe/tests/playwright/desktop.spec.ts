import { test, expect } from "@playwright/test";

/**
 * Sprint B3 회귀 — desktop entry sanity checks.
 *
 * Several scenarios depend on a live BFF + camp data being reachable
 * from the preview server. When the data layer is empty (CI without a
 * fixture, dev without backend) the assertions degrade gracefully —
 * presence of the structural selector is enough to prove the entry
 * mounted.
 */
test.describe("desktop fe — B3 회귀", () => {
  test("home renders header + map shell", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("header")).toBeVisible();
    // Leaflet may take a tick to mount its container even when there's
    // no data — a generous timeout keeps this resilient on slow CI.
    await expect(page.locator(".leaflet-container")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/총/)).toBeVisible();
  });

  test("apply region chip updates list", async ({ page }) => {
    await page.goto("/");
    // Region chips live inside `[data-region-row]` (FilterBar). Without
    // facets the row is empty — skip rather than fail.
    const regionRow = page.locator("[data-region-row]");
    await regionRow.waitFor({ timeout: 5000 }).catch(() => undefined);
    const chips = regionRow.locator("button.chip");
    const count = await chips.count();
    test.skip(count === 0, "no region chips — backend / data unavailable");
    await chips.first().click();
    // After click the chip is marked active (● prefix per legacy).
    await expect(chips.first()).toContainText("●", { timeout: 2000 });
  });

  test("card click opens DetailPanel", async ({ page }) => {
    await page.goto("/");
    const cards = page.locator("[data-camp-card]");
    await cards.first().waitFor({ timeout: 5000 }).catch(() => undefined);
    const cardCount = await cards.count();
    test.skip(cardCount === 0, "no camp cards — backend / data unavailable");
    await cards.first().click();
    await expect(page.locator('[data-panel="detail"]')).toBeVisible({ timeout: 3000 });
  });

  test("view toggle split/map/list", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "지도" }).click();
    await expect(page.locator(".leaflet-container")).toBeVisible();
    await page.getByRole("button", { name: "리스트" }).click();
    // After switching to list view the leaflet container should be
    // unmounted from the DOM (App conditionally renders the map section).
    await expect(page.locator(".leaflet-container")).toHaveCount(0, { timeout: 2000 });
  });

  test("search input renders", async ({ page }) => {
    await page.goto("/");
    const search = page.locator('input[placeholder*="검색"]');
    await expect(search).toBeVisible();
    await search.fill("강원");
    // The dropdown only renders when the BFF returns hits — assert on
    // the input's value to confirm the typing path works regardless.
    await expect(search).toHaveValue("강원");
  });
});
