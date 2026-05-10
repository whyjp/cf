from __future__ import annotations
import json
from typing import Iterable, Iterator, Optional
from psycopg.rows import dict_row
from ...domain.models import Camp, Region, GeoPoint, Photo
from ...domain.errors import CampNotFound
from .pool import PostgresPool


_LIST_FIELDS = (
    "id, name, sido, sigungu, address, lat, lon, brief, location_brief, contact, "
    "price_start_from, price_end_to, num_of_reviews, num_of_viewed, bookmark_count, "
    "url, source, detail_url"
)


class PostgresCampReader:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def get(self, camp_id: str) -> Optional[Camp]:
        with self._pool.conn() as c, c.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT {_LIST_FIELDS} FROM camps WHERE id = %s", (camp_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._enrich(c, row)

    def _enrich(self, conn, row) -> Camp:
        cid = row["id"]
        with conn.cursor() as cur:
            cur.execute("SELECT description FROM camp_descriptions WHERE camp_id=%s", (cid,))
            d = cur.fetchone()
            description = d[0] if d else None

            def lst(table, col):
                cur.execute(f"SELECT {col} FROM {table} WHERE camp_id=%s ORDER BY {col}", (cid,))
                return [r[0] for r in cur.fetchall()]

            types = lst("camp_types", "type")
            cur.execute(
                "SELECT facility, is_additional FROM camp_facilities WHERE camp_id=%s ORDER BY facility",
                (cid,),
            )
            fac_rows = cur.fetchall()
            facs = [r[0] for r in fac_rows if not r[1]]
            addl = [r[0] for r in fac_rows if r[1]]
            hashtags = lst("camp_hashtags", "hashtag")
            loc_types = lst("camp_location_types", "location_type")
            collections = lst("camp_collections", "collection_name")
            cur.execute(
                "SELECT idx, url, thumb_url, w, h FROM camp_medias WHERE camp_id=%s ORDER BY idx",
                (cid,),
            )
            photos = [
                Photo(url=r[1], thumb_url=r[2], width=r[3], height=r[4])
                for r in cur.fetchall()
            ]

        geo = None
        if row["lat"] is not None and row["lon"] is not None:
            try:
                geo = GeoPoint(lat=float(row["lat"]), lon=float(row["lon"]))
            except Exception:
                geo = None

        return Camp(
            id=cid,
            name=row["name"],
            region=Region(
                sido=row["sido"] or "(미지정)",
                sigungu=row["sigungu"] or "(미지정)",
            ),
            address=row["address"],
            geo=geo,
            types=types,
            facilities=facs,
            additional_facilities=addl,
            location_types=loc_types,
            hashtags=hashtags,
            collections=collections,
            description=description,
            brief=row["brief"],
            location_brief=row["location_brief"],
            contact=row["contact"],
            price_start_from=row["price_start_from"],
            price_end_to=row["price_end_to"],
            num_of_reviews=row["num_of_reviews"] or 0,
            num_of_viewed=row["num_of_viewed"] or 0,
            bookmark_count=row["bookmark_count"] or 0,
            url=row["url"],
            source=row["source"] or "camfit",
            detail_url=row.get("detail_url"),
            photos=photos,
        )

    def list_filtered(
        self, *,
        sido=None, sigungu=None,
        concept=None, concepts_any=None,
        min_score=None, max_score=None,
        bbox=None, ids=None,
        limit=2000,
    ) -> list[Camp]:
        wh = []
        params: list = []
        if sido:
            wh.append("c.sido = %s")
            params.append(sido)
        if sigungu:
            wh.append("c.sigungu = %s")
            params.append(sigungu)
        if bbox:
            lon1, lat1, lon2, lat2 = bbox
            wh.append("c.lon BETWEEN %s AND %s AND c.lat BETWEEN %s AND %s")
            params.extend([
                min(lon1, lon2), max(lon1, lon2),
                min(lat1, lat2), max(lat1, lat2),
            ])
        if ids:
            wh.append("c.id = ANY(%s)")
            params.append(list(ids))

        # Build SELECT/FROM/JOINs
        select_cols = ", ".join("c." + col for col in _LIST_FIELDS.split(", "))
        sql = f"SELECT {select_cols} FROM camps c "

        # AND-semantics: each concept must satisfy min/max via separate JOIN
        if concept:
            for i, cid_filter in enumerate(concept):
                alias = f"agg_{i}"
                sql += f" JOIN camp_concept_aggregated {alias} ON {alias}.camp_id=c.id AND {alias}.concept_id=%s "
                params.append(cid_filter)
                if min_score is not None:
                    wh.append(f"{alias}.final_score >= %s")
                    params.append(min_score)
                if max_score is not None:
                    wh.append(f"{alias}.final_score <= %s")
                    params.append(max_score)

        # OR-semantics over concepts_any
        if concepts_any:
            sql += " JOIN camp_concept_aggregated agg_any ON agg_any.camp_id=c.id "
            wh.append("agg_any.concept_id = ANY(%s)")
            params.append(list(concepts_any))
            if min_score is not None:
                wh.append("agg_any.final_score >= %s")
                params.append(min_score)
            if max_score is not None:
                wh.append("agg_any.final_score <= %s")
                params.append(max_score)

        if wh:
            sql += " WHERE " + " AND ".join(wh)
        sql += " LIMIT %s"
        params.append(limit)

        with self._pool.conn() as c, c.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [self._enrich(c, r) for r in rows]

    def iter_all(self) -> Iterator[Camp]:
        # Use server-side cursor for memory-efficient iteration
        with self._pool.conn() as c:
            with c.cursor(row_factory=dict_row, name="camp_iter") as cur:
                cur.execute(f"SELECT {_LIST_FIELDS} FROM camps")
                for row in cur:
                    yield self._enrich(c, row)

    def count(self) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM camps")
            return cur.fetchone()[0]


