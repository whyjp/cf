# fe Vite migration + m.html mobile entry

**Date**: 2026-05-10
**Status**: design approved, awaiting implementation plan
**Author**: superpowers brainstorming session
**Sub-projects covered**: SP-B (fe Vite 마이그레이션) + SP-C (m.html 모바일 entry) — 두 sub-project 가 같은 Vite 프로젝트를 공유하므로 단일 spec 으로 통합
**Companion spec (parallel)**: `2026-05-10-backend-split-be-api-bff-design.md` (SP-A — backend BFF 분리)
**Depends on**: 없음. SP-A 와 독립 진행 가능. 단 SP-A 의 sprint A4 와 본 spec 의 sprint B4 는 같은 배포 사이클 묶음 권장.

## 1. Goal

현재 `fe/` 는 단일 HTML React+Babel 프로토타입 (`index.html` 1797 lines, `graph.html` 980 lines, CDN 의존만). 모바일 대응은 사실상 부재 (`hidden md:flex` 로 헤더 컨트롤 전체가 모바일에서 안 보임). 본 작업은:

1. **fe/ 를 Vite + TypeScript 프로젝트로 마이그레이션** — 컴포넌트 모듈화, HMR, 코드분할, npm 의존성 관리
2. **m.html 모바일 전용 entry 추가** — Google Maps 스타일 지도-도미넌트 + 3단 BottomSheet, 데스크톱 기능 패리티
3. **데스크톱과 모바일이 데이터·도메인 계층 공유** (`src/shared/`) — projection 외 hook·API client·distance 헬퍼 1소스

목적:
- 모바일 사용자에게도 캠핑장 지도 + 검색 + 필터 + ETA + 상세 풀 기능 제공
- fe 코드베이스의 유지보수성 (TS 안전망, 컴포넌트 분리, npm dep)
- 빌드 산출 1개로 두 entry 동시 배포

## 2. Out of scope

- **fe/graph.html (어드민 그래프 페이지) 의 모바일 대응 또는 Vite 마이그레이션** — 어드민 전용. CDN+Babel 그대로 유지. Vite 빌드에서 `public/graph.html` 로 통과.
- **PWA·서비스워커·오프라인** — 후속.
- **푸시·알림·계정** — 후속.
- **i18n** — 한국어 단일 (현 상태 유지).
- **데스크톱 UX 변경** — Vite 마이그레이션은 동작 동등성 유지가 원칙. 디자인 개선은 별도 spec.
- **SP-A 백엔드 분리** — 본 spec 의 fe 는 backend 가 cf_backend 든 cf-be-for-fe 든 base URL 8070 만 봄. 동시 진행 시 호환.

## 3. Architectural decisions (from brainstorming)

| 결정 | 선택 | 트레이드오프 |
|---|---|---|
| 모바일 대응 형태 | **별도 m.html 모바일 전용 페이지** | 반응형 단일 index.html: 한 파일 비대화·데스크톱 회귀 위험. 하이브리드 컴포넌트: 분기 복잡도. |
| 모바일 기능 범위 | **데스크톱 기능 패리티** | 코어/확장: 사용자 입장 기능 차별 발생. |
| 모바일 메인 레이아웃 | **지도-도미넌트 + 3단 BottomSheet (Google Maps 패턴)** | 하단 탭바: 지도·리스트 동시 맥락 상실. 세로 스크롤 단일: 지도 사용 시 항상 스크롤. |
| 코드 공유 / 빌드 | **Vite + TypeScript (제대로된 빌드 도입)** | shared.js 추출(no-build): README 철학 유지하나 컴포넌트 공유 불가. 완전 복제: API 변경 시 두 곳 동기. |
| 진입 경로 | **UA 자동 리다이렉트 + "데스크톱으로" 토글** | 자동 리다이렉트 없음: 데스크톱 / 진입 모바일 사용자 일반적. 반응형 감지 후 swap: 상위 결정과 충돌. |

## 4. Final directory layout

