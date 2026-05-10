from __future__ import annotations
from typing import Iterable, Optional, Protocol, runtime_checkable
from ..domain.models import GeoPoint


@runtime_checkable
class Geocoder(Protocol):
    """Resolves a (Korean) address string to lat/lon.

    Implementations should return None for unresolvable addresses rather than
    raising — callers treat None as "leave the camp without coords".
    """

    def lookup(self, address: str, *, hint: str | None = None) -> Optional[GeoPoint]: ...

    # Optional: batch entry point. Implementations that have a meaningful
    # batch path (subprocess fan-out, vectorized HTTP, etc.) should override.
    # The default Protocol implementation iterates lookup() — callers should
    # prefer hasattr-checking or always passing through whatever is wired.
    def lookup_many(
        self, items: Iterable[tuple[str, str | None]],
    ) -> dict[str, Optional[GeoPoint]]:
        """Resolve many (address, hint) pairs in one shot.

        Returns a mapping ``address → GeoPoint | None`` keyed by the FIRST
        argument of each input pair. Duplicate addresses collapse to one
        cache key per the convention used by ``CachedGeocoder``.
        """
        ...
