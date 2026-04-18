"""Tests for the test mapper."""
from __future__ import annotations

import pytest

from impactlens.core.models import (
    ImpactResult,
    Language,
    TestCase,
    TestFramework,
)
from impactlens.mapping.test_mapper import map_tests


def _test(name: str, file_class: str, covered: list[str] | None = None) -> TestCase:
    """Helper to build a TestCase quickly."""
    return TestCase(
        id=f"com.example.{file_class}#{name}",
        name=name,
        file_path=f"src/test/java/com/example/{file_class}.java",
        language=Language.JAVA,
        framework=TestFramework.JUNIT5,
        covered_symbols=covered or [],
    )


@pytest.fixture
def all_tests() -> list[TestCase]:
    return [
        _test("testFormat", "PriceFormatterTest", ["java:com.example.util.PriceFormatter"]),
        _test("testFormatCurrency", "PriceFormatterTest", ["java:com.example.util.PriceFormatter"]),
        _test("testPremium", "DiscountCalculatorTest", ["java:com.example.pricing.DiscountCalculator"]),
        _test("testStandard", "DiscountCalculatorTest", ["java:com.example.pricing.DiscountCalculator"]),
        _test("testNoDiscount", "DiscountCalculatorTest", ["java:com.example.pricing.DiscountCalculator"]),
        _test("testTax", "TaxCalculatorTest", ["java:com.example.pricing.TaxCalculator"]),
        _test("testOrderPremium", "OrderServiceTest", ["java:com.example.service.OrderService"]),
        _test("testOrderStandard", "OrderServiceTest", ["java:com.example.service.OrderService"]),
        _test("testCheckout", "CheckoutHandlerTest", ["java:com.example.api.CheckoutHandler"]),
    ]


class TestMapTests:
    def test_convention_matches_leaf_change(self, all_tests):
        """Changing PriceFormatter → PriceFormatterTest matched by convention."""
        impact = ImpactResult(
            changed_symbols=["java:com.example.util.PriceFormatter.format"],
            impacted_symbols=[
                "java:com.example.util.PriceFormatter.format",
                "java:com.example.api.CheckoutHandler.checkout",
            ],
            impacted_files=[
                "src/main/java/com/example/util/PriceFormatter.java",
                "src/main/java/com/example/api/CheckoutHandler.java",
            ],
            selected_tests=[],
        )

        selected = map_tests(impact, all_tests)
        selected_names = {t.name for t in selected}

        assert "testFormat" in selected_names
        assert "testFormatCurrency" in selected_names
        assert "testCheckout" in selected_names
        # Tests for DiscountCalculator and TaxCalculator should NOT be selected
        assert "testPremium" not in selected_names
        assert "testTax" not in selected_names

    def test_import_match_catches_transitive(self, all_tests):
        """Import-based matching catches tests via covered_symbols."""
        impact = ImpactResult(
            changed_symbols=["java:com.example.pricing.DiscountCalculator.calculateDiscount"],
            impacted_symbols=[
                "java:com.example.pricing.DiscountCalculator.calculateDiscount",
                "java:com.example.service.OrderService.getOrderTotal",
                "java:com.example.api.CheckoutHandler.checkout",
            ],
            impacted_files=[
                "src/main/java/com/example/pricing/DiscountCalculator.java",
                "src/main/java/com/example/service/OrderService.java",
                "src/main/java/com/example/api/CheckoutHandler.java",
            ],
            selected_tests=[],
        )

        selected = map_tests(impact, all_tests)
        ids = {t.id for t in selected}

        # Convention should catch DiscountCalculatorTest, OrderServiceTest, CheckoutHandlerTest
        assert any("DiscountCalculatorTest" in i for i in ids)
        assert any("OrderServiceTest" in i for i in ids)
        assert any("CheckoutHandlerTest" in i for i in ids)
        # PriceFormatterTest should NOT be selected
        assert not any("PriceFormatterTest" in i for i in ids)

    def test_empty_impact_returns_empty(self, all_tests):
        impact = ImpactResult(
            changed_symbols=[], impacted_symbols=[],
            impacted_files=[], selected_tests=[],
        )
        assert map_tests(impact, all_tests) == []

    def test_no_tests_available(self):
        impact = ImpactResult(
            changed_symbols=["java:Foo.bar"],
            impacted_symbols=["java:Foo.bar"],
            impacted_files=["Foo.java"],
            selected_tests=[],
        )
        assert map_tests(impact, []) == []

    def test_prefix_matching_catches_method_level_impact(self, all_tests):
        """If the impacted symbol is a method but the test covers the class,
        prefix matching should still select the test."""
        impact = ImpactResult(
            changed_symbols=["java:com.example.pricing.DiscountCalculator.calculateDiscount"],
            impacted_symbols=["java:com.example.pricing.DiscountCalculator.calculateDiscount"],
            impacted_files=["src/main/java/com/example/pricing/DiscountCalculator.java"],
            selected_tests=[],
        )

        selected = map_tests(impact, all_tests)
        selected_names = {t.name for t in selected}

        # The test covers "java:com.example.pricing.DiscountCalculator" (class level)
        # The impacted symbol is "...DiscountCalculator.calculateDiscount" (method level)
        # Prefix matching should catch this
        assert "testPremium" in selected_names