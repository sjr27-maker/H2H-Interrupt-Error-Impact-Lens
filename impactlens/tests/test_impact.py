"""Tests for the impact analyzer."""
from __future__ import annotations

import pytest

from impactlens.analysis.impact import compute_impact, _find_changed_symbols
from impactlens.core.models import (
    CallEdge,
    ChangedRegion,
    ChangeType,
    Language,
    LineRange,
    SourceSymbol,
    SymbolKind,
)
from impactlens.graph.call_graph import CallGraph


def _sym(name: str, qname: str, kind: str, file: str, start: int, end: int) -> SourceSymbol:
    """Helper to create a SourceSymbol quickly."""
    return SourceSymbol(
        id=f"java:{qname}",
        name=name,
        qualified_name=qname,
        kind=SymbolKind(kind),
        file_path=file,
        start_line=start,
        end_line=end,
        language=Language.JAVA,
    )


def _edge(caller_qname: str, callee_qname: str, line: int = 1) -> CallEdge:
    return CallEdge(
        caller=f"java:{caller_qname}",
        callee=f"java:{callee_qname}",
        call_site_line=line,
    )


@pytest.fixture
def sample_graph() -> CallGraph:
    """
    Build a graph matching the sample project structure:

    CheckoutHandler.checkout
        ├──▶ OrderService.getOrderTotal
        │       ├──▶ DiscountCalculator.calculateDiscount
        │       └──▶ TaxCalculator.calculateTax
        └──▶ PriceFormatter.format
    """
    g = CallGraph()

    # Symbols
    symbols = [
        _sym("PriceFormatter", "util.PriceFormatter", "class", "util/PriceFormatter.java", 1, 10),
        _sym("format", "util.PriceFormatter.format", "method", "util/PriceFormatter.java", 3, 5),
        _sym("formatWithCurrency", "util.PriceFormatter.formatWithCurrency", "method", "util/PriceFormatter.java", 7, 9),
        _sym("DiscountCalculator", "pricing.DiscountCalculator", "class", "pricing/DiscountCalculator.java", 1, 10),
        _sym("calculateDiscount", "pricing.DiscountCalculator.calculateDiscount", "method", "pricing/DiscountCalculator.java", 3, 8),
        _sym("TaxCalculator", "pricing.TaxCalculator", "class", "pricing/TaxCalculator.java", 1, 10),
        _sym("calculateTax", "pricing.TaxCalculator.calculateTax", "method", "pricing/TaxCalculator.java", 4, 6),
        _sym("OrderService", "service.OrderService", "class", "service/OrderService.java", 1, 20),
        _sym("getOrderTotal", "service.OrderService.getOrderTotal", "method", "service/OrderService.java", 10, 18),
        _sym("CheckoutHandler", "api.CheckoutHandler", "class", "api/CheckoutHandler.java", 1, 25),
        _sym("checkout", "api.CheckoutHandler.checkout", "method", "api/CheckoutHandler.java", 12, 16),
    ]
    g.add_symbols(symbols)

    # Edges: caller → callee
    edges = [
        _edge("api.CheckoutHandler.checkout", "service.OrderService.getOrderTotal", 13),
        _edge("api.CheckoutHandler.checkout", "util.PriceFormatter.format", 14),
        _edge("service.OrderService.getOrderTotal", "pricing.DiscountCalculator.calculateDiscount", 12),
        _edge("service.OrderService.getOrderTotal", "pricing.TaxCalculator.calculateTax", 14),
    ]
    g.add_calls(edges)

    return g


@pytest.fixture
def mock_adapter():
    """A minimal adapter that just does range overlap (the default ABC behavior)."""
    from impactlens.core.adapter import LanguageAdapter
    from impactlens.core.models import Language, TestCase

    class MockAdapter(LanguageAdapter):
        @property
        def language(self): return Language.JAVA
        @property
        def source_extensions(self): return (".java",)
        @property
        def test_file_patterns(self): return ()
        def parse_file(self, f, r): return []
        def extract_calls(self, f, r, k): return []
        def extract_tests(self, f, r): return []

    return MockAdapter()


