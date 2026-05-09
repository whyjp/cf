"""Use-case: seed concept vocabulary + auto-derive from existing camp data.

Idempotent — re-running is safe (UPSERT on id, plus name-conflict resolution
that privileges curated seeds over auto-derived hashtag concepts).

Seed-vs-hashtag UNIQUE(name) collision:
  The `concepts.name` column has a UNIQUE constraint. A previous vocab run
  may have inserted `(id='h_청결', name='청결', source='hashtag')`. On the
  next run with a new seed `(id='mgmt_clean2', name='청결', source='manual',
  category='management')`, an ON CONFLICT (id) clause does NOT catch the
  collision — the INSERT fails on UNIQUE(name) and breaks the seed pass.
  This use-case detects that case and deletes the conflicting auto-derived
  row first so the seed wins. Auto-derived rows are reproducible from
  raw data; seeds carry curated category/is_axis metadata that's harder
  to rebuild.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

from ..domain.concept_seeds import SEEDS
from ..domain.models import Concept
from ..ports.repo import CampReader, ConceptRepository


_SLUG_RE = re.compile(r"[^a-zA-Z0-9가-힣]+")


def _slug(name: str) -> str:
    return _SLUG_RE.sub("_", name).strip("_").lower()


@dataclass
class BuildVocabulary:
    camp_reader: CampReader
    concept_repo: ConceptRepository

    def execute(self) -> int:
        n = 0
        # 1) Curated seeds. Before each upsert, resolve any UNIQUE(name)
        # collision by deleting an existing auto-derived row that holds the
        # same name under a different id. Seeds are authoritative; the
        # hashtag pass will simply re-skip the freed name later in this run.
        seed_names: set[str] = {name for _, name, *_ in SEEDS}
        seed_ids: set[str] = {cid for cid, *_ in SEEDS}
        for cid, name, category, is_axis in SEEDS:
            existing = self.concept_repo.find_by_name(name)
            if existing is not None and existing.id != cid and existing.id not in seed_ids:
                self.concept_repo.delete_by_id(existing.id)
            self.concept_repo.upsert_concept(
                Concept(id=cid, name=name, source="manual",
                        category=category, is_axis=is_axis)
            )
            n += 1
        # 2) Auto-derived from camp hashtags + facilities
        # Pre-load existing concept ids and names from PG. Without this, a
        # hashtag iteration could try to INSERT a row whose name collides
        # with a previously-persisted concept (different id) and the
        # `ON CONFLICT (id)` clause would not catch it — UNIQUE(name) raises.
        seen: set[str] = set(seed_ids)
        seen_names: set[str] = set(seed_names)
        for existing in self.concept_repo.all():
            seen.add(existing.id)
            seen_names.add(existing.name)
        for camp in self.camp_reader.iter_all():
            for h in camp.hashtags:
                slug = "h_" + _slug(h)
                if slug in seen or h in seen_names:
                    continue
                seen.add(slug)
                seen_names.add(h)
                self.concept_repo.upsert_concept(
                    Concept(id=slug, name=h, source="hashtag")
                )
                n += 1
            for f in (camp.facilities + camp.additional_facilities):
                slug = "f_" + _slug(f)
                if slug in seen or f in seen_names:
                    continue
                seen.add(slug)
                seen_names.add(f)
                self.concept_repo.upsert_concept(
                    Concept(id=slug, name=f, source="facility")
                )
                n += 1
        return n
