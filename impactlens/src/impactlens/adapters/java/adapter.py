"""
JavaAdapter — implements LanguageAdapter for Java source code.

Converts tree-sitter parse results into language-agnostic core types
(SourceSymbol, CallEdge, TestCase) that the pipeline operates on.
"""
from __future__ import annotations

import logging
from pathlib import Path

from impactlens.adapters.java.parser import JavaParser, ParseResult
from impactlens.core.adapter import LanguageAdapter
from impactlens.core.models import (
    CallEdge,
    Language,
    SourceSymbol,
    SymbolKind,
    TestCase,
    TestFramework,
)
from impactlens.core.registry import registry

log = logging.getLogger(__name__)

# Map our parser's kind strings to SymbolKind enum
_KIND_MAP = {
    "class": SymbolKind.CLASS,
    "interface": SymbolKind.INTERFACE,
    "method": SymbolKind.METHOD,
    "constructor": SymbolKind.CONSTRUCTOR,
}


class JavaAdapter(LanguageAdapter):
    """Language adapter for Java (JDK 8+)."""

    def __init__(self) -> None:
        self._parser = JavaParser()
        # Cache: file_path -> ParseResult (cleared between runs)
        self._parse_cache: dict[str, ParseResult] = {}

    # ----- identity --------------------------------------------------------

    @property
    def language(self) -> Language:
        return Language.JAVA

    @property
    def source_extensions(self) -> tuple[str, ...]:
        return (".java",)

    @property
    def test_file_patterns(self) -> tuple[str, ...]:
        return (
            "**/src/test/java/**/*Test.java",
            "**/src/test/java/**/Test*.java",
            "**/src/test/java/**/*Tests.java",
        )

    # ----- discovery -------------------------------------------------------

    def discover_source_files(self, repo_root: Path) -> list[Path]:
        """Discover non-test Java files, preferring Maven layout."""
        candidates = list(repo_root.glob("**/src/main/java/**/*.java"))
        if not candidates:
            # Fallback: any .java not under test directories
            candidates = [
                f for f in repo_root.rglob("*.java")
                if "/test/" not in str(f).replace("\\", "/")
                and "/Test" not in f.name
                and not f.name.endswith("Test.java")
                and not f.name.endswith("Tests.java")
            ]
        return sorted(set(candidates))

    # ----- helpers ---------------------------------------------------------

    def _get_parse_result(self, file_path: Path) -> ParseResult:
        """Parse a file, using cache to avoid re-parsing."""
        key = str(file_path)
        if key not in self._parse_cache:
            self._parse_cache[key] = self._parser.parse_file(file_path)
        return self._parse_cache[key]

    def _make_symbol_id(self, qualified_name: str) -> str:
        """Create a SymbolId: 'java:<qualified_name>'."""
        return f"java:{qualified_name}"

    def _relative_path(self, file_path: Path, repo_root: Path) -> str:
        """Get repo-relative path as string."""
        try:
            return str(file_path.relative_to(repo_root))
        except ValueError:
            return str(file_path)

    # ----- parsing ---------------------------------------------------------

    def parse_file(self, file_path: Path, repo_root: Path) -> list[SourceSymbol]:
        """Extract all symbols (classes, methods, constructors) from a Java file."""
        result = self._get_parse_result(file_path)
        rel_path = self._relative_path(file_path, repo_root)

        symbols: list[SourceSymbol] = []
        for raw in result.symbols:
            kind = _KIND_MAP.get(raw.kind, SymbolKind.METHOD)
            symbols.append(SourceSymbol(
                id=self._make_symbol_id(raw.qualified_name),
                name=raw.name,
                qualified_name=raw.qualified_name,
                kind=kind,
                file_path=rel_path,
                start_line=raw.start_line,
                end_line=raw.end_line,
                language=Language.JAVA,
            ))

        log.debug("Parsed %s: %d symbols", file_path.name, len(symbols))
        return symbols

    def extract_calls(
        self,
        file_path: Path,
        repo_root: Path,
        known_symbols: dict[str, SourceSymbol],
    ) -> list[CallEdge]:
        """Extract call edges from a Java file, resolving against known symbols."""
        result = self._get_parse_result(file_path)
        rel_path = self._relative_path(file_path, repo_root)

        # Build lookup structures for name resolution
        # 1. Map short class names from imports to their full package
        import_map: dict[str, str] = {}  # short name → full qualified path
        wildcard_packages: list[str] = []

        for imp in result.imports:
            if imp.is_wildcard:
                wildcard_packages.append(imp.full_path)
            else:
                # "com.example.util.PriceFormatter" → "PriceFormatter" → full path
                short = imp.full_path.rsplit(".", 1)[-1]
                import_map[short] = imp.full_path

        # 2. Find symbols defined in THIS file (for intra-file calls)
        file_symbols = [
            s for s in known_symbols.values()
            if s.file_path == rel_path
        ]
        file_classes = {s.name: s for s in file_symbols if s.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE)}
        file_methods = {s.name: s for s in file_symbols if s.kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR)}

        # 3. Build a "which method is this call inside?" lookup
        method_symbols_sorted = sorted(
            [s for s in file_symbols if s.kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR)],
            key=lambda s: s.start_line,
        )

        def find_enclosing_method(line: int) -> SourceSymbol | None:
            """Find the method/constructor that contains the given line."""
            best = None
            for s in method_symbols_sorted:
                if s.start_line <= line <= s.end_line:
                    # Pick the innermost (most nested) match
                    if best is None or s.start_line >= best.start_line:
                        best = s
            return best

        # 4. Build reverse index: class short name → list of method SourceSymbols
        #    across the entire codebase (for resolving receiver.method() calls)
        class_methods: dict[str, list[SourceSymbol]] = {}
        for sym in known_symbols.values():
            if sym.kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR) and sym.language == Language.JAVA:
                # qualified_name is like "com.example.Foo.bar"
                parts = sym.qualified_name.rsplit(".", 2)
                if len(parts) >= 2:
                    class_qname = sym.qualified_name[:sym.qualified_name.rfind(".")]
                    class_short = class_qname.rsplit(".", 1)[-1]
                    class_methods.setdefault(class_short, []).append(sym)

        def resolve_callee(method_name: str, receiver: str | None) -> str | None:
            """Try to resolve a method call to a known SymbolId."""
            if receiver and receiver != "this":
                # receiver could be a variable name or a class name
                # First check if receiver matches an imported class
                receiver_class = import_map.get(receiver)
                if not receiver_class:
                    # Maybe it's a field typed to one of our known classes
                    # Check if any class in the file has a field with this name
                    # For now, try matching receiver directly as a class name
                    receiver_class = receiver

                # Look up methods of the receiver class
                receiver_short = receiver_class.rsplit(".", 1)[-1] if receiver_class else receiver
                candidates = class_methods.get(receiver_short, [])
                for c in candidates:
                    if c.name == method_name:
                        return c.id

                # Try wildcard imports
                for pkg in wildcard_packages:
                    test_id = f"java:{pkg}.{receiver}.{method_name}"
                    if test_id in known_symbols:
                        return test_id

            elif receiver == "this" or receiver is None:
                # Intra-class call — look for method in the same class
                # Find the enclosing class of the file
                for fc in file_classes.values():
                    test_qname = f"{fc.qualified_name}.{method_name}"
                    test_id = f"java:{test_qname}"
                    if test_id in known_symbols:
                        return test_id

            # Brute-force fallback: look for any method with this name
            # (low confidence — could be wrong if multiple classes have same method name)
            matches = [
                s for s in known_symbols.values()
                if s.name == method_name
                and s.kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR)
                and s.language == Language.JAVA
            ]
            if len(matches) == 1:
                return matches[0].id

            return None

        edges: list[CallEdge] = []

        # Process method invocations
        for call in result.calls:
            caller_sym = find_enclosing_method(call.line)
            if not caller_sym:
                continue  # Call outside a method body (field initializer, etc.)

            callee_id = resolve_callee(call.method_name, call.receiver)
            if callee_id and callee_id != caller_sym.id:  # Skip self-recursion noise
                edges.append(CallEdge(
                    caller=caller_sym.id,
                    callee=callee_id,
                    call_site_line=call.line,
                    confidence=1.0,
                ))

        # Process constructor calls (new ClassName(...))
        for ctor_call in result.constructor_calls:
            caller_sym = find_enclosing_method(ctor_call.line)
            if not caller_sym:
                continue

            # Resolve the class name to its constructor
            class_qname = import_map.get(ctor_call.class_name)
            if not class_qname:
                # Check same-package classes
                if result.package:
                    class_qname = f"{result.package}.{ctor_call.class_name}"
                else:
                    class_qname = ctor_call.class_name

            # Look for the constructor symbol
            ctor_id = f"java:{class_qname}.{ctor_call.class_name}"
            if ctor_id in known_symbols:
                edges.append(CallEdge(
                    caller=caller_sym.id,
                    callee=ctor_id,
                    call_site_line=ctor_call.line,
                    confidence=1.0,
                ))
            else:
                # No explicit constructor — link to the class itself
                class_id = f"java:{class_qname}"
                if class_id in known_symbols:
                    edges.append(CallEdge(
                        caller=caller_sym.id,
                        callee=class_id,
                        call_site_line=ctor_call.line,
                        confidence=0.8,  # lower confidence — implicit constructor
                    ))

        log.debug("Extracted %d call edges from %s", len(edges), file_path.name)
        return edges

    def extract_tests(self, file_path: Path, repo_root: Path) -> list[TestCase]:
        """Extract JUnit test methods from a test file."""
        result = self._get_parse_result(file_path)
        rel_path = self._relative_path(file_path, repo_root)

        source = file_path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()

        tests: list[TestCase] = []

        for sym in result.symbols:
            if sym.kind != "method":
                continue

            # Check if this method has @Test annotation
            # Look at lines immediately above the method start
            is_test = False
            search_start = max(0, sym.start_line - 5)  # look up to 5 lines above
            search_end = sym.start_line
            for i in range(search_start, search_end):
                if i < len(lines) and "@Test" in lines[i]:
                    is_test = True
                    break

            if not is_test:
                continue

            # Determine the test ID for Maven Surefire: ClassName#methodName
            class_name = sym.parent_class or ""
            test_id = f"{class_name}#{sym.name}"

            # Figure out which source symbols this test might cover
            # based on imports in the test file
            covered: list[str] = []
            for imp in result.imports:
                if not imp.is_static and not imp.is_wildcard:
                    candidate_id = f"java:{imp.full_path}"
                    covered.append(candidate_id)

            tests.append(TestCase(
                id=test_id,
                name=sym.name,
                file_path=rel_path,
                language=Language.JAVA,
                framework=TestFramework.JUNIT5,
                covered_symbols=covered,
            ))

        log.debug("Extracted %d test cases from %s", len(tests), file_path.name)
        return tests

    def clear_cache(self) -> None:
        """Clear the parse cache. Call between analysis runs."""
        self._parse_cache.clear()


# Register on import
registry.register(JavaAdapter())