"""
Test mapper — maps impacted source symbols to relevant test cases.

Uses a layered strategy:
  Layer 1: Convention-based (FooClass → FooClassTest)
  Layer 2: Import-based (test imports impacted class)
  Layer 3: LLM-assisted (Day 4 — for ambiguous cases)

Each layer adds to the selected set. No layer removes selections from
a previous layer — they're additive.
"""
from __future__ import annotations

import logging
from pathlib import PurePosixPath

from impactlens.core.models import ImpactResult, TestCase

log = logging.getLogger(__name__)


def _convention_match(
    impacted_files: list[str],
    all_tests: list[TestCase],
) -> set[str]:
    """
    Layer 1: Convention-based mapping.

    Maps source files to test files by naming convention:
      src/main/java/.../FooClass.java → src/test/java/.../FooClassTest.java
      src/main/java/.../FooClass.java → src/test/java/.../TestFooClass.java
      src/main/java/.../FooClass.java → src/test/java/.../FooClassTests.java

    Returns set of matched test IDs.
    """
    selected: set[str] = set()

    # Build a set of impacted class names (without path and extension)
    impacted_class_names: set[str] = set()
    for fp in impacted_files:
        name = PurePosixPath(fp).stem  # e.g., "OrderService"
        impacted_class_names.add(name)

    for test in all_tests:
        test_stem = PurePosixPath(test.file_path).stem  # e.g., "OrderServiceTest"

        for class_name in impacted_class_names:
            # Check standard conventions
            if (
                test_stem == f"{class_name}Test"
                or test_stem == f"Test{class_name}"
                or test_stem == f"{class_name}Tests"
            ):
                selected.add(test.id)
                log.debug("  CONVENTION: %s matched via %s", test.id, class_name)
                break

    return selected


def _import_match(
    impacted_symbols: list[str],
    all_tests: list[TestCase],
) -> set[str]:
    """
    Layer 2: Import-based mapping.

    Each TestCase has a `covered_symbols` list populated during extract_tests.
    These are the SymbolIds of classes imported by the test file.
    If any imported class is in the impacted set, the test is relevant.

    Returns set of matched test IDs.
    """
    selected: set[str] = set()
    impacted_set = set(impacted_symbols)

    for test in all_tests:
        for covered_id in test.covered_symbols:
            if covered_id in impacted_set:
                selected.add(test.id)
                log.debug("  IMPORT: %s covers impacted symbol %s", test.id, covered_id)
                break

        # Also check if any impacted symbol's qualified_name is a prefix of a
        # covered symbol (handles class-level imports covering all methods)
        if test.id not in selected:
            for covered_id in test.covered_symbols:
                # covered_id is like "java:com.example.OrderService"
                # impacted might be "java:com.example.OrderService.getOrderTotal"
                for imp_id in impacted_set:
                    if imp_id.startswith(covered_id + ".") or covered_id.startswith(imp_id + "."):
                        selected.add(test.id)
                        log.debug("  IMPORT (prefix): %s covers %s via %s", test.id, imp_id, covered_id)
                        break
                if test.id in selected:
                    break

    return selected


def map_tests(
    impact: ImpactResult,
    all_tests: list[TestCase],
) -> list[TestCase]:
    """
    Select tests that cover the impacted symbols.

    Applies layers in order. Each layer adds to the selection set.
    Returns the list of selected TestCase objects with deduplication.

    Args:
        impact: The ImpactResult from the impact analyzer.
        all_tests: All test cases discovered in the repository.

    Returns:
        List of TestCase objects to run.
    """
    if not all_tests:
        log.warning("No test cases available to map.")
        return []

    if not impact.impacted_symbols and not impact.impacted_files:
        log.warning("No impacted symbols or files — no tests to select.")
        return []

    log.info("Mapping %d impacted symbols to %d available tests",
             len(impact.impacted_symbols), len(all_tests))

    selected_ids: set[str] = set()

    # Layer 1: Convention
    convention_hits = _convention_match(impact.impacted_files, all_tests)
    selected_ids.update(convention_hits)
    log.info("  Layer 1 (convention): %d tests matched", len(convention_hits))

    # Layer 2: Import
    import_hits = _import_match(impact.impacted_symbols, all_tests)
    new_from_import = import_hits - selected_ids
    selected_ids.update(import_hits)
    log.info("  Layer 2 (import): %d tests matched (%d new)", len(import_hits), len(new_from_import))

    # Layer 3: LLM (Day 4 — placeholder)
    # llm_hits = _llm_match(impact, all_tests, unselected)
    # selected_ids.update(llm_hits)

    # Build final list preserving original order
    selected: list[TestCase] = [t for t in all_tests if t.id in selected_ids]

    log.info("Total selected: %d of %d tests (%.0f%% reduction)",
             len(selected), len(all_tests),
             (1 - len(selected) / len(all_tests)) * 100 if all_tests else 0)

    return selected