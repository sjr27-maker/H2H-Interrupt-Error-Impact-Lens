"""
Load pre-computed analysis results for demo purposes.

Used for large repos (like Apache Commons Lang) where live analysis
would be too slow on free-tier hosting.
"""
from __future__ import annotations

import json
from pathlib import Path


def get_precomputed_results() -> dict[str, dict]:
    """Load all pre-computed result files."""
    results = {}
    precomputed_dir = Path(__file__).parent.parent / "docs" / "precomputed"

    if not precomputed_dir.exists():
        return results

    for json_file in precomputed_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
            name = data.get("repo", json_file.stem)
            results[name] = data
        except (json.JSONDecodeError, KeyError):
            continue

    return results


def render_precomputed(data: dict) -> None:
    """Render pre-computed results in Streamlit."""
    import streamlit as st

    stats = data.get("stats", {})

    st.markdown(f"### {data.get('repo', 'Unknown')}")
    st.markdown(f"*Commits: `{data.get('base_commit', '?')}` → `{data.get('head_commit', '?')}`*")
    st.markdown(f"*Analysis completed in {data.get('analysis_time_seconds', '?')}s*")

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Symbols", stats.get("total_symbols", 0))
    with m2:
        st.metric("Call Edges", stats.get("call_edges", 0))
    with m3:
        st.metric("Tests", stats.get("total_tests", 0))
    with m4:
        st.metric("Reduction", f"{stats.get('reduction_percent', 0)}%")

    # Changed symbols
    changed = data.get("changed_symbols", [])
    if changed:
        st.markdown("#### Changed Symbols")
        for sym in changed[:20]:
            st.markdown(f"- `{sym}`")
        if len(changed) > 20:
            st.markdown(f"*... and {len(changed) - 20} more*")

    # Selected tests
    tests = data.get("selected_tests", [])
    if tests:
        st.markdown("#### Selected Tests")
        for t in tests[:20]:
            st.markdown(f"- `{t.get('id', t)}`")
        if len(tests) > 20:
            st.markdown(f"*... and {len(tests) - 20} more*")

    # Timings
    timings = data.get("timings", {})
    if timings:
        st.markdown("#### Timings")
        st.json(timings)