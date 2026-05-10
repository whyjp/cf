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

## Transport
```sh
# Dev → Prod
rsync -avz seed/latest/ user@prod:/path/to/cf/seed/latest/
ssh user@prod 'cd /path/to/cf && bash scripts/db-seed-load.sh'
```
