# P2 Spec Addendum — 5 Important Filter Dimensions

- **Date**: 2026-05-09 (after T12 implementation)
- **Predecessor**: `2026-05-09-p2-pg-embedding-kg-design.md`
- **Status**: Locks domain-specific requirements before downstream tasks (T20 vocabulary, T24 negation, T26 review signals).

User-provided domain knowledge for camping-site filtering. These shape (a) which concepts must be in the seed vocabulary, (b) how review signals get weighted, and (c) a new "Michelin-style marking" output for management quality.

Source priority (already in §3.3): **camfit native filter (1.0) > review (0.7) > description (0.5)**. This addendum extends *what* gets extracted at each source.

---

## D1. Site Surface Material (사이트 재질)

**Examples**: 파쇄석 (gravel), 데크 (deck), 마사토 (decomposed granite), 잔디 (grass), 우드칩 (wood chips), 흙 (dirt)

**Why important**: Determines tent peg behavior, drainage, comfort. A "deck" site is fundamentally different from a "grass" site even within the same camp.

**Sources, in priority order**:
1. **camfit native filter** if present (some sites tag this in camp facilities or zone-level data — `/v1/camps/zones/{id}` payload may carry it).
2. **detail page extraction** — scan `description` and `policy` text for substring matches.
3. **review extraction** — count user mentions in review text.

**Promotion rule (per user)**: when a material appears in detail/review but not in camfit's native filter list, **promote it to a first-class concept** automatically (insert into `concepts` table with `source='ngram'` or `source='manual'`). This is already supported by the 3-source signal model — but seed concepts must be present so KeyBERT vocab can score them. **Action**: add to `domain/concept_seeds.py` (Task 20).

**New concepts to seed**:

```python
("surface_gravel",   "파쇄석",   "surface", False),
("surface_deck",     "데크",     "surface", False),
("surface_sand",     "마사토",   "surface", False),
("surface_grass",    "잔디",     "surface", False),
("surface_woodchip", "우드칩",   "surface", False),
("surface_dirt",     "흙바닥",   "surface", False),
```

Category `surface`. Not axis (not a primary toggle).

---

## D2. Management Quality / Manner-Time Enforcement (관리 정도)

**Why important**: Determines actual rest experience. Quiet camps with strict manner-time enforcement and clean restrooms separate "good" from "great" within the same price/region tier.

**Hard to score directly** — there's no objective metric. Per user: build a **Michelin-style marking system** based on **review temperature**.

**Approach**:
- Read each review's text + the `is_clean / is_kind / is_manner_maintained / is_convenient` boolean signals (already in `reviews` table).
- Run **temperature-weighted sentiment** on text (not just count of mentions): intensifier words ("정말", "너무", "강추", "최고") boost positive; complaint words ("실망", "짜증", "별로", "최악") boost negative.
- Aggregate per camp: `mark_score = Σ (intensity_i × polarity_i × concept_match) / Σ |intensity_i|`.
- Bucket the score into 4 levels: `bib` (basic), `recommended`, `notable`, `exceptional`. (Optional names — final naming TBD; mapping to numeric percentile.)

**New domain entity**: `Mark` (analogous to Theme but per-camp continuous rating).

**Schema delta (alembic 0002 migration, deferred to a new task)**:

```sql
camp_marks (
  camp_id text PRIMARY KEY REFERENCES camps,
  axis    text NOT NULL,                         -- 'management' | 'view' | 'kids' | ...
  level   text NOT NULL,                         -- 'bib' | 'recommended' | 'notable' | 'exceptional'
  score   numeric(5,4),                          -- raw temperature-weighted score
  evidence text,                                 -- example phrase
  computed_at timestamptz DEFAULT now()
);
```

Independent of `camp_concept_aggregated` (concepts are categorical; marks are graded).

**New use-case `ComputeMarks`** (added to plan as Task 28.5 or new milestone M3.5).

**New port** `MarkRepository` in `ports/repo.py`.

---

## D3. Natural View (뷰 — 강/바다/산/호수)

**Already partly seeded** (riverview, oceanview, mountainview). Per user, **review-temperature satisfaction** must weight in addition to camfit's official filter.

**Action**:
- Confirm seeded concepts cover river / sea / mountain / lake / forest views.
- `ExtractReviewSignals` must apply temperature weighting (not just polarity ±1) when computing `score` for view-axis concepts. (See D2 for the temperature mechanism.)
- Multi-source aggregation: `final_score = 1.0 × filter + 0.7 × review_temperature + 0.5 × description`. Already in spec §3.3 — temperature replaces the simple `(pos-neg)/total` review score formula.

**Plan delta**:
- Task 26 (`ExtractReviewSignals`) — change formula from `(pos-neg)/total` to **temperature-weighted**. Implementation lives in `adapters/extract/negation.py` or a new `adapters/extract/temperature.py`.

