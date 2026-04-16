"""Call graph construction and traversal using NetworkX.
Implemented Day 2-3."""
from __future__ import annotations

import networkx as nx

from impactlens.core.models import CallEdge, SourceSymbol


class CallGraph:
    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

    def add_symbol(self, sym: SourceSymbol) -> None:
        self._g.add_node(sym.id, symbol=sym)

    def add_call(self, edge: CallEdge) -> None:
        self._g.add_edge(edge.caller, edge.callee, data=edge)

    def ancestors_of(self, symbol_id: str) -> set[str]:
        """Return all transitive callers of symbol_id."""
        if symbol_id not in self._g:
            return set()
        return nx.ancestors(self._g, symbol_id)

    @property
    def graph(self) -> nx.DiGraph:
        return self._g