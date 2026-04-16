"""TestRunner ABC — runs selected tests and reports results.
Concrete runners (MavenRunner, PytestRunner) arrive Day 3."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from impactlens.core.models import TestCase, TestResult


class TestRunner(ABC):
    @abstractmethod
    def run(self, tests: list[TestCase], repo_path: Path) -> list[TestResult]:
        ...