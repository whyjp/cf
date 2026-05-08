---
skill_name: shipoftheseus:theseus-orchestrator
skill_version: 0.9.38
phase: 04-audience
project_id: etago
fingerprint: etago-04-audience-v1
prev_fingerprint: etago-04-nfr-v1
produced_at: 2026-05-09
audience: external-reviewer
---

# Phase 04 — Commentary Policy (Q-D-AUDIENCE)

답: **external-reviewer** (default).

## 의미

- 페이즈 08 implementation 의 주석 정책: *audience-aware* — exported function/type 에 godoc 의무, 비자명 분기 (regex / fallback / encoding) 에 why-comment 의무.
- 단, *과도한* 주석은 anti-pattern (CLAUDE.md "Default to writing no comments" + audience swap 의 균형). guideline:
  - exported godoc: ≤ 2줄 요약 + 비-자명 contract만
  - inline why-comment: 비-자명 의사결정 (User-Agent fixed / fallback trigger / charset 처리) 만

## 페이즈 08 implementer 적용

implementer 프롬프트 (페이즈 08 진입 시) 에 본 audience swap 적용. 외부 reviewer cold-read 가능 코드.
