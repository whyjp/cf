"""FalkorDB adapter implementing ports.graph.GraphStore."""
from __future__ import annotations
from typing import Any, Optional

from falkordb import FalkorDB


class FalkorGraph:
    """Cypher-via-FalkorDB GraphStore.

    Each `query()` opens a fresh client (cheap — same TCP) so the adapter is
    stateless and safe to share across use-cases.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, graph: str = "camfit"):
        self._host = host
        self._port = port
        self._graph = graph

    def _g(self):
        return FalkorDB(host=self._host, port=self._port).select_graph(self._graph)

    def query(self, cypher: str, params: dict | None = None) -> list[list[Any]]:
        rs = self._g().query(cypher, params=params or {})
        return [list(r) for r in (rs.result_set or [])]

    def reset(self, graph_name: Optional[str] = None) -> None:
        target = graph_name or self._graph
        g = FalkorDB(host=self._host, port=self._port).select_graph(target)
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
