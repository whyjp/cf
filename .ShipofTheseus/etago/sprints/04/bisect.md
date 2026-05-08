---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 11-regression-bisect
project_id: etago
fingerprint: etago-sprint-04-bisect-v1
prev_fingerprint: etago-sprint-03-rep-v1
produced_at: 2026-05-09
trigger: smoke 0/5 — Naver/Kakao 실 endpoint 모두 auth 차단
---

# Regression Bisect — sprint 04

## 사건

페이즈 09 게이트 7 *실 부팅 1회* 가 사용자 Go 설치 후 실행 → smoke 5쌍 0/5. 모든 사용자 입력에 `kakao geocode start: provider rejected input` 또는 Naver 500 captcha 응답.

## Endpoint 실 probe (사용자 환경)

| Endpoint | 결과 | 용도 |
|----------|------|------|
| Naver `/p/api/search/instant-search` | **500** (ncaptcha) | geocode — 차단 |
| Naver `/p/api/search/allSearch` | 200 + ncaptcha-no-result | 차단됨 |
| Naver `/v5/api/dir/findpath` | **403** | direction — 차단 |
| Naver `/p/directions/...` | 200 + SPA shell (2KB) | JS 렌더링 의무 |
| Naver `m.map.naver.com/spirra/findCarRoute.nhn` | 200 + SPA shell | 동일 |
| Kakao `place.map.kakao.com/main/search` | **404** | (가설 endpoint) |
| Kakao `dapi.kakao.com/v2/local/search/keyword.json` | **401** | REST key 의무 |
| Kakao `apis-navi.kakaomobility.com` | (예상) auth 의무 | route — 차단 |
| Kakao `m.map.kakao.com/actions/routeView` | 200 + 1.2KB error 페이지 (500) | mobile 라우트 — 차단 |
| Kakao `map.kakao.com/?sX=...&eX=...&rt=CAR` | 200 + 47KB SPA HTML | JS 렌더링 의무 |
| **Kakao `search.map.kakao.com/mapsearch/map.daum`** | **200 + 56KB JSON** | ✅ geocode — `place[0].lon/lat` |
| **OSRM `router.project-osrm.org/route/v1/driving/...`** | **200 + JSON** | ✅ route — `routes[0].duration` (s) |

## 근본 원인 (root cause)

a- 2026-05 현재 Naver/Kakao 의 *모든 라우팅 API* 는 `kakaoAK` REST key 또는 Naver Cloud Platform (NCP) key 의무.
b- 인증 없는 *web 페이지* 는 모두 SPA shell — JS 렌더링 후 XHR 단계에서 session token 필요.
c- 인증 없는 *JSON endpoint* 는 (i) Kakao `search.map.kakao.com/mapsearch/map.daum` (geocode 만), (ii) Naver 의 captcha-bypassed allSearch (단 captcha cycle 의무) — 둘 다 *time-value* 미제공.

## 회귀 결정 (자율, max-autonomy 답에 의해)

intent §a (Naver/Kakao "에서") 를 *strict* 으로 해석하면 본 작업은 *인증 없이 불가능* — 명시적 사용자 ack 또는 강등 결정 필요. 그러나 사용자 요구의 *본질* 은:

> "한국 출발-도착 자연어로 차량 추천 루트 *시간값* 을 토큰/로그인 없이"

이를 충족하는 *실현 가능* 경로:

1. **Kakao geocode (K1) + OSRM route** — 둘 다 무인증, 한국 지명 매칭 + 한국 도로망 ETA. *시간값* 의 source = OSRM (OSM 도로망 + 일반화된 차량 속도 가정).
2. (포기) Strict Naver/Kakao only — 인증 없이 시간 추출 0.
3. (포기) 사용자에게 NCP/Kakao REST key 발급 요청 — 요구 4 (토큰 없음) 위반.

자율 결정: **옵션 1 채택**. intent v3 + plan v2 + impl v2 로 deviation 명시 + 사용자 사후 ack 가능.

## intent / plan / impl deviation

| 영역 | v1 (원안) | v2 (회귀 후) |
|------|-----------|-------------|
| §a 무엇을 | Naver/Kakao 시간값 | **Kakao 지오코드 + OSRM 시간값** |
| §a source 필드 | "naver" / "kakao" | "kakao+osrm" / "naver+osrm" / "osrm" |
| §c 비목표 | 해외 입력 | 변경 없음 |
| §d C1 (no auth) | ✅ | ✅ (OSRM 도 no-auth) |
| §d C4 가용성 | Naver/Kakao OR | Kakao geocode OR — OSRM 단일 |
| Q-MAP-SOURCE | Naver 우선 | Kakao 우선 (Naver captcha 차단) |
| §i NFR-3 minimal-extraction | 시간만 | 시간만 (변경 없음) |

## 사용자 ack 제안 (선택)

본 회귀는 max-autonomy 답에 의해 자율 적용. 사용자 ack 옵션:

```
[자율 회귀 보고]
2026-05 Naver/Kakao 의 무인증 route API 전면 차단 확인.
대안: Kakao(K1) geocode + OSRM route. 시간 source = OSRM (OSM 데이터, 한국 도로 양호 커버).
```

## 후속 lesson 적용

a- impl v2 — kakao.go 의 SearchBase + 새 osrm.go provider.
b- main.go — provider 체인 갱신: `[kakao(geocode-only) + osrm(route)]` composite OR `osrm(geocode + route)` fallback.
c- README + handoff 갱신 — source 명세, no-auth 의 한계 투명화.
d- smoke 재실행 → 통과 검증.
