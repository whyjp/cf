"""Mock geocoder — returns a fixed Seoul-area point for any non-empty address."""
from __future__ import annotations
from typing import Optional

from ...domain.models import GeoPoint


class MockGeocoder:
    name = "mock"

    def __init__(self, lat: float = 37.5, lon: float = 127.0):
        self._lat = lat
        self._lon = lon

    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]:
        if not address:
            return None
        return GeoPoint(lat=self._lat, lon=self._lon)
