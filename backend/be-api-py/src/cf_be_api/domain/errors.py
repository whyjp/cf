"""Domain-level exceptions. Adapters wrap raw lib exceptions into these."""


class DomainError(Exception):
    pass


class CampNotFound(DomainError):
    def __init__(self, camp_id: str):
        super().__init__(f"camp not found: {camp_id}")
        self.camp_id = camp_id


class EmbeddingDimMismatch(DomainError):
    pass


class GeocodeUnresolved(DomainError):
    pass


class EtaUnavailable(DomainError):
    pass


class GraphUnavailable(DomainError):
    pass


class SourceUnavailable(DomainError):
    pass
