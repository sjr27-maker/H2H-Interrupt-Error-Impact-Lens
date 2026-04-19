"""Day 2 integration test — diff + parse + graph working together."""
from __future__ import annotations

from pathlib import Path

import pytest

from impactlens.adapters.java.adapter import JavaAdapter
from impactlens.core.diff import extract_changed_regions
from impactlens.core.models import ChangeType
from impactlens.graph.call_graph import CallGraph


@pytest.fixture
def sample_root() -> Path:
    root = Path("sample_repos/java_demo")
    if not root.exists():
        pytest.skip("Sample repo not found")
    # Check it has git history
    if not (root / ".git").exists():
        pytest.skip("Sample repo has no git history — run scripts/setup_sample_repo.sh")
    return root


@pytest.fixture
def adapter() -> JavaAdapter:
    a = JavaAdapter()
    a.clear_cache()
    return a


class TestDay2Integration:
    def test_diff_finds_changes(self, sample_root: Path):
        """Diff between commits 1 and 2 should find PriceFormatter change."""
        regions = extract_changed_regions(sample_root, "HEAD~4", "HEAD~3")
        files = {r.file_path for r in regions}
        # Should find PriceFormatter.java modified
        pf_regions = [r for r in regions if "PriceFormatter" in r.file_path]
        assert len(pf_regions) >= 1
        assert pf_regions[0].change_type == ChangeType.MODIFIED

    def test_parse_all_source_files(self, adapter: JavaAdapter, sample_root: Path):
        """All source files should parse without errors."""
        files = adapter.discover_source_files(sample_root)
        total_symbols = 0
        for f in files:
            symbols = adapter.parse_file(f, sample_root)
            assert len(symbols) >= 1, f"No symbols extracted from {f.name}"
            total_symbols += len(symbols)
        assert total_symbols >= 10

    def test_call_graph_has_expected_structure(self, adapter: JavaAdapter, sample_root: Path):
        """The call graph should contain edges from caller to callee."""
        files = adapter.discover_source_files(sample_root)

        all_symbols = []
        for f in files:
            all_symbols.extend(adapter.parse_file(f, sample_root))

        known = {s.id: s for s in all_symbols}
        graph = CallGraph()
        graph.add_symbols(all_symbols)

        for f in files:
            edges = adapter.extract_calls(f, sample_root, known)
            graph.add_calls(edges)

        # Graph should be non-trivial
        assert graph.node_count >= 10
        assert graph.edge_count >= 1

        # Print summary for manual inspection
        print(f"\nGraph summary: {graph.summary()}")
        print(f"All nodes: {sorted(n for n in graph.graph.nodes)}")
        print(f"All edges: {sorted((u, v) for u, v in graph.graph.edges)}")

    def test_changed_symbols_can_be_attributed(self, adapter: JavaAdapter, sample_root: Path):
        """Changed line ranges should map to specific symbols."""
        regions = extract_changed_regions(sample_root, "HEAD~4", "HEAD~3")

        # Parse PriceFormatter to get its symbols
        pf_path = sample_root / "src/main/java/com/impactlens/demo/util/PriceFormatter.java"
        if not pf_path.exists():
            pytest.skip("PriceFormatter not found")

        symbols = adapter.parse_file(pf_path, sample_root)
        pf_regions = [r for r in regions if "PriceFormatter" in r.file_path]

        # Map changes to symbols
        affected = adapter.symbols_in_range(symbols, pf_regions)
        assert len(affected) >= 1
        affected_names = {s.name for s in affected}
        # The format() method was changed — it should be in the affected set
        # (or the class itself if the range spans the class)
        assert len(affected_names) >= 1
        print(f"\nAffected symbols: {affected_names}")