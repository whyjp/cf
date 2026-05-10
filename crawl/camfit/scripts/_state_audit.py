"""One-shot data state audit for hybrid-search readiness research.

Reports:
  PG: row counts + coverage (geocode, embed, descriptions, signals, marks, themes, concepts)
  Pgvector: embedding count, dim sample, model_name distribution
  FalkorDB: label counts, edge type counts, signature edges
  Quality: concept score distribution, mark axis spread, embedding text length
"""
from __future__ import annotations
import json
import sys

import psycopg
from falkordb import FalkorDB

PG_DSN = "postgresql://camfit:camfit@localhost:5432/camfit"


def fetchone(cur, sql: str, params: tuple = ()) -> object:
    cur.execute(sql, params)
    r = cur.fetchone()
    return r[0] if r else None


def fetchall(cur, sql: str, params: tuple = ()) -> list:
    cur.execute(sql, params)
    return cur.fetchall()


def pg_audit() -> dict:
    out: dict = {}
    with psycopg.connect(PG_DSN) as c, c.cursor() as cur:
        # Camp coverage
        out["camps_total"] = fetchone(cur, "SELECT count(*) FROM camps")
        out["camps_with_latlon"] = fetchone(
            cur, "SELECT count(*) FROM camps WHERE lat IS NOT NULL AND lon IS NOT NULL"
        )
        out["camps_with_address"] = fetchone(
            cur, "SELECT count(*) FROM camps WHERE address IS NOT NULL AND address <> ''"
        )
        out["camps_with_brief"] = fetchone(
            cur, "SELECT count(*) FROM camps WHERE brief IS NOT NULL AND brief <> ''"
        )
        out["camps_with_description"] = fetchone(
            cur,
            "SELECT count(*) FROM camp_descriptions WHERE description IS NOT NULL AND length(description) > 20",
        )
        out["camps_with_sido"] = fetchone(
            cur, "SELECT count(*) FROM camps WHERE sido IS NOT NULL AND sido <> ''"
        )
        out["distinct_sido"] = fetchone(cur, "SELECT count(DISTINCT sido) FROM camps")
        out["distinct_sigungu"] = fetchone(cur, "SELECT count(DISTINCT (sido, sigungu)) FROM camps")

        # Tags / facilities / hashtags
        out["camp_types_rows"] = fetchone(cur, "SELECT count(*) FROM camp_types")
        out["distinct_types"] = fetchone(cur, "SELECT count(DISTINCT type) FROM camp_types")
        out["camp_facilities_rows"] = fetchone(cur, "SELECT count(*) FROM camp_facilities")
        out["distinct_facilities"] = fetchone(
            cur, "SELECT count(DISTINCT facility) FROM camp_facilities"
        )
        out["camp_hashtags_rows"] = fetchone(cur, "SELECT count(*) FROM camp_hashtags")
        out["distinct_hashtags"] = fetchone(cur, "SELECT count(DISTINCT hashtag) FROM camp_hashtags")
        out["camp_collections_rows"] = fetchone(cur, "SELECT count(*) FROM camp_collections")
        out["distinct_collections"] = fetchone(
            cur, "SELECT count(DISTINCT collection_name) FROM camp_collections"
        )
        out["camp_location_types_rows"] = fetchone(cur, "SELECT count(*) FROM camp_location_types")

        # Reviews
        out["reviews_total"] = fetchone(cur, "SELECT count(*) FROM reviews")
        out["camps_with_reviews"] = fetchone(
            cur, "SELECT count(DISTINCT camp_id) FROM reviews"
        )

        # Concepts
        out["concepts_total"] = fetchone(cur, "SELECT count(*) FROM concepts")
        out["concept_axes_total"] = fetchone(
            cur, "SELECT count(*) FROM concepts WHERE is_axis = true"
        )
        out["concept_sources"] = fetchall(
            cur, "SELECT source, count(*) FROM concepts GROUP BY source ORDER BY 2 DESC"
        )
        out["filter_concept_mappings"] = fetchone(
            cur, "SELECT count(*) FROM filter_concept_mapping"
        )

        # Signals
        out["filter_signals_rows"] = fetchone(cur, "SELECT count(*) FROM camp_filter_signals")
        out["desc_signals_rows"] = fetchone(cur, "SELECT count(*) FROM camp_desc_signals")
        out["review_signals_rows"] = fetchone(cur, "SELECT count(*) FROM camp_review_signals")
        out["camps_with_filter_signals"] = fetchone(
            cur, "SELECT count(DISTINCT camp_id) FROM camp_filter_signals"
        )
        out["camps_with_desc_signals"] = fetchone(
            cur, "SELECT count(DISTINCT camp_id) FROM camp_desc_signals"
        )
        out["camps_with_review_signals"] = fetchone(
            cur, "SELECT count(DISTINCT camp_id) FROM camp_review_signals"
        )

        # Aggregated matview
        out["cca_rows"] = fetchone(cur, "SELECT count(*) FROM camp_concept_aggregated")
        out["cca_positive"] = fetchone(
            cur, "SELECT count(*) FROM camp_concept_aggregated WHERE final_score > 0"
        )
        out["cca_camps_with_positive"] = fetchone(
            cur,
            "SELECT count(DISTINCT camp_id) FROM camp_concept_aggregated WHERE final_score > 0",
        )
        out["cca_score_quartiles"] = fetchall(
            cur,
            "SELECT min(final_score), percentile_cont(0.25) WITHIN GROUP (ORDER BY final_score), "
            "percentile_cont(0.5) WITHIN GROUP (ORDER BY final_score), "
            "percentile_cont(0.75) WITHIN GROUP (ORDER BY final_score), "
            "max(final_score) "
            "FROM camp_concept_aggregated WHERE final_score > 0",
        )
        out["cca_top_concepts"] = fetchall(
            cur,
            "SELECT c.name, count(*) FROM camp_concept_aggregated agg "
            "JOIN concepts c ON c.id = agg.concept_id "
            "WHERE agg.final_score > 0 "
            "GROUP BY c.name ORDER BY 2 DESC LIMIT 12",
        )

        # Marks
        out["marks_total"] = fetchone(cur, "SELECT count(*) FROM camp_marks")
        out["marks_axes"] = fetchall(
            cur,
            "SELECT axis, count(*), array_agg(DISTINCT level) "
            "FROM camp_marks GROUP BY axis ORDER BY 2 DESC",
        )

        # Themes
        out["themes_total"] = fetchone(cur, "SELECT count(*) FROM themes")
        out["themes_with_centroid"] = fetchone(
            cur, "SELECT count(*) FROM themes WHERE centroid IS NOT NULL"
        )
        out["camp_themes_assigned"] = fetchone(cur, "SELECT count(*) FROM camp_themes")
        out["distinct_themed_camps"] = fetchone(
            cur, "SELECT count(DISTINCT camp_id) FROM camp_themes"
        )

        # Embeddings
        out["embeddings_total"] = fetchone(cur, "SELECT count(*) FROM camp_embeddings")
        out["embedding_models"] = fetchall(
            cur,
            "SELECT model_name, count(*) FROM camp_embeddings GROUP BY model_name",
        )
        # avg vector dim (sanity — should match 768)
        out["embeddings_unique_text_hashes"] = fetchone(
            cur, "SELECT count(DISTINCT text_hash) FROM camp_embeddings"
        )
        out["embedding_oldest"] = fetchone(cur, "SELECT min(created_at) FROM camp_embeddings")
        out["embedding_newest"] = fetchone(cur, "SELECT max(created_at) FROM camp_embeddings")

        # Geocode cache
        out["geocode_cache_rows"] = fetchone(cur, "SELECT count(*) FROM geocodes")
        out["geocode_cache_with_latlon"] = fetchone(
            cur, "SELECT count(*) FROM geocodes WHERE lat IS NOT NULL AND lon IS NOT NULL"
        )

        # ETA cache
        out["eta_cache_rows"] = fetchone(cur, "SELECT count(*) FROM eta_cache")

        # Lexical-search readiness: are there any tsvector/GIN indexes?
        out["text_indexes"] = fetchall(
            cur,
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND (indexdef ILIKE '%%gin%%' OR indexdef ILIKE '%%tsvector%%' OR indexdef ILIKE '%%trgm%%')",
        )
        # Extensions installed
        out["extensions"] = fetchall(
            cur, "SELECT extname FROM pg_extension ORDER BY extname"
        )

        # Description length distribution (corpus quality for embedding)
        out["desc_length_stats"] = fetchall(
            cur,
            "SELECT min(length(description)), avg(length(description))::int, "
            "max(length(description)), count(*) FROM camp_descriptions "
            "WHERE description IS NOT NULL",
        )
        # Reviews length per camp
        out["reviews_per_camp_stats"] = fetchall(
            cur,
            "WITH x AS (SELECT camp_id, count(*) n FROM reviews GROUP BY camp_id) "
            "SELECT min(n), avg(n)::int, max(n), count(*) FROM x",
        )
    return out


