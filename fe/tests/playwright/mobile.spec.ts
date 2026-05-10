import { test, expect } from "@playwright/test";

/**
 * Sprint C5 회귀 — mobile entry + toggle round-trip.
 *
 * Note: vite preview 자체는 UA-sniff 를 안 한다. UA-기반 "/" → /m.html 302
 * 는 BFF (cf_be_for_fe) 가 처리. 따라서 preview 환경에서는 m.html 직접
 * 진입으로 mobile bundle smoke 만 검증하고, UA redirect 는 BFF 에 대해
 * PLAYWRIGHT_BASE_URL=http://localhost:8070 로 돌릴 때만 단언한다.
 */
test.describe("mobile fe — C5 회귀", () => {
  test("mobile shell renders on /m.html", async ({ page }) => {
    await page.goto("/m.html");
    // TopBar — title "camfit" + menu(≡) + search(🔍).
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByRole("button", { name: "menu" })).toBeVisible();
    await expect(page.getByRole("button", { name: "search" })).toBeVisible();
  });

  test("menu opens dropdown with desktop toggle", async ({ page }) => {
    await page.goto("/m.html");
    await page.getByRole("button", { name: "menu" }).click();
    const menu = page.getByTestId("mobile-menu");
    await expect(menu).toBeVisible();
    await expect(menu.getByRole("button", { name: /데스크톱으로/ })).toBeVisible();
  });

  test("desktop toggle sets cookie + navigates to /", async ({ page, context }) => {
    await page.goto("/m.html");
    await page.getByRole("button", { name: "menu" }).click();
    const toggle = page.getByTestId("mobile-menu").getByRole("button", {
      name: /데스크톱으로/,
    });
    // Toggle navigates to "/" — wait for the URL change.
    await Promise.all([page.waitForURL(/\/$/), toggle.click()]);
    // Cookie set.
    const cookies = await context.cookies();
    const c = cookies.find((c) => c.name === "prefer_desktop");
    expect(c?.value).toBe("1");
  });

  test.describe("BFF UA redirect (only when PLAYWRIGHT_BASE_URL points to BFF)", () => {
    test.skip(
      !process.env.PLAYWRIGHT_BASE_URL?.includes(":8070"),
      "BFF target not configured — set PLAYWRIGHT_BASE_URL=http://localhost:8070",
    );
    test("/ on iPhone redirects to /m.html", async ({ page }) => {
      const resp = await page.goto("/", { waitUntil: "commit" });
      // 302 → final URL ends with /m.html.
      await expect(page).toHaveURL(/\/m\.html$/);
      expect(resp?.status()).toBeLessThan(400);
    });
  });
});
