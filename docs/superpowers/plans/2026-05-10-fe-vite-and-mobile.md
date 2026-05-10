# SP-B/C fe Vite Migration + m.html Mobile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** fe/ 단일 HTML React+Babel → Vite + TypeScript 프로젝트 (B 단계). m.html 모바일 entry 추가, BottomSheet 패턴 (C 단계). 데스크톱·모바일이 `src/shared/` 에서 hooks/api/types/filters/geo/tokens 공유.

**Architecture:** Vite multi-entry (index.html / m.html / public/graph.html). 데이터 계층은 plain TS (no React deps), 컴포넌트는 entry 별 분리. BFF (cf-be-for-fe) 가 fe/dist 를 mount. dev 모드는 Vite proxy.

**Tech Stack:** Vite, React 18, TypeScript (strict), Tailwind (PostCSS 빌드), Leaflet + leaflet.markercluster (npm), Playwright (회귀).

**Spec:** `docs/superpowers/specs/2026-05-10-fe-vite-and-mobile-design.md`

**Workflow:** 작은 단위 commit, sprint = 1 PR, `gh pr merge --auto --merge`. 브랜치명 `sprint/b<N>-...` 또는 `sprint/c<N>-...`.

**SP-A 와의 인터리브 권장 순서 (단일 워커):**
B1 → A1 → A2 → B2 → B3 → A3 → B4 → C1 → C2 → A4 → A5 → C3 → C4 → C5 → A6 → A7 → B5 → C6.
운영 묶음: A4(BFF eta 통과) + B4(mount 전환) 같은 배포 사이클.

---

## Task B1: Vite 프로젝트 셋업 + graph.html 이전

**Goal:** fe/ 에 Vite + TS + Tailwind + React 도입. 빈 entry 로 build 통과 확인. 현 fe/index.html / fe/graph.html 은 그대로 (병행 동작). graph.html 만 fe/public/ 으로 이동 (Vite copy).

