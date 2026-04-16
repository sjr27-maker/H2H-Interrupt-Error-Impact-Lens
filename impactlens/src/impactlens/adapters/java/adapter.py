"""
JavaAdapter — implements LanguageAdapter for Java source code.

Responsibilities:
  - Discover .java files under Maven/Gradle source roots
  - Parse them via JavaParser (tree-sitter)
  - Produce SourceSymbol, CallEdge, TestCase instances conforming to the
    core data contract

Day 1: skeleton only — methods raise NotImplementedError or return [].
Day 2: real parsing and symbol extraction.
"""
from __future__ import annotations

import logging
from pathlib import Path

from impactlens.adapters.java.parser import JavaParser
from impactlens.core.adapter import LanguageAdapter
from impactlens.core.models import (
    CallEdge,
    Language,
    SourceSymbol,
    TestCase,
)
from impactlens.core.registry import registry

log = logging.getLogger(__name__)


class JavaAdapter(LanguageAdapter):
    """Language adapter for Java (JDK 8+)."""

    def __init__(self) -> None:
        self._parser = JavaParser()

    # ----- identity --------------------------------------------------------

    @property
    def language(self) -> Language:
        return Language.JAVA

    @property
    def source_extensions(self) -> tuple[str, ...]:
        return (".java",)

    @property
    def test_file_patterns(self) -> tuple[str, ...]:
        # Maven convention: src/test/java/...; filename ends with Test.java
        return (
            "**/src/test/java/**/*Test.java",
            "**/src/test/java/**/Test*.java",
            "**/src/test/java/**/*Tests.java",
        )

    # ----- discovery -------------------------------------------------------

    def discover_source_files(self, repo_root: Path) -> list[Path]:
        """Override default: respect Maven layout — only look in src/main/java."""
        candidates = list(repo_root.glob("**/src/main/java/**/*.java"))
        # Fallback for non-Maven layouts
        if not candidates:
            candidates = list(repo_root.rglob("*.java"))
            candidates = [c for c in candidates if "src/test" not in str(c).replace("\\", "/")]
        return sorted(set(candidates))

    # ----- parsing (Day 2 work) -------------------------------------------

    def parse_file(self, file_path: Path, repo_root: Path) -> list[SourceSymbol]:
        log.debug("JavaAdapter.parse_file(%s) — Day 1 stub", file_path)
        # Day 2: walk the tree-sitter tree and produce SourceSymbol instances
        return []

    def extract_calls(
        self,
        file_path: Path,
        repo_root: Path,
        known_symbols: dict[str, SourceSymbol],
    ) -> list[CallEdge]:
        log.debug("JavaAdapter.extract_calls(%s) — Day 1 stub", file_path)
        # Day 2: tree-sitter query for method_invocation, resolve against known_symbols
        return []

    def extract_tests(self, file_path: Path, repo_root: Path) -> list[TestCase]:
        log.debug("JavaAdapter.extract_tests(%s) — Day 1 stub", file_path)
        # Day 2: find methods with @Test annotation, produce TestCase instances
        return []


# Register on import
registry.register(JavaAdapter())