"""
LanguageAdapter — the abstract interface that every supported language
implements. The pipeline orchestrator depends ONLY on this interface, never
on a concrete language module. To add a new language:

  1. Create src/impactlens/adapters/<lang>/adapter.py
  2. Subclass LanguageAdapter and implement all abstract methods
  3. Register the adapter in src/impactlens/core/registry.py
  4. Add the Language enum value in core/models.py if needed

That's it. The rest of the pipeline works unchanged.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from impactlens.core.models import (
    CallEdge,
    ChangedRegion,
    Language,
    SourceSymbol,
    TestCase,
)


class LanguageAdapter(ABC):
    """Abstract base class for language-specific parsing and analysis."""

    # ----- identity --------------------------------------------------------

    @property
    @abstractmethod
    def language(self) -> Language:
        """The Language enum value this adapter handles."""

    @property
    @abstractmethod
    def source_extensions(self) -> tuple[str, ...]:
        """File extensions considered source for this language, e.g. ('.java',)."""

    @property
    @abstractmethod
    def test_file_patterns(self) -> tuple[str, ...]:
        """Glob-style patterns for test files, e.g. ('**/*Test.java', '**/Test*.java')."""

    # ----- discovery -------------------------------------------------------

    def discover_source_files(self, repo_root: Path) -> list[Path]:
        """Find all source files of this language in the repo.
        Default implementation uses `source_extensions`. Adapters can override
        to respect build-system conventions (e.g., only files under src/main)."""
        files: list[Path] = []
        for ext in self.source_extensions:
            files.extend(repo_root.rglob(f"*{ext}"))
        return sorted(set(files))

    def discover_test_files(self, repo_root: Path) -> list[Path]:
        """Find all test files in the repo."""
        files: list[Path] = []
        for pattern in self.test_file_patterns:
            files.extend(repo_root.glob(pattern))
        return sorted(set(files))

    # ----- parsing ---------------------------------------------------------

    @abstractmethod
    def parse_file(self, file_path: Path, repo_root: Path) -> list[SourceSymbol]:
        """Extract all defined symbols from a single source file.
        Must produce SymbolIds that are unique and stable across runs."""

    @abstractmethod
    def extract_calls(
        self, file_path: Path, repo_root: Path, known_symbols: dict[str, SourceSymbol]
    ) -> list[CallEdge]:
        """Extract call edges from this file. `known_symbols` is a repo-wide
        map of SymbolId -> SourceSymbol for name resolution."""

    @abstractmethod
    def extract_tests(self, file_path: Path, repo_root: Path) -> list[TestCase]:
        """Extract individual test cases from a test file."""

    # ----- change attribution ---------------------------------------------

    def symbols_in_range(
        self,
        file_symbols: Iterable[SourceSymbol],
        changed_regions: Iterable[ChangedRegion],
    ) -> list[SourceSymbol]:
        """Given a file's symbols and the ranges changed in it, return which
        symbols overlap the changes. Language-agnostic default; adapters can
        override for language-specific logic (e.g., imports at file top)."""
        out: list[SourceSymbol] = []
        for region in changed_regions:
            rng = region.new_range or region.old_range
            if rng is None:
                continue
            for sym in file_symbols:
                # Overlap check: intervals [sym.start,sym.end] and [rng.start,rng.end]
                if sym.start_line <= rng.end and rng.start <= sym.end_line:
                    out.append(sym)
        # Dedupe preserving order
        seen: set[str] = set()
        uniq: list[SourceSymbol] = []
        for s in out:
            if s.id not in seen:
                seen.add(s.id)
                uniq.append(s)
        return uniq