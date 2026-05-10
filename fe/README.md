# fe/

> **SP-B 마이그레이션 진행 중 (B1~B5)** — Vite + TS + Tailwind 로 점진 이전.
> B1 완료 시점: 빌드 파이프라인만 도입. 사용자가 보는 화면은 여전히
> `index.legacy.html` (CDN+Babel, 백엔드의 임시 root 핸들러가 서빙).
> B3 에서 진짜 entry 부착, B4 에서 백엔드 mount → `fe/dist/` 전환.

## Vite 사용법 (SP-B 이후)

```bash
cd fe
npm install
npm run dev      # http://localhost:5173 (HMR, /sites 등은 :8070 으로 proxy)
npm run build    # tsc -b && vite build → fe/dist/
npm run preview  # http://localhost:4173 (build 결과 미리보기)
npm run test     # vitest run
```

엔트리: `fe/index.html` (Vite). 어드민 그래프 뷰는 `fe/public/graph.html`
로 옮겨졌고 빌드 시 `fe/dist/graph.html` 로 복사됨 (CDN+Babel 그대로 유지).

## 레거시 (B5 까지 유지)

`fe/index.legacy.html` — `huashu-design` 단일 HTML React+Babel 프로토타입.
외부 의존은 CDN 만 (React, Babel, Tailwind, Leaflet, markercluster, Pretendard).
B1~B3 동안 백엔드 root 핸들러가 이 파일을 서빙.

## 부팅

가장 간단한 방법: `camfit-puller serve` 가 자동으로 이 디렉터리를 `/` 에 mount 합니다.

```bash
camfit-puller serve
# → http://localhost:8070/
```

별도로 띄우고 싶으면 (예: 디자인 작업 중):

```bash
cd fe
python -m http.server 5500
# → http://localhost:5500
```

`location.port === "8070"` 일 때는 같은 origin 으로 API 호출, 그 외는 `http://localhost:8070` 로 fetch (FastAPI CORS 허용 처리됨).

## 디자인 노트

- 모스 그린 / 종이 톤 / ember 강조 — 캠핑/숲 모티프, generic AI tropes 회피.
- 토포그래피 SVG 라인 배경 + 산 모양 SVG 로고.
- Pretendard variable 한글 — 한국 사용자 친화.
- 핀 색: 모스 / 청록 (계곡) / ember (키즈) / 갈색 (트램펄린).
- 분할/지도/리스트 3 모드 토글.
- 우측 슬라이드 패널 — 캠프 상세 + Leaflet 미니맵.

## 배포

단일 파일이라 어디든 정적 호스팅 가능. API base URL 만 같은 host:8070 또는 환경 변수로 분리 빌드.
