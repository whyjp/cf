"""Caching decorator for Geocoder — wraps any Geocoder + a cache repository.

Looks up address in PG geocode cache before hitting the upstream geocoder.
For batch calls, only cache misses are forwarded to ``inner.lookup_many``
(when the inner supports it), so re-runs over partially-resolved data are
free against the cache.
"""
from __future__ import annotations
from typing import Iterable, Optional

from ...domain.models import GeoPoint


class CachedGeocoder:
    """Implements Geocoder. Composition: cache-repo + inner Geocoder."""

    def __init__(self, inner, cache_repo, *, source: str = "cached"):
        # `cache_repo` must expose .get(address) -> Optional[(lat, lon)]
        # and .put(address, lat, lon, source).
        self._inner = inner
        self._cache = cache_repo
        self._source = source

    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]:
        if not address:
            return None
        # 1) Cache hit?
        hit = self._cache.get(address)
        if hit is not None:
            lat, lon = hit
            try:
                return GeoPoint(lat=lat, lon=lon)
            except Exception:
                # Out-of-bbox or invalid cached row — drop, fall through to upstream
                pass
        # 2) Upstream
        result = self._inner.lookup(address, hint=hint)
        # 3) Cache (even None — to avoid hammering on bad addresses)
        if result is not None:
            self._cache.put(address, result.lat, result.lon, self._source)
        else:
            self._cache.put(address, None, None, self._source)
        return result

    def lookup_many(
        self, items: Iterable[tuple[str, str | None]],
    ) -> dict[str, Optional[GeoPoint]]:
        """Batch entry: pull cache hits, send misses to ``inner.lookup_many``.

        Falls back to per-item ``lookup`` calls when the inner adapter does
        not implement ``lookup_many`` (e.g. NominatimGeocoder).
        """
        items_list = [(a, h) for a, h in items if a]
        out: dict[str, Optional[GeoPoint]] = {}
        misses: list[tuple[str, str | None]] = []
        seen: set[str] = set()

        for addr, hint in items_list:
            if addr in seen:
                continue
            seen.add(addr)
            hit = self._cache.get(addr)
            if hit is not None:
                lat, lon = hit
                try:
                    out[addr] = GeoPoint(lat=lat, lon=lon)
                    continue
                except Exception:
                    # Fall through to re-resolve
                    pass
            misses.append((addr, hint))

        if not misses:
            return out

        # Inner can either expose lookup_many (preferred for subprocess
        # adapters where one process amortizes spawn cost) or only lookup.
        inner_many = getattr(self._inner, "lookup_many", None)
        if callable(inner_many):
            resolved = inner_many(misses)
        else:
            resolved = {addr: self._inner.lookup(addr, hint=hint) for addr, hint in misses}

        for addr, hint in misses:
            point = resolved.get(addr)
            if point is not None:
                self._cache.put(addr, point.lat, point.lon, self._source)
            else:
                self._cache.put(addr, None, None, self._source)
            out[addr] = point
        return out
