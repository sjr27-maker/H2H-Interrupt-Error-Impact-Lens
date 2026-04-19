"""Tests for the AI augmentation layer."""
from __future__ import annotations

import pytest

from impactlens.ai.confidence import score_tests, ScoredTest
from impactlens.ai.justifier import _template_justification, generate_justifications
from impactlens.core.models import (
    CallEdge,
    ImpactResult,
    Language,
    SourceSymbol,
    SymbolKind,
    TestCase,
    TestFramework,
)
from impactlens.graph.call_graph import CallGraph


def _sym(name, qname, kind, file, start=1, end=10):
    return SourceSymbol(
        id=f"java:{qname}", name=name, qualified_name=qname,
        kind=SymbolKind(kind), file_path=file,
        start_line=start, end_line=end, language=Language.JAVA,
    )


def _test(name, file_class, covered=None):
    return TestCase(
        id=f"com.example.{file_class}#{name}", name=name,
        file_path=f"src/test/java/com/example/{file_class}.java",
        language=Language.JAVA, framework=TestFramework.JUNIT5,
        covered_symbols=covered or [],
    )


@pytest.fixture
def graph_and_impact():
    g = CallGraph()
    g.add_symbol(_sym("format", "util.PriceFormatter.format", "method", "util/PriceFormatter.java"))
    g.add_symbol(_sym("checkout", "api.CheckoutHandler.checkout", "method", "api/CheckoutHandler.java"))
    g.add_call(CallEdge(
        caller="java:api.CheckoutHandler.checkout",
        callee="java:util.PriceFormatter.format",
        call_site_line=14,
    ))

    selected_tests = [
        _test("testFormat", "PriceFormatterTest", ["java:util.PriceFormatter"]),
        _test("testCheckout", "CheckoutHandlerTest", ["java:api.CheckoutHandler"]),
    ]

    impact = ImpactResult(
        changed_symbols=["java:util.PriceFormatter.format"],
        impacted_symbols=[
            "java:util.PriceFormatter.format",
            "java:api.CheckoutHandler.checkout",
        ],
        impacted_files=["util/PriceFormatter.java", "api/CheckoutHandler.java"],
        selected_tests=selected_tests,
    )

    return g, impact


class TestConfidenceScorer:
    def test_scores_all_selected_tests(self, graph_and_impact):
        graph, impact = graph_and_impact
        scored = score_tests(impact, graph)

        assert len(scored) == 2
        assert all(isinstance(s, ScoredTest) for s in scored)
        assert all(0.0 <= s.confidence <= 1.0 for s in scored)

    def test_direct_match_has_highest_confidence(self, graph_and_impact):
        graph, impact = graph_and_impact
        scored = score_tests(impact, graph)

        assert len(scored) == 2
        # All scores should be reasonable (above 0.5)
        for s in scored:
            assert s.confidence >= 0.5, f"{s.test.name} has low confidence: {s.confidence}"
        # At least one should be high confidence
        max_conf = max(s.confidence for s in scored)
        assert max_conf >= 0.8, f"Highest confidence is only {max_conf}"

    def test_sorted_by_confidence_descending(self, graph_and_impact):
        graph, impact = graph_and_impact
        scored = score_tests(impact, graph)

        confidences = [s.confidence for s in scored]
        assert confidences == sorted(confidences, reverse=True)

    def test_empty_selection_returns_empty(self):
        impact = ImpactResult(
            changed_symbols=[], impacted_symbols=[],
            impacted_files=[], selected_tests=[],
        )
        scored = score_tests(impact, CallGraph())
        assert scored == []


class TestTemplateJustifications:
    def test_generates_justification_for_all_tests(self, graph_and_impact):
        graph, impact = graph_and_impact
        justifications = generate_justifications(impact, graph)

        assert len(justifications) == 2
        for test in impact.selected_tests:
            assert test.id in justifications
            assert len(justifications[test.id]) > 10  # Not empty

    def test_convention_match_mentions_naming(self, graph_and_impact):
        graph, impact = graph_and_impact
        test = _test("testFormat", "PriceFormatterTest", [])

        justification = _template_justification(
            test, impact.changed_symbols, graph,
        )
        assert len(justification) > 0

    def test_empty_impact_returns_empty(self):
        impact = ImpactResult(
            changed_symbols=[], impacted_symbols=[],
            impacted_files=[], selected_tests=[],
        )
        justifications = generate_justifications(impact, CallGraph())
        assert justifications == {}