"""End-to-end pipeline integration test against the sample Java repo."""
from __future__ import annotations

from pathlib import Path

import pytest

from impactlens.core.pipeline import run_analysis
from impactlens.core.registry import register_all_adapters


@pytest.fixture(autouse=True)
def _register():
    register_all_adapters()


@pytest.fixture
def sample_root() -> Path:
    root = Path("sample_repos/java_demo")
    if not root.exists():
        pytest.skip("Sample repo not found")
    if not (root / ".git").exists():
        pytest.skip("Run scripts/setup_sample_repo.sh first")
    return root


class TestPipelineEndToEnd:
    def test_leaf_change_selects_correct_tests(self, sample_root):
        """
        PriceFormatter change (HEAD~4..HEAD~3):
        Expected blast radius: PriceFormatter → CheckoutHandler
        Expected tests: PriceFormatterTest, CheckoutHandlerTest
        """
        result = run_analysis(sample_root, "HEAD~4", "HEAD~3")

        impact = result.analysis.impact
        selected_files = {t.file_path for t in impact.selected_tests}

        # Must select PriceFormatterTest methods
        assert any("PriceFormatter" in f for f in selected_files), \
            f"PriceFormatterTest not selected. Selected: {selected_files}"

        # Must select CheckoutHandlerTest (transitive caller)
        assert any("CheckoutHandler" in f for f in selected_files), \
            f"CheckoutHandlerTest not selected. Selected: {selected_files}"

        # Must NOT select TaxCalculatorTest (not in blast radius)
        assert not any("TaxCalculator" in f for f in selected_files), \
            f"TaxCalculatorTest incorrectly selected. Selected: {selected_files}"

        # Reduction should be > 0
        assert len(impact.selected_tests) < result.analysis.total_tests

    def test_mid_level_change_ripples_correctly(self, sample_root):
        """
        DiscountCalculator change (HEAD~3..HEAD~2):
        Expected: DiscountCalculator → OrderService → CheckoutHandler
        """
        result = run_analysis(sample_root, "HEAD~3", "HEAD~2")

        impact = result.analysis.impact
        selected_files = {t.file_path for t in impact.selected_tests}

        assert any("DiscountCalculator" in f for f in selected_files), \
            f"DiscountCalculatorTest not selected. Selected: {selected_files}"
        assert any("OrderService" in f for f in selected_files), \
            f"OrderServiceTest not selected. Selected: {selected_files}"
        assert any("CheckoutHandler" in f for f in selected_files), \
            f"CheckoutHandlerTest not selected. Selected: {selected_files}"

    def test_new_file_addition(self, sample_root):
        """
        CurrencyConverter added (HEAD~2..HEAD~1):
        Should have minimal blast radius initially.
        """
        result = run_analysis(sample_root, "HEAD~2", "HEAD~1")

        impact = result.analysis.impact

        # CurrencyConverter files should be in impacted
        assert any("CurrencyConverter" in f for f in impact.impacted_files), \
            f"CurrencyConverter not in impacted files. Got: {impact.impacted_files}"

        # Timings should be populated
        assert result.timings.total_ms > 0

    def test_pipeline_produces_valid_analysis_run(self, sample_root):
        """The AnalysisRun should have all fields populated."""
        result = run_analysis(sample_root, "HEAD~4", "HEAD~3")

        assert result.analysis.repo_path == str(sample_root)
        assert result.analysis.total_symbols > 0
        assert result.analysis.total_tests > 0
        assert len(result.analysis.changed_regions) > 0
        assert result.graph.node_count > 0
        assert result.graph.edge_count > 0

    def test_json_output_is_serializable(self, sample_root):
        """Results should be JSON-serializable."""
        import json

        result = run_analysis(sample_root, "HEAD~4", "HEAD~3")

        output = {
            "changed_symbols": result.analysis.impact.changed_symbols,
            "impacted_symbols": result.analysis.impact.impacted_symbols,
            "selected_tests": [t.model_dump(mode="json") for t in result.analysis.impact.selected_tests],
            "timings": result.timings.summary(),
        }

        serialized = json.dumps(output, indent=2)
        assert len(serialized) > 100

    def test_same_commit_returns_no_impact(self, sample_root):
        """Diffing a commit against itself should yield zero impact."""
        result = run_analysis(sample_root, "HEAD", "HEAD")

        assert len(result.analysis.impact.changed_symbols) == 0
        assert len(result.analysis.impact.selected_tests) == 0