**Files:**
- Create: `fe/package.json`
- Create: `fe/vite.config.ts`
- Create: `fe/tsconfig.json`
- Create: `fe/tsconfig.node.json`
- Create: `fe/tailwind.config.js`
- Create: `fe/postcss.config.js`
- Create: `fe/.gitignore` (node_modules, dist)
- Create: `fe/src/desktop/main.tsx` (placeholder)
- Move: `fe/graph.html` → `fe/public/graph.html`
- Modify: `fe/README.md` (Vite 사용법 추가, 기존 readme 위에)

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/b1-vite-setup
```

- [ ] **Step 2: package.json**

`fe/package.json`:

```json
{
  "name": "cf-fe",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 4173",
    "test": "vitest run"
  },
  "dependencies": {
    "leaflet": "^1.9.4",
    "leaflet.markercluster": "^1.5.3",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/leaflet": "^1.9.12",
    "@types/leaflet.markercluster": "^1.5.4",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.41",
    "tailwindcss": "^3.4.10",
    "typescript": "^5.5.4",
    "vite": "^5.4.2",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 3: tsconfig**

`fe/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "resolveJsonModule": true,
    "useDefineForClassFields": true,
    "types": ["vite/client", "vitest/globals"]
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`fe/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: vite.config.ts**

`fe/vite.config.ts`:

```ts
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
});
```

- [ ] **Step 5: Tailwind + PostCSS**

`fe/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./m.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
```

`fe/postcss.config.js`:

```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 6: .gitignore + 빈 entry**

`fe/.gitignore`:

```
node_modules/
dist/
*.local
.vite/
```

`fe/src/desktop/main.tsx` (placeholder — B3 에서 진짜 App 으로 교체):

```tsx
// B1 placeholder — B3 에서 App.tsx import + render 로 교체
import "./styles.css";

const root = document.getElementById("root");
if (root) root.textContent = "fe (Vite) — placeholder. B3 에서 실제 App 부착.";
```

`fe/src/desktop/styles.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: graph.html 이전**

```bash
mkdir -p fe/public
git mv fe/graph.html fe/public/graph.html
```

graph.html 내부의 base URL 결정 로직은 SP-A A5 에서 갱신. B1 단계에서는 그대로 옮기기만.

- [ ] **Step 8: 새 index.html (Vite entry) — B3 까지 대기**

⚠️ B1 에서는 *Vite-style* index.html 을 만들지 *않음*. 현 fe/index.html (CDN+Babel, 1797 lines) 그대로 유지. B3 에서 교체.

대신 build 가 동작하는지 확인하기 위해, **임시 index.html.new 를 사용하지 않고** Vite 가 현 index.html 을 어떻게 다루는지 확인:

```bash
cd fe && npm install
npm run build 2>&1 | tail -20
cd ..
```

⚠️ Vite 가 현 index.html 의 `<script type="text/babel">` 을 만나면 인식 못 해 빌드 실패할 수 있음. 그럴 경우:

옵션 A (권장): 현 index.html 임시 백업, Vite-friendly placeholder 로 교체. B3 에서 진짜 entry 로 교체.

```bash
git mv fe/index.html fe/index.legacy.html
```

`fe/index.html` 신규 (Vite entry placeholder):

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>cf — placeholder</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/desktop/main.tsx"></script>
</body>
</html>
```

⚠️ 이 시점부터 fe 가 정상 페이지를 서빙 못함 (placeholder). B2~B3 동안에는 백엔드 mount 가 여전히 fe/ 직접이라면 (B4 전), 사용자가 보는 화면도 placeholder. **B1~B3 작업 동안에는 백엔드의 fe_dir 을 fe/ 그대로 유지하되, 사용자 트래픽 영향 인지**.

대안 — **B1 단계에서 백엔드 mount 를 일시적으로 fe/index.legacy.html 로 분기**:

`backend/be-for-fe/src/cf_be_for_fe/api.py` 또는 cf_be_api 의 mount 부분 (현재 mount 위치):

```python
# B1 단계 임시
@app.get("/", include_in_schema=False)
def temp_root():
    return FileResponse(_settings.fe_dir / "index.legacy.html")
```

⚠️ 이 임시 변경은 B4 (mount 전환) 에서 영구 변경으로 흡수. B1 PR 에서 같이 commit.

⚠️ 본 sprint 의 ⚠️ 가 많은 만큼 — 실행자가 의도 정확히 파악하도록. **결정 추천: 옵션 A + 임시 root 핸들러**. B1 PR 에 `index.legacy.html` 백업 + 새 `index.html` placeholder + 임시 root 핸들러 같이 들어감.

- [ ] **Step 9: build PASS 확인**

```bash
cd fe && npm run build 2>&1 | tail -10
ls dist/
cd ..
```

기대: `fe/dist/index.html`, `fe/dist/graph.html`, `fe/dist/assets/*.js` 산출.

- [ ] **Step 10: Commit (작은 단위)**

```bash
# Commit 1: 패키지 메타
git add fe/package.json fe/tsconfig.json fe/tsconfig.node.json \
        fe/vite.config.ts fe/tailwind.config.js fe/postcss.config.js fe/.gitignore
git commit -m "chore(fe): vite + react + ts + tailwind setup

package.json, tsconfig, vite.config (single entry desktop+proxy),
tailwind/postcss config. SP-B B1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 2: graph.html 이전
git add fe/public/
git commit -m "chore(fe): move graph.html → public/ (Vite copy)

어드민 graph.html 은 CDN+Babel 그대로. Vite 가 dist/graph.html 로 복사.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 3: index.html placeholder + legacy 백업 + 임시 root 핸들러
git add fe/index.html fe/index.legacy.html fe/src/desktop/main.tsx fe/src/desktop/styles.css
git commit -m "chore(fe): placeholder entry + legacy backup

기존 index.html → index.legacy.html (CDN+Babel). 새 index.html 은 Vite entry
placeholder. main.tsx 도 placeholder. B3 에서 진짜 App 부착. SP-B B1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 4: 백엔드 임시 root 핸들러
git add backend/be-for-fe/src/cf_be_for_fe/api.py 2>/dev/null || \
  git add backend/be-api/src/cf_be_api/api.py
git commit -m "feat(backend): temp root handler → fe/index.legacy.html during B1~B3

SP-B 마이그레이션 동안 사용자가 보는 화면은 legacy. B4 mount 전환에서 정리.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: Push + PR + auto-merge**

```bash
git push -u origin sprint/b1-vite-setup
gh pr create --title "chore(fe): vite + react + ts setup (SP-B B1)" \
  --body "$(cat <<'EOF'
## Summary
SP-B sprint B1.

- Vite + React 18 + TS strict + Tailwind + PostCSS 도입
- vite.config: desktop entry only (mobile 은 C1 에서 추가) + dev proxy 8070
- graph.html → public/graph.html (Vite copy 패스스루, 어드민 CDN+Babel 유지)
- 현 index.html → index.legacy.html 백업, 새 index.html 은 placeholder
- 백엔드 임시 root → legacy (B3 까지 사용자 화면 영향 없음)

다음 sprint B2: 데이터 계층 (hooks/api/types) shared 추출.

## Test plan
- [x] cd fe && npm install PASS
- [x] npm run build PASS, dist/ 산출
- [x] dist/graph.html 존재

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --auto --merge
```

---

## Task B2: 데이터 계층 추출 → src/shared/

**Goal:** fe/index.legacy.html 의 hooks·헬퍼·constants 를 `src/shared/` 의 TS 모듈로 이전. JSX 없는 순수 데이터 계층. tsc strict 통과.

**Files:**
- Create: `fe/src/shared/api.ts`
- Create: `fe/src/shared/types.ts`
- Create: `fe/src/shared/constants.ts`
- Create: `fe/src/shared/geo.ts`
- Create: `fe/src/shared/filters.ts`
- Create: `fe/src/shared/hooks/useFacets.ts`
- Create: `fe/src/shared/hooks/useSites.ts`
- Create: `fe/src/shared/hooks/useDetail.ts`
- Create: `fe/src/shared/hooks/useUserLocation.ts`
- Create: `fe/src/shared/hooks/useFeaturedAxes.ts`
- Create: `fe/src/shared/hooks/useManagementMarks.ts`
- Create: `fe/src/shared/hooks/useEtaBatch.ts`
- Create: `fe/src/shared/styles/tokens.css`
- Create: `fe/tests/shared/geo.test.ts`
- Create: `fe/tests/shared/filters.test.ts`

**원본 라인 매핑 (index.legacy.html):**
- 129~131: `API` 상수 → `api.ts` (env 기반으로 재작성)
- 136~144: `useFacets` → `hooks/useFacets.ts`
- 150~153: `CONCEPT_FILTER_KEYS` → `filters.ts`
- 155~159: `setSerialize` → `filters.ts`
- 161~201: `useSites` → `hooks/useSites.ts`
- 203~218: `useManagementMarks` → `hooks/useManagementMarks.ts`
- 221~228: `useDetail` → `hooks/useDetail.ts`
- 230~261: `useUserLocation` → `hooks/useUserLocation.ts`
- 266~282: `haversineKm`, `formatKm` → `geo.ts`
- 284~297: `useFeaturedAxes` → `hooks/useFeaturedAxes.ts`
- 299~308: `fetchEtaBatch` + (관련 useEtaBatch 추론) → `hooks/useEtaBatch.ts`
- ETA_HARD_CAP 등 상수 → `constants.ts`

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/b2-shared-extract
```

- [ ] **Step 2: types.ts**

`fe/src/shared/types.ts`:

```ts
// 도메인 타입 — fe-friendly projection (BFF 적용 후 형태)

export interface Site {
  id: string;
  name: string;
  sido?: string;
  sigungu?: string;
  lat?: number;
  lon?: number;
  categories?: string[];
  locationTypes?: string[];
  collections?: { name: string }[];
  // ... fe/index.legacy.html 의 row.* 사용처를 grep 으로 채움
  [extra: string]: unknown;   // 점진적 강화
}

export interface FeaturedAxis {
  id: string;
  name: string;
  icon?: string;
  color?: string;
  conceptIds?: string[];
}

export interface FacetData {
  regions: Array<{ sido: string; sigungu: string; count: number }>;
  concept_axes: unknown[];
  concepts: unknown[];
  themes: unknown[];
}

export type MgmtLevel = "bib" | "recommended" | "notable" | "exceptional";

export interface MgmtMark {
  camp_id: string;
  level: MgmtLevel;
}

export interface EtaResult {
  minutes?: number;
  within?: boolean;
  error?: string;
}

export interface EtaBatchResponse {
  results: Record<string, EtaResult>;
}

export interface UserCoords {
  lat: number;
  lon: number;
}

export type UserLocStatus = "idle" | "asking" | "ok" | "denied" | "error" | "unsupported";
```

⚠️ row 의 정확한 키들은 fe/index.legacy.html 의 사용처 (`r.lat`, `r.lon`, `r.sido`, `r.collections`, `r.featured`, `r.management`, etc.) grep 으로 도출:

```bash
grep -oE "r\.[a-zA-Z_]+\b" fe/index.legacy.html | sort -u
```

- [ ] **Step 3: api.ts**

`fe/src/shared/api.ts`:

```ts
/**
 * API base URL.
 *
 * - Vite dev (port 5173): proxy 가 /sites 등을 8070 으로 → base = "" 동일 origin
 * - Production (BFF mount): 동일 origin → base = ""
 * - 명시 환경변수 VITE_API_BASE 가 있으면 우선 (예: 어드민 분리 호스트)
 */
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(API_BASE + path, location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const r = await fetch(url.toString());
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

export async function postJson<T, B>(path: string, body: B, signal?: AbortSignal): Promise<T> {
  const r = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

export function buildSitesUrl(params: { region?: string; concept?: string[] }): string {
  const u = new URLSearchParams();
  if (params.region) u.append("region", params.region);
  for (const id of params.concept ?? []) u.append("concept", id);
  return `${API_BASE}/sites?${u.toString()}`;
}
```

- [ ] **Step 4: constants.ts**

`fe/src/shared/constants.ts`:

```ts
/**
 * ETA 계산이 호출하는 fleet 상한. 너무 많은 점을 etago 에 던지면 부하 폭발 →
 * fe 가 "ETA 적용" 누를 때 후보가 N 개 초과면 미리 잘라 BFF 호출.
 */
export const ETA_HARD_CAP = 200;

/**
 * 대표축 색상 매핑 — index.legacy.html style 의 .pin-pin.<axis> 와 일치해야.
 * (실제 값은 index.legacy.html 의 :root + style 블록에서 복사)
 */
export const AXIS_COLORS: Record<string, string> = {
  valley: "#2c6e7b",
  kids: "#c8553d",
  trampoline: "#6b4f2c",
  halloween: "#ff7518",
  cherry: "#ffb7c5",
  autumn: "#d35400",
};
```

- [ ] **Step 5: geo.ts**

`fe/src/shared/geo.ts`:

```ts
/**
 * Haversine — 두 점의 대권 거리 km.
 * 원본: fe/index.legacy.html:266
 */
export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/**
 * km 포맷 — < 1km 면 m, < 10km 면 소수점 1, 그 이상 정수 km.
 * 원본: fe/index.legacy.html:276
 */
export function formatKm(km: number | null | undefined): string {
  if (km == null) return "";
  if (km < 1) return `${Math.round(km * 1000)} m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}
```

- [ ] **Step 6: filters.ts**

`fe/src/shared/filters.ts`:

```ts
import type { Site } from "./types";

/**
 * Concept-shaped filter slots. 모든 슬롯의 값들을 union 해서
 * repeated `concept=<id>` 쿼리로 BFF 호출. 백엔드 AND 의미.
 * 원본: fe/index.legacy.html:150
 */
export const CONCEPT_FILTER_KEYS = [
  "conceptAxis",
  "view",
  "facility",
  "kidsFacility",
  "surface",
  "space",
  "parking",
  "audience",
  "vibe",
] as const;

export type ConceptFilterKey = (typeof CONCEPT_FILTER_KEYS)[number];

/**
 * Set 의 stable string — useEffect deps 용.
 * 원본: fe/index.legacy.html:155
 */
export function setSerialize(set: Set<string> | undefined): string {
  if (!set || set.size === 0) return "";
  return [...set].sort().join("|");
}

/**
 * 클라사이드 필터 — region 다중·terrain·collection·facilityRaw·management 등
 * 서버 인덱스 없는 컬럼들. 데스크톱 / 모바일 동일 로직.
 *
 * (원본은 fe/index.legacy.html 의 App 안의 visibleRows useMemo —
 *  거기서 클라사이드 필터 부분만 추출. 정확한 로직은 원본 1:1 복사.)
 */
export function visibleRows(rows: Site[], filters: Filters): Site[] {
  // 원본의 visibleRows 본체 그대로 (region 다중, terrain, collection,
  // facilityRaw, management, featured 토글 등) — index.legacy.html 의
  // App() 안에서 추출. ⚠️ 작업 시 원본 코드를 그대로 복사하고 타입만 부여.
  return rows;   // placeholder — 실제 구현은 원본 복제
}

export interface Filters {
  region: Set<string>;
  // ... CONCEPT_FILTER_KEYS 별 Set<string>
  terrain?: Set<string>;
  collection?: Set<string>;
  facilityRaw?: Set<string>;
  management?: Set<string>;
  featured?: Set<string>;
}
```

⚠️ `visibleRows` 본체는 fe/index.legacy.html 의 App() 안 useMemo 에서 그대로 복제 — 길이 ~80 라인 추정. 위 코드는 시그니처/타입만.

- [ ] **Step 7: hooks 7개**

`fe/src/shared/hooks/useFacets.ts`:

```ts
import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { FacetData } from "../types";

/**
 * 원본: fe/index.legacy.html:136
 */
export function useFacets(): { data: FacetData; err: string | null } {
  const [data, setData] = useState<FacetData>({
    regions: [],
    concept_axes: [],
    concepts: [],
    themes: [],
  });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    getJson<FacetData>("/facets")
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);
  return { data, err };
}
```

`fe/src/shared/hooks/useSites.ts`:

```ts
import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "../api";
import { CONCEPT_FILTER_KEYS, setSerialize, type Filters } from "../filters";
import type { Site } from "../types";

/**
 * 원본: fe/index.legacy.html:161
 */
export function useSites(filters: Filters): { rows: Site[]; loading: boolean; err: string | null } {
  const [rows, setRows] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const conceptKey = useMemo(
    () => CONCEPT_FILTER_KEYS.map((k) => setSerialize((filters as any)[k])).join("/"),
    CONCEPT_FILTER_KEYS.map((k) => (filters as any)[k]),
  );
  const regionKey = useMemo(() => setSerialize(filters.region), [filters.region]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (filters.region.size === 1) {
      const [only] = filters.region;
      params.append("region", only);
    }
    const conceptIds = new Set<string>();
    for (const k of CONCEPT_FILTER_KEYS) {
      const s = (filters as any)[k] as Set<string> | undefined;
      if (!s) continue;
      for (const v of s) conceptIds.add(v);
    }
    for (const id of conceptIds) params.append("concept", id);

    setLoading(true);
    setErr(null);
    fetch(`${API_BASE}/sites?${params.toString()}`)
      .then((r) => r.json())
      .then((d) => setRows(Array.isArray(d) ? d : []))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [regionKey, conceptKey]);

  return { rows, loading, err };
}
```

`fe/src/shared/hooks/useDetail.ts`:

```ts
import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { Site } from "../types";

/**
 * 원본: fe/index.legacy.html:221
 */
export function useDetail(id: string | null): Site | null {
  const [data, setData] = useState<Site | null>(null);
  useEffect(() => {
    if (!id) {
      setData(null);
      return;
    }
    getJson<Site>(`/sites/${id}`)
      .then(setData)
      .catch(() => setData(null));
  }, [id]);
  return data;
}
```

`fe/src/shared/hooks/useUserLocation.ts`:

```ts
import { useCallback, useEffect, useState } from "react";
import type { UserCoords, UserLocStatus } from "../types";

/**
 * 원본: fe/index.legacy.html:230
 */
export function useUserLocation(): {
  coords: UserCoords | null;
  status: UserLocStatus;
  refresh: () => void;
} {
  const [state, setState] = useState<{ coords: UserCoords | null; status: UserLocStatus }>({
    coords: null,
    status: "idle",
  });

  const refresh = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState({ coords: null, status: "unsupported" });
      return;
    }
    setState((s) => ({ coords: s.coords, status: "asking" }));
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setState({
          coords: { lat: pos.coords.latitude, lon: pos.coords.longitude },
          status: "ok",
        }),
      (err) =>
        setState({
          coords: null,
          status: err.code === err.PERMISSION_DENIED ? "denied" : "error",
        }),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 5 * 60 * 1000 },
    );
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { ...state, refresh };
}
```

`fe/src/shared/hooks/useFeaturedAxes.ts`:

```ts
import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { FeaturedAxis } from "../types";

/**
 * 원본: fe/index.legacy.html:284
 */
export function useFeaturedAxes(): FeaturedAxis[] {
  const [axes, setAxes] = useState<FeaturedAxis[]>([]);
  useEffect(() => {
    getJson<FeaturedAxis[]>("/featured-axes")
      .then((d) => setAxes(Array.isArray(d) ? d : []))
      .catch(() => setAxes([]));
  }, []);
  return axes;
}
```

`fe/src/shared/hooks/useManagementMarks.ts`:

```ts
import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { MgmtLevel, MgmtMark } from "../types";

/**
 * 원본: fe/index.legacy.html:203
 * 한 번에 모두 fetch — 칩 토글마다 재요청 안 함.
 */
export function useManagementMarks(): Map<string, MgmtLevel> | null {
  const [byId, setById] = useState<Map<string, MgmtLevel> | null>(null);
  useEffect(() => {
    getJson<MgmtMark[]>("/marks/management/camps", { limit: 2000 })
      .then((arr) => {
        const m = new Map<string, MgmtLevel>();
        if (Array.isArray(arr)) for (const x of arr) m.set(x.camp_id, x.level);
        setById(m);
      })
      .catch(() => setById(new Map()));
  }, []);
  return byId;
}
```

`fe/src/shared/hooks/useEtaBatch.ts`:

```ts
import { useState, useCallback } from "react";
import { postJson } from "../api";
import type { EtaBatchResponse, UserCoords } from "../types";

interface BatchInput {
  origin: UserCoords;
  ids: string[];
  max_minutes?: number;
}

/**
 * 원본: fetchEtaBatch (fe/index.legacy.html:299) + App.tsx 의 ETA 상태 관리 일부.
 * loading/results/error/abort 상태를 한 훅으로 묶음.
 */
export function useEtaBatch(): {
  results: Record<string, { minutes?: number; within?: boolean; error?: string }> | null;
  loading: boolean;
  err: string | null;
  apply: (input: BatchInput) => Promise<void>;
  clear: () => void;
} {
  const [results, setResults] = useState<EtaBatchResponse["results"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const apply = useCallback(async (input: BatchInput) => {
    setLoading(true);
    setErr(null);
    try {
      const body = { ...input, concurrency: 4, timeout_s: 12 };
      const data = await postJson<EtaBatchResponse, typeof body>("/eta/batch", body);
      setResults(data.results);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setResults(null);
    setErr(null);
  }, []);

  return { results, loading, err, apply, clear };
}
```

- [ ] **Step 8: tokens.css**

`fe/src/shared/styles/tokens.css`:

```css
:root {
  --moss: #2c4a3e;
  --moss-deep: #1a2f26;
  --moss-soft: #cfdcc9;
  --bark: #6b4f2c;
  --paper: #f4f1e8;
  --paper-2: #ebe5d2;
  --ink: #1a1a17;
  --ember: #c8553d;
}
```

(fe/index.legacy.html 의 :root 블록 그대로 복사.)

- [ ] **Step 9: 단위 테스트**

`fe/tests/shared/geo.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { haversineKm, formatKm } from "../../src/shared/geo";

describe("haversineKm", () => {
  it("returns 0 for same point", () => {
    expect(haversineKm(37.5, 127.0, 37.5, 127.0)).toBeCloseTo(0, 5);
  });
  it("approx Seoul → Busan ~325km", () => {
    const km = haversineKm(37.5665, 126.978, 35.1796, 129.0756);
    expect(km).toBeGreaterThan(300);
    expect(km).toBeLessThan(360);
  });
});

describe("formatKm", () => {
  it("renders < 1km in m", () => {
    expect(formatKm(0.42)).toBe("420 m");
  });
  it("renders < 10km with one decimal", () => {
    expect(formatKm(3.7)).toBe("3.7 km");
  });
  it("renders >= 10km as integer", () => {
    expect(formatKm(42.3)).toBe("42 km");
  });
  it("returns empty for null", () => {
    expect(formatKm(null)).toBe("");
  });
});
```

`fe/tests/shared/filters.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { setSerialize, CONCEPT_FILTER_KEYS } from "../../src/shared/filters";

describe("setSerialize", () => {
  it("returns empty string for empty set", () => {
    expect(setSerialize(new Set())).toBe("");
  });
  it("returns sorted pipe-joined string", () => {
    expect(setSerialize(new Set(["b", "a", "c"]))).toBe("a|b|c");
  });
});

describe("CONCEPT_FILTER_KEYS", () => {
  it("matches the spec'd 9 slots", () => {
    expect(CONCEPT_FILTER_KEYS).toEqual([
      "conceptAxis", "view", "facility", "kidsFacility",
      "surface", "space", "parking", "audience", "vibe",
    ]);
  });
});
```

- [ ] **Step 10: build + tsc strict + vitest**

```bash
cd fe
npm install   # vitest 첫 추가
npx tsc --noEmit 2>&1 | tail -20
npm run test 2>&1 | tail -10
npm run build 2>&1 | tail -5
cd ..
```

기대:
- tsc: 에러 0
- vitest: 8 PASS (geo 4 + filters 2 + 그 외 sanity)
- build: PASS

⚠️ 첫 시도에서 strict 가 짜증날 수 있음 — `Site` 의 `[extra: string]: unknown` 인덱스 시그니처 때문에 hooks 안의 `r.lat` 등 직접 접근에서 narrowing 필요. 빠른 처리: `// @ts-expect-error TODO: strict types for Site` 주석 후 후속 cleanup.

- [ ] **Step 11: Commit**

```bash
# Commit 1: types + api + constants
git add fe/src/shared/types.ts fe/src/shared/api.ts fe/src/shared/constants.ts
git commit -m "feat(fe/shared): types + api client + constants

JSX 없는 순수 데이터 계층. SP-B B2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 2: geo + filters + tokens
git add fe/src/shared/geo.ts fe/src/shared/filters.ts fe/src/shared/styles/
git commit -m "feat(fe/shared): geo + filters + design tokens

haversineKm/formatKm, CONCEPT_FILTER_KEYS/setSerialize/visibleRows skeleton,
tokens.css. SP-B B2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 3: hooks 7개
git add fe/src/shared/hooks/
git commit -m "feat(fe/shared): hooks — facets/sites/detail/userLocation/featuredAxes/marks/eta

원본 fe/index.legacy.html 의 7 hooks 를 TS 로 이전. SP-B B2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 4: 테스트
git add fe/tests/
git commit -m "test(fe/shared): geo + filters unit tests (vitest)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 12: Push + PR**

```bash
git push -u origin sprint/b2-shared-extract
gh pr create --title "feat(fe/shared): data layer extract (SP-B B2)" \
  --body "SP-B sprint B2. types/api/constants/geo/filters/hooks 7개 + tokens.css + vitest.

다음 sprint B3: 데스크톱 컴포넌트 이전 + 진짜 entry.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task B3: 데스크톱 컴포넌트 이전 + entry 부착 + 회귀 fixture

**Goal:** index.legacy.html 의 컴포넌트 (App, FilterBar, EtaBar, CampList, MapView, MiniMap, DetailPanel, SearchBox, LocationPill, Stat, Chip, MultiChip, FilterRow, PinDots, DynamicChip, EtaBadge) 를 `src/desktop/components/*.tsx` 로 이전. main.tsx 에서 `<App />` 부착. Playwright 5 시나리오 회귀.

**Files:**
- Create: `fe/src/desktop/App.tsx`
- Create: `fe/src/desktop/components/MapView.tsx`
- Create: `fe/src/desktop/components/MiniMap.tsx`
- Create: `fe/src/desktop/components/FilterBar.tsx` (FilterRow, MultiChip 포함 또는 분리)
- Create: `fe/src/desktop/components/CampList.tsx`
- Create: `fe/src/desktop/components/DetailPanel.tsx`
- Create: `fe/src/desktop/components/SearchBox.tsx`
- Create: `fe/src/desktop/components/EtaBar.tsx`
- Create: `fe/src/desktop/components/LocationPill.tsx`
- Create: `fe/src/desktop/components/atoms.tsx` (Stat, Chip, PinDots, DynamicChip, EtaBadge — 작은 visual atoms)
- Modify: `fe/src/desktop/main.tsx` — placeholder 제거, ReactDOM.createRoot + App
- Modify: `fe/src/desktop/styles.css` — index.legacy.html 의 <style> 블록 옮김 (CSS 변수는 tokens.css 에 있음)
- Create: `fe/tests/playwright/desktop.spec.ts`
- Create: `fe/playwright.config.ts`

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/b3-desktop-components
```

- [ ] **Step 2: styles.css 보강 — legacy 의 style 블록 이전**

`fe/index.legacy.html` 의 `<style>` 블록 (line ~28~120) 의 `:root`, `body`, `.topo`, `.display`, `.hairline`, `.chip`, `.btn`, `.toggle-pill`, `.card`, `.num`, `.kbd`, `.leaflet-container`, `.pin-cluster`, `.pin-pin*`, scrollbar 모두 `fe/src/desktop/styles.css` 에 옮김 (`:root` 는 tokens.css 와 중복 제거).

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@import "../shared/styles/tokens.css";

/* index.legacy.html style 블록 본체 — :root 제외 */
html, body { height: 100%; }
body { font-family: ...; background: ...; }
.topo { background-image: url("..."); }
/* ... 끝까지 복사 */
```

- [ ] **Step 3: atoms.tsx**

`fe/src/desktop/components/atoms.tsx`:

```tsx
import type { FeaturedAxis, Site } from "../../shared/types";

/** 원본: fe/index.legacy.html:380 */
export function Chip({ children, tone }: { children: React.ReactNode; tone?: "warm" | "bark" }) {
  const className = tone === "warm" ? "chip warm" : tone === "bark" ? "chip bark" : "chip";
  return <span className={className}>{children}</span>;
}

/** 원본: fe/index.legacy.html:385 */
export function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-[0.3em] text-stone-500 font-medium">{label}</div>
      <div className="display text-lg font-bold leading-none mt-1 num">{value}</div>
      {sub && <div className="text-[10px] text-stone-500 mt-1">{sub}</div>}
    </div>
  );
}

/** 원본: fe/index.legacy.html:342 */
export function PinDots({ row, axes }: { row: Site; axes: FeaturedAxis[] }) {
  // 원본 1:1 복사
  return null;   // ⚠️ 작업 시 원본 본체 복제
}

/** 원본: fe/index.legacy.html:353 */
export function DynamicChip(props: { name: string; active: boolean; onClick: () => void; count?: number }) {
  return null;   // ⚠️ 원본 복제
}

/** 원본: fe/index.legacy.html:369 */
export function EtaBadge({ minutes, within, error }: { minutes?: number; within?: boolean; error?: string }) {
  return null;   // ⚠️ 원본 복제
}
```

⚠️ ⚠️ 마커가 붙은 컴포넌트들은 fe/index.legacy.html 의 해당 라인부터 함수 끝까지 *그대로* 복제. JSX 는 그대로, 함수 시그니처에 TS 타입만 부여. 클래스명·스타일 동일.

- [ ] **Step 4: 나머지 컴포넌트들 — 동일 패턴**

각 컴포넌트:
1. fe/index.legacy.html 의 해당 함수 본체 복사
2. 새 파일 (e.g., `fe/src/desktop/components/MapView.tsx`) 에 붙이기
3. props 타입 정의 (`interface MapViewProps { rows: Site[]; ... }`)
4. import 정리 (React, hooks, types)
5. tsc strict 통과 — narrowing 안 되면 `// @ts-expect-error` 임시 마커

라인 매핑:
- `MapView`: line 430~566 → MapView.tsx
- `MiniMap`: line 568~644 → MiniMap.tsx
- `toggleChipSelection`: line 646 → atoms.tsx 또는 FilterBar.tsx 안으로
- `MultiChip`: line 660~677 → FilterBar.tsx 안 (또는 별도)
- `FilterRow`: line 679~716 → FilterBar.tsx 안
- `FilterBar`: line 718~1061 → FilterBar.tsx
- `SearchBox`: line 1063~1140 → SearchBox.tsx
- `CampList`: line 1142~1205 → CampList.tsx
- `DetailPanel`: line 1207~1372 → DetailPanel.tsx
- `EtaBar`: line 1374~1422 → EtaBar.tsx
- `minutesFrom`: line 1424 → EtaBar.tsx 안
- `App`: line 1426~1784 → App.tsx

각 파일의 import:

```tsx
import { useState, useEffect, useMemo, useRef, useCallback } from "react";
// hooks
import { useFacets } from "../../shared/hooks/useFacets";
import { useSites } from "../../shared/hooks/useSites";
// 등 필요한 것
import type { Site, FeaturedAxis } from "../../shared/types";
```

- [ ] **Step 5: App.tsx — index.legacy.html App() 본체 복제**

`fe/src/desktop/App.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useFacets } from "../shared/hooks/useFacets";
import { useSites } from "../shared/hooks/useSites";
import { useDetail } from "../shared/hooks/useDetail";
import { useUserLocation } from "../shared/hooks/useUserLocation";
import { useFeaturedAxes } from "../shared/hooks/useFeaturedAxes";
import { useManagementMarks } from "../shared/hooks/useManagementMarks";
import { useEtaBatch } from "../shared/hooks/useEtaBatch";
import { ETA_HARD_CAP } from "../shared/constants";
import { CampList } from "./components/CampList";
import { MapView } from "./components/MapView";
import { DetailPanel } from "./components/DetailPanel";
import { FilterBar } from "./components/FilterBar";
import { EtaBar } from "./components/EtaBar";
import { SearchBox } from "./components/SearchBox";
import { LocationPill } from "./components/LocationPill";
import { Stat } from "./components/atoms";

export function App() {
  // ⚠️ fe/index.legacy.html line 1426~1784 의 App 본체 그대로 복사.
  // - useState/useMemo 호출들 그대로
  // - JSX 그대로
  // - 클래스명·스타일·이벤트 핸들러 그대로
  // 단지 import 가 위에서 가져옴.
  return <div className="h-screen flex flex-col overflow-hidden">{/* ... */}</div>;
}
```

- [ ] **Step 6: main.tsx — App 부착**

`fe/src/desktop/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("#root not found");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// esc 단축키 — 원본 fe/index.legacy.html line ~1786
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") window.dispatchEvent(new CustomEvent("camfit:close-detail"));
});
```

- [ ] **Step 7: index.html — Vite entry 본판**

`fe/index.html` (B1 의 placeholder 교체):

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>camfit-puller — 캠핑장 지도</title>
  <link rel="stylesheet" as="style" crossorigin
    href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/desktop/main.tsx"></script>
</body>
</html>
```

⚠️ Leaflet CSS 는 일단 CDN 유지 (markercluster 의 background-image url 이 CDN 패스 가정). npm 으로 옮기려면 CSS path 별도 fix 필요 — B5 cleanup 에서.

- [ ] **Step 8: build + 수동 smoke**

```bash
cd fe
npm install leaflet leaflet.markercluster @types/leaflet @types/leaflet.markercluster   # 누락 시
npx tsc --noEmit 2>&1 | tail -20
npm run build 2>&1 | tail -10
npm run preview &
PREVIEW_PID=$!
sleep 2
# 브라우저: http://localhost:4173 — 데스크톱 페이지가 정상 렌더되어야
echo "manual: open http://localhost:4173 + click 5 features"
sleep 30
kill $PREVIEW_PID
cd ..
```

수동 검증 5개 (체크리스트):
- [ ] 홈 진입 후 지도 + 카드 리스트 + 헤더 컨트롤 표시
- [ ] 지역 chip 1개 클릭 → 카드 갱신 + 지도 핀 갱신
- [ ] 카드 클릭 → DetailPanel 우슬라이드
- [ ] 분할/지도/리스트 토글 각각 변경
- [ ] 검색어 입력 → 결과 표시

- [ ] **Step 9: Playwright 셋업 + 회귀 fixture**

`fe/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/playwright",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:4173",
    headless: true,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run preview -- --port 4173",
    port: 4173,
    reuseExistingServer: true,
  },
});
```

`fe/tests/playwright/desktop.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test.describe("desktop fe — B3 회귀", () => {
  test("home renders header + cards + map", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator(".leaflet-container")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/총/)).toBeVisible();
  });

  test("apply region chip updates list", async ({ page }) => {
    await page.goto("/");
    // 첫 region chip 클릭 — 정확한 셀렉터는 FilterBar 구현에 따라 조정
    const firstRegion = page.locator('[data-region]').first();
    if (await firstRegion.count() > 0) {
      await firstRegion.click();
      await expect(page.locator(".card")).toHaveCount({ timeout: 3000 } as any);
    }
  });

  test("card click opens DetailPanel", async ({ page }) => {
    await page.goto("/");
    await page.locator(".card").first().click();
    // DetailPanel 가 우측에서 슬라이드인 — fixed position
    await expect(page.locator('[data-panel="detail"]')).toBeVisible({ timeout: 2000 });
  });

  test("view toggle split/map/list", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "지도" }).click();
    await expect(page.locator(".leaflet-container")).toBeVisible();
    await page.getByRole("button", { name: "리스트" }).click();
    // 리스트 모드 — 지도 사라짐
  });

  test("search returns results", async ({ page }) => {
    await page.goto("/");
    const search = page.locator('input[placeholder*="검색"]');
    await search.fill("강원");
    await search.press("Enter");
    await expect(page.getByText(/검색결과/)).toBeVisible({ timeout: 3000 });
  });
});
```

⚠️ 셀렉터들 (`[data-region]`, `[data-panel="detail"]`) 은 컴포넌트가 `data-*` 속성을 노출해야 동작. 컴포넌트 작성 시 추가 또는 텍스트 기반 fallback 사용.

```bash
cd fe
npm install -D @playwright/test
npx playwright install chromium
npx playwright test 2>&1 | tail -10
cd ..
```

기대: 5 PASS (또는 일부는 데이터 의존성으로 skip).

- [ ] **Step 10: Commit (작은 단위 — 파일 그룹별)**

```bash
# Commit 1: atoms + 작은 컴포넌트
git add fe/src/desktop/styles.css fe/src/desktop/components/atoms.tsx \
        fe/src/desktop/components/LocationPill.tsx \
        fe/src/desktop/components/SearchBox.tsx
