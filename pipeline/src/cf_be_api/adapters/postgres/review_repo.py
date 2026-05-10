from __future__ import annotations
from typing import Iterable, Iterator, Literal
from ...domain.models import Review
from .pool import PostgresPool


class PostgresReviewReader:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def top_for(self, camp_id: str, n: int = 3,
                sort: Literal["score", "recent"] = "score") -> list[Review]:
        order = "score DESC NULLS LAST" if sort == "score" else "review_timestamp DESC"
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute(
                f"""SELECT id, camp_id, user_nick, season, user_type, num_of_days,
                          score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp
                    FROM reviews WHERE camp_id=%s ORDER BY {order} LIMIT %s""",
                (camp_id, n),
            )
            return [self._row(r) for r in cur.fetchall()]

    def total_for(self, camp_id: str) -> int:
        with self._pool.conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) FROM reviews WHERE camp_id=%s", (camp_id,))
            return cur.fetchone()[0]

    def iter_for(self, camp_id: str) -> Iterator[Review]:
        with self._pool.conn() as c:
            with c.cursor(name=f"rev_{camp_id}") as cur:
                cur.execute(
                    """SELECT id, camp_id, user_nick, season, user_type, num_of_days,
                              score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp
                       FROM reviews WHERE camp_id=%s""",
                    (camp_id,),
                )
                for r in cur:
                    yield self._row(r)

    @staticmethod
    def _row(r) -> Review:
        return Review(
            id=r[0], camp_id=r[1], user_nick=r[2], season=r[3], user_type=r[4],
            num_of_days=r[5],
            score=float(r[6]) if r[6] is not None else None,
            text=r[7],
            is_clean=r[8], is_kind=r[9], is_manner=r[10], is_convenient=r[11],
            review_timestamp=r[12],
        )


class PostgresReviewWriter:
    def __init__(self, pool: PostgresPool):
        self._pool = pool

    def upsert_many(self, reviews: Iterable[Review]) -> int:
        n = 0
        with self._pool.conn() as c, c.cursor() as cur:
            for r in reviews:
                cur.execute(
                    """INSERT INTO reviews (id, camp_id, user_nick, season, user_type,
                          num_of_days, score, text, is_clean, is_kind, is_manner, is_convenient, review_timestamp)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET
                         score=EXCLUDED.score, text=EXCLUDED.text""",
                    (r.id, r.camp_id, r.user_nick, r.season, r.user_type, r.num_of_days,
                     r.score, r.text, r.is_clean, r.is_kind, r.is_manner, r.is_convenient,
                     r.review_timestamp),
                )
                cur.execute("DELETE FROM review_medias WHERE review_id=%s", (r.id,))
                if r.medias:
                    cur.executemany(
                        "INSERT INTO review_medias (review_id, idx, url) VALUES (%s,%s,%s)",
                        [(r.id, i, u) for i, u in enumerate(r.medias)],
                    )
                n += 1
        return n
