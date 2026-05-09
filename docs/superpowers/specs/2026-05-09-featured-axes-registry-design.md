# Featured Axes Registry — Design

- **Date**: 2026-05-09
- **Author**: claude (with whyjp)
- **Sub-project**: camfit-puller FE 대표축 system extensibility
- **Approved approach**: α — Backend single source + `/featured-axes` API

## Problem

The current 대표축 (featured axis) row exposes 3 hardcoded boolean shortcuts: 계곡 (`has_valley`), 키즈캠핑 (`has_kids`), 트램펄린 (`has_trampoline`). The user wants to add 할로윈 / 벚꽃 / 단풍 now and more keywords easily later.

The current implementation hardcodes each axis in **6 places**:

| # | Location | Role |
|---|---|---|
| 1 | `api.py:_camp_to_fe_row` | derives `has_<id>` flag via keyword match |
| 2 | `fe/index.html` `FEATURED_CATEGORY` / `FEATURED_FACILITY` map | excludes featured names from dynamic chip rows |
| 3 | `fe/index.html` `PinDots` component | map-pin tone (valley/kids/tramp) |
| 4 | `fe/index.html` 대표축 chip row | toggle button per axis |
| 5 | `fe/index.html` `CampList` per-card chips | duplicate of axis label list |
| 6 | `fe/index.html` `visibleRows` + `preEtaRows` filter logic | client-side AND filter |

A 4th, 5th, 6th axis through this pattern is unmaintainable.

Additionally, the haystack used for keyword matching omits `description` and `brief`, even though the new seasonal keywords live primarily there:

```
벚꽃   hashtag 23 / desc 16 / review 18  (max 23)
단풍   hashtag  7 / desc 20 / review  7  (max 20)
할로윈 hashtag  3 / desc 10 / review  1  (max 10)
```

Without `description` in the haystack, 할로윈 is essentially invisible.

## Goal

A single canonical registry that drives all 6 surfaces, plus a haystack that includes free-form text fields. Adding a new axis becomes a one-line entry in the registry; the FE re-derives chip metadata at mount time via a thin API endpoint.

## Architecture

```
domain/featured_axes.py    ← canonical registry (single source of truth)
       │
       ├──→ api.py:_camp_to_fe_row    derive r.has_<id> per axis
       │
       └──→ api.py:GET /featured-axes  emit chip metadata as JSON

fe/index.html
       └──→ useFeaturedAxes()   fetch /featured-axes once on mount
              │
              ├── FEATURED_NAMES set  (chip dedup)
              ├── PinDots component   (map pin tone)
              ├── 대표축 chip row     (filter toggles)
              ├── CampList chips      (per-card display)
              └── preEtaRows / visibleRows filter loops
```

Backend is the source of truth. Keywords stay backend-only (matching logic). The FE only ever sees `id / ko / icon / tone`.

## Components

### `domain/featured_axes.py` — new file

```python
"""Featured axis registry — boolean shortcut filters surfaced as 대표축 chips.

Each axis is keyword-matched (case-insensitive substring) against the
union of camp.collections + types + facilities + location_types +
hashtags + description + brief. Adding a new axis = 1 entry below.
"""
from typing import TypedDict


class FeaturedAxis(TypedDict):
    id: str            # snake_case, becomes r.has_<id>
    ko: str            # display label (Korean)
    icon: str          # emoji
    tone: str          # "" | "warm" | "bark" — chip color family
    keywords: list[str]  # case-insensitive substring matches (mixed en/ko)


FEATURED_AXES: list[FeaturedAxis] = [
    {"id": "valley",     "ko": "계곡",     "icon": "🌊", "tone": "",
     "keywords": ["valley", "계곡"]},
    {"id": "kids",       "ko": "키즈캠핑", "icon": "🧒", "tone": "warm",
     "keywords": ["kids", "키즈", "아이"]},
    {"id": "trampoline", "ko": "트램펄린", "icon": "🤸", "tone": "bark",
     "keywords": ["trampoline", "트램펄린", "트램폴린"]},
    {"id": "halloween",  "ko": "할로윈",   "icon": "🎃", "tone": "warm",
     "keywords": ["할로윈", "핼러윈", "핼로윈", "halloween"]},
    {"id": "cherry",     "ko": "벚꽃",     "icon": "🌸", "tone": "warm",
     "keywords": ["벚꽃", "벚나무"]},
    {"id": "autumn",     "ko": "단풍",     "icon": "🍁", "tone": "bark",
     "keywords": ["단풍"]},
]

# Module-level invariants — fail-fast at import.
assert len({a["id"] for a in FEATURED_AXES}) == len(FEATURED_AXES), "duplicate id"
for _a in FEATURED_AXES:
    assert _a["keywords"], f"empty keywords for axis {_a['id']}"
    assert _a["tone"] in ("", "warm", "bark"), f"bad tone for {_a['id']}"
```

### `api.py` changes

**`_camp_to_fe_row`** — extend haystack and replace hardcoded `has_*` block:

```python
from .domain.featured_axes import FEATURED_AXES

def _camp_to_fe_row(c) -> dict:
    ...
    haystack = " ".join(
        cats + types + facs + location_types + hashtags
        + [c.description or "", c.brief or ""]   # NEW
    ).lower()

    def _matches(*needles: str) -> bool:
        return any(n.lower() in haystack for n in needles)

    row = {
        "id": c.id, "name": c.name, ..., "categories": ..., "facilities": ...,
        ...
        "num_of_reviews": c.num_of_reviews,
        "bookmark_count": c.bookmark_count,
        "url": c.url,
    }
    for axis in FEATURED_AXES:
        row[f"has_{axis['id']}"] = _matches(*axis["keywords"])
    return row
```

