"""Nominatim (OpenStreetMap) geocoder adapter — implements ports.geocode.Geocoder.

Honors Nominatim ToS: max 1 req/sec, identifies via UA. The 1-req/sec gate is
the *adapter's* responsibility — wrap with CachedGeocoder to avoid repeated calls
for the same address.

Coarse-match guard: Nominatim cheerfully returns county/district centroids
when it can't resolve a road or 지번 — that's how 100+ camps ended up at the
same (lat, lon) on the FE map. We reject any result whose `osm_type` /
`class` / `addresstype` indicates an admin-level boundary instead of a
building/road point.
"""
from __future__ import annotations
import threading
import time
from typing import Optional

import httpx

from ...domain.models import GeoPoint


_KR_LAT = (33.0, 39.0)
_KR_LON = (124.0, 132.0)

# Nominatim address types that mean "we matched the admin region, not the
# specific spot". These are the queries that produce 100-camps-on-one-pin.
_COARSE_ADDRESS_TYPES = {
    "country", "state", "region", "province",
    "county", "city", "town", "village", "municipality",
    "borough", "city_district", "suburb", "neighbourhood",
}
_COARSE_CLASSES = {"boundary", "place"}


class NominatimGeocoder:
    name = "nominatim"

    def __init__(self, *,
                 user_agent: str = "camfit-puller/0.1 (research; contact via repo whyjp/cf)",
                 timeout_s: float = 20.0,
                 rate_limit_s: float = 1.05):
        self._ua = user_agent
        self._timeout = timeout_s
        self._rate_limit_s = rate_limit_s
        self._last_call = 0.0
        # Lock the rate-limit gate so multiple threads can safely call lookup()
        # without violating Nominatim's 1 req/sec policy.  Only the gate is
        # held during sleep — the HTTP request itself runs unlocked, but the
        # gate ensures requests are spaced ≥ rate_limit_s apart.
        self._gate = threading.Lock()
        self._client = httpx.Client(timeout=timeout_s, follow_redirects=True)

    def _wait_rate_limit(self) -> None:
        with self._gate:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self._rate_limit_s:
                time.sleep(self._rate_limit_s - elapsed)
            self._last_call = time.monotonic()

    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]:
        if not address:
            return None
        self._wait_rate_limit()
        try:
            r = self._client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": address,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "kr",
                    "accept-language": "ko",
                    "addressdetails": 1,
                },
                headers={"User-Agent": self._ua, "Accept": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            if not data:
                return None
            doc = data[0]
            atype = (doc.get("addresstype") or "").lower()
            klass = (doc.get("class") or "").lower()
            # Admin-level / boundary results are dropped — they're how every
            # camp in 영월군 ends up at the county centroid.
            if atype in _COARSE_ADDRESS_TYPES or klass in _COARSE_CLASSES:
                return None
            lat = float(doc["lat"])
            lon = float(doc["lon"])
            if not (_KR_LAT[0] <= lat <= _KR_LAT[1] and _KR_LON[0] <= lon <= _KR_LON[1]):
                return None
            return GeoPoint(lat=lat, lon=lon)
        except Exception:
            return None