def falkor_audit() -> dict:
    out: dict = {}
    g = FalkorDB(host="localhost", port=6379).select_graph("camfit")
    try:
        out["labels"] = []
        for row in g.query("CALL db.labels()").result_set or []:
            lbl = row[0]
            cnt = g.query(f"MATCH (n:`{lbl}`) RETURN count(n)").result_set
            out["labels"].append((lbl, int(cnt[0][0]) if cnt else 0))
        out["edges"] = []
        for row in g.query("CALL db.relationshipTypes()").result_set or []:
            rt = row[0]
            cnt = g.query(f"MATCH ()-[r:`{rt}`]->() RETURN count(r)").result_set
            out["edges"].append((rt, int(cnt[0][0]) if cnt else 0))
        # has_concept score distribution
        sc = g.query(
            "MATCH ()-[r:HAS_CONCEPT]->() RETURN min(r.score), avg(r.score), max(r.score), count(r)"
        ).result_set
        out["has_concept_score_stats"] = sc[0] if sc else None
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main() -> None:
    pg = pg_audit()
    fk = falkor_audit()
    print("=" * 60)
    print("PG state")
    print("=" * 60)
    for k, v in pg.items():
        print(f"{k}: {v}")
    print()
    print("=" * 60)
    print("FalkorDB state")
    print("=" * 60)
    for k, v in fk.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
