"""Git diff extraction. Language-agnostic — produces ChangedRegion instances.
Implemented Day 2."""
from __future__ import annotations

from pathlib import Path

from impactlens.core.models import ChangedRegion


def extract_changed_regions(
    repo_path: Path, base: str, head: str
) -> list[ChangedRegion]:
    """Return the list of ChangedRegion between two git refs."""
    raise NotImplementedError("Implemented Day 2")