git commit -m "feat(fe/desktop): atoms + LocationPill + SearchBox

원본 index.legacy.html 의 visual atoms 와 작은 컴포넌트 이전. SP-B B3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 2: 큰 컴포넌트
git add fe/src/desktop/components/MapView.tsx \
        fe/src/desktop/components/MiniMap.tsx \
        fe/src/desktop/components/CampList.tsx \
        fe/src/desktop/components/DetailPanel.tsx \
        fe/src/desktop/components/FilterBar.tsx \
        fe/src/desktop/components/EtaBar.tsx
git commit -m "feat(fe/desktop): MapView, FilterBar, CampList, DetailPanel, EtaBar

본격 컴포넌트 6개 이전. SP-B B3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 3: App + entry
git add fe/src/desktop/App.tsx fe/src/desktop/main.tsx fe/index.html
git commit -m "feat(fe/desktop): App + main.tsx + Vite index.html

Placeholder 교체 + ReactDOM.createRoot. SP-B B3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# Commit 4: Playwright
git add fe/playwright.config.ts fe/tests/playwright/ fe/package.json
git commit -m "test(fe/desktop): playwright 5-scenario regression

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: Push + PR**

```bash
git push -u origin sprint/b3-desktop-components
gh pr create --title "feat(fe/desktop): components + App + Vite entry (SP-B B3)" \
  --body "SP-B sprint B3. 데스크톱 컴포넌트 16개 이전 + Vite entry 부착 + Playwright 5 회귀.

다음 sprint B4: 백엔드 mount 전환 fe/ → fe/dist/.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task B4: 백엔드 mount → fe/dist/ 전환

**Goal:** 백엔드 (cf_be_for_fe 또는 cf_be_api 진행 상태에 따라) 의 `fe_dir` 을 `fe/` → `fe/dist/` 로. 빌드 산출이 서빙. dev 모드는 Vite proxy.

**Files:**
- Modify: `backend/be-for-fe/src/cf_be_for_fe/settings.py` (SP-A 진행 시) — `fe_dir` 추가
- Or modify: `backend/be-api/src/cf_be_api/settings.py` (SP-A 미진행 시) — `fe_dir` 변경
- Modify: 해당 `api.py` — mount 의 디렉터리 변경, B1 의 임시 root 핸들러 제거
- Modify: `fe/README.md` — 빌드·배포 안내

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/b4-mount-dist
```

