# cf-be-for-fe

BFF (Backend-For-Frontend). 외부 노출. fe 의 모든 트래픽이 진입.

- be-api 를 httpx 로 호출, projection·aggregation 적용
- 인증·캐싱·rate-limit 은 본 sprint 범위 외 (출 진입점 자리만 확보)

## Run

```sh
# Dev — be-api 가 :8071 떠있다고 가정
BFF_BE_API_BASE_URL=http://localhost:8071 \
  uv run --package cf-be-for-fe uvicorn cf_be_for_fe.api:app --port 8070 --reload
```

## Endpoints (A2 시점)

얇은 통과: `/facets`, `/concepts*`, `/themes*`, `/marks*`, `/featured-axes`. 후속 sprint 에서 `/sites*`, `/eta*` 추가 + projection.

## Settings

| Env var | Default | Notes |
|---|---|---|
| `BFF_BE_API_BASE_URL` | `http://localhost:8071` | upstream cf-be-api |
| `BFF_TIMEOUT_S` | `12.0` | httpx Client timeout |
| `BFF_ALLOWED_ORIGINS` | `["*"]` | CORS 화이트리스트 (prod 는 fe origin 으로 좁힘) |

## Out of scope

- `/admin/*`, `/graph/*` — be-api 직접 호출 (어드민 전용, VPC 내부 가정). 자세한 내용은 `backend/be-api/README.md` 참조.
- 인증·캐싱·rate-limit — 후속 sprint
