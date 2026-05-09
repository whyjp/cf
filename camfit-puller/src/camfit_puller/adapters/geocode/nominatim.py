"""Nominatim (OpenStreetMap) geocoder adapter — implements ports.geocode.Geocoder.

Honors Nominatim ToS: max 1 req/sec, identifies via UA. The 1-req/sec gate is
the *adapter's* responsibility — wrap with CachedGeocoder to avoid repeated calls
for the same address.
"""
from __future__ import annotations
import threading
import time
from typing import Optional

import httpx

from ...domain.models import GeoPoint


_KR_LAT = (33.0, 39.0)
_KR_LON = (124.0, 132.0)


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
                },
                headers={"User-Agent": self._ua, "Accept": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            if not data:
                return None
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            if not (_KR_LAT[0] <= lat <= _KR_LAT[1] and _KR_LON[0] <= lon <= _KR_LON[1]):
                return None
            return GeoPoint(lat=lat, lon=lon)
        except Exception:
            return None
