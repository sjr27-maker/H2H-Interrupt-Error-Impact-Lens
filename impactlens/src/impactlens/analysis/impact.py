"""Impact analyzer — computes blast radius from changed symbols via reverse
reachability on the call graph. Implemented Day 3."""
from __future__ import annotations

from impactlens.core.models import ImpactResult
from impactlens.graph.call_graph import CallGraph


def compute_impact(
    graph: CallGraph, changed_symbol_ids: list[str]
) -> ImpactResult:
    """Return the ImpactResult for a set of changed symbols."""
    raise NotImplementedError("Implemented Day 3")