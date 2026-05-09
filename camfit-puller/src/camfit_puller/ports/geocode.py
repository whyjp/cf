from __future__ import annotations
from typing import Optional, Protocol, runtime_checkable
from ..domain.models import GeoPoint


@runtime_checkable
class Geocoder(Protocol):
    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]: ...