- [ ] **Step 2: 현 mount 위치 식별**

```bash
grep -rn "StaticFiles\|fe_dir\|FileResponse.*fe" backend/
```

대상 파일 결정 — SP-A 진행 정도에 따라 cf_be_for_fe/api.py 또는 cf_be_api/api.py.

- [ ] **Step 3: settings 갱신**

`backend/be-for-fe/src/cf_be_for_fe/settings.py` (또는 cf_be_api/settings.py):

```python
class Settings(BaseSettings):
    # ... 기존 필드
    fe_dir: Path = Path(__file__).resolve().parents[3] / "fe" / "dist"
```

⚠️ `parents[3]` 의 정확한 깊이는 패키지 위치에 따라 — 실 깊이를 `Path(__file__).resolve()` 출력으로 확인. cf_be_for_fe 의 경우 `backend/be-for-fe/src/cf_be_for_fe/settings.py` → `parents[3]` = `backend/be-for-fe/`. 그러므로 `parents[5]` 가 repo root. 정정:

```python
fe_dir: Path = Path(__file__).resolve().parents[4] / "fe" / "dist"
```

⚠️ 실측: `python -c "from pathlib import Path; print(Path('backend/be-for-fe/src/cf_be_for_fe/settings.py').resolve().parents)"` 로 확인.

- [ ] **Step 4: api.py mount + B1 임시 root 정리**

```python
# 임시 root 핸들러 제거 (B1 에서 추가한 것)
# @app.get("/", include_in_schema=False)
# def temp_root(): ...   # ← 삭제

# StaticFiles mount 는 그대로 (이미 fe_dir 가리킴)
fe_path = _settings.fe_dir
if fe_path.is_dir():
    app.mount("/", StaticFiles(directory=str(fe_path), html=True), name="fe")
```

- [ ] **Step 5: 빌드 후 부팅 smoke**

```bash
cd fe && npm run build && cd ..

# 백엔드 부팅 (BFF 또는 be-api 단독 — SP-A 진행 정도에 따라)
./scripts/dev-up.sh   # SP-A A6 이후
# 또는
uv run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app --port 8070 &

sleep 2
curl -sf http://localhost:8070/ | head -c 200 && echo
# → fe/dist/index.html 의 첫 200byte (TS Vite 빌드 산출)

curl -sf http://localhost:8070/m.html
# → C1 까지는 404 (mobile entry 아직 없음)

curl -sf http://localhost:8070/graph.html | head -c 200
# → fe/dist/graph.html (CDN+Babel)

./scripts/dev-down.sh
```

기대:
- `/` 가 빌드된 데스크톱 페이지 응답
- `/graph.html` 이 그대로 CDN+Babel 페이지 응답
- API 호출 (`/sites` 등) 정상

- [ ] **Step 6: Vite dev mode 검증**

```bash
# 백엔드 부팅
./scripts/dev-up.sh
# 별도 터미널: Vite dev
cd fe && npm run dev
# 브라우저: http://localhost:5173 — Vite HMR + API proxy 8070
```

- [ ] **Step 7: Commit + Push + PR**

```bash
git add backend/ fe/README.md
git commit -m "feat(backend,fe): mount fe/dist/ + remove B1 temp root

settings.fe_dir = repo_root/fe/dist. Vite 빌드 산출이 BFF 에서 서빙.
B1 에서 추가했던 임시 root 핸들러 제거. SP-B B4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/b4-mount-dist
gh pr create --title "feat(backend,fe): mount fe/dist (SP-B B4)" \
  --body "SP-B sprint B4. fe_dir → fe/dist, 임시 root 핸들러 제거. 빌드 산출 서빙.

⚠️ 운영 묶음: SP-A A4 와 같은 배포 사이클 권장.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task B5: 잔여 husk — index.legacy.html 삭제 + README

**Goal:** 더 이상 필요 없는 fe/index.legacy.html 삭제. fe/README.md 갱신.

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/b5-husk-readme
```

- [ ] **Step 2: legacy 파일 삭제**

```bash
git rm fe/index.legacy.html
```

⚠️ 시점: B4 가 머지되어 사용자 트래픽이 fe/dist 로 가고 있음을 확인 후. 이전 머지면 cancel.

- [ ] **Step 3: README 갱신**

`fe/README.md`:

````markdown
# fe/

Vite + React 18 + TypeScript 단일 프로젝트. 두 entry — 데스크톱 (`index.html`) + 모바일 (`m.html`). 어드민 그래프는 `public/graph.html` (CDN+Babel 유지).

## Dev

```sh
# 백엔드 부팅 (별도 터미널)
./scripts/dev-up.sh

# Vite dev 서버 (HMR)
cd fe && npm run dev
# → http://localhost:5173 — API 호출은 8070 으로 proxy
```

## Build & deploy

```sh
cd fe && npm run build
# → fe/dist/index.html, fe/dist/m.html, fe/dist/graph.html, fe/dist/assets/*
```

백엔드 (cf-be-for-fe 또는 cf-be-api) 가 `fe/dist/` 를 `/` 에 mount. 어드민은 graph.html 을 별도 base URL (`?api=`) 로 사용.

## Architecture

`docs/superpowers/specs/2026-05-10-fe-vite-and-mobile-design.md` 참조.

## 디자인 노트

- 모스 그린 / 종이 톤 / ember 강조 — 캠핑/숲 모티프
- Pretendard variable 한글
- 핀 색: 모스 / 청록 (계곡) / ember (키즈) / 갈색 (트램펄린)
- 모바일: 지도 도미넌트 + 3단 BottomSheet

## 디렉터리

```
src/
  shared/        # 데스크톱·모바일 공유 (hooks·api·types·filters·geo·tokens)
  desktop/       # index.html entry — App.tsx + components/*
  mobile/        # m.html entry — MobileShell + BottomSheet 등
public/
  graph.html     # 어드민 (CDN+Babel)
```
````

- [ ] **Step 4: Commit + Push + PR**

```bash
git add -A
git commit -m "chore(fe): drop index.legacy.html + README rewrite

Vite 본판 안정화 후 legacy 백업 제거. README 갱신. SP-B B5 (final).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/b5-husk-readme
gh pr create --title "chore(fe): drop legacy + README (SP-B B5)" --body "SP-B final.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task C1: 모바일 셸 + 빈 entry

**Goal:** `src/mobile/` 셸 — m.html, main.tsx, MobileShell (TopBar + 빈 지도 영역 + 빈 BottomSheet). build 통과, /m.html fetch 가능.

**Files:**
- Create: `fe/m.html`
- Create: `fe/src/mobile/main.tsx`
- Create: `fe/src/mobile/App.tsx`
- Create: `fe/src/mobile/styles.css`
- Create: `fe/src/mobile/components/MobileShell.tsx`
- Create: `fe/src/mobile/components/TopBar.tsx`
- Modify: `fe/vite.config.ts` — `mobile` entry 활성화

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/c1-mobile-shell
```

- [ ] **Step 2: vite.config 갱신**

