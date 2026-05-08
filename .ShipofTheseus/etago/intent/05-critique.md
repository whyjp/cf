---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 05-critique
project_id: etago
fingerprint: etago-05-crit-v1
prev_fingerprint: etago-01-add-v1
produced_at: 2026-05-09
critic: critic-agent (cold parallel review)
---

# Phase 05 — Critique

intent v1 + 04 답 + refresh-1 통합 비평. directional-simplification + premortem-friction + parallel-cold-review 룰.

## Premortem (가상 실패 시나리오)

| 시나리오 | 빈도 | 대응 |
|---------|------|------|
| 6개월 후 Naver 가 directions schema 변경 → 빈 응답 | High | adapter 인터페이스 + 응답 schema validation + Kakao fallback 자동 |
| corp proxy 환경 사용자 첫 호출 502 | High | error 메시지에 proxy hint + `--ua` flag 안내 |
| 자연어 "강남" 매칭 모호 → 사용자 의도와 다른 결과 | Med | stderr 에 매칭 후보 ≥ 2 시 hint |
| Naver 가 cookie+CSRF 강제 (recent change) | Med | 1차 GET 후 set-cookie + 2차 호출 — adapter 가 흡수 |
| Windows 한글 인자 전달 깨짐 (PowerShell vs cmd) | Med | utf8 args 의무, README 에 `chcp 65001` 명시 |
| 5xx 빈도 / IP 차단 | Low | 호출자 책임 (Q-N7) + UA fallback hint |

## Directional Simplification

intent 의 *복잡도* 가 본질이 아닌 영역:

a- *fallback 체인* — 단일 source 로 충분하면 더 단순. 하지만 사용자가 explicit Naver+Kakao fallback 채택 — 유지.
b- *3개 universe plan* — 본 G3 default. 본 작업이 *adapter 패턴* 중심이라 universe 간 의미 분기 자연스럽다 (Naver-only / Kakao-only / both-race) — 유지.
c- *dacapo 1+ 회* — G3 의 quality 보증 — 유지.

## Domain Failure Patterns

| 패턴 | 본 작업에 적용 |
|------|------|
| Schema reverse-engineering brittleness | 의무 — adapter test fixtures 분기 |
| Anonymous endpoint deprecation | 의무 — fallback chain (이미 채택) |
| Korean encoding edge | 의무 — UTF-8 enforcement + Windows test |
| Network flakiness | 의무 — retry 0 (CLI 단발) + clear stderr |

## Parallel Cold Review

cold reader 가 처음 본다 가정 시 명료성 점수:
- 산출물 의도: 0.95 (한 줄 재진술 일치).
- 입출력 형식: 0.95 (예제 명료).
- error semantics: 0.85 ← 비평 대상. plan 에서 exit-code 매트릭스 정의 의무 (D-6 답).
- fallback semantics: 0.85 ← 비평 대상. plan 에서 fallback trigger 룰 표 의무 (D-4 답).

## Plan-tree 분기 후보 (페이즈 06 universe seed)

| Universe | seed 의미 |
|----------|---------|
| 1 | "Naver-first, Kakao-fallback, sequential" — sync chain |
| 2 | "Naver+Kakao race, first-success" — concurrent |
| 3 | "abstract 'router' 인터페이스 + plug-in providers" — extensible (over-engineering 위험 검증) |

## 비평 결정

a- intent v1 §c "톨게이트비" 항 삭제 (refresh-2 에서 적용).
b- intent v1 §d C3 fallback 합산 임계 `total ≤ 12s` 추가 (refresh-2).
c- exit-code 매트릭스 + fallback trigger 룰 → plan 의 본문 의무.
d- 페이즈 06 universe 3 seed 채택 (위 표).
