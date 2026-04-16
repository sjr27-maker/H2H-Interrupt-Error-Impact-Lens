"""
Tree-sitter Java parser wrapper. Encapsulates grammar loading and query
execution so the adapter layer stays clean.

Day 1: skeleton that initializes the grammar and exposes stubs.
Day 2: actual query-based extraction of classes, methods, imports, calls.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class JavaParser:
    """Wraps tree-sitter's Java grammar."""

    def __init__(self) -> None:
        self._language = None
        self._parser = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            import tree_sitter_java as tsjava
            from tree_sitter import Language, Parser

            # Newer tree-sitter Python API takes the language capsule directly
            self._language = Language(tsjava.language())
            self._parser = Parser(self._language)
            self._initialized = True
            log.info("Java tree-sitter grammar initialized")
        except Exception as e:
            log.error("Failed to initialize Java tree-sitter grammar: %s", e)
            raise RuntimeError(
                "Could not initialize Java parser. Ensure tree-sitter and "
                "tree-sitter-java are installed. See docs/setup.md."
            ) from e

    def parse_source(self, source: bytes) -> Any:
        """Parse Java source bytes, return the tree-sitter Tree object."""
        self._ensure_initialized()
        return self._parser.parse(source)

    def parse_file(self, file_path: Path) -> Any:
        source = file_path.read_bytes()
        return self.parse_source(source)

    # Day 2: add query-based extraction methods
    # def extract_classes(self, tree) -> list[dict]: ...
    # def extract_methods(self, tree) -> list[dict]: ...
    # def extract_imports(self, tree) -> list[dict]: ...
    # def extract_calls(self, tree) -> list[dict]: ...