```ts
build: {
  rollupOptions: {
    input: {
      desktop: resolve(__dirname, "index.html"),
      mobile: resolve(__dirname, "m.html"),
    },
  },
},
```

- [ ] **Step 3: m.html**

`fe/m.html`:

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#2c4a3e" />
  <title>camfit · 모바일</title>
  <link rel="stylesheet" as="style" crossorigin
    href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/mobile/main.tsx"></script>
</body>
</html>
```

`viewport-fit=cover` 는 iOS 노치 안전영역 활용용.

- [ ] **Step 4: styles.css + main.tsx + App.tsx**

`fe/src/mobile/styles.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@import "../shared/styles/tokens.css";

html, body, #root { height: 100dvh; margin: 0; }
body {
  font-family: "Pretendard Variable", Pretendard, ui-sans-serif, system-ui;
  color: var(--ink);
  background: var(--paper);
  overflow: hidden;
}
```

`fe/src/mobile/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("#root not found");
ReactDOM.createRoot(root).render(
  <React.StrictMode><App /></React.StrictMode>
);
```

`fe/src/mobile/App.tsx`:

```tsx
import { MobileShell } from "./components/MobileShell";
export function App() { return <MobileShell />; }
```

- [ ] **Step 5: MobileShell + TopBar (빈 셸)**

`fe/src/mobile/components/TopBar.tsx`:

```tsx
export function TopBar() {
  return (
    <header className="h-14 px-4 flex items-center justify-between border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
      <button aria-label="menu" className="text-xl">≡</button>
      <h1 className="display text-base font-bold">camfit</h1>
      <button aria-label="search" className="text-xl">🔍</button>
    </header>
  );
}
```

`fe/src/mobile/components/MobileShell.tsx`:

```tsx
import { TopBar } from "./TopBar";

