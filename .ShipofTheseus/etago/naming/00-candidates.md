---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 00-naming-candidates
project_id: __pending
fingerprint: pending-00-cand-v1
prev_fingerprint: null
produced_at: 2026-05-09
---

# Phase 00 — 프로젝트 명명 후보

## 도메인 요약 (인용)

> 1. daum or naver map 에서 start - end 의 소요시간의 차량기준 추천 루트의 시간값을 얻는 cli
> 2. map service 에서 얻을건 오로지 실제 소요시간 이외에는 없음
> 3. start - end 의 자연어 입력의 최우선 순위를 반영
> 4. 토큰이나 로그인없이 얻을 수 있어야함
> 5. golang 으로 작성

핵심 의미군: **Korean map (Naver/Daum-Kakao) + drive ETA + CLI + no-auth + natural language**.

## 후보 (5)

| # | 후보 | 의미 | 충돌 검사 | 정당화 |
|---|------|------|-----------|--------|
| 1 | `kmap-eta` | Korean Map ETA (Estimated Time of Arrival) | npm `kmap` 존재 (다른 도메인, JS lib). GitHub `kmap-eta` 동명 0. | 도메인 (한국 지도) + 산출물 (ETA) 직관. CLI 와 결합 잘 맞음. |
| 2 | `kroute-time` | Korean Route Time | GitHub `kroute` 동명 0. 의미 충돌 0. | route-time 직관. 다만 ETA 보다 일반어 ("route" 가 길찾기 외 의미 가능). |
| 3 | `daero` | 한국어 "대로(大路)" — 큰 길 / "어디로(daero)" 동음 어감 | npm/PyPI 0. 단어 어감 불명. | 한국 도메인 어감 강함. 단, 비-한국어권 reviewer cold-read 모호. |
| 4 | `naerimap` | 내림(시간 줄어듦/도착) + map | 동명 0 (조어). | 의미 직관 약함 — reject 후보. |
| 5 | `etago` | ETA + Go (언어) | npm `etago` 0. github 단일 무관 repo. | 짧고 기억 용이. 산출물 (ETA) + 언어 (Go) 함의. CLI 명령으로도 적절 (`etago "강남" "수원"`). |

## 추천 순위

1. `etago` — CLI 호출 친화 (`etago start end`), 언어 (Go) + 산출물 (ETA) 의미 명료, 충돌 0.
2. `kmap-eta` — 도메인 (Korean map) 명시 강함, 다만 CLI 명령으로 길음.
3. `kroute-time` — 직관적이나 추상도 약간 높음.

## 모듈 후보 (1차)

CLI 단일 모듈 — 그러나 내부 모듈은 아래 의미군:
- `naturalinput` — 자연어 start/end → 정규화
- `geocode` — 주소/지명 → 좌표 (필요 시)
- `route` — 좌표 → 소요시간 (외부 map service)
- `cli` — 진입점 (cobra / 표준 flag)