**New concept seeds**:
```python
("lakeview",         "호수뷰",   "view",        False),
("forestview",       "숲뷰",     "view",        False),
```
(riverview/oceanview/mountainview already in initial seeds.)

---

## D4. Site Spaciousness + Parking Layout (캠핑장 사이트의 공간)

**Why important**: Privacy, fire safety, gear setup ergonomics.

**Sub-axes**:
- **Site space generosity** — "넓다 / 좁다 / 빽빽하다" → temperature-weighted from reviews.
- **Parking layout** — three discrete cases:
  1. `parking_on_site` — car parks within the site footprint
  2. `parking_adjacent` — car parks beside or in front of the site (auxiliary slot)
  3. `parking_separate` — car parks in a separate parking lot away from the site

**Source**: Detail JSON usually has `address1`, `description`, and `policy` text. Camfit's filter has booleans like "주차 가능". For granular layout, extract from description text (rule-based + KeyBERT seeded with above 3 concept ids).

**New concepts to seed**:
```python
("space_generous",    "넓은 사이트",  "space", False),
("space_tight",       "좁은 사이트",  "space", False),
("parking_on_site",   "사이트내 주차", "parking", False),
("parking_adjacent",  "옆 주차 보조", "parking", False),
("parking_separate",  "별도 주차장",  "parking", False),
```

`parking_*` concepts are mutually exclusive per camp — first match wins via score ordering.

---

## D5. Kids Facilities (어린이 시설)

**Already partly covered** (kids axis, trampoline). Expand to include:
- 어린이 놀이터 (playground)
- 모래놀이 (sandpit)
- 동물 (animal petting / 동물체험)
- 키즈존 / 키즈수영장
- 어린이전용 화장실

**Source**: camfit basic filter + review temperature + description text scan.

**New concept seeds**:
```python
("playground",       "어린이놀이터", "kids_facility", False),
("sandpit",          "모래놀이장",   "kids_facility", False),
("animal_petting",   "동물체험",     "kids_facility", False),
("kids_pool",        "키즈수영장",   "kids_facility", False),
("kids_toilet",      "어린이화장실", "kids_facility", False),
```

(`kids` axis itself stays — these are sub-facilities under the kids umbrella.)

---

## Plan deltas (locked; downstream tasks must absorb)

| Task | Change |
|------|--------|
| **T20 BuildVocabulary** | Extend `domain/concept_seeds.py` SEEDS list with all D1–D5 entries above. ~30 new rows. |
| **T24 HeuristicNegationExtractor** | Add **temperature lexicon** alongside `NEG_TOKENS`. New constants: `INTENSIFIER_POSITIVE = ("정말", "너무", "강추", "최고", "완벽", "매우", "엄청", "굉장히", ...)` and `INTENSIFIER_NEGATIVE = ("실망", "짜증", "별로", "최악", "후회", "아쉬", "안 좋")`. |
| **T26 ExtractReviewSignals** | Replace `score = (pos − neg) / total` with **temperature-weighted**: `score = Σ_i sentiment_intensity_i × polarity_i / Σ_i |sentiment_intensity_i|`. Each review sentence's `sentiment_intensity_i` is `1.0 + 0.5 × intensifier_count` (capped at 2.0). Polarity stays ±1 from negation rules. Result is signed score in [-1, +1] with magnitude ≈ confidence. |
| **NEW T28.5** `ComputeMarks` | Aggregates per-camp temperature-weighted concept scores into Michelin-style level buckets and writes to a new `camp_marks` table. New ports: `MarkRepository`. New schema delta migration `0002_marks.py`. |
| **NEW T29.5** Marks in API | `GET /sites?mark_axis=management&mark_min=recommended` — filter via mark level. `GET /marks` — facets endpoint. |
| **T37 API refactor** | DetailPanel response includes `marks` array (each `{axis, level, score, evidence}`). |

---

## Acceptance criteria delta

Add to spec §15:

11. `GET /sites?concept=surface_deck&min_score=0.5` returns ≥3 deck-surface camps (after pipeline run on real 429 dataset).
12. `GET /marks?axis=management&level=exceptional` returns top-quality camps; manual spot-check confirms reviews mention positive management attributes.
13. Each Mark row has non-empty `evidence` snippet (provenance for human verification).
14. Temperature-weighted review score correctly distinguishes a 5-star "정말 너무 좋아요!" review (high positive intensity) from a flat "괜찮아요" review (low intensity).

---

## Why this is an addendum and not a blocker

The hexagonal architecture established in T1–T12 absorbs these additions cleanly:
- New concepts → seed list extension only (T20, no port changes)
- Temperature scoring → adapter swap (replace `HeuristicNegationExtractor`'s scoring formula; port unchanged)
- Marks → new port + new repository adapter + new use-case (additive, no edits to existing code)

Therefore the implementation plan T1–T44 can **continue without revision** through T19; downstream tasks T20, T24, T26 absorb the concept and lexicon expansions; new tasks T28.5/T29.5 are inserted at their natural points.

End of addendum.
