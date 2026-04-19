"""
Test justification generator.

For each selected test, produces a human-readable explanation of WHY
it was selected. Uses the call graph to build the dependency chain,
then optionally asks the LLM to phrase it naturally.

Works without an LLM — falls back to template-based justifications
built from the call graph structure.
"""
from __future__ import annotations

import logging
from pathlib import PurePosixPath

from impactlens.ai.llm_client import get_llm_client
from impactlens.core.models import ImpactResult, SourceSymbol, TestCase
from impactlens.graph.call_graph import CallGraph

log = logging.getLogger(__name__)


def _build_chain(
    graph: CallGraph,
    changed_id: str,
    test: TestCase,
) -> list[str]:
    """
    Build the shortest dependency chain from a changed symbol to a test's
    covered symbols. Returns a list of symbol names forming the chain.
    """
    # Find which covered symbol connects to the changed symbol
    for covered_id in test.covered_symbols:
        # Check if covered_id is an ancestor of changed_id (or the same)
        if covered_id == changed_id:
            sym = graph.get_symbol(changed_id)
            return [sym.name if sym else changed_id]

        ancestors = graph.ancestors_of(changed_id)
        if covered_id in ancestors or changed_id == covered_id:
            # Build the path
            chain = []
            sym = graph.get_symbol(changed_id)
            chain.append(sym.name if sym else changed_id.split(".")[-1])

            # Walk up to find a path to covered_id
            current = changed_id
            visited = {current}
            while current != covered_id:
                callers = graph.direct_callers(current)
                next_hop = None
                for caller in callers:
                    if caller not in visited:
                        if caller == covered_id or covered_id in graph.ancestors_of(caller):
                            next_hop = caller
                            break
                        # Simple: just pick any unvisited caller
                        if next_hop is None:
                            next_hop = caller

                if next_hop is None:
                    break

                visited.add(next_hop)
                sym = graph.get_symbol(next_hop)
                chain.append(sym.name if sym else next_hop.split(".")[-1])
                current = next_hop

            return chain

    # Fallback: convention-based match, no chain
    return []


def _template_justification(
    test: TestCase,
    changed_symbols: list[str],
    graph: CallGraph,
) -> str:
    """Generate a justification using templates (no LLM needed)."""
    test_class = PurePosixPath(test.file_path).stem  # e.g., "PriceFormatterTest"

    # Find which changed symbol relates to this test
    for changed_id in changed_symbols:
        chain = _build_chain(graph, changed_id, test)
        changed_sym = graph.get_symbol(changed_id)
        changed_name = changed_sym.name if changed_sym else changed_id.split(".")[-1]

        if chain and len(chain) > 1:
            chain_str = " → ".join(chain)
            return (
                f"Selected because {changed_name} was modified, which affects "
                f"this test through the call chain: {chain_str}"
            )
        elif chain:
            return f"Selected because {changed_name} was directly modified and this test exercises it"

    # Convention-based match
    for changed_id in changed_symbols:
        changed_sym = graph.get_symbol(changed_id)
        if changed_sym:
            source_stem = PurePosixPath(changed_sym.file_path).stem
            if source_stem in test_class:
                return (
                    f"Selected by naming convention: {test_class} corresponds to "
                    f"the modified file {source_stem}.java"
                )

    return "Selected based on import analysis — this test imports a class affected by the change"


def _llm_justifications(
    tests: list[TestCase],
    changed_symbols: list[str],
    graph: CallGraph,
) -> dict[str, str]:
    """
    Use the LLM to generate natural-language justifications for all
    selected tests in a single batch call.
    """
    client = get_llm_client()
    if not client.is_available():
        return {}

    # Build context for the LLM
    changes_desc = []
    for sym_id in changed_symbols:
        sym = graph.get_symbol(sym_id)
        if sym:
            changes_desc.append(f"- {sym.qualified_name} ({sym.kind.value}) in {sym.file_path}")

    tests_desc = []
    for t in tests:
        tests_desc.append(f"- {t.id} in {t.file_path}")

    # Build edge descriptions
    edges_desc = []
    for sym_id in changed_symbols:
        callers = graph.direct_callers(sym_id)
        sym = graph.get_symbol(sym_id)
        sym_name = sym.name if sym else sym_id
        for caller_id in callers:
            caller_sym = graph.get_symbol(caller_id)
            caller_name = caller_sym.name if caller_sym else caller_id
            edges_desc.append(f"- {caller_name} calls {sym_name}")

    prompt = f"""You are analyzing the impact of code changes on a Java codebase.

CHANGED SYMBOLS:
{chr(10).join(changes_desc)}

RELEVANT CALL EDGES:
{chr(10).join(edges_desc) if edges_desc else "No direct callers found in the graph."}

SELECTED TESTS:
{chr(10).join(tests_desc)}

For each selected test, write a ONE-SENTENCE justification explaining why this test needs to run given the changes above. Focus on the dependency chain — which changed symbol affects which code that this test exercises.

Respond ONLY with a JSON object where keys are test IDs and values are justification strings. No markdown, no explanation, just the JSON.

Example format:
{{"com.example.FooTest#testBar": "Your change to calculateDiscount affects getOrderTotal, which this test exercises through OrderService"}}"""

    system = (
        "You are a precise code analysis tool. Generate concise, accurate "
        "justifications for test selections based on dependency analysis. "
        "Respond only with valid JSON."
    )

    data = client.complete_json(prompt, system=system, max_tokens=1500)

    if isinstance(data, dict):
        log.info("LLM generated %d justifications", len(data))
        return {k: str(v) for k, v in data.items()}

    log.warning("LLM justification response was not a valid JSON object")
    return {}


def generate_justifications(
    impact: ImpactResult,
    graph: CallGraph,
) -> dict[str, str]:
    """
    Generate justifications for all selected tests.

    Strategy:
    1. Try LLM-based justifications (richer, more natural)
    2. Fall back to template-based justifications for any tests
       the LLM didn't cover (or if LLM is unavailable)

    Returns:
        dict mapping test_id → justification string
    """
    if not impact.selected_tests:
        return {}

    justifications: dict[str, str] = {}

    # Step 1: Try LLM
    llm_results = _llm_justifications(
        impact.selected_tests,
        impact.changed_symbols,
        graph,
    )
    justifications.update(llm_results)

    # Step 2: Fill gaps with templates
    for test in impact.selected_tests:
        if test.id not in justifications:
            justifications[test.id] = _template_justification(
                test, impact.changed_symbols, graph,
            )

    return justifications