```
fe/
├─ package.json                  # NEW
├─ vite.config.ts                # NEW — multi-entry, server.proxy
├─ tsconfig.json                 # NEW — strict
├─ tailwind.config.js            # NEW
├─ postcss.config.js             # NEW
├─ index.html                    # MODIFIED — Vite entry, <script type="module" src="/src/desktop/main.tsx">
├─ m.html                        # NEW — Vite entry, <script type="module" src="/src/mobile/main.tsx">
├─ public/
│  ├─ graph.html                 # MOVED from fe/graph.html — 어드민, CDN+Babel 그대로
│  └─ favicon.ico, og-image.png
├─ src/
│  ├─ shared/                    # ⭐ 두 페이지가 공유
│  │  ├─ api.ts                  # API base URL = import.meta.env.VITE_API_BASE 또는 ""
│  │  ├─ hooks/
│  │  │  ├─ useFacets.ts
│  │  │  ├─ useSites.ts
│  │  │  ├─ useDetail.ts
│  │  │  ├─ useUserLocation.ts
│  │  │  ├─ useFeaturedAxes.ts
│  │  │  ├─ useManagementMarks.ts
│  │  │  └─ useEtaBatch.ts
│  │  ├─ types.ts                # Site, FacetData, FeaturedAxis, EtaResult, MgmtMark, …
│  │  ├─ filters.ts              # CONCEPT_FILTER_KEYS, setSerialize, visibleRows
│  │  ├─ geo.ts                  # haversineKm, formatKm
│  │  ├─ constants.ts            # ETA_HARD_CAP, axis 색 매핑, 색 토큰 (TS export)
│  │  └─ styles/
│  │     └─ tokens.css           # CSS 변수 (--moss, --ember, --paper, --bark, ...) — index.html / m.html 공유
│  ├─ desktop/
│  │  ├─ main.tsx                # ReactDOM.createRoot
│  │  ├─ App.tsx                 # 현 index.html 내부 App
│  │  └─ components/
│  │     ├─ FilterBar.tsx
│  │     ├─ EtaBar.tsx
│  │     ├─ CampList.tsx
│  │     ├─ MapView.tsx
│  │     ├─ DetailPanel.tsx
│  │     ├─ SearchBox.tsx
│  │     ├─ LocationPill.tsx
│  │     ├─ Stat.tsx
│  │     ├─ MobileToggle.tsx     # 좁은 뷰포트일 때만 표시 — "모바일로 돌아가기"
│  │     └─ … (기존 visual atoms)
│  └─ mobile/
│     ├─ main.tsx
│     ├─ App.tsx                 # MobileShell 래퍼
│     └─ components/
│        ├─ MobileShell.tsx      # TopBar + Map + FAB + BottomSheet 컨테이너
│        ├─ TopBar.tsx
│        ├─ MobileMap.tsx        # Leaflet 모바일 컨트롤 위치 조정
│        ├─ BottomSheet.tsx      # 3단 스냅 (peek/half/full)
│        ├─ MobileCampList.tsx   # 단순화 카드
│        ├─ FilterFAB.tsx
│        ├─ FilterSheet.tsx      # 풀스크린 모달
│        ├─ DetailSheet.tsx      # 풀스크린 상세 + 미니맵
│        ├─ MobileSearchOverlay.tsx
│        ├─ EtaSheet.tsx         # 풀스크린 ETA 입력
│        ├─ LocationChip.tsx
│        └─ DesktopToggle.tsx    # localStorage prefer + cookie 동기 + / 이동
└─ tests/
   ├─ shared.test.ts             # filters.visibleRows, geo.haversineKm 등 단위
   └─ playwright/                # 시나리오 회귀
      ├─ desktop.spec.ts         # B3 회귀 (5 시나리오)
      └─ mobile.spec.ts          # C 단계 동작 검증
```

## 5. 모바일 UX (C 단계)

### 5.1 화면 셸
```
┌─────────────────────────────┐
│ [≡] camfit         [🔍]     │ ← TopBar (~56dp)
├─────────────────────────────┤
│      Leaflet 지도 (full)     │
│       마커·클러스터          │ ← BottomSheet 위에 오버레이
│           [📍]              │ ← FAB-내위치 (우하단)
│         [필터 N]             │ ← FAB-필터 (활성 시 카운트 배지)
├─━━━ 핸들 ━━━━━━━━━━━━━━━━━━┤
│ 1,234곳 · 강원 · 계곡        │ ← BottomSheet (peek=120dp)
│ ─────────────────────────── │
│ 캠핑장 A         12km   →   │
│ 캠핑장 B          5km   →   │
└─────────────────────────────┘
```

### 5.2 BottomSheet 3단 스냅
| 단계 | 높이 | 보이는 것 |
|---|---|---|
| **peek** | 120dp | 헤더 1줄 (총 N곳 + 활성 필터 요약) + 카드 1줄 끝자락 |
| **half** | 50vh (`50dvh`) | 헤더 + 카드 ~5개 + 지도 50% 보임 |
| **full** | 100dvh - 56 | 헤더 + 카드 풀스크롤 + 지도 안 보임 |