class PostgresCampWriter:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert_many(self, camps: Iterable[Camp]) -> int:
        n = 0
        with self._pool.conn() as c, c.cursor() as cur:
            for camp in camps:
                cur.execute(
                    """
                    INSERT INTO camps (id, name, sido, sigungu, address, lat, lon,
                                       brief, location_brief, contact,
                                       price_start_from, price_end_to,
                                       num_of_reviews, num_of_viewed, bookmark_count,
                                       url, source, detail_url, fetched_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                    ON CONFLICT (id) DO UPDATE SET
                      name=EXCLUDED.name, sido=EXCLUDED.sido, sigungu=EXCLUDED.sigungu,
                      address=EXCLUDED.address, brief=EXCLUDED.brief,
                      location_brief=EXCLUDED.location_brief, contact=EXCLUDED.contact,
                      price_start_from=EXCLUDED.price_start_from, price_end_to=EXCLUDED.price_end_to,
                      num_of_reviews=EXCLUDED.num_of_reviews, num_of_viewed=EXCLUDED.num_of_viewed,
                      bookmark_count=EXCLUDED.bookmark_count, url=EXCLUDED.url,
                      source=EXCLUDED.source, detail_url=EXCLUDED.detail_url
                    """,
                    (
                        camp.id, camp.name, camp.region.sido, camp.region.sigungu,
                        camp.address,
                        camp.geo.lat if camp.geo else None,
                        camp.geo.lon if camp.geo else None,
                        camp.brief, camp.location_brief, camp.contact,
                        camp.price_start_from, camp.price_end_to,
                        camp.num_of_reviews, camp.num_of_viewed, camp.bookmark_count,
                        camp.url, camp.source, camp.detail_url,
                    ),
                )
                if camp.description is not None:
                    cur.execute(
                        "INSERT INTO camp_descriptions (camp_id, description) VALUES (%s, %s) "
                        "ON CONFLICT (camp_id) DO UPDATE SET description=EXCLUDED.description",
                        (camp.id, camp.description),
                    )
                # m:n tables: wipe then insert (idempotent)
                for tbl, col, vals in [
                    ("camp_types", "type", camp.types),
                    ("camp_hashtags", "hashtag", camp.hashtags),
                    ("camp_location_types", "location_type", camp.location_types),
                    ("camp_collections", "collection_name", camp.collections),
                ]:
                    cur.execute(f"DELETE FROM {tbl} WHERE camp_id=%s", (camp.id,))
                    if vals:
                        cur.executemany(
                            f"INSERT INTO {tbl} (camp_id, {col}) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            [(camp.id, v) for v in vals],
                        )
                cur.execute("DELETE FROM camp_facilities WHERE camp_id=%s", (camp.id,))
                facs = [(camp.id, f, False) for f in camp.facilities] + [
                    (camp.id, f, True) for f in camp.additional_facilities
                    if f not in camp.facilities
                ]
                if facs:
                    cur.executemany(
                        "INSERT INTO camp_facilities (camp_id, facility, is_additional) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        facs,
                    )
                cur.execute("DELETE FROM camp_medias WHERE camp_id=%s", (camp.id,))
                if camp.photos:
                    cur.executemany(
                        "INSERT INTO camp_medias (camp_id, idx, url, thumb_url, w, h) VALUES (%s,%s,%s,%s,%s,%s)",
                        [
                            (camp.id, i, p.url, p.thumb_url, p.width, p.height)
                            for i, p in enumerate(camp.photos)
                        ],
                    )
                n += 1
        return n

    def set_geo(self, camp_id: str, lat: float, lon: float) -> None:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE camps SET lat=%s, lon=%s, geocoded_at=now() WHERE id=%s",
                (lat, lon, camp_id),
            )

    def delete(self, camp_id: str) -> bool:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM camps WHERE id=%s", (camp_id,))
            return cur.rowcount > 0
