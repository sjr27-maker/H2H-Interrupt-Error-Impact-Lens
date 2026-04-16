"""Pipeline orchestrator — stitches diff → adapter → graph → impact → runner.
Full implementation Day 3."""
from __future__ import annotations

from pathlib import Path

from impactlens.core.models import AnalysisRun


def run_analysis(
    repo_path: Path, base: str, head: str
) -> AnalysisRun:
    raise NotImplementedError("Implemented Day 3")