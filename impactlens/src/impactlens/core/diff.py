"""
Git diff extraction — language-agnostic.

Takes a repository path and two git refs (commits, branches, tags),
produces a list of ChangedRegion instances describing what changed.
Uses GitPython to access the diff programmatically.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from git import Repo, NULL_TREE
from git.diff import Diff

from impactlens.core.models import ChangedRegion, ChangeType, LineRange

log = logging.getLogger(__name__)

# Regex to parse unified diff hunk headers: @@ -old_start,old_count +new_start,new_count @@
_HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE
)


def _classify_change(diff_item: Diff) -> ChangeType:
    """Map GitPython's diff flags to our ChangeType enum."""
    if diff_item.new_file:
        return ChangeType.ADDED
    if diff_item.deleted_file:
        return ChangeType.DELETED
    if diff_item.renamed_file:
        return ChangeType.RENAMED
    return ChangeType.MODIFIED


def _parse_hunks(diff_text: str) -> list[tuple[LineRange | None, LineRange | None]]:
    """
    Parse unified diff output to extract old and new line ranges per hunk.

    Each hunk produces one (old_range, new_range) tuple.
    For additions, old_range is None. For deletions, new_range is None.
    """
    hunks: list[tuple[LineRange | None, LineRange | None]] = []

    for match in _HUNK_RE.finditer(diff_text):
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) is not None else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) is not None else 1

        old_range = None
        if old_count > 0:
            old_range = LineRange(start=old_start, end=old_start + old_count - 1)

        new_range = None
        if new_count > 0:
            new_range = LineRange(start=new_start, end=new_start + new_count - 1)

        hunks.append((old_range, new_range))

    return hunks


def _get_file_path(diff_item: Diff) -> str:
    """Get the relevant file path from a diff item.

    For renames, returns the NEW path (b_path).
    For deletions, returns the OLD path (a_path).
    Otherwise, returns whichever is available, preferring b_path.
    """
    if diff_item.deleted_file:
        return diff_item.a_path
    if diff_item.b_path:
        return diff_item.b_path
    return diff_item.a_path


def extract_changed_regions(
    repo_path: Path, base: str, head: str
) -> list[ChangedRegion]:
    """
    Extract all changed regions between two git refs.

    Args:
        repo_path: Path to the git repository root.
        base: The base git ref (commit hash, branch name, tag, or HEAD~N).
        head: The head git ref (default: HEAD).

    Returns:
        List of ChangedRegion, one per hunk. A single file with 3 changed
        hunks produces 3 ChangedRegion entries (same file_path, different ranges).

    Raises:
        ValueError: If refs can't be resolved.
        git.exc.InvalidGitRepositoryError: If repo_path isn't a git repo.
    """
    repo = Repo(str(repo_path))

    # Resolve refs to commit objects
    try:
        base_commit = repo.commit(base)
    except Exception as e:
        raise ValueError(f"Cannot resolve base ref '{base}': {e}") from e

    try:
        head_commit = repo.commit(head)
    except Exception as e:
        raise ValueError(f"Cannot resolve head ref '{head}': {e}") from e

    log.info(
        "Diffing %s..%s in %s",
        str(base_commit)[:8],
        str(head_commit)[:8],
        repo_path,
    )

    # Get the diff between the two commits
    # create_patch=True gives us the actual unified diff text for hunk parsing
    diffs = base_commit.diff(head_commit, create_patch=True)

    regions: list[ChangedRegion] = []

    for diff_item in diffs:
        change_type = _classify_change(diff_item)
        file_path = _get_file_path(diff_item)

        # Skip non-Java files (the adapter will filter too, but this is cheaper)
        # Actually, keep this language-agnostic — the core shouldn't filter by extension.
        # The pipeline orchestrator handles that.

        old_path = None
        if diff_item.renamed_file and diff_item.a_path:
            old_path = diff_item.a_path

        if change_type == ChangeType.ADDED:
            # Entire file is new — count total lines in the new blob
            try:
                new_content = diff_item.b_blob.data_stream.read().decode(
                    "utf-8", errors="replace"
                )
                line_count = new_content.count("\n") + 1
            except Exception:
                line_count = 1

            regions.append(
                ChangedRegion(
                    file_path=file_path,
                    change_type=change_type,
                    old_range=None,
                    new_range=LineRange(start=1, end=line_count),
                    old_path=old_path,
                )
            )
            log.debug("  ADD  %s (1-%d)", file_path, line_count)
            continue

        if change_type == ChangeType.DELETED:
            # Entire file removed — count lines in the old blob
            try:
                old_content = diff_item.a_blob.data_stream.read().decode(
                    "utf-8", errors="replace"
                )
                line_count = old_content.count("\n") + 1
            except Exception:
                line_count = 1

            regions.append(
                ChangedRegion(
                    file_path=file_path,
                    change_type=change_type,
                    old_range=LineRange(start=1, end=line_count),
                    new_range=None,
                    old_path=old_path,
                )
            )
            log.debug("  DEL  %s (1-%d)", file_path, line_count)
            continue

        # MODIFIED or RENAMED — parse hunks from the unified diff
        try:
            diff_text = diff_item.diff.decode("utf-8", errors="replace")
        except Exception:
            diff_text = ""

        hunks = _parse_hunks(diff_text)

        if not hunks:
            # No parseable hunks (binary file, or empty diff) — treat as whole-file
            regions.append(
                ChangedRegion(
                    file_path=file_path,
                    change_type=change_type,
                    old_range=None,
                    new_range=None,
                    old_path=old_path,
                )
            )
            log.debug("  %s  %s (no hunks)", change_type.value.upper(), file_path)
        else:
            for old_range, new_range in hunks:
                regions.append(
                    ChangedRegion(
                        file_path=file_path,
                        change_type=change_type,
                        old_range=old_range,
                        new_range=new_range,
                        old_path=old_path,
                    )
                )
                old_str = f"{old_range.start}-{old_range.end}" if old_range else "—"
                new_str = f"{new_range.start}-{new_range.end}" if new_range else "—"
                log.debug(
                    "  %s  %s  old[%s] new[%s]",
                    change_type.value.upper(),
                    file_path,
                    old_str,
                    new_str,
                )

    log.info("Found %d changed regions across %d files", len(regions), len(set(r.file_path for r in regions)))
    return regions