"""
Confidence scorer for test selections.

Assigns a 0.0–1.0 confidence to each selected test based on:
- How it was matched (convention, import, LLM)
- Depth of the dependency chain
- Whether the changed symbol is directly tested or transitively impacted
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import PurePosixPath

from impactlens.core.models import ImpactResult, TestCase
from impactlens.graph.call_graph import CallGraph

log = logging.getLogger(__name__)


@dataclass
class ScoredTest:
    """A test with its confidence score and match method."""
    test: TestCase
    confidence: float
    match_method: str  # "direct", "convention", "import", "transitive", "llm"
    chain_depth: int   # 0 = direct, 1 = one hop, etc.


def _compute_chain_depth(
    test: TestCase,
    changed_symbols: list[str],
    graph: CallGraph,
) -> int:
    """
    Compute the shortest dependency chain depth from any changed symbol
    to any symbol covered by this test.
    0 = test directly covers a changed symbol
    1 = test covers a caller of a changed symbol
    N = N hops away
    """
    min_depth = 999

    changed_set = set(changed_symbols)

    for covered_id in test.covered_symbols:
        # Direct match
        if covered_id in changed_set:
            return 0

        # Check if any changed symbol is a descendant of covered
        # (i.e., covered calls something that eventually calls changed)
        for changed_id in changed_symbols:
            ancestors = graph.ancestors_of(changed_id)
            if covered_id in ancestors:
                # Find depth by walking
                depth = 1
                current_level = {changed_id}
                visited = {changed_id}
                while current_level and depth < min_depth:
                    next_level = set()
                    for node in current_level:
                        for caller in graph.direct_callers(node):
                            if caller == covered_id:
                                min_depth = min(min_depth, depth)
                                break
                            if caller not in visited:
                                visited.add(caller)
                                next_level.add(caller)
                    depth += 1
                    current_level = next_level

    return min_depth if min_depth < 999 else -1


def _determine_match_method(
    test: TestCase,
    changed_symbols: list[str],
    impacted_files: list[str],
    graph: CallGraph,
) -> str:
    """Determine how this test was matched to the impact."""
    test_stem = PurePosixPath(test.file_path).stem
    changed_set = set(changed_symbols)

    # Check if test directly covers a changed symbol
    for covered_id in test.covered_symbols:
        if covered_id in changed_set:
            return "direct"
        # Check prefix (class vs method level)
        for cid in changed_set:
            if cid.startswith(covered_id + ".") or covered_id.startswith(cid + "."):
                return "import"

    # Check convention match
    for f in impacted_files:
        source_stem = PurePosixPath(f).stem
        if (test_stem == f"{source_stem}Test"
            or test_stem == f"Test{source_stem}"
            or test_stem == f"{source_stem}Tests"):
            return "convention"

    return "transitive"


def score_tests(
    impact: ImpactResult,
    graph: CallGraph,
) -> list[ScoredTest]:
    """
    Score all selected tests with confidence values.

    Scoring rules:
    - direct match (test covers changed symbol):     0.95 - 1.0
    - convention match (naming pattern):             0.85 - 0.95
    - import match (test imports impacted class):    0.70 - 0.85
    - transitive (multi-hop dependency chain):       0.50 - 0.70
    - LLM-assisted:                                  confidence from LLM

    Deeper chains reduce confidence:
    - Each hop reduces score by 0.05
    """
    scored: list[ScoredTest] = []

    for test in impact.selected_tests:
        method = _determine_match_method(
            test, impact.changed_symbols, impact.impacted_files, graph
        )
        depth = _compute_chain_depth(test, impact.changed_symbols, graph)

        # Base confidence by match method
        if method == "direct":
            base = 0.98
        elif method == "convention":
            base = 0.90
        elif method == "import":
            base = 0.80
        elif method == "transitive":
            base = 0.60
        else:
            base = 0.50

        # Depth penalty: -0.05 per hop, minimum 0.3
        depth_penalty = max(0, depth) * 0.05
        confidence = max(0.30, base - depth_penalty)

        scored.append(ScoredTest(
            test=test,
            confidence=round(confidence, 2),
            match_method=method,
            chain_depth=depth,
        ))

        log.debug("  %s: %.2f (%s, depth=%d)",
                  test.id, confidence, method, depth)

    # Sort by confidence descending
    scored.sort(key=lambda s: s.confidence, reverse=True)

    return scored