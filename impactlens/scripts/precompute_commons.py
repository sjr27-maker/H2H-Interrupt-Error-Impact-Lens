"""
Pre-compute ImpactLens analysis on Apache Commons Lang and cache results.

This runs locally (takes ~30-60 seconds) and saves the output as JSON
that the dashboard can load instantly without re-analyzing.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from impactlens.core.registry import register_all_adapters
from impactlens.core.pipeline import run_analysis


def main():
    register_all_adapters()

    repo_path = Path("sample_repos/commons_lang")
    if not repo_path.exists():
        print("ERROR: Apache Commons Lang not found.")
        print("Run: git submodule update --init")
        sys.exit(1)

    if not (repo_path / ".git").exists():
        print("ERROR: commons_lang is not a git repo.")
        print("Run: git submodule update --init")
        sys.exit(1)

    output_dir = Path("docs/precomputed")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze a recent commit
    # Find a good commit to analyze
    # Find a commit that actually modifies Java source files
    from git import Repo
    repo = Repo(str(repo_path))

    base_commit = None
    head_commit = None

    for commit in repo.iter_commits("HEAD", max_count=50):
        if not commit.parents:
            continue
        diffs = commit.parents[0].diff(commit)
        java_src_files = [
            d.b_path for d in diffs
            if d.b_path
            and d.b_path.endswith(".java")
            and "src/main" in d.b_path
        ]
        if java_src_files:
            head_commit = commit
            base_commit = commit.parents[0]
            print(f"Found commit with {len(java_src_files)} Java source changes:")
            print(f"  {str(head_commit)[:8]}: {head_commit.summary[:70]}")
            for f in java_src_files[:5]:
                print(f"    - {f}")
            if len(java_src_files) > 5:
                print(f"    ... and {len(java_src_files) - 5} more")
            break

    if not base_commit:
        print("ERROR: No recent commits modify Java source files.")
        print("Try checking out a different tag or branch.")
        sys.exit(1)

    base = str(base_commit)[:8]
    head = str(head_commit)[:8]

    print(f"Analyzing commons_lang: {base}..{head}")
    print(f"This may take 30-60 seconds...")
    print()

    start = time.time()

    try:
        result = run_analysis(repo_path, base, head)
    except Exception as e:
        print(f"Analysis failed: {e}")
        print("Trying with HEAD~1..HEAD instead...")
        try:
            result = run_analysis(repo_path, "HEAD~1", "HEAD")
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            sys.exit(1)

    elapsed = time.time() - start

    analysis = result.analysis
    impact = analysis.impact

    # Print summary
    print(f"Completed in {elapsed:.1f}s")
    print(f"  Source files:     {len(result.graph.graph.nodes)}")
    print(f"  Total symbols:    {analysis.total_symbols}")
    print(f"  Call edges:       {result.graph.edge_count}")
    print(f"  Total tests:      {analysis.total_tests}")
    print(f"  Changed symbols:  {len(impact.changed_symbols)}")
    print(f"  Impacted symbols: {len(impact.impacted_symbols)}")
    print(f"  Selected tests:   {len(impact.selected_tests)}")

    if analysis.total_tests > 0:
        reduction = (1 - len(impact.selected_tests) / analysis.total_tests) * 100
        print(f"  Reduction:        {reduction:.0f}%")

    # Save as JSON
    output = {
        "repo": "Apache Commons Lang 3.14.0",
        "base_commit": base,
        "head_commit": head,
        "analysis_time_seconds": round(elapsed, 1),
        "stats": {
            "total_symbols": analysis.total_symbols,
            "call_edges": result.graph.edge_count,
            "total_tests": analysis.total_tests,
            "changed_symbols": len(impact.changed_symbols),
            "impacted_symbols": len(impact.impacted_symbols),
            "selected_tests": len(impact.selected_tests),
            "reduction_percent": round(
                (1 - len(impact.selected_tests) / analysis.total_tests) * 100, 1
            ) if analysis.total_tests > 0 else 0,
        },
        "changed_symbols": impact.changed_symbols[:50],  # Truncate for readability
        "impacted_files": impact.impacted_files[:50],
        "selected_tests": [
            {"id": t.id, "file": t.file_path}
            for t in impact.selected_tests[:50]
        ],
        "timings": result.timings.summary(),
    }

    output_file = output_dir / "commons_lang_analysis.json"
    output_file.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {output_file}")


if __name__ == "__main__":
    main()