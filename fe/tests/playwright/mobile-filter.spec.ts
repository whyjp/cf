import { test, expect } from "@playwright/test";

/**
 * Sprint P2 회귀 — mobile FilterFAB / FilterSheet / EtaSheet (C4 컴포넌트).
 *
 * Strategy (mobile.spec.ts 패턴 그대로):
 *   - 구조적 단언 (FAB 가시, 시트 풀스크린 마운트, "적용" 버튼 등)은 BFF
 *     없이도 통과해야 한다. mobile bundle smoke 의 연장선.
 *   - 데이터 의존 단언 (지역 칩 토글 → 리스트 카운트 변화)은 facets/sites
 *     데이터가 없으면 test.skip() 으로 graceful 패스. desktop.spec.ts 의
 *     "apply region chip updates list" 와 동일 정책.
 *
 * Selectors:
 *   - FilterFAB: aria-label="필터" (단일 fixed FAB).
 *   - FilterSheet: header h2 "필터" + footer "적용" 버튼.
 *   - EtaSheet  : BottomSheet 헤더의 aria-label="ETA 설정" 트리거,
 *                 시트 내부 header h2 "ETA" + "적용" 버튼.
 *   data-* 셀렉터를 컴포넌트에 추가하지 않는 이유: 디자인 토큰이 한국어
 *   라벨 + aria-label 위주라서 사용자 시점 셀렉터로도 안정적.
 */
test.describe("mobile filter UX — P2 회귀", () => {
  test("FilterFAB 가 우하단 고정 위치에 노출된다", async ({ page }) => {
    await page.goto("/m.html");
    const fab = page.getByRole("button", { name: "필터" });
    await expect(fab).toBeVisible();
    // FilterFAB 는 fixed bottom-32 right-4. position:fixed 인지 단언.
    const position = await fab.evaluate((el) => getComputedStyle(el).position);
    expect(position).toBe("fixed");
  });

  test("FilterFAB 탭 → FilterSheet 풀스크린 모달 열림", async ({ page }) => {
    await page.goto("/m.html");
    const fab = page.getByRole("button", { name: "필터" });
    await fab.click();
    // FilterSheet 헤더 h2 "필터" + 적용 버튼이 동시에 떠야 시트가 마운트
    // 됐다고 단정 가능 (FAB 라벨도 "필터" 라서 h2/role 로 명확히 구분).
    const sheetTitle = page.getByRole("heading", { name: "필터", level: 2 });
    await expect(sheetTitle).toBeVisible();
    await expect(page.getByRole("button", { name: "적용" })).toBeVisible();
    // ← 닫기 버튼 (aria-label="close") 이 같이 떠야 함.
    await expect(page.getByRole("button", { name: "close" })).toBeVisible();
  });

  test("FilterSheet 지역 칩 토글 → 적용 → 시트 닫힘", async ({ page }) => {
    await page.goto("/m.html");
    await page.getByRole("button", { name: "필터" }).click();
    const sheetTitle = page.getByRole("heading", { name: "필터", level: 2 });
    await expect(sheetTitle).toBeVisible();

    // 지역 섹션의 sido 칩 — facets.regions 가 비어 있으면 "지역 정보를
    // 불러오는 중…" placeholder. 칩 자체는 px-3 py-1.5 rounded-full text-sm
    // border 스타일의 button 이지만, 헤더 버튼 ("←", "적용") 과 구분하기
    // 위해 시트 본문 영역 안에서만 찾는다.
    const sheetBody = page.locator(".fixed.inset-0.z-50").last();
    const regionChips = sheetBody.locator("section").first().locator("button");
    const chipCount = await regionChips.count();
    test.skip(
      chipCount === 0,
      "no sido chips — facets/regions 데이터 없음 (BFF 미연결)",
    );

    const firstChip = regionChips.first();
    await firstChip.click();
    // 적용 — onApply → setFilters + setFilterOpen(false). 시트가 사라져야 함.
    await page.getByRole("button", { name: "적용" }).click();
    await expect(sheetTitle).toBeHidden({ timeout: 3000 });
  });

  test("BottomSheet 헤더의 ⏱ ETA 탭 → EtaSheet 열림", async ({ page }) => {
    await page.goto("/m.html");
    // EtaSheet 트리거는 aria-label="ETA 설정" — BottomSheet 헤더에 상주.
    const etaTrigger = page.getByRole("button", { name: "ETA 설정" });
    await expect(etaTrigger).toBeVisible();
    await etaTrigger.click();
    // EtaSheet 헤더 h2 "ETA" 가 떠야 시트가 마운트됐다고 단정.
    await expect(
      page.getByRole("heading", { name: "ETA", level: 2 }),
    ).toBeVisible();
    // 풀스크린 모달이므로 적용 + ← 가 같이 떠야 함.
    await expect(page.getByRole("button", { name: "적용" })).toBeVisible();
    await expect(page.getByRole("button", { name: "close" })).toBeVisible();
  });

  test("EtaSheet — 사용자 좌표 없으면 적용 버튼 비활성", async ({
    page,
    context,
  }) => {
    // useUserLocation 은 navigator.geolocation 으로부터 coords 를 받는다.
    // Playwright 컨텍스트 단에서 geolocation permission 을 명시적으로 차단
    // (default 도 prompt 라 자동 grant 안 됨, 하지만 명시적이 안전).
    await context.clearPermissions();
    await page.goto("/m.html");
    await page.getByRole("button", { name: "ETA 설정" }).click();
    await expect(
      page.getByRole("heading", { name: "ETA", level: 2 }),
    ).toBeVisible();
    // 적용 버튼은 disabled — !coords || loading || candidateIds.length === 0.
    // 좌표 없으므로 disabled 가 firm 단언 (BFF 무관).
    const applyBtn = page.getByRole("button", { name: "적용" });
    await expect(applyBtn).toBeDisabled();
    // "내 위치 권한이 필요합니다" 안내 문구가 같이 떠야 함.
    await expect(page.getByText(/내 위치 권한이 필요합니다/)).toBeVisible();
  });
});
