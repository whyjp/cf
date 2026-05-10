# seed/

Production seed dumps (postgres + falkordb).

## Layout
```
seed/
├── .gitignore       (ignores *.dump and *.rdb — track manifest only)
├── README.md        (this file)
└── latest/          (default seed dir)
    ├── postgres.dump   pg_dump -F c (custom format, compressed)
    ├── falkor.rdb      Redis RDB snapshot
    └── manifest.json   schema_rev, embed_model, counts, created_at
```

## Workflow

### Dev box (생성)
```sh
bash scripts/db-dump.sh                # → seed/latest/
bash scripts/db-dump.sh seed/2026-05-10/   # 특정 디렉터리
```

### 운영서버 (1회 부팅 시 시드 로딩)
```sh
# 1. 컨테이너 + 스키마 부팅
bash scripts/db-up.sh
uv run --package cf-be-api alembic upgrade head

# 2. seed/latest/ 를 ssh/rsync 로 전송 후
bash scripts/db-seed-load.sh           # idempotent: camps>0 면 skip
bash scripts/db-seed-load.sh --force   # 강제 재로드
```

## 크기 (참고)
- `postgres.dump` ~12 MB (2,504 camps + embeddings + signals)
- `falkor.rdb` ~3 MB (2,504 nodes + edges)
- `manifest.json` < 1 KB

## Idempotency
- `db-seed-load.sh` 가 sentinel `.run/seed-loaded` + `camps` 테이블 카운트 둘 다 검사. 이미 로드된 환경에서 재실행해도 안전 (`--force` 미지정 시 skip).
- `db-dump.sh` 는 같은 디렉터리에 매번 덮어쓰기.

## Transport — Self-hosted prod (docker)
```sh
rsync -avz seed/latest/ user@prod:/path/to/cf/seed/latest/
ssh user@prod 'cd /path/to/cf && bash scripts/db-seed-load.sh'
```

## Transport — Managed Postgres (Render / Supabase / RDS)
```sh
export DATABASE_URL='postgresql://USER:PASS@HOST/DB?sslmode=require'
bash scripts/db-seed-load-url.sh

# 또는 인자로:
bash scripts/db-seed-load-url.sh "postgresql://..."
```

호환성:
- ✅ Render Postgres (pg 15+, pgvector 자동)
- ✅ Supabase (pgvector 대시보드 또는 자동 enable)
- ✅ AWS RDS / GCP Cloud SQL (pgvector pre-installed)
- 옵션 `--no-owner --no-acl` 자동 적용 (cloud non-superuser 친화)
- ⚠️ falkordb 는 managed 없음 — 별도 호스트 필요 (Render Web Service docker 또는 self-hosted VM)
- 필요 권한: 대상 role 이 `CREATE / DROP` + `CREATE EXTENSION` 가능

Idempotency: `camps` 카운트 > 0 시 skip (override: `FORCE=1 bash scripts/db-seed-load-url.sh`).
