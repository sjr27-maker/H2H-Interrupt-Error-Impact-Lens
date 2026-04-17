"""
Tree-sitter Java parser.

Extracts classes, methods, constructors, imports, and method invocations
from Java source files. Returns raw dicts — the JavaAdapter converts them
into Pydantic models.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class RawSymbol:
    """Intermediate representation before conversion to SourceSymbol."""
    name: str
    qualified_name: str
    kind: str  # "class", "method", "constructor", "interface"
    start_line: int
    end_line: int
    parent_class: str | None = None


@dataclass
class RawImport:
    """A single import statement."""
    full_path: str      # e.g. "com.example.util.PriceFormatter"
    is_static: bool = False
    is_wildcard: bool = False


@dataclass
class RawCall:
    """A method invocation found in source."""
    method_name: str
    receiver: str | None = None  # e.g. "formatter", "PriceFormatter", "this"
    line: int = 0


@dataclass
class RawConstructorCall:
    """A 'new ClassName(...)' expression."""
    class_name: str
    line: int = 0


@dataclass
class ParseResult:
    """Everything extracted from a single Java file."""
    package: str | None = None
    imports: list[RawImport] = field(default_factory=list)
    symbols: list[RawSymbol] = field(default_factory=list)
    calls: list[RawCall] = field(default_factory=list)
    constructor_calls: list[RawConstructorCall] = field(default_factory=list)


class JavaParser:
    """Wraps tree-sitter's Java grammar for structured extraction."""

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

            self._language = Language(tsjava.language())
            self._parser = Parser(self._language)
            self._initialized = True
            log.info("Java tree-sitter grammar initialized")
        except Exception as e:
            log.error("Failed to initialize Java tree-sitter: %s", e)
            raise RuntimeError(
                "Could not initialize Java parser. "
                "pip install tree-sitter tree-sitter-java"
            ) from e

    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a Java file and extract all structural information."""
        self._ensure_initialized()
        source = file_path.read_bytes()
        tree = self._parser.parse(source)
        return self._extract(tree.root_node, source)

    def parse_source(self, source: bytes) -> ParseResult:
        """Parse Java source bytes directly."""
        self._ensure_initialized()
        tree = self._parser.parse(source)
        return self._extract(tree.root_node, source)

    def _node_text(self, node: Any, source: bytes) -> str:
        """Get the text content of a tree-sitter node."""
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _extract(self, root: Any, source: bytes) -> ParseResult:
        """Walk the tree and extract everything."""
        result = ParseResult()

        # Extract package declaration
        result.package = self._extract_package(root, source)

        # Extract imports
        result.imports = self._extract_imports(root, source)

        # Extract class/interface declarations with their methods
        self._extract_declarations(root, source, result, parent_class=None)

        # Extract method invocations and constructor calls
        self._extract_invocations(root, source, result)

        return result

    def _extract_package(self, root: Any, source: bytes) -> str | None:
        """Find the package declaration."""
        for child in root.children:
            if child.type == "package_declaration":
                # The package name is in a scoped_identifier or identifier child
                for c in child.children:
                    if c.type in ("scoped_identifier", "identifier"):
                        return self._node_text(c, source)
        return None

    def _extract_imports(self, root: Any, source: bytes) -> list[RawImport]:
        """Extract all import statements."""
        imports: list[RawImport] = []
        for child in root.children:
            if child.type == "import_declaration":
                text = self._node_text(child, source)
                is_static = "static" in text
                is_wildcard = text.rstrip(";").strip().endswith(".*")

                # Get the imported path (scoped_identifier or identifier)
                path = ""
                for c in child.children:
                    if c.type in ("scoped_identifier", "identifier"):
                        path = self._node_text(c, source)
                    elif c.type == "asterisk":
                        is_wildcard = True

                if path:
                    # Clean up — remove trailing .* if present
                    path = path.rstrip(".*").rstrip(".")
                    if is_wildcard:
                        path = path  # keep as package path for wildcard
                    imports.append(RawImport(
                        full_path=path,
                        is_static=is_static,
                        is_wildcard=is_wildcard,
                    ))
        return imports

    def _extract_declarations(
        self,
        node: Any,
        source: bytes,
        result: ParseResult,
        parent_class: str | None,
    ) -> None:
        """Recursively extract class, interface, and method declarations."""
        for child in node.children:
            if child.type in ("class_declaration", "interface_declaration"):
                class_name = None
                for c in child.children:
                    if c.type == "identifier":
                        class_name = self._node_text(c, source)
                        break

                if class_name:
                    qualified = class_name
                    if result.package:
                        qualified = f"{result.package}.{class_name}"
                    if parent_class:
                        qualified = f"{parent_class}.{class_name}"

                    kind = "interface" if child.type == "interface_declaration" else "class"

                    result.symbols.append(RawSymbol(
                        name=class_name,
                        qualified_name=qualified,
                        kind=kind,
                        start_line=child.start_point[0] + 1,  # tree-sitter is 0-indexed
                        end_line=child.end_point[0] + 1,
                        parent_class=parent_class,
                    ))

                    # Recurse into the class body for methods and inner classes
                    body = None
                    for c in child.children:
                        if c.type == "class_body" or c.type == "interface_body":
                            body = c
                            break

                    if body:
                        self._extract_methods(body, source, result, qualified)
                        # Recurse for inner classes
                        self._extract_declarations(body, source, result, parent_class=qualified)

            # Handle top-level — some files might have declarations inside
            # program > class_declaration; recurse into all children
            elif child.type not in (
                "package_declaration", "import_declaration",
                "line_comment", "block_comment",
            ):
                self._extract_declarations(child, source, result, parent_class)

    def _extract_methods(
        self,
        class_body: Any,
        source: bytes,
        result: ParseResult,
        class_qualified_name: str,
    ) -> None:
        """Extract method and constructor declarations from a class body."""
        for child in class_body.children:
            if child.type == "method_declaration":
                method_name = None
                for c in child.children:
                    if c.type == "identifier":
                        method_name = self._node_text(c, source)
                        break

                if method_name:
                    qualified = f"{class_qualified_name}.{method_name}"
                    result.symbols.append(RawSymbol(
                        name=method_name,
                        qualified_name=qualified,
                        kind="method",
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent_class=class_qualified_name,
                    ))

            elif child.type == "constructor_declaration":
                ctor_name = None
                for c in child.children:
                    if c.type == "identifier":
                        ctor_name = self._node_text(c, source)
                        break

                if ctor_name:
                    qualified = f"{class_qualified_name}.{ctor_name}"
                    result.symbols.append(RawSymbol(
                        name=ctor_name,
                        qualified_name=qualified,
                        kind="constructor",
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parent_class=class_qualified_name,
                    ))

    def _extract_invocations(
        self, node: Any, source: bytes, result: ParseResult
    ) -> None:
        """Recursively extract all method_invocation and object_creation_expression nodes."""
        if node.type == "method_invocation":
            method_name = None
            receiver = None

            for c in node.children:
                if c.type == "identifier":
                    # Could be receiver or method name depending on position
                    if method_name is None:
                        method_name = self._node_text(c, source)
                    else:
                        # Previous was receiver, this is method
                        receiver = method_name
                        method_name = self._node_text(c, source)
                elif c.type in ("field_access", "scoped_identifier"):
                    receiver = self._node_text(c, source)
                elif c.type == "this":
                    receiver = "this"

            # In tree-sitter Java, method_invocation children are typically:
            #   object "." identifier argument_list
            # So re-parse: find the last identifier before argument_list
            children_types = [(c.type, c) for c in node.children]
            identifiers = [(t, c) for t, c in children_types if t == "identifier"]

            if len(identifiers) >= 1:
                # Last identifier is the method name
                method_name = self._node_text(identifiers[-1][1], source)
                # If there's something before the dot, that's the receiver
                receiver = None
                for i, (t, c) in enumerate(children_types):
                    if t == ".":
                        # Everything before the dot is the receiver
                        for prev_t, prev_c in children_types[:i]:
                            if prev_t in ("identifier", "field_access", "this"):
                                receiver = self._node_text(prev_c, source)
                        break

            if method_name:
                result.calls.append(RawCall(
                    method_name=method_name,
                    receiver=receiver,
                    line=node.start_point[0] + 1,
                ))

        elif node.type == "object_creation_expression":
            # new ClassName(...)
            for c in node.children:
                if c.type in ("type_identifier", "scoped_type_identifier",
                              "generic_type"):
                    class_name = self._node_text(c, source)
                    # Strip generics: Map<String, Double> → Map
                    if "<" in class_name:
                        class_name = class_name[:class_name.index("<")]
                    result.constructor_calls.append(RawConstructorCall(
                        class_name=class_name,
                        line=c.start_point[0] + 1,
                    ))
                    break

        # Recurse into children
        for child in node.children:
            self._extract_invocations(child, source, result)