**New `/featured-axes` endpoint:**

```python
@app.get("/featured-axes")
def featured_axes() -> list[dict]:
    """FE-facing chip metadata. Keywords field is intentionally omitted —
    the FE only needs id/ko/icon/tone for rendering; matching happens
    server-side in _camp_to_fe_row."""
    return [
        {"id": a["id"], "ko": a["ko"], "icon": a["icon"], "tone": a["tone"]}
        for a in FEATURED_AXES
    ]
```

### `fe/index.html` changes

**`useFeaturedAxes` hook** — new, fetched once at App mount:

```js
function useFeaturedAxes() {
  const [data, setData] = useState([]);
  useEffect(() => {
    fetch(`${API}/featured-axes`)
      .then(r => r.json())
      .then(d => setData(Array.isArray(d) ? d : []))
      .catch(() => setData([]));
  }, []);
  return data;
}
```

**6 surface-level replacements:**

1. `FEATURED_NAMES` set: `new Set(featuredAxes.map(a => a.ko))`
2. `PinDots`: iterate `featuredAxes`, render `<span class="pin-pin {axis.id}">` for first axis where `r[has_${axis.id}]` is true.
3. 대표축 chip row: `featuredAxes.map(a => <button onClick={...} className={chip ${a.tone}}>...</button>)`
4. `CampList` per-card: `featuredAxes.filter(a => r[`has_${a.id}`]).map(a => <Chip tone={a.tone}>{a.icon} {a.ko}</Chip>)`
5. `preEtaRows` filter loop: `for (const a of featuredAxes) if (filters[`has_${a.id}`]) out = out.filter(r => r[`has_${a.id}`]);`
6. `filters` initial state: `Object.fromEntries(featuredAxes.map(a => [`has_${a.id}`, false]))`

**CSS (`pin-pin.{id}`)** — keep existing valley/kids/tramp colors. New axes (halloween/cherry/autumn) get inline color via `style={{background: ...}}` per-tone fallback. No new CSS classes added — keeps the change scoped.

## Data Flow

```
1. App mount
   FE: useFeaturedAxes() → GET /featured-axes
       → [{id, ko, icon, tone} × 6]
   FE: useFacets() / useSites() proceed in parallel — independent.

2. /sites response
   For each camp row: backend already populated r.has_<id> for every axis
   (haystack matched on description+brief+all-existing fields).

3. User clicks a 대표축 chip
   FE: setFilters(prev => ({...prev, has_<id>: !prev.has_<id>}))
   → preEtaRows recomputes (cheap client-side filter)
   → visibleRows / map / list re-render
```

## Migration

Adding a new axis (after this work lands):

```
1. Edit domain/featured_axes.py — append 1 entry
2. Restart backend
3. FE picks it up automatically on next page load
```

No pipeline rerun, no DB migration, no FE rebuild needed. Existing `r.has_*` flags are derived per-request from `_camp_to_fe_row`, not stored.

## Error Handling

- **`/featured-axes` returns []** (e.g., backend unreachable) → 대표축 row renders empty. Filter logic loops over `[]` → no-op. Page still works without 대표축 shortcuts.
- **Bad registry entry** (duplicate id, empty keywords) → fail at module import, server boot fails loudly. Better than silent UI breakage.
- **Stale FE cache after registry edit** → user sees old chips until hard refresh. Acceptable; not different from any other FE-bundle change.

## Testing

| Layer | Test |
|---|---|
| unit | `_camp_to_fe_row` returns `has_<id>` for every registry id; halloween-keyword camps surface as `has_halloween=true` (≥10 expected) |
| unit | Empty registry → row carries no `has_*` keys (no crash) |
| contract | `GET /featured-axes` returns list[dict] with id/ko/icon/tone, keywords omitted |
| regression | After change, `has_valley/has_kids/has_trampoline` counts match prior baseline (138/529/231 ±5%) |

No FE unit tests exist in this repo; manual verification (Playwright tap or visual) covers the chip-row render path.

## Out of Scope

- Negation-aware matching for the new axes ("노할로윈" → has_halloween=false). Current `has_kids` already mis-classifies "노키즈" as kids; this remains a known limitation across the whole featured-axis surface, to be tackled separately if it becomes load-bearing.
- Score / weighting per axis. Current model is pure boolean (substring presence ⇒ true).
- Concept-system unification. The existing concept seeds for `spring`/`autumn` (category=`season`) remain in PG and continue to populate `camp_concept_aggregated` independently — the featured-axes registry coexists, and the FE 컨셉 chip row still surfaces them via `/facets`.

## Acceptance Criteria

1. ✅ `domain/featured_axes.py` exists with the 6 entries above and module-level invariants.
2. ✅ `_camp_to_fe_row` derives `has_<id>` for every axis from a description+brief-extended haystack.
3. ✅ `GET /featured-axes` returns the registry minus `keywords`.
4. ✅ `fe/index.html` renders the 6-chip 대표축 row from the API response — adding a 7th entry to the registry surfaces it on next page load with no FE edits.
5. ✅ Existing 3-axis behavior is preserved (counts within ±5% of pre-change).
6. ✅ Halloween captures the description-based camps that were previously missed (≥10 camps).
