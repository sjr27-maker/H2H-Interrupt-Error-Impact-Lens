"""
Call graph construction and traversal using NetworkX.

The graph is directed: edge from A → B means "A calls B".
Impact analysis walks the graph BACKWARDS: "what transitively calls
the changed function?" = nx.ancestors(graph, changed_node).
"""
from __future__ import annotations

import logging
from collections import defaultdict

import networkx as nx

from impactlens.core.models import CallEdge, SourceSymbol

log = logging.getLogger(__name__)


class CallGraph:
    """Wrapper around a NetworkX DiGraph for call-graph operations."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self._symbols: dict[str, SourceSymbol] = {}

    # ----- construction ----------------------------------------------------

    def add_symbol(self, sym: SourceSymbol) -> None:
        """Add a symbol (function/method/class) as a node."""
        self._g.add_node(sym.id, symbol=sym)
        self._symbols[sym.id] = sym

    def add_symbols(self, symbols: list[SourceSymbol]) -> None:
        for s in symbols:
            self.add_symbol(s)

    def add_call(self, edge: CallEdge) -> None:
        """Add a call edge. Creates nodes if they don't exist yet."""
        if not self._g.has_node(edge.caller):
            self._g.add_node(edge.caller)
        if not self._g.has_node(edge.callee):
            self._g.add_node(edge.callee)
        self._g.add_edge(
            edge.caller,
            edge.callee,
            call_site_line=edge.call_site_line,
            confidence=edge.confidence,
        )

    def add_calls(self, edges: list[CallEdge]) -> None:
        for e in edges:
            self.add_call(e)

    # ----- queries ---------------------------------------------------------

    def ancestors_of(self, symbol_id: str) -> set[str]:
        """Return all transitive callers of symbol_id (reverse reachability)."""
        if symbol_id not in self._g:
            return set()
        return nx.ancestors(self._g, symbol_id)

    def descendants_of(self, symbol_id: str) -> set[str]:
        """Return everything that symbol_id transitively calls."""
        if symbol_id not in self._g:
            return set()
        return nx.descendants(self._g, symbol_id)

    def direct_callers(self, symbol_id: str) -> set[str]:
        """Return immediate callers (one hop backwards)."""
        if symbol_id not in self._g:
            return set()
        return set(self._g.predecessors(symbol_id))

    def direct_callees(self, symbol_id: str) -> set[str]:
        """Return immediate callees (one hop forward)."""
        if symbol_id not in self._g:
            return set()
        return set(self._g.successors(symbol_id))

    def get_symbol(self, symbol_id: str) -> SourceSymbol | None:
        return self._symbols.get(symbol_id)

    def has_symbol(self, symbol_id: str) -> bool:
        return symbol_id in self._g

    # ----- inspection ------------------------------------------------------

    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()

    @property
    def graph(self) -> nx.DiGraph:
        """Direct access to the underlying DiGraph (for visualization)."""
        return self._g

    def files_containing(self, symbol_ids: set[str]) -> set[str]:
        """Get the set of files that contain any of the given symbols."""
        files: set[str] = set()
        for sid in symbol_ids:
            sym = self._symbols.get(sid)
            if sym:
                files.add(sym.file_path.replace("\\", "/"))
        return files

    def symbols_in_file(self, file_path: str) -> list[SourceSymbol]:
        """Get all symbols defined in a specific file."""
        normalized = file_path.replace("\\", "/")
        return [
            s for s in self._symbols.values()
            if s.file_path.replace("\\", "/") == normalized
        ]   

    def summary(self) -> dict:
        """Return a summary dict for logging/debugging."""
        file_count = len(set(s.file_path for s in self._symbols.values()))
        return {
            "nodes": self.node_count,
            "edges": self.edge_count,
            "files": file_count,
            "symbols_by_kind": self._count_by_kind(),
        }

    def _count_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for s in self._symbols.values():
            counts[s.kind.value] += 1
        return dict(counts)

    def __repr__(self) -> str:
        return f"CallGraph(nodes={self.node_count}, edges={self.edge_count})"