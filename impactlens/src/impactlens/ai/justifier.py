"""
Test justification generator.

For each selected test, produces a human-readable explanation of WHY
it was selected. Uses the call graph to build the dependency chain,
then optionally asks the LLM to phrase it naturally.

Works without an LLM — falls back to detailed template-based justifications
built from the call graph structure.
"""
from __future__ import annotations

import logging
from pathlib import PurePosixPath

from impactlens.ai.llm_client import get_llm_client
from impactlens.core.models import ImpactResult, SourceSymbol, TestCase
from impactlens.graph.call_graph import CallGraph

log = logging.getLogger(__name__)

# Only justify the top N tests via LLM to control cost and latency
LLM_BATCH_SIZE = 15


def _find_connection_chain(
    graph: CallGraph,
    changed_symbols: list[str],
    test: TestCase,
) -> tuple[list[str], str | None]:
    """
    Find how a test connects to the changed symbols through the call graph.

    Returns:
        (chain_of_names, changed_symbol_name) — the path from changed → test,
        and the name of the changed symbol that connects.
    """
    changed_set = set(changed_symbols)

    for covered_id in test.covered_symbols:
        # Direct: test covers a changed symbol
        for cid in changed_symbols:
            if covered_id == cid or cid.startswith(covered_id + ".") or covered_id.startswith(cid + "."):
                sym = graph.get_symbol(cid)
                return ([sym.name if sym else cid.split(".")[-1]], sym.name if sym else None)

        # Transitive: walk callers from changed symbols to find covered_id
        for cid in changed_symbols:
            ancestors = graph.ancestors_of(cid)
            if covered_id in ancestors:
                # Build the chain
                chain = []
                changed_sym = graph.get_symbol(cid)
                chain.append(changed_sym.name if changed_sym else cid.split(".")[-1])

                # Walk up from changed symbol toward covered_id
                current = cid
                visited = {current}
                max_depth = 5
                depth = 0

                while current != covered_id and depth < max_depth:
                    callers = graph.direct_callers(current)
                    next_hop = None
                    for caller in callers:
                        if caller == covered_id:
                            next_hop = caller
                            break
                        if caller not in visited and caller in ancestors:
                            next_hop = caller
                            break
                    if next_hop is None:
                        for caller in callers:
                            if caller not in visited:
                                next_hop = caller
                                break

                    if next_hop is None:
                        break

                    visited.add(next_hop)
                    sym = graph.get_symbol(next_hop)
                    chain.append(sym.name if sym else next_hop.split(".")[-1])
                    current = next_hop
                    depth += 1

                return (chain, changed_sym.name if changed_sym else None)

    return ([], None)


def _template_justification(
    test: TestCase,
    changed_symbols: list[str],
    graph: CallGraph,
) -> str:
    """Generate a detailed justification using templates (no LLM needed)."""
    test_class = PurePosixPath(test.file_path).stem
    chain, changed_name = _find_connection_chain(graph, changed_symbols, test)

    if chain and len(chain) >= 3:
        chain_str = " → ".join(chain)
        return (
            f"The modification to {chain[0]} propagates through the call chain "
            f"{chain_str}. This test exercises {chain[-1]}, which is transitively "
            f"affected by the change. Running this test ensures the ripple effect "
            f"of the modification has not introduced regressions in downstream behavior."
        )
    elif chain and len(chain) == 2:
        return (
            f"The change to {chain[0]} directly affects {chain[1]}, which this test "
            f"exercises. Since {chain[1]} calls {chain[0]}, any behavioral change in "
            f"{chain[0]} could alter {chain[1]}'s output. This test validates that "
            f"the integration between these two components still works correctly."
        )
    elif chain and len(chain) == 1:
        return (
            f"This test directly exercises {chain[0]}, which was modified in this "
            f"change. The test validates the core behavior of {chain[0]} and must "
            f"run to confirm the modification works as intended without breaking "
            f"existing functionality."
        )

    # Convention-based match
    for cid in changed_symbols:
        changed_sym = graph.get_symbol(cid)
        if changed_sym:
            source_stem = PurePosixPath(changed_sym.file_path).stem
            if source_stem in test_class:
                return (
                    f"This test class ({test_class}) corresponds to the modified source "
                    f"file {source_stem}.java by naming convention. Changes to "
                    f"{changed_sym.name} in {source_stem} could affect any behavior "
                    f"validated by this test. Running it ensures the modification "
                    f"does not break the contract that {test_class} verifies."
                )

    # Import-based match — provide specifics about what was imported
    imported_classes = []
    for covered_id in test.covered_symbols:
        for cid in changed_symbols:
            if cid.startswith(covered_id) or covered_id.startswith(cid):
                sym = graph.get_symbol(cid)
                if sym:
                    imported_classes.append(sym.name)

    if imported_classes:
        names = ", ".join(set(imported_classes))
        return (
            f"This test imports {names}, which is in the blast radius of the current "
            f"change. The import relationship means this test depends on the behavior "
            f"of the modified code, either directly or through transitive calls. "
            f"Running it validates that the dependency chain remains correct."
        )

    # Final fallback — still give useful context
    changed_names = []
    for cid in changed_symbols[:3]:
        sym = graph.get_symbol(cid)
        if sym:
            changed_names.append(sym.name)

    if changed_names:
        return (
            f"This test is in the impact zone of changes to {', '.join(changed_names)}. "
            f"While the exact call chain could not be statically resolved, the test's "
            f"imports overlap with the affected code region. Running it provides "
            f"additional safety against regressions from the modification."
        )

    return (
        "This test was selected based on its relationship to the changed code. "
        "The analysis indicates a potential dependency that warrants verification."
    )


