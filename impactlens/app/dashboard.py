"""
ImpactLens Web Dashboard — Streamlit app.

Launch with: streamlit run app/dashboard.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

from impactlens.core.registry import register_all_adapters

# Register adapters once
register_all_adapters()

# ── Page Config ──
st.set_page_config(
    page_title="ImpactLens",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #888;
        margin-top: -10px;
        margin-bottom: 20px;
    }
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 15px 20px;
        text-align: center;
        border: 1px solid #333;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #00b894;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #aaa;
        margin-top: 4px;
    }
    .blast-tag-changed {
        background: #d63031;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .blast-tag-impacted {
        background: #e17055;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .blast-tag-safe {
        background: #00b894;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .confidence-high { color: #00b894; font-weight: bold; }
    .confidence-mid  { color: #fdcb6e; font-weight: bold; }
    .confidence-low  { color: #d63031; font-weight: bold; }
    div[data-testid="stSidebar"] {
        background: #0e1117;
    }
</style>
""", unsafe_allow_html=True)


def get_sample_repos() -> dict[str, Path]:
    """Discover available sample repositories."""
    repos = {}
    sample_dir = project_root / "sample_repos"
    if not sample_dir.exists():
        return repos

    for child in sorted(sample_dir.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            repos[child.name] = child

    return repos


def get_commits(repo_path: Path, max_count: int = 20) -> list[dict]:
    """Get recent commits from a repo."""
    try:
        from git import Repo
        repo = Repo(str(repo_path))
        commits = []
        for c in repo.iter_commits("HEAD", max_count=max_count):
            commits.append({
                "hash": str(c)[:8],
                "full_hash": str(c),
                "message": c.summary[:80],
                "author": str(c.author),
                "date": c.committed_datetime.strftime("%Y-%m-%d %H:%M"),
            })
        return commits
    except Exception as e:
        st.error(f"Failed to read commits: {e}")
        return []


def run_pipeline(repo_path: Path, base: str, head: str):
    """Run the ImpactLens pipeline and return results."""
    from impactlens.core.pipeline import run_analysis
    return run_analysis(repo_path, base, head, run_tests=False)


# ── Sidebar ──
with st.sidebar:
    st.markdown("## ImpactLens")
    st.markdown("*Change anything. Test only what matters.*")
    st.divider()

    # Repo selection
    repos = get_sample_repos()

    if not repos:
        st.warning("No sample repos found. Run `scripts/setup_sample_repo.sh`")
        st.stop()

    repo_name = st.selectbox(
        "Repository",
        options=list(repos.keys()),
        format_func=lambda x: f"{x} ({'demo' if 'demo' in x else 'real-world'})",
    )
    repo_path = repos[repo_name]

    st.divider()
    st.markdown("**Pre-computed analyses**")
    from app.precomputed import get_precomputed_results, render_precomputed

    precomputed = get_precomputed_results()
    if precomputed:
        precomputed_name = st.selectbox(
            "View cached analysis",
            options=["(none)"] + list(precomputed.keys()),
            label_visibility="collapsed",
        )
        if precomputed_name != "(none)":
            st.session_state["show_precomputed"] = precomputed_name
    else:
        st.caption("No pre-computed results available.")

    # Commit selection
    commits = get_commits(repo_path)

    if len(commits) < 2:
        st.warning("Need at least 2 commits to analyze.")
        st.stop()

    st.markdown("**Base commit** (before change)")
    base_idx = st.selectbox(
        "Base",
        options=range(len(commits)),
        index=min(1, len(commits) - 1),
        format_func=lambda i: f"{commits[i]['hash']} — {commits[i]['message']}",
        label_visibility="collapsed",
    )

    st.markdown("**Head commit** (after change)")
    head_idx = st.selectbox(
        "Head",
        options=range(len(commits)),
        index=0,
        format_func=lambda i: f"{commits[i]['hash']} — {commits[i]['message']}",
        label_visibility="collapsed",
    )

    if base_idx <= head_idx:
        st.error("Base must be an older commit than Head.")
        st.stop()

    base_ref = commits[base_idx]["full_hash"]
    head_ref = commits[head_idx]["full_hash"]

    st.divider()

    # Quick demo buttons
    st.markdown("**Quick demos**")
    col1, col2 = st.columns(2)

    quick_demo = None
    if repo_name == "java_demo" and len(commits) >= 5:
        with col1:
            if st.button("Leaf change", use_container_width=True):
                quick_demo = ("HEAD~4", "HEAD~3")
            if st.button("New file", use_container_width=True):
                quick_demo = ("HEAD~2", "HEAD~1")
        with col2:
            if st.button("Mid ripple", use_container_width=True):
                quick_demo = ("HEAD~3", "HEAD~2")
            if st.button("Multi-change", use_container_width=True):
                quick_demo = ("HEAD~1", "HEAD")

    if quick_demo:
        base_ref = quick_demo[0]
        head_ref = quick_demo[1]

    st.divider()

    # Analyze button
    analyze_clicked = st.button(
        "Analyze Impact",
        type="primary",
        use_container_width=True,
    )

    # LLM status
    from impactlens.ai.llm_client import get_llm_client
    client = get_llm_client()
    if client.is_available():
        st.success(f"AI: {client.provider_name}", icon="🤖")
    else:
        st.info("AI: templates only (no API key)", icon="📝")


# ── Main Content ──
st.markdown('<p class="main-header">ImpactLens</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Impact analysis and selective test execution</p>', unsafe_allow_html=True)

# Check if we should run analysis
if analyze_clicked or quick_demo:
    with st.spinner("Running impact analysis..."):
        start = time.time()
        try:
            result = run_pipeline(repo_path, base_ref, head_ref)
            elapsed = time.time() - start
            st.session_state["result"] = result
            st.session_state["elapsed"] = elapsed
            st.session_state["repo_name"] = repo_name
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

# Show pre-computed results if selected
if st.session_state.get("show_precomputed"):
    name = st.session_state["show_precomputed"]
    precomputed = get_precomputed_results()
    if name in precomputed:
        render_precomputed(precomputed[name])
        st.divider()

# Display results if available
if "result" in st.session_state:
    result = st.session_state["result"]
    elapsed = st.session_state["elapsed"]
    analysis = result.analysis
    impact = analysis.impact

    # ── Metrics Row ──
    m1, m2, m3, m4, m5 = st.columns(5)

    with m1:
        st.metric("Symbols Parsed", f"{analysis.total_symbols}")
    with m2:
        st.metric("Call Edges", f"{result.graph.edge_count}")
    with m3:
        st.metric("Changed", f"{len(impact.changed_symbols)}")
    with m4:
        st.metric("Impacted", f"{len(impact.impacted_symbols)}")
    with m5:
        if analysis.total_tests > 0:
            reduction = (1 - len(impact.selected_tests) / analysis.total_tests) * 100
            st.metric("Reduction", f"{reduction:.0f}%")
        else:
            st.metric("Reduction", "N/A")

    st.divider()

    # ── Tabs ──
    tab_graph, tab_tests, tab_details, tab_timings = st.tabs([
        "Call Graph",
        "Selected Tests",
        "Impact Details",
        "Timings",
    ])

    # ── TAB 1: Call Graph ──
    with tab_graph:
        st.markdown("### Interactive Call Graph")
        st.markdown("Red = changed, Orange = impacted, Green = safe. Hover for details.")

        from app.graph_viz import render_call_graph
        render_call_graph(result.graph, impact)

    # ── TAB 2: Selected Tests ──
    with tab_tests:
        st.markdown("### Selected Tests")

        if impact.selected_tests:
            test_count = len(impact.selected_tests)
            total = analysis.total_tests
            st.markdown(f"**{test_count}** of **{total}** tests selected "
                        f"(**{(1 - test_count/total)*100:.0f}%** reduction)")

            # Build score lookup
            score_lookup = {}
            for st_item in result.scored_tests:
                score_lookup[st_item.test.id] = (st_item.confidence, st_item.match_method)

            for i, t in enumerate(impact.selected_tests):
                conf, method = score_lookup.get(t.id, (0.0, "unknown"))
                justification = impact.reasoning.get(t.id, "No justification available")

                # Color for confidence
                if conf >= 0.85:
                    conf_color = "confidence-high"
                elif conf >= 0.65:
                    conf_color = "confidence-mid"
                else:
                    conf_color = "confidence-low"

                with st.expander(f"**{i+1}. {t.id}**  —  {conf:.0%} confidence"):
                    col_a, col_b = st.columns([1, 3])
                    with col_a:
                        st.markdown(f"**Confidence:** `{conf:.0%}`")
                        st.markdown(f"**Method:** `{method}`")
                        st.markdown(f"**File:** `{t.file_path}`")
                    with col_b:
                        st.markdown("**Justification:**")
                        st.info(justification)
        else:
            st.warning("No tests were selected for this change.")

    # ── TAB 3: Impact Details ──
    with tab_details:
        st.markdown("### Changed Regions")

        if analysis.changed_regions:
            regions_data = []
            for r in analysis.changed_regions:
                old_str = f"{r.old_range.start}-{r.old_range.end}" if r.old_range else "—"
                new_str = f"{r.new_range.start}-{r.new_range.end}" if r.new_range else "—"
                regions_data.append({
                    "File": r.file_path,
                    "Change": r.change_type.value,
                    "Old Range": old_str,
                    "New Range": new_str,
                })
            st.dataframe(regions_data, use_container_width=True, hide_index=True)

        st.markdown("### Changed Symbols")
        for sym_id in impact.changed_symbols:
            sym = result.graph.get_symbol(sym_id)
            if sym:
                st.markdown(f"- `{sym.qualified_name}` ({sym.kind.value}) in `{sym.file_path}`")
            else:
                st.markdown(f"- `{sym_id}`")

        st.markdown("### Impacted Symbols (transitive)")
        transitive = set(impact.impacted_symbols) - set(impact.changed_symbols)
        if transitive:
            for sym_id in sorted(transitive):
                sym = result.graph.get_symbol(sym_id)
                if sym:
                    st.markdown(f"- `{sym.qualified_name}` ({sym.kind.value})")
                else:
                    st.markdown(f"- `{sym_id}`")
        else:
            st.info("No transitive impact — changes are isolated.")

        st.markdown("### Impacted Files")
        for f in impact.impacted_files:
            st.markdown(f"- `{f}`")

    # ── TAB 4: Timings ──
    with tab_timings:
        st.markdown("### Pipeline Performance")

        timings = result.timings
        timing_data = {
            "Stage": ["Diff Extraction", "Parsing", "Graph Building",
                      "Impact Analysis", "Test Mapping", "Total"],
            "Duration": [
                f"{timings.diff_ms:.0f}ms",
                f"{timings.parse_ms:.0f}ms",
                f"{timings.graph_ms:.0f}ms",
                f"{timings.impact_ms:.0f}ms",
                f"{timings.mapping_ms:.0f}ms",
                f"{timings.total_ms:.0f}ms",
            ],
        }
        st.dataframe(timing_data, use_container_width=True, hide_index=True)

        # Bar chart
        import pandas as pd
        chart_data = pd.DataFrame({
            "Stage": ["Diff", "Parse", "Graph", "Impact", "Mapping"],
            "Time (ms)": [
                timings.diff_ms, timings.parse_ms, timings.graph_ms,
                timings.impact_ms, timings.mapping_ms,
            ],
        })
        st.bar_chart(chart_data.set_index("Stage"))

        # Test reduction visual
        if analysis.total_tests > 0:
            st.markdown("### Test Reduction")
            selected = len(impact.selected_tests)
            skipped = analysis.total_tests - selected

            reduction_data = pd.DataFrame({
                "Category": ["Selected (will run)", "Skipped (not impacted)"],
                "Count": [selected, skipped],
            })
            st.bar_chart(reduction_data.set_index("Category"))

else:
    # Landing page
    st.markdown("""
    ### How to use

    1. **Select a repository** from the sidebar
    2. **Pick two commits** — a base (before) and head (after)
    3. **Click "Analyze Impact"** to run the pipeline
    4. **Explore results** — call graph, selected tests, impact details

    Or use the **Quick demo** buttons to analyze pre-configured scenarios.

    ---

    **What ImpactLens does:**

    Given a code change in a Java repository, ImpactLens identifies which functions
    are affected (the "blast radius") and selects only the tests that exercise
    that code. The result: run 3 tests instead of 11, saving 73% of test time.
    """)