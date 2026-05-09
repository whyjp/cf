"""Use-case: compute Michelin-style marks from review-temperature signals.

Algorithm per axis (e.g. axis='management'):
  1. Find concepts in that category (e.g. concepts.category='audience' for kids,
     concepts.id='private_bathroom' / 'kindness' / etc. — for v1 we use a fixed
     axis-to-concepts mapping).
  2. For each camp, sum review-signal scores for concepts in this axis.
  3. Filter to camps with score > 0 (positive signal — others get no mark).
  4. Bucket by quantile of remaining scores:
       p<=25  -> 'bib'           (basic)
       p25-50 -> 'recommended'
       p50-75 -> 'notable'
       p>75   -> 'exceptional'
  5. Use a representative review snippet as evidence.

For v1, the axis-to-concepts mapping is hard-coded (curated). Future: derive
from concepts.category programmatically.
"""
from __future__ import annotations
from dataclasses import dataclass

import statistics

from ..domain.models import Mark
from ..adapters.postgres.pool import PostgresPool


# axis -> list of concept ids that contribute to this axis
AXIS_CONCEPTS: dict[str, list[str]] = {
    "kids": ["kids", "playground", "sandpit", "kids_pool", "kids_toilet"],
    "view": ["valley", "oceanview", "riverview", "mountainview", "lakeview", "forestview"],
    "facility": ["trampoline", "swimmingpool", "warmpool", "private_bathroom"],
    "vibe": ["private", "stargazing"],
    "pets": ["pets", "animal_petting"],
}

_LEVELS = ["bib", "recommended", "notable", "exceptional"]


@dataclass
class ComputeMarks:
    """Note: depends on concrete PostgresPool (PG-specific bucketing query)."""

    pool: PostgresPool
    mark_repo: "PostgresMarkRepo"  # type: ignore  # forward-ref to avoid cycle

    def execute(self) -> dict[str, int]:
        """Returns {axis: n_marked_camps} summary."""
        result: dict[str, int] = {}
        with self.pool.conn() as c, c.cursor() as cur:
            for axis, concept_ids in AXIS_CONCEPTS.items():
                if not concept_ids:
                    result[axis] = 0
                    continue
                # Aggregate review-signal score per camp for this axis
                placeholders = ",".join(["%s"] * len(concept_ids))
                cur.execute(
                    f"""
                    SELECT camp_id, SUM(score) AS total_score, MAX(evidence) AS evidence
                    FROM camp_review_signals
                    WHERE concept_id IN ({placeholders})
                    GROUP BY camp_id
                    HAVING SUM(score) > 0
                    ORDER BY total_score
                    """,
                    tuple(concept_ids),
                )
                rows = cur.fetchall()
                if not rows:
                    result[axis] = 0
                    continue
                scores = [float(r[1]) for r in rows]
                # Quantile thresholds within positively-scored camps
                if len(scores) < 4:
                    # Too few -- assign all to 'bib' (entry level)
                    quantiles = [scores[0]] * 3
                else:
                    qs = statistics.quantiles(scores, n=4)  # 3 cutoffs (p25,p50,p75)
                    quantiles = qs
                count_per_axis = 0
                # We need to wipe previous marks for this axis only -- fold into the
                # mark_repo.replace_for_camp call which deletes ALL axes for the camp.
                # To keep idempotency, we instead delete marks for this axis first.
                cur.execute("DELETE FROM camp_marks WHERE axis=%s", (axis,))
                for cid, score, evidence in rows:
                    score_f = float(score)
                    if score_f <= quantiles[0]:
                        level = "bib"
                    elif score_f <= quantiles[1]:
                        level = "recommended"
                    elif score_f <= quantiles[2]:
                        level = "notable"
                    else:
                        level = "exceptional"
                    cur.execute(
                        """INSERT INTO camp_marks (camp_id, axis, level, score, evidence)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (camp_id, axis) DO UPDATE SET
                             level=EXCLUDED.level, score=EXCLUDED.score,
                             evidence=EXCLUDED.evidence, computed_at=now()""",
                        (cid, axis, level, score_f, evidence),
                    )
                    count_per_axis += 1
                result[axis] = count_per_axis
        return result
