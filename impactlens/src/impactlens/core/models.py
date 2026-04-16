"""
Core data models for ImpactLens.

These types form the contract between the language-agnostic pipeline and
the language-specific adapters. Changes here ripple everywhere — treat them
as a stable API from Day 2 onward.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Language(str, Enum):
    JAVA = "java"
    PYTHON = "python"
    GO = "go"
    # Add new languages here. Adapters register themselves against these values.


class SymbolKind(str, Enum):
    CLASS = "class"
    METHOD = "method"         # class-bound
    FUNCTION = "function"     # module-level (for Python/Go)
    FIELD = "field"
    CONSTRUCTOR = "constructor"
    INTERFACE = "interface"


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestFramework(str, Enum):
    JUNIT5 = "junit5"
    JUNIT4 = "junit4"
    PYTEST = "pytest"
    GO_TEST = "go_test"


# ---------------------------------------------------------------------------
# Symbols & calls (the codebase representation)
# ---------------------------------------------------------------------------

class SourceSymbol(BaseModel):
    """A defined symbol in source code — a class, method, or function."""
    id: str = Field(..., description="Unique id: '<lang>:<qualified_name>[#member]'")
    name: str
    qualified_name: str
    kind: SymbolKind
    file_path: str = Field(..., description="Repo-relative path")
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    language: Language

    model_config = {"frozen": True}

    def __hash__(self) -> int:
        return hash(self.id)


class CallEdge(BaseModel):
    """A static or inferred call from one symbol to another."""
    caller: str = Field(..., description="SymbolId of caller")
    callee: str = Field(..., description="SymbolId of callee")
    call_site_line: int = Field(..., ge=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

class LineRange(BaseModel):
    start: int = Field(..., ge=1)
    end: int = Field(..., ge=1)


class ChangedRegion(BaseModel):
    """A contiguous changed region within a single file."""
    file_path: str
    change_type: ChangeType
    old_range: Optional[LineRange] = None
    new_range: Optional[LineRange] = None
    old_path: Optional[str] = Field(
        default=None,
        description="For renames: the previous path",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCase(BaseModel):
    """A single test method or function."""
    id: str = Field(..., description="Framework-parsable ID")
    name: str
    file_path: str
    language: Language
    framework: TestFramework
    covered_symbols: list[str] = Field(
        default_factory=list,
        description="SymbolIds this test is believed to exercise",
    )


class TestResult(BaseModel):
    test_id: str
    status: TestStatus
    duration_ms: float = Field(..., ge=0.0)
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Analysis output
# ---------------------------------------------------------------------------

class ImpactResult(BaseModel):
    """Output of the impact analyzer."""
    changed_symbols: list[str]
    impacted_symbols: list[str]
    impacted_files: list[str]
    selected_tests: list[TestCase]
    reasoning: dict[str, str] = Field(default_factory=dict)


class AnalysisRun(BaseModel):
    """Top-level result returned to the CLI / dashboard."""
    repo_path: str
    base_commit: str
    head_commit: str
    changed_regions: list[ChangedRegion]
    impact: ImpactResult
    total_symbols: int
    total_tests: int