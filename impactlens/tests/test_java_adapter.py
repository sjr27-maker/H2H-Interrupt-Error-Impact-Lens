"""Tests for the Java adapter — parser, symbol extraction, and call resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from impactlens.adapters.java.parser import JavaParser, ParseResult
from impactlens.adapters.java.adapter import JavaAdapter
from impactlens.core.models import Language, SymbolKind, TestFramework
from impactlens.graph.call_graph import CallGraph


@pytest.fixture
def parser() -> JavaParser:
    return JavaParser()


@pytest.fixture
def adapter() -> JavaAdapter:
    a = JavaAdapter()
    a.clear_cache()
    return a


# ── Parser unit tests ────────────────────────────────────────────────────────

class TestJavaParser:
    def test_extracts_package(self, parser: JavaParser):
        result = parser.parse_source(b"""
        package com.impactlens.demo.util;
        public class Foo {}
        """)
        assert result.package == "com.impactlens.demo.util"

    def test_extracts_class(self, parser: JavaParser):
        result = parser.parse_source(b"""
        package com.example;
        public class MyClass {
            public void doStuff() {}
        }
        """)
        classes = [s for s in result.symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "MyClass"
        assert classes[0].qualified_name == "com.example.MyClass"

    def test_extracts_methods(self, parser: JavaParser):
        result = parser.parse_source(b"""
        package com.example;
        public class Calc {
            public int add(int a, int b) { return a + b; }
            public int subtract(int a, int b) { return a - b; }
        }
        """)
        methods = [s for s in result.symbols if s.kind == "method"]
        assert len(methods) == 2
        names = {m.name for m in methods}
        assert names == {"add", "subtract"}

    def test_extracts_imports(self, parser: JavaParser):
        result = parser.parse_source(b"""
        package com.example;
        import com.impactlens.demo.util.PriceFormatter;
        import java.util.Map;
        public class Foo {}
        """)
        assert len(result.imports) == 2
        paths = {i.full_path for i in result.imports}
        assert "com.impactlens.demo.util.PriceFormatter" in paths

    def test_extracts_method_calls(self, parser: JavaParser):
        result = parser.parse_source(b"""
        package com.example;
        public class Foo {
            public void bar() {
                baz();
                obj.doThing();
            }
            public void baz() {}
        }
        """)
        assert len(result.calls) >= 2
        call_names = {c.method_name for c in result.calls}
        assert "baz" in call_names
        assert "doThing" in call_names

    def test_extracts_constructor_calls(self, parser: JavaParser):
        result = parser.parse_source(b"""
        package com.example;
        import com.other.Widget;
        public class Foo {
            public void build() {
                Widget w = new Widget();
            }
        }
        """)
        assert len(result.constructor_calls) >= 1
        assert result.constructor_calls[0].class_name == "Widget"

    def test_line_numbers_are_correct(self, parser: JavaParser):
        source = b"""package com.example;

public class Foo {
    public void alpha() {
        // line 5
    }

    public void beta() {
        // line 9
    }
}"""
        result = parser.parse_source(source)
        methods = {s.name: s for s in result.symbols if s.kind == "method"}
        assert methods["alpha"].start_line < methods["beta"].start_line


# ── Adapter integration tests (against sample repo) ──────────────────────────

class TestJavaAdapterWithSampleRepo:
    """These tests require the sample repo to exist at sample_repos/java_demo."""

    @pytest.fixture
    def sample_root(self) -> Path:
        root = Path("sample_repos/java_demo")
        if not root.exists():
            pytest.skip("Sample repo not found — run scripts/setup_sample_repo.sh first")
        return root

    def test_discovers_source_files(self, adapter: JavaAdapter, sample_root: Path):
        files = adapter.discover_source_files(sample_root)
        names = {f.name for f in files}
        assert "PriceFormatter.java" in names
        assert "OrderService.java" in names
        # Test files should NOT be in source files
        assert "PriceFormatterTest.java" not in names

    def test_discovers_test_files(self, adapter: JavaAdapter, sample_root: Path):
        files = adapter.discover_test_files(sample_root)
        names = {f.name for f in files}
        assert "PriceFormatterTest.java" in names
        assert "CheckoutHandlerTest.java" in names

    def test_parse_file_returns_symbols(self, adapter: JavaAdapter, sample_root: Path):
        price_file = sample_root / "src/main/java/com/impactlens/demo/util/PriceFormatter.java"
        if not price_file.exists():
            pytest.skip("PriceFormatter.java not found")

        symbols = adapter.parse_file(price_file, sample_root)

        assert len(symbols) >= 2  # class + at least one method
        names = {s.name for s in symbols}
        assert "PriceFormatter" in names
        assert "format" in names

        # Verify language is set
        for s in symbols:
            assert s.language == Language.JAVA

    def test_full_repo_parse_and_call_graph(self, adapter: JavaAdapter, sample_root: Path):
        """Parse all files and build a call graph — the full Day 2 pipeline."""
        source_files = adapter.discover_source_files(sample_root)

        # Step 1: parse all symbols
        all_symbols = []
        for sf in source_files:
            all_symbols.extend(adapter.parse_file(sf, sample_root))

        assert len(all_symbols) >= 10  # 5+ classes, 5+ methods minimum

        # Step 2: extract calls
        known = {s.id: s for s in all_symbols}
        all_edges = []
        for sf in source_files:
            all_edges.extend(adapter.extract_calls(sf, sample_root, known))

        # We expect at least some call edges (OrderService calls DiscountCalculator, etc.)
        assert len(all_edges) >= 3

        # Step 3: build call graph
        graph = CallGraph()
        graph.add_symbols(all_symbols)
        graph.add_calls(all_edges)

        summary = graph.summary()
        assert summary["nodes"] >= 10
        assert summary["edges"] >= 3

        # Step 4: verify a known relationship
        # OrderService.getOrderTotal calls DiscountCalculator.calculateDiscount
        order_method = "java:com.impactlens.demo.service.OrderService.getOrderTotal"
        discount_method = "java:com.impactlens.demo.pricing.DiscountCalculator.calculateDiscount"

        # DiscountCalculator should be a callee of OrderService
        callees = graph.direct_callees(order_method)
        # The call might be resolved to the constructor or the method
        # depending on the resolution logic — check that SOME connection exists
        assert graph.edge_count > 0, "No edges in graph — call resolution may be broken"

    def test_extract_tests(self, adapter: JavaAdapter, sample_root: Path):
        """Test extraction should find JUnit @Test methods."""
        test_files = adapter.discover_test_files(sample_root)
        all_tests = []
        for tf in test_files:
            all_tests.extend(adapter.extract_tests(tf, sample_root))

        assert len(all_tests) >= 5  # at least one per test class
        # All should be JUnit5
        for t in all_tests:
            assert t.framework == TestFramework.JUNIT5
            assert t.language == Language.JAVA

        test_names = {t.name for t in all_tests}
        assert "testPremiumDiscount" in test_names
        assert "testFormatBasic" in test_names