- 드래그·플링: pointer events, velocity 임계로 스냅 결정
- 외부 라이브러리 미도입 — vanilla pointer events 직접 (`useBottomSheet()` 커스텀 훅)
- 핸들 영역만 `touch-action: none`, 본문 카드 리스트는 default → 지도 pan 과 sheet drag 충돌 방지

### 5.3 인터랙션
- **마커 탭** → BottomSheet half 자동 이동 + 해당 카드로 스크롤·하이라이트 + 카드 위 미니 정보 풍선
- **마커 탭 두 번째** → DetailSheet 풀스크린
- **클러스터 탭** → 줌인 (Leaflet 기본)
- **지도 빈 영역 탭** → BottomSheet peek 복귀
- **카드 탭** → DetailSheet 풀스크린
- **FAB 필터** → FilterSheet 풀스크린 모달
- **FAB 내위치** → 지도 내 위치로 fly + LocationChip 갱신

### 5.4 디자인 토큰
- 탭 타깃 ≥ 44×44dp
- BottomSheet 핸들: 36×4dp 회색 바, 16dp 패딩
- 카드 패딩 데스크톱 14dp → 모바일 18dp
- 폰트: Pretendard Variable, 본문 15dp / 부제 13dp
- 안전 영역: `env(safe-area-inset-bottom)` BottomSheet peek 에 가산
- 색 토큰: `src/shared/styles/tokens.css` (--moss, --ember, --paper, --bark, …) — 데스크톱과 동일

## 6. 진입 경로 & 라우팅

### 6.1 자동 리다이렉트 (서버측)
백엔드(SP-A 진행 시 be-for-fe, 미진행 시 cf_backend)의 `/` 핸들러:

```python
@app.get("/", include_in_schema=False)
def root_redirect(request):
    ua = request.headers.get("user-agent", "")
    if MOBILE_UA_RE.search(ua) and not request.cookies.get("prefer_desktop"):
        return RedirectResponse("/m.html")
    return FileResponse(fe_dist / "index.html")
```

`MOBILE_UA_RE = re.compile(r"Mobi|Android|iPhone|iPad|iPod", re.I)` 정도.

### 6.2 클라 측 보강
`index.html` 의 entry script 가 `window.matchMedia("(max-width: 640px)").matches && !localStorage.getItem("prefer_desktop")` 일 때 `location.replace("/m.html")` — UA 가 안 맞아도 좁은 뷰포트면 모바일로.

### 6.3 토글
- `DesktopToggle` (m.html 우상단 메뉴) → `localStorage.setItem("prefer_desktop", "1")` + `document.cookie = "prefer_desktop=1; path=/; max-age=31536000"` + `location.assign("/")`
- `MobileToggle` (index.html 우상단, 좁은 뷰포트일 때만 표시) → 둘 다 삭제 + `location.assign("/m.html")`

### 6.4 cookie 보존 실패 대비
iOS Safari privacy mode 등 cookie 미보존 환경 → 자동 리다이렉트 루프 위험. localStorage 우선 검사, 둘 다 실패 시 sessionStorage 의 refer 카운터로 5초 동안 동일 페이지 재요청 무시.

## 7. 데이터 흐름

- 모든 hook (`useFacets`, `useSites`, `useDetail`, `useUserLocation`, `useFeaturedAxes`, `useManagementMarks`, `useEtaBatch`) 은 `src/shared/hooks/` 단일 소스
- `api.ts` base URL = `import.meta.env.VITE_API_BASE` (없으면 `""` 동일 origin)
- visibleRows 클라사이드 필터 (terrain·collection·facilityRaw·management) → `src/shared/filters.ts`
- haversineKm·formatKm → `src/shared/geo.ts`

## 8. 빌드 & 백엔드 mount 통합

### 8.1 vite.config.ts (개략)
```ts
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        desktop: resolve(__dirname, "index.html"),
        mobile: resolve(__dirname, "m.html"),
      },
    },
  },
  server: {
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
});
```

(개별 prefix 나열 — `'/'` proxy 는 HTML 자체도 백엔드로 가서 dev HMR 깨짐.)

### 8.2 백엔드 mount 전환
- 빌드: `npm run build` → `fe/dist/index.html`, `fe/dist/m.html`, `fe/dist/assets/*`, `fe/dist/graph.html`
- 백엔드 settings: `fe_dir` = `fe/` → `fe/dist/`
- StaticFiles mount 동일 (`html=True`)
- root redirect 핸들러는 fe_dir 보다 먼저 등록 (FastAPI 라우트 순서)

### 8.3 dev 모드
- 데스크톱·모바일 fe 개발: `npm run dev` (Vite :5173) — proxy 가 `/sites` 등을 8070 으로
- 백엔드: `uvicorn cf_be_for_fe.api:app --port 8070` (또는 SP-A 미완 시 `cf_backend.api:app`)
- 두 프로세스 동시 실행

