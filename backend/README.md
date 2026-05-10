# backend/

cf 의 백엔드 — uv workspace 두 패키지로 구성:

- **be-api/** (`cf-be-api`) — DB-tier. domain·ports·usecases·adapters + raw 도메인 응답 FastAPI. 프로덕션 VPC 내부 격리.
- **be-for-fe/** (`cf-be-for-fe`) — BFF. projection·aggregation. 외부 노출. fe 가 호출.

## Run (local dev)

```sh
./scripts/dev-up.sh
./scripts/dev-down.sh
```

## Test

```sh
./scripts/test.sh
```

## Architecture

`docs/superpowers/specs/2026-05-10-backend-split-be-api-bff-design.md`
