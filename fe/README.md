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