export function MobileShell() {
  return (
    <div className="h-dvh flex flex-col">
      <TopBar />
      <main className="flex-1 relative overflow-hidden">
        <div className="absolute inset-0" style={{ background: "var(--paper-2)" }}>
          {/* C2 에서 MobileMap */}
          <p className="text-center mt-20 text-stone-500">지도 자리 (C2)</p>
        </div>
        {/* C2 에서 BottomSheet */}
        <div className="absolute bottom-0 left-0 right-0 h-[120px] bg-white border-t" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
          <div className="mx-auto mt-2 w-9 h-1 rounded-full bg-stone-300" />
          <p className="text-center text-stone-500 mt-3">BottomSheet 자리 (C2)</p>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 6: build + smoke**

```bash
cd fe
npm run build 2>&1 | tail -10
ls dist/m.html dist/index.html dist/graph.html
npm run preview &
PID=$!
sleep 2
curl -sf http://localhost:4173/m.html | head -c 200 && echo
kill $PID
cd ..
```

기대: `dist/m.html` 생성, fetch 시 placeholder 셸 HTML 응답.

- [ ] **Step 7: Commit + Push + PR**

```bash
git add fe/m.html fe/vite.config.ts fe/src/mobile/
git commit -m "feat(fe/mobile): empty shell + Vite mobile entry

m.html + main.tsx + App.tsx + MobileShell + TopBar (placeholder).
vite.config.input 에 mobile 추가. SP-C C1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/c1-mobile-shell
gh pr create --title "feat(fe/mobile): shell + Vite entry (SP-C C1)" \
  --body "SP-C C1. m.html + 빈 셸. 다음 C2 에서 BottomSheet + MobileMap 진짜 부착.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task C2: BottomSheet + MobileMap

**Goal:** vanilla pointer events 기반 3단 스냅 BottomSheet + Leaflet 모바일 컨트롤. shared/hooks 사용.

**Files:**
- Create: `fe/src/mobile/components/BottomSheet.tsx`
- Create: `fe/src/mobile/hooks/useBottomSheet.ts`
- Create: `fe/src/mobile/components/MobileMap.tsx`
- Modify: `fe/src/mobile/components/MobileShell.tsx` — 진짜 컴포넌트 부착

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/c2-bottomsheet-map
```

- [ ] **Step 2: useBottomSheet 훅**

`fe/src/mobile/hooks/useBottomSheet.ts`:

```ts
import { useCallback, useRef, useState } from "react";

export type Snap = "peek" | "half" | "full";

export const SNAP_HEIGHTS: Record<Snap, (vh: number) => number> = {
  peek: () => 120,
  half: (vh) => Math.round(vh * 0.5),
  full: (vh) => vh - 56,    // - TopBar 56dp
};

interface DragState {
  startY: number;
  startHeight: number;
  velocity: number;
  lastY: number;
  lastT: number;
}

export function useBottomSheet(initial: Snap = "peek") {
  const [snap, setSnap] = useState<Snap>(initial);
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const stateRef = useRef<DragState | null>(null);

  const getVh = () => window.innerHeight;
  const currentHeight = dragHeight ?? SNAP_HEIGHTS[snap](getVh());

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture(e.pointerId);
    stateRef.current = {
      startY: e.clientY,
      startHeight: SNAP_HEIGHTS[snap](getVh()),
      velocity: 0,
      lastY: e.clientY,
      lastT: performance.now(),
    };
  }, [snap]);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const s = stateRef.current;
    if (!s) return;
    const dy = e.clientY - s.startY;
    const newH = Math.max(80, Math.min(getVh(), s.startHeight - dy));
    setDragHeight(newH);
    const t = performance.now();
    const dt = Math.max(1, t - s.lastT);
    s.velocity = (s.lastY - e.clientY) / dt;   // px/ms, 위로가 양수
    s.lastY = e.clientY;
    s.lastT = t;
  }, []);

  const onPointerUp = useCallback(() => {
    const s = stateRef.current;
    if (!s) return;
    stateRef.current = null;
    const h = dragHeight ?? SNAP_HEIGHTS[snap](getVh());
    const vh = getVh();
    // 속도 임계 — |v| > 0.5 px/ms 면 방향으로 한 칸 점프
    if (s.velocity > 0.5) {
      setSnap(snap === "peek" ? "half" : "full");
    } else if (s.velocity < -0.5) {
      setSnap(snap === "full" ? "half" : "peek");
    } else {
      // 가장 가까운 스냅으로
      const peekH = SNAP_HEIGHTS.peek(vh);
      const halfH = SNAP_HEIGHTS.half(vh);
      const fullH = SNAP_HEIGHTS.full(vh);
      const dPeek = Math.abs(h - peekH);
      const dHalf = Math.abs(h - halfH);
      const dFull = Math.abs(h - fullH);
      if (dPeek <= dHalf && dPeek <= dFull) setSnap("peek");
      else if (dHalf <= dFull) setSnap("half");
      else setSnap("full");
    }
    setDragHeight(null);
  }, [dragHeight, snap]);

  return {
    snap,
    setSnap,
    currentHeight,
    handleProps: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp },
  };
}
```

- [ ] **Step 3: BottomSheet 컴포넌트**

`fe/src/mobile/components/BottomSheet.tsx`:

```tsx
import type { ReactNode } from "react";
import { useBottomSheet, type Snap } from "../hooks/useBottomSheet";

interface Props {
  initial?: Snap;
  children: ReactNode;   // header + scroll body
}

export function BottomSheet({ initial, children }: Props) {
  const { currentHeight, handleProps } = useBottomSheet(initial);
  return (
    <div
      className="absolute bottom-0 left-0 right-0 bg-white shadow-[0_-8px_24px_-12px_rgba(0,0,0,0.18)] rounded-t-2xl flex flex-col"
      style={{
        height: currentHeight,
        paddingBottom: "env(safe-area-inset-bottom)",
        transition: "height 120ms ease-out",
        touchAction: "pan-x",
      }}
    >
      <div
        {...handleProps}
        className="flex justify-center items-center h-7 cursor-grab"
        style={{ touchAction: "none" }}
        aria-label="sheet handle"
      >
        <div className="w-9 h-1 rounded-full bg-stone-300" />
      </div>
      <div className="flex-1 overflow-y-auto overscroll-contain">{children}</div>
    </div>
  );
}
```

- [ ] **Step 4: MobileMap 컴포넌트**

`fe/src/mobile/components/MobileMap.tsx`:

```tsx
import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import type { Site } from "../../shared/types";

interface Props {
  rows: Site[];
  onPick?: (id: string) => void;
}

export function MobileMap({ rows, onPick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, {
      center: [36.5, 127.8],
      zoom: 7,
      zoomControl: false,   // 모바일은 우하단 커스텀 위치
    });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "© OpenStreetMap",
    }).addTo(map);
    mapRef.current = map;

    const cluster = L.markerClusterGroup();
    map.addLayer(cluster);
    clusterRef.current = cluster;

    return () => {
      map.remove();
      mapRef.current = null;
      clusterRef.current = null;
    };
  }, []);

  // rows 변할 때 마커 갱신
  useEffect(() => {
    const cluster = clusterRef.current;
    if (!cluster) return;
    cluster.clearLayers();
    for (const r of rows) {
      if (typeof r.lat !== "number" || typeof r.lon !== "number") continue;
      const m = L.marker([r.lat, r.lon]);
      m.on("click", () => onPick?.(r.id));
      cluster.addLayer(m);
    }
  }, [rows, onPick]);

  return <div ref={ref} className="absolute inset-0" />;
}
```

- [ ] **Step 5: MobileShell — 진짜 부착**

`fe/src/mobile/components/MobileShell.tsx` 갱신:

```tsx
import { useState } from "react";
import { TopBar } from "./TopBar";
import { MobileMap } from "./MobileMap";
import { BottomSheet } from "./BottomSheet";
import { useSites } from "../../shared/hooks/useSites";
import type { Filters } from "../../shared/filters";

export function MobileShell() {
  const [filters] = useState<Filters>({ region: new Set() });
  const { rows, loading } = useSites(filters);
  const [, setPicked] = useState<string | null>(null);

  return (
    <div className="h-dvh flex flex-col">
      <TopBar />
      <main className="flex-1 relative overflow-hidden">
        <MobileMap rows={rows} onPick={setPicked} />
        <BottomSheet initial="peek">
          <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
            <span className="num font-semibold">{loading ? "…" : rows.length.toLocaleString()}</span>
            <span className="text-sm text-stone-500"> 곳</span>
          </div>
          <div>
            {rows.slice(0, 30).map((r) => (
              <div key={r.id} className="px-4 py-3 border-b" style={{ borderColor: "rgba(26,26,23,0.06)" }}>
                <div className="font-medium">{r.name}</div>
                <div className="text-xs text-stone-500">{r.sido} · {r.sigungu}</div>
              </div>
            ))}
          </div>
        </BottomSheet>
      </main>
    </div>
  );
}
```

- [ ] **Step 6: build + 모바일 뷰포트 smoke**

```bash
cd fe && npm run build 2>&1 | tail -5
npm run preview &
PID=$!
sleep 2
# 브라우저 모바일 emulation (Chrome devtools, 360x740) 으로 http://localhost:4173/m.html
echo "manual: open http://localhost:4173/m.html in mobile viewport"
sleep 30
kill $PID
cd ..
```

수동 검증:
- [ ] 지도 풀스크린, 우하단 줌 컨트롤
- [ ] BottomSheet 핸들 드래그 → 위로 확장 / 아래로 축소
- [ ] 핸들에서 손 뗌 → 가장 가까운 스냅으로
- [ ] 카드 리스트 스크롤
- [ ] 마커 탭 (현재는 setPicked 만, UI 변화는 C3)

- [ ] **Step 7: Commit + Push + PR**

```bash
git add fe/src/mobile/
git commit -m "feat(fe/mobile): BottomSheet 3-snap + MobileMap

vanilla pointer events 핸들, velocity 기반 스냅 결정.
Leaflet + markercluster, 줌 컨트롤 우하단. SP-C C2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/c2-bottomsheet-map
gh pr create --title "feat(fe/mobile): BottomSheet + Map (SP-C C2)" \
  --body "SP-C C2. 3단 BottomSheet + MobileMap.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task C3: MobileCampList + DetailSheet + MobileSearchOverlay + LocationChip

**Goal:** 카드 리스트 컴포넌트화, 카드 탭 → DetailSheet 풀스크린, 검색 오버레이, 위치 chip.

**Files:**
- Create: `fe/src/mobile/components/MobileCampList.tsx`
- Create: `fe/src/mobile/components/DetailSheet.tsx`
- Create: `fe/src/mobile/components/MobileSearchOverlay.tsx`
- Create: `fe/src/mobile/components/LocationChip.tsx`
- Modify: `fe/src/mobile/components/MobileShell.tsx`

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/c3-list-detail-search-loc
```

- [ ] **Step 2: MobileCampList**

`fe/src/mobile/components/MobileCampList.tsx`:

```tsx
import { useUserLocation } from "../../shared/hooks/useUserLocation";
import { haversineKm, formatKm } from "../../shared/geo";
import type { Site } from "../../shared/types";

interface Props {
  rows: Site[];
  onPick: (id: string) => void;
}

export function MobileCampList({ rows, onPick }: Props) {
  const { coords } = useUserLocation();
  return (
    <ul>
      {rows.map((r) => {
        const km =
          coords && typeof r.lat === "number" && typeof r.lon === "number"
            ? haversineKm(coords.lat, coords.lon, r.lat, r.lon)
            : null;
        return (
          <li
            key={r.id}
            className="px-4 py-4 border-b active:bg-stone-50"
            style={{ borderColor: "rgba(26,26,23,0.06)" }}
            onClick={() => onPick(r.id)}
          >
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold truncate">{r.name}</div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {r.sido} · {r.sigungu}
                </div>
              </div>
              {km != null && <div className="text-sm text-stone-600 num">{formatKm(km)}</div>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
```

- [ ] **Step 3: DetailSheet**

`fe/src/mobile/components/DetailSheet.tsx`:

```tsx
import { useEffect } from "react";
import { useDetail } from "../../shared/hooks/useDetail";

interface Props {
  id: string | null;
  onClose: () => void;
}

export function DetailSheet({ id, onClose }: Props) {
  const data = useDetail(id);

  useEffect(() => {
    if (!id) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [id, onClose]);

  if (!id) return null;

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <header className="h-14 px-4 flex items-center justify-between border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
        <button onClick={onClose} aria-label="close" className="text-xl">←</button>
        <h2 className="display font-semibold truncate">{data?.name ?? "로딩 중…"}</h2>
        <span className="w-6" />
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {data ? (
          <>
            <div className="text-sm text-stone-600">{data.sido} · {data.sigungu}</div>
            {/* MiniMap, 카테고리, 시설, ETA, etc. — 데스크톱 DetailPanel 의 핵심 섹션 이전 */}
            <pre className="text-xs bg-stone-50 p-2 rounded overflow-x-auto">{JSON.stringify(data, null, 2).slice(0, 800)}</pre>
          </>
        ) : (
          <div className="text-stone-500">불러오는 중…</div>
        )}
      </div>
    </div>
  );
}
```

⚠️ DetailSheet 의 본문은 데스크톱 DetailPanel 의 섹션 (대표 정보·카테고리·시설·ETA·미니맵) 을 동일하게 — 모바일 폭에 맞게 layout 만 stacked 로. C3 의 첫 컷은 placeholder JSON, 후속 PR 에서 풀 디테일.

- [ ] **Step 4: MobileSearchOverlay**

`fe/src/mobile/components/MobileSearchOverlay.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { getJson } from "../../shared/api";
import type { Site } from "../../shared/types";

interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (id: string) => void;
}

export function MobileSearchOverlay({ open, onClose, onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!q.trim()) { setResults([]); return; }
    setLoading(true);
    const t = setTimeout(() => {
      getJson<Site[]>("/sites/search", { q, k: 20 })
        .then((arr) => setResults(Array.isArray(arr) ? arr : []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 200);   // debounce
    return () => clearTimeout(t);
  }, [q]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <header className="h-14 px-2 flex items-center gap-2 border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
        <button onClick={onClose} aria-label="close" className="text-xl px-3">←</button>
        <input
          ref={inputRef}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="캠핑장 검색"
          className="flex-1 h-10 px-2 outline-none text-base"
        />
      </header>
      <div className="flex-1 overflow-y-auto">
        {loading && <div className="p-4 text-stone-500">검색 중…</div>}
        {!loading && results.map((r) => (
          <button
            key={r.id}
            className="w-full text-left px-4 py-3 border-b active:bg-stone-50"
            style={{ borderColor: "rgba(26,26,23,0.06)" }}
            onClick={() => { onPick(r.id); onClose(); }}
          >
            <div className="font-semibold">{r.name}</div>
            <div className="text-xs text-stone-500">{r.sido} · {r.sigungu}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: LocationChip**

`fe/src/mobile/components/LocationChip.tsx`:

```tsx
import { useUserLocation } from "../../shared/hooks/useUserLocation";

export function LocationChip() {
  const { status, refresh } = useUserLocation();
  const labels: Record<typeof status, string> = {
    idle: "위치",
    asking: "위치 요청 중…",
    ok: "내 위치",
    denied: "위치 거부됨",
    error: "위치 오류",
    unsupported: "지원 안 함",
  };
  return (
    <button
      onClick={refresh}
      className="px-3 py-1.5 rounded-full text-xs border"
      style={{ borderColor: "rgba(26,26,23,0.18)", background: "var(--paper)" }}
    >
      📍 {labels[status]}
    </button>
  );
}
```

- [ ] **Step 6: MobileShell — 통합**

`fe/src/mobile/components/MobileShell.tsx`:

```tsx
import { useState } from "react";
import { TopBar } from "./TopBar";
import { MobileMap } from "./MobileMap";
import { BottomSheet } from "./BottomSheet";
import { MobileCampList } from "./MobileCampList";
import { DetailSheet } from "./DetailSheet";
import { MobileSearchOverlay } from "./MobileSearchOverlay";
import { LocationChip } from "./LocationChip";
import { useSites } from "../../shared/hooks/useSites";
import type { Filters } from "../../shared/filters";

export function MobileShell() {
  const [filters] = useState<Filters>({ region: new Set() });
  const { rows, loading } = useSites(filters);
  const [picked, setPicked] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className="h-dvh flex flex-col">
      <TopBar onSearch={() => setSearchOpen(true)} />
      <main className="flex-1 relative overflow-hidden">
        <MobileMap rows={rows} onPick={setPicked} />
        <div className="absolute top-3 right-3 z-10"><LocationChip /></div>
        <BottomSheet initial="peek">
          <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
            <span className="num font-semibold">{loading ? "…" : rows.length.toLocaleString()}</span>
            <span className="text-sm text-stone-500"> 곳</span>
          </div>
          <MobileCampList rows={rows} onPick={setPicked} />
        </BottomSheet>
      </main>
      <DetailSheet id={picked} onClose={() => setPicked(null)} />
      <MobileSearchOverlay open={searchOpen} onClose={() => setSearchOpen(false)} onPick={setPicked} />
    </div>
  );
}
```

`TopBar` 갱신 (검색 콜백 받기):

```tsx
export function TopBar({ onSearch }: { onSearch?: () => void }) {
  return (
    <header className="h-14 px-4 flex items-center justify-between border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
      <button aria-label="menu" className="text-xl">≡</button>
      <h1 className="display text-base font-bold">camfit</h1>
      <button aria-label="search" className="text-xl" onClick={onSearch}>🔍</button>
    </header>
  );
}
```

- [ ] **Step 7: build + smoke**

```bash
cd fe && npm run build && npm run preview &
PID=$!
sleep 2
# 브라우저 모바일 뷰: m.html — 카드 탭 → DetailSheet, 검색 → 결과
sleep 60
kill $PID
cd ..
```

- [ ] **Step 8: Commit + Push + PR**

```bash
git add fe/src/mobile/
git commit -m "feat(fe/mobile): MobileCampList + DetailSheet + Search + LocationChip

카드 → DetailSheet, TopBar 검색 → SearchOverlay (debounced 200ms),
위치 chip status 5종. SP-C C3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/c3-list-detail-search-loc
gh pr create --title "feat(fe/mobile): list/detail/search/loc (SP-C C3)" \
  --body "SP-C C3. 카드 리스트 + 풀스크린 디테일 + 검색 오버레이 + 위치 chip.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task C4: FilterFAB + FilterSheet + EtaSheet

**Goal:** 풀스크린 필터/ETA 입력 모달. FAB 버튼 → 모달 열림. 적용 시 카드·핀 갱신.

**Files:**
- Create: `fe/src/mobile/components/FilterFAB.tsx`
- Create: `fe/src/mobile/components/FilterSheet.tsx`
- Create: `fe/src/mobile/components/EtaSheet.tsx`
- Modify: `fe/src/mobile/components/MobileShell.tsx` — filters state 끌어올림 + sheet 컨테이너

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/c4-filter-eta
```

- [ ] **Step 2: FilterFAB**

`fe/src/mobile/components/FilterFAB.tsx`:

```tsx
interface Props {
  count: number;
  onClick: () => void;
}

export function FilterFAB({ count, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-32 right-4 z-20 h-12 px-4 rounded-full shadow-lg flex items-center gap-2 font-medium"
      style={{ background: "var(--moss)", color: "#f7f4e8" }}
      aria-label="필터"
    >
      ✨ 필터
      {count > 0 && (
        <span className="ml-1 inline-flex items-center justify-center min-w-5 h-5 rounded-full text-xs"
              style={{ background: "var(--ember)" }}>
          {count}
        </span>
      )}
    </button>
  );
}
```

- [ ] **Step 3: FilterSheet — 풀스크린 모달**

`fe/src/mobile/components/FilterSheet.tsx`:

```tsx
import { useState } from "react";
import { useFacets } from "../../shared/hooks/useFacets";
import { useFeaturedAxes } from "../../shared/hooks/useFeaturedAxes";
import type { Filters } from "../../shared/filters";

interface Props {
  open: boolean;
  filters: Filters;
  onApply: (next: Filters) => void;
  onClose: () => void;
}

export function FilterSheet({ open, filters, onApply, onClose }: Props) {
  const { data: facets } = useFacets();
  const axes = useFeaturedAxes();
  const [draft, setDraft] = useState<Filters>(filters);

  if (!open) return null;

  const toggleRegion = (sido: string) => {
    setDraft((d) => {
      const next = new Set(d.region);
      next.has(sido) ? next.delete(sido) : next.add(sido);
      return { ...d, region: next };
    });
  };

  // 지역 unique sido 목록
  const sidos = Array.from(new Set((facets.regions ?? []).map((r) => r.sido)));

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <header className="h-14 px-4 flex items-center justify-between border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
        <button onClick={onClose} className="text-xl" aria-label="close">←</button>
        <h2 className="display font-semibold">필터</h2>
        <button onClick={() => onApply(draft)} className="px-3 py-1.5 rounded-md font-medium"
                style={{ background: "var(--moss)", color: "#f7f4e8" }}>
          적용
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-6">
        <section>
          <h3 className="text-sm font-semibold mb-2">지역</h3>
          <div className="flex flex-wrap gap-2">
            {sidos.map((s) => (
              <button
                key={s}
                onClick={() => toggleRegion(s)}
                className="px-3 py-1.5 rounded-full text-sm border"
                style={{
                  background: draft.region.has(s) ? "var(--moss)" : "var(--paper)",
                  color: draft.region.has(s) ? "#f7f4e8" : "var(--ink)",
                  borderColor: "rgba(26,26,23,0.18)",
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">대표축</h3>
          <div className="flex flex-wrap gap-2">
            {axes.map((a) => (
              <span key={a.id} className="px-3 py-1.5 rounded-full text-sm border"
                    style={{ borderColor: "rgba(26,26,23,0.18)" }}>
                {a.icon ?? "•"} {a.name}
              </span>
            ))}
          </div>
          <p className="text-xs text-stone-500 mt-2">대표축 토글은 후속 sprint 에서.</p>
        </section>

        {/* concept axes / view / facility 등은 동일 패턴으로 추가 — facets.concept_axes 등 활용 */}
      </div>
    </div>
  );
}
```

⚠️ FilterSheet 첫 컷은 region + 대표축 표시. concept axes (view, facility, kidsFacility, surface, space, parking, audience, vibe) 는 facets.concept_axes 의 구조에 맞춰 동일 패턴 추가. 데스크톱 FilterBar 의 9슬롯 모두 옮길 때까지 후속 commit (같은 PR 안).

- [ ] **Step 4: EtaSheet**

`fe/src/mobile/components/EtaSheet.tsx`:

```tsx
import { useState } from "react";
import { useEtaBatch } from "../../shared/hooks/useEtaBatch";
import { useUserLocation } from "../../shared/hooks/useUserLocation";

interface Props {
  open: boolean;
  candidateIds: string[];
  onApplied: (results: Record<string, { minutes?: number; within?: boolean }> | null) => void;
  onClose: () => void;
}

export function EtaSheet({ open, candidateIds, onApplied, onClose }: Props) {
  const { coords } = useUserLocation();
  const [hours, setHours] = useState(2);
  const [mins, setMins] = useState(0);
  const { apply, loading, results, err } = useEtaBatch();

  if (!open) return null;

  const submit = async () => {
    if (!coords) return;
    const max_minutes = hours * 60 + mins;
    await apply({ origin: coords, ids: candidateIds, max_minutes });
    onApplied(results);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
      <header className="h-14 px-4 flex items-center justify-between border-b" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
        <button onClick={onClose} className="text-xl">←</button>
        <h2 className="display font-semibold">ETA</h2>
        <button onClick={submit} disabled={!coords || loading}
                className="px-3 py-1.5 rounded-md font-medium disabled:opacity-50"
                style={{ background: "var(--moss)", color: "#f7f4e8" }}>
          {loading ? "계산 중…" : "적용"}
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {!coords && <div className="text-sm text-stone-500">내 위치 권한이 필요합니다.</div>}
        <div>
          <label className="text-sm font-semibold">최대 이동 시간</label>
          <div className="flex gap-3 mt-2">
            <select value={hours} onChange={(e) => setHours(+e.target.value)} className="border rounded px-2 py-1">
              {Array.from({ length: 9 }).map((_, i) => <option key={i} value={i}>{i} 시간</option>)}
            </select>
            <select value={mins} onChange={(e) => setMins(+e.target.value)} className="border rounded px-2 py-1">
              {[0, 15, 30, 45].map((m) => <option key={m} value={m}>{m} 분</option>)}
            </select>
          </div>
        </div>
        <div className="text-xs text-stone-500">후보 {candidateIds.length} 곳 (상한 200)</div>
        {err && <div className="text-sm text-[color:var(--ember)]">에러: {err}</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: MobileShell — sheet 통합 + filters state 끌어올림**

`fe/src/mobile/components/MobileShell.tsx`:

```tsx
import { useState, useMemo } from "react";
import { TopBar } from "./TopBar";
import { MobileMap } from "./MobileMap";
import { BottomSheet } from "./BottomSheet";
import { MobileCampList } from "./MobileCampList";
import { DetailSheet } from "./DetailSheet";
import { MobileSearchOverlay } from "./MobileSearchOverlay";
import { LocationChip } from "./LocationChip";
import { FilterFAB } from "./FilterFAB";
import { FilterSheet } from "./FilterSheet";
import { EtaSheet } from "./EtaSheet";
import { useSites } from "../../shared/hooks/useSites";
import { ETA_HARD_CAP } from "../../shared/constants";
import type { Filters } from "../../shared/filters";

export function MobileShell() {
  const [filters, setFilters] = useState<Filters>({ region: new Set() });
  const { rows, loading } = useSites(filters);
  const [picked, setPicked] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [etaOpen, setEtaOpen] = useState(false);
  const [etaResults, setEtaResults] = useState<Record<string, { minutes?: number; within?: boolean }> | null>(null);

  const filterCount = filters.region.size; // ⚠️ 다른 슬롯도 포함되도록 후속 확장
  const candidateIds = useMemo(() => rows.slice(0, ETA_HARD_CAP).map((r) => r.id), [rows]);

  const visibleRows = etaResults
    ? rows.filter((r) => etaResults[r.id]?.within !== false)
    : rows;

  return (
    <div className="h-dvh flex flex-col">
      <TopBar onSearch={() => setSearchOpen(true)} />
      <main className="flex-1 relative overflow-hidden">
        <MobileMap rows={visibleRows} onPick={setPicked} />
        <div className="absolute top-3 right-3 z-10"><LocationChip /></div>
        <FilterFAB count={filterCount} onClick={() => setFilterOpen(true)} />
        <BottomSheet initial="peek">
          <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
            <div>
              <span className="num font-semibold">{loading ? "…" : visibleRows.length.toLocaleString()}</span>
              <span className="text-sm text-stone-500"> 곳</span>
            </div>
            <button onClick={() => setEtaOpen(true)} className="text-sm text-[color:var(--ember)]">⏱ ETA</button>
          </div>
          <MobileCampList rows={visibleRows} onPick={setPicked} />
        </BottomSheet>
      </main>
      <DetailSheet id={picked} onClose={() => setPicked(null)} />
      <MobileSearchOverlay open={searchOpen} onClose={() => setSearchOpen(false)} onPick={setPicked} />
      <FilterSheet open={filterOpen} filters={filters} onApply={(next) => { setFilters(next); setFilterOpen(false); }} onClose={() => setFilterOpen(false)} />
      <EtaSheet open={etaOpen} candidateIds={candidateIds} onApplied={setEtaResults} onClose={() => setEtaOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 6: build + smoke**

```bash
cd fe && npm run build && npm run preview &
PID=$!
sleep 2
echo "manual: m.html — FAB → FilterSheet 적용 / ETA → EtaSheet 적용"
sleep 60
kill $PID
cd ..
```

- [ ] **Step 7: Commit + Push + PR**

```bash
git add fe/src/mobile/
git commit -m "feat(fe/mobile): FilterFAB + FilterSheet + EtaSheet

풀스크린 필터·ETA 모달, FAB 버튼 + 카운트 배지.
filters state 를 MobileShell 로 끌어올림. SP-C C4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/c4-filter-eta
gh pr create --title "feat(fe/mobile): filter + eta sheets (SP-C C4)" \
  --body "SP-C C4. 풀스크린 모달 패턴.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task C5: 진입 라우팅 — UA 자동 + DesktopToggle/MobileToggle

**Goal:** 백엔드 `/` 핸들러가 UA·cookie 기반 분기. 양 페이지에 토글 + cookie/localStorage 동기.

**Files:**
- Modify: 백엔드 api.py (BFF 또는 be-api — mount 가 있는 곳) — root 핸들러 추가
- Create: `fe/src/mobile/components/DesktopToggle.tsx`
- Modify: `fe/src/mobile/components/TopBar.tsx` — 메뉴 → DesktopToggle
- Create: `fe/src/desktop/components/MobileToggle.tsx`
- Modify: `fe/src/desktop/App.tsx` 또는 Header — 좁은 뷰포트일 때 MobileToggle 표시

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/c5-routing
```

- [ ] **Step 2: 백엔드 root 핸들러**

`backend/be-for-fe/src/cf_be_for_fe/api.py` (mount 위에 추가):

```python
import re
from fastapi import Request
from fastapi.responses import RedirectResponse, FileResponse

MOBILE_UA_RE = re.compile(r"Mobi|Android|iPhone|iPad|iPod", re.I)


@app.get("/", include_in_schema=False)
def root_redirect(request: Request):
    ua = request.headers.get("user-agent", "")
    is_mobile_ua = bool(MOBILE_UA_RE.search(ua))
    prefer_desktop = request.cookies.get("prefer_desktop") == "1"
    prefer_mobile = request.cookies.get("prefer_mobile") == "1"

    if is_mobile_ua and not prefer_desktop:
        return RedirectResponse("/m.html", status_code=302)
    if not is_mobile_ua and prefer_mobile:
        return RedirectResponse("/m.html", status_code=302)
    # default: index.html — StaticFiles 가 응답 (mount 가 / 에 걸려있음)
    return FileResponse(_settings.fe_dir / "index.html")
```

⚠️ FastAPI route 정의 순서: `app.get("/")` 가 `app.mount("/")` 보다 먼저 정의되어야 우선. 현재 mount 가 함수 끝 무렵에 있으므로 OK.

- [ ] **Step 3: DesktopToggle (모바일 → 데스크톱)**

`fe/src/mobile/components/DesktopToggle.tsx`:

```tsx
export function DesktopToggle() {
  const go = () => {
    try { localStorage.setItem("prefer_desktop", "1"); localStorage.removeItem("prefer_mobile"); } catch {}
    document.cookie = "prefer_desktop=1; path=/; max-age=31536000";
    document.cookie = "prefer_mobile=; path=/; max-age=0";
    location.assign("/");
  };
  return (
    <button onClick={go} className="text-sm text-stone-600 underline underline-offset-2">
      데스크톱으로 보기
    </button>
  );
}
```

`fe/src/mobile/components/TopBar.tsx` 갱신 (메뉴 클릭 → 간단한 popover or 직접 토글):

```tsx
import { useState } from "react";
import { DesktopToggle } from "./DesktopToggle";

export function TopBar({ onSearch }: { onSearch?: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="h-14 px-4 flex items-center justify-between border-b relative" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
      <button aria-label="menu" className="text-xl" onClick={() => setMenuOpen((v) => !v)}>≡</button>
      <h1 className="display text-base font-bold">camfit</h1>
      <button aria-label="search" className="text-xl" onClick={onSearch}>🔍</button>
      {menuOpen && (
        <div className="absolute top-14 left-2 z-30 bg-white rounded-lg shadow-lg p-3 border" style={{ borderColor: "rgba(26,26,23,0.12)" }}>
          <DesktopToggle />
        </div>
      )}
    </header>
  );
}
```

- [ ] **Step 4: MobileToggle (데스크톱 → 모바일)**

`fe/src/desktop/components/MobileToggle.tsx`:

```tsx
import { useEffect, useState } from "react";

export function MobileToggle() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    setShow(mq.matches);
    const h = (e: MediaQueryListEvent) => setShow(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  if (!show) return null;

  const go = () => {
    try { localStorage.removeItem("prefer_desktop"); localStorage.setItem("prefer_mobile", "1"); } catch {}
    document.cookie = "prefer_desktop=; path=/; max-age=0";
    document.cookie = "prefer_mobile=1; path=/; max-age=31536000";
    location.assign("/m.html");
  };

  return (
    <button onClick={go} className="text-xs text-stone-600 underline ml-3">
      모바일로 보기
    </button>
  );
}
```

`fe/src/desktop/App.tsx` 의 Header 부분에 `<MobileToggle />` 삽입 (예: 우측 컨트롤 묶음 끝 또는 좁은 뷰포트 시 별도 줄):

```tsx
import { MobileToggle } from "./components/MobileToggle";
// ...
<div className="hidden md:flex gap-6 items-end">
  {/* 기존 ... */}
</div>
<div className="md:hidden flex justify-end p-2">
  <MobileToggle />
</div>
```

- [ ] **Step 5: 클라사이드 보강 — index.html 의 inline script (좁은 뷰포트 자동 모바일)**

⚠️ Vite entry 의 main.tsx 에서 mount 직전 체크:

`fe/src/desktop/main.tsx`:

```tsx
const preferDesktop =
  localStorage.getItem("prefer_desktop") === "1" ||
  document.cookie.includes("prefer_desktop=1");

if (!preferDesktop && window.matchMedia("(max-width: 640px)").matches) {
  // sessionStorage refer counter — 무한 루프 가드
  const refer = parseInt(sessionStorage.getItem("redirect_count") ?? "0", 10);
  if (refer < 3) {
    sessionStorage.setItem("redirect_count", String(refer + 1));
    location.replace("/m.html");
    // 아래 부착 안 함
    throw new Error("redirected to m.html");
  }
} else {
  sessionStorage.removeItem("redirect_count");
}

// 이하 기존 createRoot...
```

동일하게 `fe/src/mobile/main.tsx` 에 데스크톱 선호 시 / 로 리다이렉트 — 단 모바일은 UA 자체가 모바일이라 보통 진입 OK, 안 함.

- [ ] **Step 6: 테스트 (수동 + curl)**

```bash
cd fe && npm run build && cd ..
./scripts/dev-up.sh
sleep 2

# UA 모바일 시뮬
curl -sI -A "Mozilla/5.0 (iPhone; CPU iPhone OS 16) AppleWebKit/605.1" http://localhost:8070/ | grep -i location
# → location: /m.html

# UA 데스크톱
curl -sI -A "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537" http://localhost:8070/ | head -5

# UA 모바일 + cookie prefer_desktop
curl -sI -A "iPhone" -b "prefer_desktop=1" http://localhost:8070/ | head -5

./scripts/dev-down.sh
```

기대:
- 모바일 UA → 302 /m.html
- 데스크톱 UA → 200 (StaticFiles index.html)
- 모바일 UA + prefer_desktop cookie → 200 (StaticFiles index.html)

- [ ] **Step 7: Playwright 모바일 시나리오 추가**

`fe/tests/playwright/mobile.spec.ts`:

```ts
import { test, expect, devices } from "@playwright/test";

test.use({ ...devices["iPhone 12"] });

test.describe("mobile fe — C5 routing + 동작", () => {
  test("/ on iPhone redirects to /m.html", async ({ page }) => {
    const response = await page.goto("/", { waitUntil: "domcontentloaded" });
    // Vite preview 에서는 root 핸들러가 없을 수 있음. 백엔드와 통합 시점에 검증.
    if (response?.status() === 302) {
      expect(response.headers()["location"]).toBe("/m.html");
    } else {
      // preview 모드 — fallback to direct
      await page.goto("/m.html");
    }
    await expect(page.locator("h1")).toContainText("camfit");
  });

  test("desktop toggle round-trip", async ({ page, context }) => {
    await page.goto("/m.html");
    await page.locator('[aria-label="menu"]').click();
    await page.getByText("데스크톱으로 보기").click();
    // / 로 이동 + cookie 설정 확인
    expect(page.url()).toContain("/");
    const cookies = await context.cookies();
    expect(cookies.find((c) => c.name === "prefer_desktop")?.value).toBe("1");
  });
});
```

`fe/playwright.config.ts` 에 mobile project 추가:

```ts
projects: [
  { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  { name: "mobile", use: { ...devices["iPhone 12"] } },
],
```

```bash
cd fe && npx playwright test 2>&1 | tail -10
cd ..
```

- [ ] **Step 8: Commit + Push + PR**

```bash
git add backend/ fe/src/mobile/ fe/src/desktop/ fe/playwright.config.ts fe/tests/playwright/
git commit -m "feat: routing — UA auto-redirect + Desktop/MobileToggle

백엔드 / 핸들러 UA·cookie 분기, FE 양 entry 의 토글 +
cookie/localStorage 동기, sessionStorage refer counter 루프 가드,
Playwright 모바일 회귀. SP-C C5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/c5-routing
gh pr create --title "feat: mobile UA routing + toggle (SP-C C5)" \
  --body "SP-C C5. 진입 라우팅 자동 + 양방향 토글.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Task C6: 안전 영역 + 디자인 토큰 정리 + Lighthouse 참고

**Goal:** iOS safe-area 가산 점검, dvh 폴백, 디자인 토큰 일관성 최종 점검, Lighthouse 모바일 점수 참고 측정.

**Files:**
- Modify: 모바일 컴포넌트 — safe-area inset 누락 확인
- Modify: `fe/src/shared/styles/tokens.css` — 누락된 토큰 추가
- Create: `fe/docs/lighthouse-baseline.md` (참고 점수)

- [ ] **Step 1: Branch**

```bash
git checkout main && git pull
git checkout -b sprint/c6-mobile-polish
```

- [ ] **Step 2: safe-area 점검**

검색:

```bash
grep -rn "safe-area-inset\|env(" fe/src/
```

확인 — 다음에 모두 있어야 (또는 의식적 제외):
- BottomSheet `paddingBottom: env(safe-area-inset-bottom)`
- DetailSheet, FilterSheet, EtaSheet, MobileSearchOverlay 의 풀스크린 컨테이너
- TopBar — `paddingTop: env(safe-area-inset-top)` 추가 (노치 대응)

`TopBar.tsx`:

```tsx
<header
  className="h-14 px-4 flex items-center justify-between border-b relative"
  style={{
    borderColor: "rgba(26,26,23,0.12)",
    paddingTop: "env(safe-area-inset-top)",
  }}
>
```

⚠️ paddingTop 추가 시 h-14 가 부족 — 별도 wrapper div 또는 height 계산 변경. 권장:

```tsx
<div style={{ paddingTop: "env(safe-area-inset-top)", background: "var(--paper)" }}>
  <header className="h-14 ...">...</header>
</div>
```

MobileShell 의 `flex-1` main 도 safe-area 영향 받음 — `min-height: 0` 확인.

- [ ] **Step 3: dvh 폴백**

```bash
grep -rn "dvh\|100vh" fe/src/
```

`100dvh` 사용처 검증. 폴백 필요 시 inline:

```css
height: 100vh;
height: 100dvh;
```

또는 `tailwind.config.js` extend:

```js
theme: {
  extend: {
    height: { "screen-d": "100dvh" },
  },
},
```

후 클래스 `h-screen-d`.

- [ ] **Step 4: tokens.css 누락 토큰 보강**

데스크톱과 모바일 컴포넌트 둘 다 사용하는 색·간격 토큰이 모두 tokens.css 에 있는지 확인:

```bash
grep -rn "rgba(26,26,23\|rgba(44,74,62\|--moss\|--ember\|--paper" fe/src/
```

자주 쓰이는 rgba 가 있으면 토큰화:

```css
:root {
  --moss: #2c4a3e;
  --moss-deep: #1a2f26;
  --moss-soft: #cfdcc9;
  --bark: #6b4f2c;
  --paper: #f4f1e8;
  --paper-2: #ebe5d2;
  --ink: #1a1a17;
  --ember: #c8553d;
  /* 자주 쓰이는 보더 */
  --border-faint: rgba(26, 26, 23, 0.06);
  --border-soft: rgba(26, 26, 23, 0.12);
  --border-firm: rgba(26, 26, 23, 0.18);
}
```

후 인라인 `rgba(26,26,23,0.12)` 를 `var(--border-soft)` 로 점진 교체 (전체 교체는 별도 cleanup 라운드 — 본 sprint 는 토큰 정의만).

- [ ] **Step 5: Lighthouse 측정 (참고)**

```bash
cd fe && npm run build && npm run preview &
PID=$!
sleep 2

# Chrome devtools Lighthouse 모바일 모드로 http://localhost:4173/m.html 측정
# CLI 옵션:
npx lighthouse http://localhost:4173/m.html \
  --preset=desktop --output=json --output-path=/tmp/lh-desktop.json --quiet
npx lighthouse http://localhost:4173/m.html \
  --emulated-form-factor=mobile --output=json --output-path=/tmp/lh-mobile.json --quiet

kill $PID
cd ..
```

`fe/docs/lighthouse-baseline.md`:

```markdown
# Lighthouse baseline (참고)

측정일: 2026-05-10
URL: /m.html (preview 빌드)

| Metric | Mobile | Desktop |
|---|---|---|
| Performance | (측정값) | (측정값) |
| Accessibility | (측정값) | (측정값) |
| Best Practices | (측정값) | (측정값) |
| SEO | (측정값) | (측정값) |

목표 (참고): Performance ≥ 80, Accessibility ≥ 90.

본 점수는 게이트 아님 — 후속 cleanup 의 시작 지점.
```

- [ ] **Step 6: Commit + Push + PR**

```bash
git add fe/
git commit -m "polish(fe/mobile): safe-area + dvh + token expansion + lighthouse baseline

env(safe-area-inset-*) 점검 (TopBar 노치 대응 등),
100dvh 폴백, --border-* 토큰 정의, Lighthouse 참고 점수 캡처.
SP-C C6 (final).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/c6-mobile-polish
gh pr create --title "polish(fe/mobile): safe-area + tokens + lighthouse (SP-C C6)" \
  --body "SP-C final. 모바일 폴리시.

SP-B/C 전체 완료.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --auto --merge
```

---

## Self-review checklist

- [x] **Spec coverage**:
  - 4절 (디렉터리 레이아웃) — B1, B2, B3, C1 에 매핑
  - 5절 (모바일 UX) — C1, C2, C3, C4 에 매핑
  - 6절 (라우팅) — C5 에 매핑
  - 7절 (데이터 흐름 shared/) — B2 에 매핑
  - 8절 (빌드 mount) — B1 (셋업), B4 (전환)
  - 9절 sprint 정의 — Task B1~B5 + C1~C6 1:1 매핑
  - 11절 위험 — 각 task 의 ⚠️ 마커에 분산 (BottomSheet 터치, dvh, cookie, Vite proxy, Tailwind 등)
  - 12절 검증 fixture — B3 (Playwright 데스크톱 5), C5 (Playwright 모바일)

- [x] **Type consistency**:
  - `Filters` 타입은 B2 (filters.ts) 정의 → B3, C1, C4 에서 사용
  - `Site` 타입은 B2 (types.ts) 정의 → 모든 컴포넌트
  - `Snap` 타입은 C2 (useBottomSheet.ts) 정의 → BottomSheet
  - hook 시그니처: `useSites(filters): { rows, loading, err }` 일관
  - cookie 이름: `prefer_desktop`, `prefer_mobile` — 백엔드 + DesktopToggle + MobileToggle + main.tsx 보강 모두 동일

- [x] **Placeholder check**:
  - ⚠️ 마커가 명시한 *원본 1:1 복사 필요* 부분 — B3 의 큰 컴포넌트들 본체는 fe/index.legacy.html 의 정확한 라인 매핑 제공 (Step 4)
  - ⚠️ `_LANDLOCKED_SIDO`, `visibleRows` 본체 — 원본 그대로 복사 (skill 의 "no placeholders" 와 다른 종류 — 실 데이터 의존, 코드 내용은 명확히 그곳에서 가져옴)
  - 모든 step 이 실제 코드 또는 명령어 포함

- [x] **PR 단위 + 자동 머지** (사용자 워크플로) — 매 task 마지막 step 에 `gh pr merge --auto --merge`

## 알려진 한계

- **B3 컴포넌트 이전의 ⚠️ 마커**: 16개 컴포넌트 본체를 코드로 풀어쓰면 plan 길이가 폭발. 대신 fe/index.legacy.html 의 라인 매핑 제공 + 변환 패턴 명시 (props 타입 부여, import 정리, // @ts-expect-error 임시 마커). 실행자가 원본 보고 1:1 복제.
- **B2 의 `visibleRows` skeleton**: 본체는 원본 fe/index.legacy.html 의 App() 안 useMemo. 원본 길이 ~80 라인.
- **C3 의 DetailSheet**: 첫 컷은 placeholder JSON. 데스크톱 DetailPanel 의 풀 콘텐츠 (Leaflet 미니맵·카테고리·시설·ETA badge 등) 는 같은 PR 에 추가 commit 또는 후속 cleanup.
- **C4 의 FilterSheet 첫 컷**: region + 대표축만. concept axes 9 슬롯 풀 추가는 같은 PR 안 commit.
- **B1 의 `parents[N]` 깊이**: B4 step 3 에서 정확한 깊이 확인 (`parents[4]` 추정).
- **C5 Playwright 라우팅 테스트**: Vite preview 에는 백엔드 라우팅 없음 → 백엔드 띄운 환경에서만 fully PASS. preview 단독은 fallback.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-fe-vite-and-mobile.md`.

**SP-A plan + SP-B/C plan 모두 완료. 두 plan 의 Sprint 권장 인터리브 순서:**

`B1 → A1 → A2 → B2 → B3 → A3 → B4 → C1 → C2 → A4 → A5 → C3 → C4 → C5 → A6 → A7 → B5 → C6`

총 18 PR (A 7개 + B 5개 + C 6개). 각 PR `gh pr merge --auto --merge`.

**다음 결정 (사용자):**
1. **Subagent-Driven 실행** (권장) — sprint 별 fresh subagent. 사용자가 sprint 사이 review.
2. **Inline 실행** — 본 세션에서 직접 sprint 진행.
3. **잠시 보류** — plan 만 보유, 추후 실행.
