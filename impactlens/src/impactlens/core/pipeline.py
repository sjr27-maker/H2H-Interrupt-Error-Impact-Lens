"""
Pipeline orchestrator — the top-level entry point that runs the full
ImpactLens analysis: diff → parse → graph → impact → map → (optional) run.

This module knows nothing about Java, Python, or any specific language.
It operates entirely through the LanguageAdapter interface and the
language-agnostic core modules.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from impactlens.analysis.impact import compute_impact
from impactlens.core.adapter import LanguageAdapter
from impactlens.core.diff import extract_changed_regions
from impactlens.core.models import (
    AnalysisRun,
    CallEdge,
    ChangedRegion,
    ImpactResult,
    SourceSymbol,
    TestCase,
    TestResult,
)
from impactlens.core.registry import registry
from impactlens.graph.call_graph import CallGraph
from impactlens.mapping.test_mapper import map_tests

log = logging.getLogger(__name__)


@dataclass
class PipelineTimings:
    """Performance timings for each pipeline stage."""
    diff_ms: float = 0
    parse_ms: float = 0
    graph_ms: float = 0
    impact_ms: float = 0
    mapping_ms: float = 0
    test_run_ms: float = 0
    total_ms: float = 0

    def summary(self) -> dict[str, str]:
        return {
            "diff": f"{self.diff_ms:.0f}ms",
            "parse": f"{self.parse_ms:.0f}ms",
            "graph": f"{self.graph_ms:.0f}ms",
            "impact": f"{self.impact_ms:.0f}ms",
            "mapping": f"{self.mapping_ms:.0f}ms",
            "test_run": f"{self.test_run_ms:.0f}ms",
            "total": f"{self.total_ms:.0f}ms",
        }


@dataclass
class PipelineResult:
    """Complete output of a pipeline run."""
    analysis: AnalysisRun
    graph: CallGraph
    all_tests: list[TestCase]
    test_results: list[TestResult]
    timings: PipelineTimings
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_analysis(
    repo_path: Path,
    base: str,
    head: str,
    run_tests: bool = False,
) -> PipelineResult:
    """
    Run the full ImpactLens pipeline.

    Args:
        repo_path: Path to the target git repository.
        base: Base git ref.
        head: Head git ref.
        run_tests: If True, execute the selected tests via the appropriate runner.

    Returns:
        PipelineResult with analysis, graph, test results, and timings.
    """
    pipeline_start = time.time()
    timings = PipelineTimings()
    errors: list[str] = []
    warnings: list[str] = []

    # ── Step 1: Extract diff ──
    log.info("Step 1/5: Extracting diff...")
    t0 = time.time()
    regions = extract_changed_regions(repo_path, base, head)
    timings.diff_ms = (time.time() - t0) * 1000
    log.info("  Found %d changed regions across %d files",
             len(regions), len(set(r.file_path for r in regions)))

    if not regions:
        warnings.append("No changes detected between refs.")

    # ── Step 2: Find adapters and parse ──
    log.info("Step 2/5: Parsing codebase...")
    t0 = time.time()

    adapters = registry.all()
    if not adapters:
        errors.append("No language adapters registered.")
        raise RuntimeError("No language adapters registered. Check register_all_adapters().")

    all_symbols: list[SourceSymbol] = []
    all_tests: list[TestCase] = []
    parse_errors: list[str] = []

    # Determine which adapter handles this repo
    # For now, use all adapters and let each discover its own files
    active_adapter: LanguageAdapter | None = None

    for adapter in adapters:
        source_files = adapter.discover_source_files(repo_path)
        test_files = adapter.discover_test_files(repo_path)

        if not source_files:
            continue

        active_adapter = adapter
        log.info("  [%s] %d source files, %d test files",
                 adapter.language.value, len(source_files), len(test_files))

        # Parse all source files
        for sf in source_files:
            try:
                symbols = adapter.parse_file(sf, repo_path)
                all_symbols.extend(symbols)
            except Exception as e:
                msg = f"Parse error in {sf.name}: {e}"
                parse_errors.append(msg)
                log.warning("  ⚠ %s", msg)

        # Extract tests
        for tf in test_files:
            try:
                tests = adapter.extract_tests(tf, repo_path)
                all_tests.extend(tests)
            except Exception as e:
                msg = f"Test extraction error in {tf.name}: {e}"
                parse_errors.append(msg)
                log.warning("  ⚠ %s", msg)

    timings.parse_ms = (time.time() - t0) * 1000
    log.info("  Extracted %d symbols, %d tests", len(all_symbols), len(all_tests))

    if parse_errors:
        warnings.extend(parse_errors)

    if not active_adapter:
        errors.append("No adapter found source files in this repository.")
        # Return a minimal result
        return PipelineResult(
            analysis=AnalysisRun(
                repo_path=str(repo_path), base_commit=base, head_commit=head,
                changed_regions=regions,
                impact=ImpactResult(changed_symbols=[], impacted_symbols=[],
                                    impacted_files=[], selected_tests=[]),
                total_symbols=0, total_tests=0,
            ),
            graph=CallGraph(),
            all_tests=[],
            test_results=[],
            timings=timings,
            errors=errors,
            warnings=warnings,
        )

    # ── Step 3: Build call graph ──
    log.info("Step 3/5: Building call graph...")
    t0 = time.time()

    graph = CallGraph()
    graph.add_symbols(all_symbols)

    known = {s.id: s for s in all_symbols}
    all_edges: list[CallEdge] = []

    for adapter in adapters:
        source_files = adapter.discover_source_files(repo_path)
        for sf in source_files:
            try:
                edges = adapter.extract_calls(sf, repo_path, known)
                all_edges.extend(edges)
            except Exception as e:
                log.warning("  ⚠ Call extraction error in %s: %s", sf.name, e)

    graph.add_calls(all_edges)
    timings.graph_ms = (time.time() - t0) * 1000

    summary = graph.summary()
    log.info("  Graph: %d nodes, %d edges, %d files",
             summary["nodes"], summary["edges"], summary["files"])

    # ── Step 4: Compute impact ──
    log.info("Step 4/5: Computing impact...")
    t0 = time.time()

    impact = compute_impact(graph, regions, active_adapter)

    timings.impact_ms = (time.time() - t0) * 1000
    log.info("  Changed: %d symbols, Impacted: %d symbols, Files: %d",
             len(impact.changed_symbols), len(impact.impacted_symbols),
             len(impact.impacted_files))

    # ── Step 5: Map to tests ──
    log.info("Step 5/5: Mapping to tests...")
    t0 = time.time()

    selected_tests = map_tests(impact, all_tests)
    impact.selected_tests = selected_tests

    timings.mapping_ms = (time.time() - t0) * 1000
    log.info("  Selected %d of %d tests (%.0f%% reduction)",
             len(selected_tests), len(all_tests),
             (1 - len(selected_tests) / len(all_tests)) * 100 if all_tests else 0)

    # ── Optional: Run tests ──
    test_results: list[TestResult] = []
    if run_tests and selected_tests:
        log.info("Running selected tests...")
        t0 = time.time()

        try:
            from impactlens.runner.maven_runner import MavenSurefireRunner
            runner = MavenSurefireRunner()
            test_results = runner.run(selected_tests, repo_path)
            timings.test_run_ms = (time.time() - t0) * 1000
            passed = sum(1 for r in test_results if r.status.value == "passed")
            failed = sum(1 for r in test_results if r.status.value == "failed")
            log.info("  Results: %d passed, %d failed, %.1fs",
                     passed, failed, timings.test_run_ms / 1000)
        except Exception as e:
            msg = f"Test execution failed: {e}"
            errors.append(msg)
            log.error("  %s", msg)
            timings.test_run_ms = (time.time() - t0) * 1000

    # ── Build final result ──
    timings.total_ms = (time.time() - pipeline_start) * 1000

    analysis = AnalysisRun(
        repo_path=str(repo_path),
        base_commit=base,
        head_commit=head,
        changed_regions=regions,
        impact=impact,
        total_symbols=len(all_symbols),
        total_tests=len(all_tests),
    )

    return PipelineResult(
        analysis=analysis,
        graph=graph,
        all_tests=all_tests,
        test_results=test_results,
        timings=timings,
        errors=errors,
        warnings=warnings,
    )