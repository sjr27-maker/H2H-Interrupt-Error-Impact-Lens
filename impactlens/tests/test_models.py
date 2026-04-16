"""Smoke tests for core data models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from impactlens.core.models import (
    CallEdge,
    ChangedRegion,
    ChangeType,
    Language,
    LineRange,
    SourceSymbol,
    SymbolKind,
)


def test_source_symbol_basic():
    sym = SourceSymbol(
        id="java:com.example.Foo#bar",
        name="bar",
        qualified_name="com.example.Foo.bar",
        kind=SymbolKind.METHOD,
        file_path="src/main/java/com/example/Foo.java",
        start_line=10,
        end_line=20,
        language=Language.JAVA,
    )
    assert sym.name == "bar"
    assert sym.language == Language.JAVA


def test_source_symbol_is_hashable():
    sym = SourceSymbol(
        id="java:com.example.Foo#bar",
        name="bar",
        qualified_name="com.example.Foo.bar",
        kind=SymbolKind.METHOD,
        file_path="Foo.java",
        start_line=1,
        end_line=2,
        language=Language.JAVA,
    )
    s = {sym}
    assert sym in s


def test_call_edge_confidence_bounds():
    with pytest.raises(ValidationError):
        CallEdge(caller="a", callee="b", call_site_line=1, confidence=1.5)


def test_changed_region_with_ranges():
    cr = ChangedRegion(
        file_path="Foo.java",
        change_type=ChangeType.MODIFIED,
        old_range=LineRange(start=10, end=15),
        new_range=LineRange(start=10, end=17),
    )
    assert cr.change_type == ChangeType.MODIFIED
    assert cr.new_range.end == 17


def test_adapter_registry_registers_java():
    """After register_all_adapters(), JavaAdapter should be available."""
    from impactlens.core.registry import register_all_adapters, registry

    register_all_adapters()
    langs = {a.language for a in registry.all()}
    assert Language.JAVA in langs