## 9. 마이그레이션 Sprint

### B 단계 — Vite 마이그레이션

| Sprint | 작업 | 검증 |
|---|---|---|
| **B1** | Vite 프로젝트 셋업 — `package.json`, `vite.config.ts`, `tsconfig.json`(strict), `@vitejs/plugin-react`, react/react-dom/leaflet/leaflet.markercluster npm, tailwindcss + postcss + autoprefixer. **현 fe/index.html / fe/graph.html 은 그대로 유지** (병행 동작). 빈 `src/desktop/main.tsx` + `index.html.new` 로 빌드만 통과 확인. **`fe/graph.html` → `fe/public/graph.html` 이동** (CDN+Babel 유지) | `npm run build` PASS, `fe/dist/graph.html` 산출 |
| **B2** | 데이터 계층 추출 — `src/shared/{api,hooks,types,filters,geo,constants}.ts` + `src/shared/styles/tokens.css`. 기존 fe/index.html 의 hooks/유틸을 옮기되 TS 타입 부여. CDN 호출 코드 → `api.ts` (env 기반) | `vitest run src/shared/` PASS, tsc strict PASS |
| **B3** | 데스크톱 컴포넌트 이전 — `src/desktop/components/` 에 FilterBar, EtaBar, CampList, MapView, DetailPanel, SearchBox, LocationPill, Stat 등. 신규 `src/desktop/App.tsx` + `main.tsx`. `index.html` 을 Vite entry 로 재작성. **회귀 fixture**: Playwright 5 시나리오 (홈, 필터, 카드 탭→DetailPanel, 분할/지도/리스트, 검색) 스크린샷 비교 | `npm run build` + `npm run preview` 후 데스크톱 페이지가 기존과 동일 동작, Playwright 5 시나리오 PASS |
| **B4** | 백엔드 mount 전환 — `fe_dir` 을 `fe/` → `fe/dist/`. **SP-A 진행 상태와 무관 — 어느 백엔드 패키지든 같은 settings 변경**. dev 모드 Vite proxy 설정 검증 | E2E: `npm run build && uv run uvicorn ...` 부팅 → :8070 / 가 빌드된 데스크톱 페이지 |
| **B5** | 잔여 husk 제거 — 이전 fe/index.html (CDN 인라인) 삭제. fe/README.md 갱신 (Vite 명령, 빌드 산출 위치, dev proxy 설정) | `git status` clean, fe/README.md 정확 |

### C 단계 — m.html 모바일 entry

| Sprint | 작업 | 검증 |
|---|---|---|
| **C1** | `src/mobile/` 셸 — `m.html`, `src/mobile/main.tsx`, `MobileShell`(TopBar + 빈 지도 영역 + 빈 BottomSheet), 빌드 entry 추가 (`vite.config.ts` rollupOptions.input) | `npm run build` PASS, `/m.html` fetch 가능, 빈 셸 표시 |
| **C2** | `BottomSheet` (vanilla pointer events 3단 스냅) + `MobileMap` (Leaflet 모바일 컨트롤 위치). shared/hooks 사용 | 모바일 뷰포트(360×740) 에서 BottomSheet 드래그 동작, 마커 탭 → BottomSheet half 이동 |
| **C3** | `MobileCampList`, `DetailSheet`, `MobileSearchOverlay`, `LocationChip` | 카드 탭 → DetailSheet, 검색 → 결과 표시 |
| **C4** | `FilterFAB` + `FilterSheet`, `EtaSheet` | 필터·ETA 적용 후 m.html 결과 데스크톱과 일치 |
| **C5** | 진입 라우팅 — 백엔드 `/` 핸들러에 UA·cookie 분기 추가 + `DesktopToggle` (m.html) / `MobileToggle` (index.html, 좁은 뷰포트만) + cookie/localStorage 동기 + iOS privacy mode 루프 가드 | UA 모바일 + cookie 없음 → /m.html 자동, "데스크톱으로" 후 새로고침 → / 유지, "모바일로" 후 새로고침 → /m.html |
| **C6** | 안전 영역·디자인 토큰 정리 + Lighthouse 모바일 점수 점검 (참고) | Lighthouse Performance ≥ 80, Accessibility ≥ 90 (참고 지표, 강제 게이트 아님) |

총 11 PR (B1~B5 + C1~C6). 각 PR = 의미 단위, 자동 머지 (`gh pr merge --auto --merge`).

## 10. SP-A 와의 인터리브

