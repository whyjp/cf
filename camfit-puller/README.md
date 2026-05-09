# camfit-puller (P2)

`https://camfit.co.kr` 의 공개 캠핑장 리스트를 PostgreSQL + pgvector + FalkorDB 위에 적재하고, 자동 카테고리 추출/임베딩 시맨틱 검색/Michelin-style 평가 마크 + huashu-design FE 로 다축 필터·지도뷰·ETA 거리 검색까지 시각화하는 *로컬-자족* 풀스택 도구.

> **예의/법적 주의** — 공개 메타데이터를 *낮은 빈도* 로 수집합니다. UA 회전 + delay 1.5~3s + robots.txt 준수가 기본 스텔스. 사용자 ack 후 CloakBrowser stealth 까지 사용한 이력은 `docs/superpowers/specs/2026-05-09-p2-pg-embedding-kg-design.md` + `intent/00-violation.md` 참조. 본 데이터는 개인 스카우팅/연구 목적이며 상업/대량 재배포 권장 안 함.

---

## Quickstart

```bash
# 1) 두 DB docker (PostgreSQL + FalkorDB) 부팅
wsl -e bash -c "cd /mnt/d/github/cf/docker && docker compose up -d"

# 2) 스키마 적용
cd camfit-puller && alembic upgrade head

# 3) 풀 파이프라인 실행 (raw JSON → PG → 임베딩 → 분류 → 테마 → 그래프)
python -m camfit_puller.cli pipeline run-all

# 4) 서비스 가동
python -m camfit_puller.cli serve --port 8070
# → http://localhost:8070/   (FE + API)
```

`pipeline run-all` 단계:

```
ingest          (data/*.json → PG)
geocode         (address → lat/lon, Nominatim 캐시)
vocab           (concept seed + hashtag/facility 자동도출)
embed           (ko-sroberta → pgvector 768d)
extract-filter  (camfit 필터 → polarity 신호)
extract-desc    (KeyBERT description 신호)
extract-review  (한국어 부정 + temperature 가중)
refresh-agg     (matview 새로고침)
themes          (HDBSCAN 자동 테마)
rebuild-graph   (PG truth → FalkorDB 재구축)
```

각 단계는 idempotent — 언제든 재실행 가능.

---

## 아키텍처 — Hexagonal (Ports & Adapters)

```
domain/         Camp / Review / Concept / Theme / GeoPoint  (pure pydantic)
ports/          11 Protocol — repo / vector / graph / embed / extract / geocode / source / eta
usecases/       12 use-cases (BuildEmbeddings, DiscoverThemes, RebuildGraph, SemanticSearch, ...)
adapters/
  postgres/     pool + 9 repos (camp, review, concept, theme, filter, mapping, signals, caches)
  pgvector/     PgvectorIndex (HNSW)
  numpy_vector/ NumpyVectorIndex (in-memory; OCP demo)
  falkor/       FalkorGraph
  embed/        KoSrobertaEmbedder + MockEmbedder
  extract/      KeyBertExtractor + HeuristicNegationExtractor
  cluster/      HdbscanClusterer
  geocode/      NominatimGeocoder + CachedGeocoder
  source/       LocalReplaySource (cf-data jsonl 곧 추가)
  eta/          EtagoSubprocessProvider (sibling etago/ 연동)
container.py    composition root (env-driven swap)
settings.py     pydantic-settings (CAMFIT_* env)
api.py          FastAPI — /sites /sites/search /sites/{id} /facets /eta /admin/* + FE static
cli.py          typer — `pipeline run-all` + 10 stages
```

env 한 줄로 어댑터 교체:
```bash
CAMFIT_VECTOR=numpy        # pgvector 대신 in-memory NumPy
CAMFIT_EMBEDDER=mock       # ko-sroberta 대신 deterministic mock (테스트용)
CAMFIT_DATA_SOURCE=mock    # source 교체
```

---

## API endpoints

