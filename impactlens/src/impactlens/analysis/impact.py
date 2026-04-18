"""
Impact analyzer — computes the blast radius of a code change.

Given a CallGraph and a set of ChangedRegions, determines:
1. Which symbols were directly changed (changed lines overlap symbol ranges)
2. Which symbols are transitively impacted (reverse reachability on the call graph)
3. Which files contain impacted symbols

The output is an ImpactResult that the test mapper consumes.
"""
from __future__ import annotations

import logging
from pathlib import Path

from impactlens.core.adapter import LanguageAdapter
from impactlens.core.models import (
    ChangedRegion,
    ChangeType,
    ImpactResult,
    SourceSymbol,
)
from impactlens.graph.call_graph import CallGraph

log = logging.getLogger(__name__)


def _find_changed_symbols(
    graph: CallGraph,
    regions: list[ChangedRegion],
    adapter: LanguageAdapter,
) -> list[SourceSymbol]:
    """
    Map ChangedRegions to the SourceSymbols they overlap.

    For each changed file, find all symbols defined in that file (from the
    graph), then check which symbols' line ranges overlap the changed hunks.
    """
    changed: list[SourceSymbol] = []
    seen_ids: set[str] = set()

    # Group regions by file
    regions_by_file: dict[str, list[ChangedRegion]] = {}
    log.debug("Regions grouped by file: %s", list(regions_by_file.keys()))
    log.debug("Graph files: %s", sorted(set(s.file_path for s in graph._symbols.values())))
    for r in regions:
        normalized_path = r.file_path.replace("\\", "/")
        regions_by_file.setdefault(normalized_path, []).append(r)

    for file_path, file_regions in regions_by_file.items():
        # Get all symbols defined in this file from the graph
        file_symbols = graph.symbols_in_file(file_path)

        if not file_symbols:
            log.debug("No symbols found in graph for changed file: %s", file_path)
            continue

        # Check for whole-file changes (ADDED or DELETED)
        whole_file_change = any(
            r.change_type in (ChangeType.ADDED, ChangeType.DELETED)
            for r in file_regions
        )

        if whole_file_change:
            # All symbols in the file are changed
            for sym in file_symbols:
                if sym.id not in seen_ids:
                    changed.append(sym)
                    seen_ids.add(sym.id)
            continue

        # For MODIFIED files, use the adapter's range-overlap logic
        affected = adapter.symbols_in_range(file_symbols, file_regions)
        for sym in affected:
            if sym.id not in seen_ids:
                changed.append(sym)
                seen_ids.add(sym.id)

    return changed


def _expand_class_to_methods(
    changed_symbols: list[SourceSymbol],
    graph: CallGraph,
) -> list[SourceSymbol]:
    """
    If a class-level symbol is changed (e.g., field initializer, class
    signature), expand the change to include all methods of that class.

    Rationale: a change to a class's structure could affect any method's
    behavior (e.g., changing a field type, adding an interface).
    """
    expanded: list[SourceSymbol] = list(changed_symbols)
    seen_ids: set[str] = {s.id for s in expanded}

    for sym in changed_symbols:
        if sym.kind.value in ("class", "interface"):
            # Find all methods in the same file whose qualified_name starts
            # with this class's qualified_name (i.e., they belong to this class)
            file_symbols = graph.symbols_in_file(sym.file_path)
            for fs in file_symbols:
                if (
                    fs.id not in seen_ids
                    and fs.qualified_name.startswith(sym.qualified_name + ".")
                    and fs.kind.value in ("method", "constructor")
                ):
                    expanded.append(fs)
                    seen_ids.add(fs.id)

    return expanded


def compute_impact(
    graph: CallGraph,
    regions: list[ChangedRegion],
    adapter: LanguageAdapter,
) -> ImpactResult:
    """
    Compute the full blast radius of a set of code changes.

    Algorithm:
        1. Map changed line ranges → changed SourceSymbols
        2. If a class is changed, expand to all its methods
        3. For each changed symbol, find all transitive callers (ancestors)
        4. Union everything → impacted set
        5. Map impacted symbols → impacted files
        6. Return ImpactResult

    Args:
        graph: The fully-built CallGraph of the codebase.
        regions: Changed regions from the diff extractor.
        adapter: The language adapter (used for symbols_in_range).

    Returns:
        ImpactResult with changed symbols, impacted symbols, and impacted files.
    """
    # Step 1: Find directly changed symbols
    changed_symbols = _find_changed_symbols(graph, regions, adapter)
    log.info("Directly changed symbols: %d", len(changed_symbols))
    for sym in changed_symbols:
        log.debug("  CHANGED: %s (%s) at %s:%d-%d",
                  sym.name, sym.kind.value, sym.file_path, sym.start_line, sym.end_line)

    if not changed_symbols:
        log.warning("No symbols found overlapping the changed regions. "
                    "This may mean the changes are outside any function/class body "
                    "(e.g., comments, whitespace, or imports only).")
        # Still return a valid result — maybe only imports changed
        changed_files = sorted(set(r.file_path for r in regions))
        return ImpactResult(
            changed_symbols=[],
            impacted_symbols=[],
            impacted_files=changed_files,
            selected_tests=[],
            reasoning={"_note": "No symbols overlapped with changed lines. "
                       "Changes may be in comments, imports, or whitespace."},
        )

    # Step 2: Expand class-level changes to methods
    changed_symbols = _expand_class_to_methods(changed_symbols, graph)
    changed_ids = [s.id for s in changed_symbols]

    # Step 3: Compute transitive impact via reverse reachability
    impacted_ids: set[str] = set(changed_ids)

    for sym_id in changed_ids:
        ancestors = graph.ancestors_of(sym_id)
        if ancestors:
            log.debug("  %s has %d transitive callers", sym_id, len(ancestors))
        impacted_ids.update(ancestors)

    log.info("Total impacted symbols: %d (changed: %d, transitive: %d)",
             len(impacted_ids), len(changed_ids),
             len(impacted_ids) - len(changed_ids))

    # Step 4: Map to files
    impacted_files = sorted(graph.files_containing(impacted_ids))

    # Log the impact chain for debugging
    for sym_id in sorted(impacted_ids - set(changed_ids)):
        sym = graph.get_symbol(sym_id)
        if sym:
            log.debug("  IMPACTED (transitive): %s in %s", sym.name, sym.file_path)

    return ImpactResult(
        changed_symbols=sorted(changed_ids),
        impacted_symbols=sorted(impacted_ids),
        impacted_files=impacted_files,
        selected_tests=[],  # Test mapper fills this in next
        reasoning={},
    )