def _llm_justifications_batched(
    tests: list[TestCase],
    changed_symbols: list[str],
    graph: CallGraph,
) -> dict[str, str]:
    """
    Use the LLM to generate justifications in small batches.
    Only processes the top LLM_BATCH_SIZE tests to control cost.
    """
    client = get_llm_client()
    if not client.is_available():
        return {}

    # Only justify top N tests via LLM
    batch = tests[:LLM_BATCH_SIZE]

    # Build context
    changes_desc = []
    for sym_id in changed_symbols[:10]:  # Limit to avoid huge prompts
        sym = graph.get_symbol(sym_id)
        if sym:
            changes_desc.append(
                f"- {sym.qualified_name} ({sym.kind.value}) in {sym.file_path} "
                f"[lines {sym.start_line}-{sym.end_line}]"
            )

    # Build edges description
    edges_desc = []
    for sym_id in changed_symbols[:10]:
        callers = graph.direct_callers(sym_id)
        sym = graph.get_symbol(sym_id)
        sym_name = sym.name if sym else sym_id
        for caller_id in list(callers)[:5]:
            caller_sym = graph.get_symbol(caller_id)
            caller_name = caller_sym.name if caller_sym else caller_id
            edges_desc.append(f"- {caller_name} calls {sym_name}")

    tests_desc = []
    for t in batch:
        test_class = PurePosixPath(t.file_path).stem
        tests_desc.append(f"- {t.id} (in {test_class})")

    prompt = f"""You are analyzing the impact of a code change in a Java codebase. Your job is to explain WHY each test needs to run.

CHANGED CODE:
{chr(10).join(changes_desc) if changes_desc else "Multiple symbols were modified."}

DEPENDENCY EDGES (caller → callee):
{chr(10).join(edges_desc) if edges_desc else "No direct call edges resolved."}

TESTS TO JUSTIFY:
{chr(10).join(tests_desc)}

For each test, write a 2-4 sentence justification that explains:
1. What changed and how it connects to this test
2. The dependency chain (which function calls which)
3. What could break if this test is skipped
4. Why this specific test is necessary

Respond ONLY with a JSON object. Keys are test IDs, values are justification strings.
No markdown fences, no extra text. Just the JSON object."""

    system = (
        "You are a senior software engineer explaining test impact analysis. "
        "Write clear, specific justifications that reference actual class and method names. "
        "Each justification should be 2-4 sentences. Respond only with valid JSON."
    )

    data = client.complete_json(prompt, system=system, max_tokens=3000)

    if isinstance(data, dict):
        log.info("LLM generated %d justifications (batch of %d)", len(data), len(batch))
        return {k: str(v) for k, v in data.items()}

    log.warning("LLM batch justification failed or returned invalid JSON")
    return {}


def generate_justifications(
    impact: ImpactResult,
    graph: CallGraph,
) -> dict[str, str]:
    """
    Generate justifications for all selected tests.

    Strategy:
    1. Try LLM for the top N tests (richer, more natural)
    2. Use detailed templates for the rest (or all, if LLM unavailable)

    Returns:
        dict mapping test_id → justification string
    """
    if not impact.selected_tests:
        return {}

    justifications: dict[str, str] = {}

    # Step 1: Try LLM for top batch
    llm_results = _llm_justifications_batched(
        impact.selected_tests,
        impact.changed_symbols,
        graph,
    )
    justifications.update(llm_results)

    # Step 2: Fill gaps with detailed templates
    for test in impact.selected_tests:
        if test.id not in justifications:
            justifications[test.id] = _template_justification(
                test, impact.changed_symbols, graph,
            )

    return justifications