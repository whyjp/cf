"""Caching decorator for Geocoder — wraps any Geocoder + a cache repository.

Looks up address in PG geocode cache before hitting the upstream geocoder.
"""
from __future__ import annotations
from typing import Optional

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
