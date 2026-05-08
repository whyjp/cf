---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-questions
project_id: etago
fingerprint: etago-04-questions-v1
prev_fingerprint: etago-03-comp-v1
produced_at: 2026-05-09
---

# Phase 04 — 질의 리스트

## 사용자에게 *명시적* 으로 질의 (4 묶음)

a- **Q-G1** (그레이드) — Phase 00 동시 진행 시 처리. 답: Grade 3.
b- **Q-MAP-SOURCE** — Naver vs Kakao 우선 + fallback. 답: Naver 우선 + Kakao fallback.
c- **Q-OUTPUT** — default 출력 형식. 답: 분(정수) 단일 라인.
d- **Q-D8** (Verification mode). 답: 실 네트워크 smoke.
e- **Q-D-AUTONOMY** (Q-D1~D7 일괄). 답: 최대 자율.

## 사용자 사전 답에 *자동 매핑* (max-autonomy 위임)

본 항목들은 페이즈 04 의 max-autonomy 답에 의해 default 채택. 사용자 explicit confirm 은 본 묶음 한 번에 위임됨.

| ID | 질문 | 자동 답 | 위임 근거 |
|----|------|---------|---------|
| Q-N3 | 자연어 모호 시 처리 | first 매칭 자동 + stderr 후보 hint | max 자율 + CLI 의 "한 줄 결과" 스타일 |
| Q-N4 | 응답 타임아웃 | 6초 (Naver), 6초 (Kakao). 합계 12초. flag `--timeout` override | C3 임계 (intent §d) + fallback 시 합계 |
| Q-N5 | User-Agent | 모던 Chrome UA 고정. flag `--ua` override | 차단 회피 + 익명성 |
| Q-N6 | 캐시 | 없음 (CLI 1회성, 호출자가 책임) | UNIX KISS |
| Q-N7 | rate limit guard | 자체 가드 0 (호출자 책임) | 단일 호출 CLI — 가드 over-engineering |
| Q-N8 | go.mod path | `github.com/whyjp/etago` | 사용자 git config = whyjp |
| Q-D9 | runtime-prereq | 외부 의존 0 (Naver/Kakao 자체) — `.env.template` 비어 있음 OK | no-auth 의무 + map service 는 external 이지만 key 부재 |
| Q-D-AUDIENCE | commentary policy | external-reviewer (default) | OSS 가능성 + handoff 동작 |
| D-1 | 자연어 어디까지 | 지명 텍스트 + 도로명 주소 모두. 좌표 (lat,lng) 는 비-자연어 — 거부 | 일반 사용자 의도 |
| D-2 | 차량 세부 | "추천" (Naver `traoptimal`, Kakao `RECOMMEND`) default | 사용자 명시 "추천 루트" |
| D-3 | 추천 루트 단일성 | 첫 번째 (`traoptimal`) | "단일 시간값" 의도 |
| D-4 | fallback 트리거 | HTTP 5xx + empty result + parse 실패 모두 | robust |
| D-5 | 자연어 모호 시 | first 매칭 + stderr 알림 (Q-N3 와 동일) | — |
| D-6 | exit code | 0 OK / 2 입력 오류 / 3 외부 실패 / 1 unknown | UNIX BSD 관용 |
| D-7 | session cookie 자동 발급 | 발급 OK (사용자 token 입력 0). 단, 디스크 영속화 0 | "토큰" = 사용자가 발급한 secret. 서비스 자동 set-cookie 는 별개 |

## 본문

각 질문의 두괄식 / 객관식 4보기 / 자동 추정은 위 AskUserQuestion 호출의 텍스트로 박혔음.
