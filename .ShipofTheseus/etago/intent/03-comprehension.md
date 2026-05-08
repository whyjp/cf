---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 03-cold-comprehension
project_id: etago
fingerprint: etago-03-comp-v1
prev_fingerprint: etago-02-review-v1
produced_at: 2026-05-09
reader: independent-comprehender (cold session)
---

# Cold Comprehension — etago

`intent/01-intent.md` 만 보고 cold reader 가 *독립 재이해* 한 결과. 표류 / 잘못된 해석 / 모호 지점을 페이즈 04 입력으로.

## 한 줄 재진술

> "한국 지도 (Naver/Kakao) 의 인증 없는 공개 API/페이지에서 *자연어로 받은 출발-도착* 의 차량 추천 경로 *소요 시간만* 정수 분 단위로 STDOUT 으로 내는 Go CLI 단일 바이너리."

## 재이해 정합성

intent §a 와 본 한 줄 재진술 — *완전 일치*. drift 0.

## 표류 의심 지점 (페이즈 04 명료화 후보)

| ID | 지점 | 의심 |
|----|------|------|
| D-1 | 자연어의 *어디까지* | "강남역" / "강남" / "서초구 강남대로 396" / "테헤란로 152" 모두 자연어인가? 좌표는 자연어 아님이 명백한가? |
| D-2 | "차량 기준" 의 *세부* | 일반 승용차? 트럭/소형/대형 구분? Naver 의 "추천" 옵션이 default. |
| D-3 | "추천 루트" 의 단일성 | Naver 는 일반적으로 3 후보 (`traoptimal`, `tracomfort`, `traavoidtoll`) 반환 — 본 CLI 는 첫 번째 (default `traoptimal`) 를 채택? |
| D-4 | fallback 트리거 | Naver 가 *결과 없음* 반환 (HTTP 200 + empty path) vs *5xx* — 둘 다 fallback 트리거인가? |
| D-5 | 자연어 모호 시 | "강남" 은 강남역인가 강남구인가? map service 의 첫 매칭을 그대로 신뢰? |
| D-6 | exit code | non-deterministic 외부 실패 (네트워크) 와 입력 오류 (자연어 매칭 0) 를 어떻게 분리? |

## intent 안 명시된 가정 (cold reader 가 *추정한* 것)

a- 입력 인자 순서: `etago <start> <end>` (위치 인자, --from/--to flag 아님). intent 호출 예제로부터 추론.
b- 출력은 line-buffered, 단일 라인 (`58 min`). intent §a 예제로부터 추론.
c- stderr 는 진단/디버그 정보, stdout 은 결과만 — UNIX convention. intent 명시 없음.
d- 한국 외 지역 (해외) 입력은 *비목표* — Naver/Kakao 자체가 한국 위주. intent 명시 없음.

→ 이 가정들은 페이즈 04 에서 사용자 *암묵 동의* 또는 *수정* 확인.

## intent 의 표현 정밀도 점검

a- "토큰이나 로그인없이" — *코드/실행 시* 의무. *map service 가 세션 cookie 자동 발급* (우회 가능) 도 금지인가? — D-7 후보.
b- "최우선 순위를 반영" — natural language input 의 "원문 보존" 으로 해석. *언어 자동 번역* (한→영) 같은 변환은 금지로 해석.
c- "오로지 실제 소요시간 이외에는 없음" — 응답 *파싱* 에서 시간 외 추출 0. *수신* 응답에 다른 필드가 있어도 OK 으로 해석.

→ a 는 페이즈 04 Q-N9 후보로 추가 권장.

## 진입 가능 결론

페이즈 04 진입 OK. D-1~D-7 은 페이즈 04 질의 input.