- SP-A 의 sprint 와 본 sprint 는 디렉터리·책임 독립 → 서로 의존 없음
- 권장 진행 순서 (단일 워커 직렬 시): **B1 → A1 → A2 → B2 → B3 → A3 → B4 → C1 → C2 → A4 → A5 → C3 → C4 → C5 → A6 → A7 → B5 → C6**
  - 이유: B1 은 가장 가벼움 (셋업), 그 후 A1·A2 가 백엔드 분리 첫 단계. B2·B3 동안 A3 회귀 fixture 캡처가 필요하므로 인터리브.
  - 단일 워커 직렬은 강제 아님 — 사용자가 한쪽에 집중하고 싶으면 한쪽만 끝까지 가도 OK.
- **운영 묶음 권장**: SP-A 의 A4 (BFF 통과 확장 마무리) + 본 spec 의 B4 (mount 전환) 는 같은 배포 사이클. 그래야 fe → BFF → be-api 풀스택 동시 cutover.

## 11. 위험·미결 사항

| 위험 | 완화 |
|---|---|
| Tailwind CDN → 빌드 도입 시 클래스명 paving 차이 | B1 시 `tailwind.config.js` `content = ["./src/**/*.{ts,tsx}", "./index.html", "./m.html"]`. B3 회귀 fixture 가 잡음 |
| Babel 인라인 → ESM 전환 시 글로벌 namespace 의존 코드 깨짐 | B2/B3 에서 `import { useState } from "react"` 일괄 변환 |
| Leaflet UMD → npm 전환 시 markercluster 호환 | `import "leaflet"; import "leaflet.markercluster"` 순서 + `@types/leaflet`. CSS 는 main.tsx 에서 import |
| BottomSheet 성능 — Leaflet pan 과 sheet drag 의 터치 이벤트 충돌 | sheet 핸들 영역만 `touch-action: none`, 본문은 default |
| 모바일 사파리 100vh 함정 (주소창 토글) | `100dvh` 사용, fallback `100vh` 병기 |
| iOS Safari cookie 보존 이슈 (privacy mode) → 자동 리다이렉트 루프 | localStorage 우선, cookie 보조. sessionStorage refer 카운터 |
| Vite dev proxy cookie 전달 누락 | `server.proxy[...] = { changeOrigin: false, cookieDomainRewrite: 'localhost' }` |
| 디자인 토큰 일관성 | `src/shared/styles/tokens.css` 추출, 두 entry 모두 import |
| TypeScript strict 도입으로 기존 hook 타입 빈틈 노출 | 빈틈은 `// @ts-expect-error TODO` 마커, 추후 cleanup. strict 자체는 켬 |
| Vite multi-entry 가 backend root redirect 와 충돌 — root 핸들러가 없으면 StaticFiles 가 index.html 만 자동 응답 | C5 시 root_redirect 핸들러 등록을 mount 보다 먼저 |
| 어드민 graph.html 의 fe/public 이동 시 base URL 호환 | graph.html 은 별도 origin 또는 동일 origin 둘 다 지원 (현 코드도 `location.port === "8070"` 분기) |
| 모바일 dev 시 실제 디바이스 테스트 | Vite dev 서버를 LAN 노출 (`--host`), QR 코드로 폰에서 테스트 |

## 12. 검증 fixture

### 12.1 데스크톱 (B3)
- Playwright 시나리오 5개 + 스크린샷 회귀:
  1. 홈 진입 후 첫 200ms 안정 상태
  2. 지역 chip 1개 적용
  3. 카드 탭 → DetailPanel 우슬라이드
  4. 분할/지도/리스트 토글 각각
  5. 검색어 입력 후 결과 표시

### 12.2 모바일 (C 단계)
- Playwright 모바일 emulation (Pixel 5 또는 iPhone 12) 동작 검증:
  1. 진입 → MobileShell + 지도 + BottomSheet peek
  2. BottomSheet 드래그 → half/full 스냅
  3. 마커 탭 → BottomSheet half + 카드 하이라이트
  4. 카드 탭 → DetailSheet 풀스크린
  5. FilterFAB → FilterSheet → 지역 1개 적용 → 카드 갱신
  6. EtaSheet 입력 → ETA 적용 → 카드 ETA 배지
  7. DesktopToggle → / 이동 → MobileToggle → /m.html 라운드트립

## 13. Next steps

본 spec 승인 후:
1. `superpowers:writing-plans` 스킬로 SP-B/C implementation plan 작성. plan 은 sprint B1~C6 단위 TODO + 각 sprint 의 verification 명령 + rollback 절차 + PR 단위 분기명 명시.
2. SP-A plan 과 함께 인터리브 진행 순서 (10절) 확정.