class TestComputeImpact:
    def test_leaf_change_impacts_direct_caller(self, sample_graph, mock_adapter):
        """Changing PriceFormatter.format should impact CheckoutHandler.checkout."""
        regions = [ChangedRegion(
            file_path="util/PriceFormatter.java",
            change_type=ChangeType.MODIFIED,
            old_range=LineRange(start=3, end=5),
            new_range=LineRange(start=3, end=7),
        )]

        result = compute_impact(sample_graph, regions, mock_adapter)

        assert "java:util.PriceFormatter.format" in result.changed_symbols
        assert "java:api.CheckoutHandler.checkout" in result.impacted_symbols
        # OrderService should NOT be impacted (PriceFormatter is not called by it)
        assert "java:service.OrderService.getOrderTotal" not in result.impacted_symbols

    def test_mid_level_change_ripples_transitively(self, sample_graph, mock_adapter):
        """Changing DiscountCalculator.calculateDiscount should impact OrderService and CheckoutHandler."""
        regions = [ChangedRegion(
            file_path="pricing/DiscountCalculator.java",
            change_type=ChangeType.MODIFIED,
            old_range=LineRange(start=3, end=6),
            new_range=LineRange(start=3, end=8),
        )]

        result = compute_impact(sample_graph, regions, mock_adapter)

        assert "java:pricing.DiscountCalculator.calculateDiscount" in result.changed_symbols
        assert "java:service.OrderService.getOrderTotal" in result.impacted_symbols
        assert "java:api.CheckoutHandler.checkout" in result.impacted_symbols

    def test_new_file_has_minimal_blast_radius(self, sample_graph, mock_adapter):
        """A newly added file with no callers should have blast radius = just itself."""
        # Add a new symbol that nobody calls
        new_sym = _sym("CurrencyConverter", "util.CurrencyConverter", "class",
                       "util/CurrencyConverter.java", 1, 20)
        sample_graph.add_symbol(new_sym)

        regions = [ChangedRegion(
            file_path="util/CurrencyConverter.java",
            change_type=ChangeType.ADDED,
            new_range=LineRange(start=1, end=20),
        )]

        result = compute_impact(sample_graph, regions, mock_adapter)

        assert "java:util.CurrencyConverter" in result.impacted_symbols
        # Should NOT ripple to anything else
        assert "java:api.CheckoutHandler.checkout" not in result.impacted_symbols

    def test_deleted_file_impacts_all_importers(self, sample_graph, mock_adapter):
        """Deleting a file should mark all its symbols as changed → ancestors impacted."""
        regions = [ChangedRegion(
            file_path="pricing/TaxCalculator.java",
            change_type=ChangeType.DELETED,
            old_range=LineRange(start=1, end=10),
        )]

        result = compute_impact(sample_graph, regions, mock_adapter)

        # TaxCalculator itself is changed
        assert "java:pricing.TaxCalculator.calculateTax" in result.impacted_symbols
        # OrderService calls TaxCalculator → impacted
        assert "java:service.OrderService.getOrderTotal" in result.impacted_symbols
        # CheckoutHandler calls OrderService → impacted transitively
        assert "java:api.CheckoutHandler.checkout" in result.impacted_symbols

    def test_no_overlapping_symbols_returns_empty(self, sample_graph, mock_adapter):
        """Changes outside any symbol body should return empty impact."""
        regions = [ChangedRegion(
            file_path="util/PriceFormatter.java",
            change_type=ChangeType.MODIFIED,
            # Line 11 is beyond any symbol in this file (symbols end at line 10)
            old_range=LineRange(start=11, end=12),
            new_range=LineRange(start=11, end=12),
        )]

        result = compute_impact(sample_graph, regions, mock_adapter)

        assert result.changed_symbols == []

    def test_multiple_changes_union_blast_radius(self, sample_graph, mock_adapter):
        """Two changes in different files should union their blast radii."""
        regions = [
            ChangedRegion(
                file_path="util/PriceFormatter.java",
                change_type=ChangeType.MODIFIED,
                old_range=LineRange(start=3, end=5),
                new_range=LineRange(start=3, end=5),
            ),
            ChangedRegion(
                file_path="pricing/TaxCalculator.java",
                change_type=ChangeType.MODIFIED,
                old_range=LineRange(start=4, end=6),
                new_range=LineRange(start=4, end=6),
            ),
        ]

        result = compute_impact(sample_graph, regions, mock_adapter)

        # Both PriceFormatter.format and TaxCalculator.calculateTax are changed
        assert "java:util.PriceFormatter.format" in result.changed_symbols
        assert "java:pricing.TaxCalculator.calculateTax" in result.changed_symbols
        # CheckoutHandler is in both blast radii
        assert "java:api.CheckoutHandler.checkout" in result.impacted_symbols

    def test_impacted_files_are_correct(self, sample_graph, mock_adapter):
        """impacted_files should list all files containing impacted symbols."""
        regions = [ChangedRegion(
            file_path="pricing/DiscountCalculator.java",
            change_type=ChangeType.MODIFIED,
            old_range=LineRange(start=3, end=6),
            new_range=LineRange(start=3, end=8),
        )]

        result = compute_impact(sample_graph, regions, mock_adapter)

        assert "pricing/DiscountCalculator.java" in result.impacted_files
        assert "service/OrderService.java" in result.impacted_files
        assert "api/CheckoutHandler.java" in result.impacted_files
        # PriceFormatter and TaxCalculator should NOT be in impacted files
        assert "util/PriceFormatter.java" not in result.impacted_files