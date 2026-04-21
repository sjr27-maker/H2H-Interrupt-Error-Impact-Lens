"""
Setup script for Streamlit Cloud deployment.
Ensures sample_repos exist and have git history.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def ensure_sample_repo():
    """Create the java_demo sample repo if it doesn't exist."""
    project_root = Path(__file__).parent.parent
    sample_dir = project_root / "sample_repos" / "java_demo"
    setup_script = project_root / "scripts" / "setup_sample_repo.sh"

    if (sample_dir / ".git").exists():
        return True

    if not sample_dir.exists():
        return False

    if setup_script.exists():
        try:
            subprocess.run(
                ["bash", str(setup_script)],
                cwd=str(project_root),
                capture_output=True,
                timeout=30,
            )
            return (sample_dir / ".git").exists()
        except Exception:
            pass

    # Manual fallback — init git and commit everything
    try:
        subprocess.run(["git", "init"], cwd=str(sample_dir), capture_output=True)
        subprocess.run(["git", "checkout", "-b", "main"], cwd=str(sample_dir), capture_output=True)
        subprocess.run(
            ["git", "-c", "user.name=Demo", "-c", "user.email=demo@demo.com",
             "add", "."],
            cwd=str(sample_dir), capture_output=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=Demo", "-c", "user.email=demo@demo.com",
             "commit", "-m", "Initial demo commit"],
            cwd=str(sample_dir), capture_output=True,
        )
        return (sample_dir / ".git").exists()
    except Exception:
        return False