"""Tests for the git diff extractor."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from git import Repo

from impactlens.core.diff import extract_changed_regions
from impactlens.core.models import ChangeType


@pytest.fixture
def temp_repo(tmp_path: Path) -> Repo:
    """Create a minimal git repo with two commits for diffing."""
    repo = Repo.init(tmp_path)
    # Need a user for commits
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    # Commit 1: initial file
    hello = tmp_path / "Hello.java"
    hello.write_text(
        "public class Hello {\n"
        "    public void greet() {\n"
        '        System.out.println("hello");\n'
        "    }\n"
        "}\n"
    )
    repo.index.add(["Hello.java"])
    repo.index.commit("Initial commit")

    return repo


class TestExtractChangedRegions:
    def test_modified_file(self, temp_repo: Repo, tmp_path: Path):
        """Modifying a file should produce MODIFIED regions with line ranges."""
        hello = tmp_path / "Hello.java"
        hello.write_text(
            "public class Hello {\n"
            "    public void greet() {\n"
            '        System.out.println("hello world!");\n'
            "    }\n"
            "\n"
            "    public void farewell() {\n"
            '        System.out.println("goodbye");\n'
            "    }\n"
            "}\n"
        )
        temp_repo.index.add(["Hello.java"])
        temp_repo.index.commit("Add farewell method")

        regions = extract_changed_regions(tmp_path, "HEAD~1", "HEAD")

        assert len(regions) >= 1
        assert all(r.file_path == "Hello.java" for r in regions)
        assert all(r.change_type == ChangeType.MODIFIED for r in regions)
        # At least one region should have a new_range
        assert any(r.new_range is not None for r in regions)

    def test_added_file(self, temp_repo: Repo, tmp_path: Path):
        """Adding a new file should produce an ADDED region spanning the whole file."""
        world = tmp_path / "World.java"
        world.write_text(
            "public class World {\n"
            "    public String name() { return \"Earth\"; }\n"
            "}\n"
        )
        temp_repo.index.add(["World.java"])
        temp_repo.index.commit("Add World class")

        regions = extract_changed_regions(tmp_path, "HEAD~1", "HEAD")

        added = [r for r in regions if r.file_path == "World.java"]
        assert len(added) == 1
        assert added[0].change_type == ChangeType.ADDED
        assert added[0].new_range is not None
        assert added[0].new_range.start == 1
        assert added[0].new_range.end >= 3  # at least 3 lines
        assert added[0].old_range is None

    def test_deleted_file(self, temp_repo: Repo, tmp_path: Path):
        """Deleting a file should produce a DELETED region."""
        hello = tmp_path / "Hello.java"
        os.remove(hello)
        temp_repo.index.remove(["Hello.java"])
        temp_repo.index.commit("Remove Hello class")

        regions = extract_changed_regions(tmp_path, "HEAD~1", "HEAD")

        deleted = [r for r in regions if r.change_type == ChangeType.DELETED]
        assert len(deleted) == 1
        assert deleted[0].file_path == "Hello.java"
        assert deleted[0].old_range is not None
        assert deleted[0].new_range is None

    def test_multiple_changes_in_one_commit(self, temp_repo: Repo, tmp_path: Path):
        """Multiple files changed in one commit should each produce regions."""
        hello = tmp_path / "Hello.java"
        hello.write_text(
            "public class Hello {\n"
            "    public void greet() {\n"
            '        System.out.println("changed");\n'
            "    }\n"
            "}\n"
        )

        world = tmp_path / "World.java"
        world.write_text("public class World {}\n")

        temp_repo.index.add(["Hello.java", "World.java"])
        temp_repo.index.commit("Modify Hello, add World")

        regions = extract_changed_regions(tmp_path, "HEAD~1", "HEAD")

        files_changed = {r.file_path for r in regions}
        assert "Hello.java" in files_changed
        assert "World.java" in files_changed

    def test_no_changes(self, temp_repo: Repo, tmp_path: Path):
        """Diffing a commit against itself should produce no regions."""
        regions = extract_changed_regions(tmp_path, "HEAD", "HEAD")
        assert regions == []

    def test_invalid_ref_raises(self, temp_repo: Repo, tmp_path: Path):
        """An invalid ref should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot resolve"):
            extract_changed_regions(tmp_path, "nonexistent_branch", "HEAD")