| 엔드포인트 | 설명 |
|----------|------|
| `GET /healthz` | postgres / falkor / embedder / etago / geocoder 헬스 |
| `GET /sites` | 다축 필터 (region, concept, concepts_any, min/max_score, bbox) |
| `GET /sites/{id}` | 풍부 detail (description + 리뷰 top-N + concept + theme + photos) |
| `GET /sites/search?q=...&k=20` | 시맨틱 검색 (자연어 → 캠프 ranking) |
| `GET /sites/{id}/similar?k=10` | 캠프 단위 nearest neighbor |
| `GET /concepts` / `GET /concepts/{name}/camps` | concept 카탈로그 + 멤버 |
| `GET /themes` / `GET /themes/{id}/camps` | 자동 테마 + 멤버 |
| `GET /eta?origin&dest` / `POST /eta/batch` | etago 거리/시간 |
| `GET /facets` | region / concept (axis vs dynamic) / theme 카운트 |
| `POST /admin/rebuild-graph`, `POST /admin/reembed` | 운영 트리거 |

---

## 테스트

```bash
pytest -q                       # unit + contract (default — fast, no DB beyond contract layer)
pytest -m integration -v        # 라이브 docker stack 대상 (10+ 통합 시나리오)
```

---

## 분류 모델 — 3-신호 + Michelin-style 평가

하드코드 boolean (`has_valley/has_kids/has_trampoline`) 폐기. 모든 카테고리는 동적 `concepts` 테이블 + 3 신호원으로 도출:

1. **camfit 필터** (가중 1.0) — 사이트의 native 카테고리/테마 멤버십. polarity (+1/-1) — "노키즈" 같은 부정 분류가 정확히 잡힘.
2. **description 임베딩** (가중 0.5) — KeyBERT cosine.
3. **review 임베딩** (가중 0.7) — 한국어 부정 + intensifier(`정말`, `최고`, `별로`...) 가중.

`camp_concept_aggregated` materialized view 가 셋을 합산해 `final_score` 산출. 양수 = 적용, 음수 = 부정, 0 = 알 수 없음.

5 필터 차원 (사용자 지정):
- D1 사이트 재질 — 파쇄석 / 데크 / 마사토 / 잔디 / 우드칩 / 흙
- D2 관리 정도 — review temperature → "Mark" 시스템 (Michelin-style, T28.5 deferred)
- D3 자연 뷰 — riverview / oceanview / mountainview / lakeview / forestview
- D4 사이트 공간 + 주차 — generous/tight + on_site/adjacent/separate
- D5 어린이 시설 — playground / sandpit / animal_petting / kids_pool / kids_toilet

---

## 디렉터리

```
camfit-puller/
├── alembic/                  PG 스키마 마이그레이션
├── src/camfit_puller/        도메인 + 포트 + 어댑터 + 유즈케이스
├── tests/
│   ├── unit/                 ~70 unit tests (mocks only)
│   ├── contract/             ~25 contract tests (live PG/embedder)
│   └── integration/          ~9 integration tests (full stack, gated)
├── scripts/                  마이그레이션 + 시드 + (legacy) P1 크롤러
└── data/                     크롤 원본 JSON (gitignored)
```

크롤러 부분은 cf-crawl 패키지로 분리 예정 (spec: `docs/superpowers/specs/2026-05-09-cf-crawl-multi-source-design.md`).

---

## 참고 문서

- `docs/superpowers/specs/2026-05-09-p2-pg-embedding-kg-design.md` — P2 핵심 spec
- `docs/superpowers/specs/2026-05-09-p2-addendum-filter-dimensions.md` — 5 필터 차원 + 부정 + intensifier
- `docs/superpowers/specs/2026-05-09-cf-crawl-multi-source-design.md` — 멀티-소스 크롤러 분리 spec (멀티 사이트 통합)
- `docs/superpowers/plans/2026-05-09-p2-pg-embedding-kg-impl.md` — 44 태스크 임플 플랜
- `docs/superpowers/plans/2026-05-09-cf-crawl-impl.md` — cf-crawl 24 태스크
