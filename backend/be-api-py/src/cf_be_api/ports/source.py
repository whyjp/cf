from __future__ import annotations
from typing import Iterator, Optional, Protocol, runtime_checkable
from ..domain.models import Camp, Review


@runtime_checkable
class DataSource(Protocol):
    name: str
    def iter_summaries(self) -> Iterator[Camp]: ...
    def get_detail(self, camp_id: str) -> Optional[Camp]: ...
    def iter_reviews(self, camp_id: str, *, sort: str = "recommend") -> Iterator[Review]: ...
    def iter_filters(self) -> Iterator[tuple[str, str, str, dict | None]]:
        """yield (id, name, kind, raw_json) for each native taxonomy entry."""
        ...
