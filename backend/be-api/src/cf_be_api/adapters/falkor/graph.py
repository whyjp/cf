"""FalkorDB adapter implementing ports.graph.GraphStore."""
from __future__ import annotations
from typing import Any, Optional

from falkordb import FalkorDB


class FalkorGraph:
    """Cypher-via-FalkorDB GraphStore.

    Holds a single FalkorDB client / graph reference for the adapter lifetime.
    A query-per-FalkorDB pattern was found to exhaust Windows ephemeral ports
    during bulk rebuild_graph runs (10k+ MERGE queries) — connection reuse fixes it.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, graph: str = "camfit"):
        self._host = host
        self._port = port
        self._graph = graph
        self._db: Optional[FalkorDB] = None
        self._g_cached: Optional[Any] = None

    def _client(self) -> FalkorDB:
        if self._db is None:
            self._db = FalkorDB(host=self._host, port=self._port)
        return self._db

    def _g(self):
        if self._g_cached is None:
            self._g_cached = self._client().select_graph(self._graph)
        return self._g_cached

    def query(self, cypher: str, params: dict | None = None) -> list[list[Any]]:
        rs = self._g().query(cypher, params=params or {})
        return [list(r) for r in (rs.result_set or [])]

    def reset(self, graph_name: Optional[str] = None) -> None:
        target = graph_name or self._graph
        if target == self._graph:
            g = self._g()
        else:
            g = self._client().select_graph(target)
        try:
            g.query("MATCH (n) DETACH DELETE n")
        except Exception:
            # Empty graph or already-reset is OK
            pass

    def healthcheck(self) -> bool:
        try:
            self._g().query("RETURN 1")
            return True
        except Exception:
            return False
