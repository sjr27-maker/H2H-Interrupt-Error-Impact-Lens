"""
ImpactLens Web Dashboard — Streamlit app.
Launch with: streamlit run app/dashboard.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

# ── Path Setup ──
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

# Setup sample repo (critical for cloud deployment)
try:
    from setup_for_cloud import ensure_sample_repo
    ensure_sample_repo()
except Exception as e:
    print(f"Sample repo setup: {e}")

from impactlens.core.registry import register_all_adapters
register_all_adapters()

# ── Page Config ──
st.set_page_config(
    page_title="ImpactLens",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        background: linear-gradient(135deg, #e17055, #fdcb6e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #888;
        margin-top: -8px;
        margin-bottom: 24px;
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2d3436;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    div[data-testid="metric-container"] label {
        color: #aaa !important;
        font-size: 0.8rem !important;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }

    /* Sidebar */
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0a14 0%, #0e1117 100%);
    }
    div[data-testid="stSidebar"] .stSelectbox label,
    div[data-testid="stSidebar"] .stTextInput label {
        color: #ccc !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }

    /* Expanders */
    details {
        border: 1px solid #2d3436 !important;
        border-radius: 8px !important;
        margin-bottom: 8px !important;
    }
    details summary {
        font-weight: 500 !important;
    }

    /* Graph container */
    .graph-frame {
        border: 1px solid #2d3436;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
    }

    /* Info/warning boxes */
    div[data-testid="stAlert"] {
        border-radius: 8px !important;
    }

    /* Dataframe */
    div[data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


# ── Clone directory ──
CLONE_DIR = Path(tempfile.gettempdir()) / "impactlens_clones"
CLONE_DIR.mkdir(exist_ok=True)


def clone_repo(url: str) -> Path | None:
    """Clone a git repo from URL. Uses shallow clone for speed."""
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    folder = f"{repo_name}_{hashlib.md5(url.encode()).hexdigest()[:8]}"
    dest = CLONE_DIR / folder

    if (dest / ".git").exists():
        return dest

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "20", "--single-branch", url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and (dest / ".git").exists():
            return dest
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def get_sample_repos() -> dict[str, Path]:
    """Discover available repositories."""
    repos = {}
    sample_dir = project_root / "sample_repos"
    if sample_dir.exists():
        for child in sorted(sample_dir.iterdir()):
            if child.is_dir() and (child / ".git").exists():
                repos[child.name] = child

    if CLONE_DIR.exists():
        for child in sorted(CLONE_DIR.iterdir()):
            if child.is_dir() and (child / ".git").exists():
                repos[f"{child.name} (cloned)"] = child

    return repos


def get_commits(repo_path: Path, max_count: int = 20) -> list[dict]:
    """Get recent commits."""
    try:
        from git import Repo
        repo = Repo(str(repo_path))
        commits = []
        for c in repo.iter_commits("HEAD", max_count=max_count):
            commits.append({
                "hash": str(c)[:8],
                "full_hash": str(c),
                "message": c.summary[:60],
            })
        return commits
    except Exception as e:
        st.error(f"Failed to read commits: {e}")
        return []


def run_pipeline(repo_path: Path, base: str, head: str):
    """Run the ImpactLens pipeline."""
    from impactlens.core.pipeline import run_analysis
    return run_analysis(repo_path, base, head, run_tests=False)


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ImpactLens")
    st.caption("_Change anything. Test only what matters._")
    st.divider()

    # ── Clone from URL ──
    st.markdown("**Analyze any Java repo**")
    git_url = st.text_input(
        "GitHub URL",
        placeholder="https://github.com/user/repo.git",
        label_visibility="collapsed",
    )

    clone_clicked = st.button("Clone & Load", use_container_width=True, disabled=not git_url)

    if clone_clicked and git_url:
        with st.spinner(f"Cloning {git_url.split('/')[-1]}..."):
            cloned = clone_repo(git_url)
            if cloned:
                st.success(f"Cloned successfully!")
                st.rerun()
            else:
                st.error("Clone failed. Check the URL and try again.")

    st.divider()

    # ── Repo selection ──
    repos = get_sample_repos()

    if not repos:
        st.warning("No repos available. Paste a GitHub URL above to get started.")

        # Show pre-computed results as fallback
        precomputed_dir = project_root / "docs" / "precomputed"
        if precomputed_dir.exists():
            for jf in precomputed_dir.glob("*.json"):
                try:
                    data = json.loads(jf.read_text())
                    st.markdown("---")
                    st.markdown(f"**Pre-computed: {data.get('repo', jf.stem)}**")
                    stats = data.get("stats", {})
                    st.metric("Symbols", stats.get("total_symbols", 0))
                    st.metric("Tests", stats.get("total_tests", 0))
                except Exception:
                    pass
        st.stop()

    repo_name = st.selectbox("Repository", options=list(repos.keys()))
    repo_path = repos[repo_name]

    st.divider()

    # ── Commits ──
    commits = get_commits(repo_path)

    if len(commits) < 2:
        st.warning("Need at least 2 commits.")
        st.stop()

    st.markdown("**Base commit** _(before)_")
    base_idx = st.selectbox(
        "Base", options=range(len(commits)),
        index=min(1, len(commits) - 1),
        format_func=lambda i: f"{commits[i]['hash']} — {commits[i]['message']}",
        label_visibility="collapsed",
    )

    st.markdown("**Head commit** _(after)_")
    head_idx = st.selectbox(
        "Head", options=range(len(commits)),
        index=0,
        format_func=lambda i: f"{commits[i]['hash']} — {commits[i]['message']}",
        label_visibility="collapsed",
    )

    if base_idx <= head_idx:
        st.error("Base must be older than Head.")
        st.stop()

    base_ref = commits[base_idx]["full_hash"]
    head_ref = commits[head_idx]["full_hash"]

    st.divider()

    # ── Quick demos ──
    if "java_demo" in repo_name and len(commits) >= 5:
        st.markdown("**Quick demos**")
        qc1, qc2 = st.columns(2)
        quick_demo = None
        with qc1:
            if st.button("Leaf change", use_container_width=True):
                quick_demo = ("HEAD~4", "HEAD~3")
            if st.button("New file", use_container_width=True):
                quick_demo = ("HEAD~2", "HEAD~1")
        with qc2:
            if st.button("Mid ripple", use_container_width=True):
                quick_demo = ("HEAD~3", "HEAD~2")
            if st.button("Multi-change", use_container_width=True):
                quick_demo = ("HEAD~1", "HEAD")

        if quick_demo:
            base_ref = quick_demo[0]
            head_ref = quick_demo[1]

        st.divider()

    # ── Analyze button ──
    analyze_clicked = st.button("Analyze Impact", type="primary", use_container_width=True)

    # ── LLM status ──
    from impactlens.ai.llm_client import get_llm_client
    llm = get_llm_client()
    if llm.is_available():
        st.success(f"AI: {llm.provider_name}", icon="🤖")
    else:
        st.info("AI: templates (no API key)", icon="📝")


# ══════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════
st.markdown('<p class="main-title">ImpactLens</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Impact analysis and selective test execution</p>', unsafe_allow_html=True)

# Run analysis
if analyze_clicked or (locals().get("quick_demo")):
    with st.spinner("Running impact analysis..."):
        try:
            t0 = time.time()
            result = run_pipeline(repo_path, base_ref, head_ref)
            st.session_state["result"] = result
            st.session_state["elapsed"] = time.time() - t0
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.stop()

# Display results
if "result" in st.session_state:
    result = st.session_state["result"]
    analysis = result.analysis
    impact = analysis.impact

    # ── Metrics ──
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Symbols", f"{analysis.total_symbols:,}")
    with m2:
        st.metric("Call Edges", f"{result.graph.edge_count:,}")
    with m3:
        st.metric("Changed", f"{len(impact.changed_symbols)}")
    with m4:
        st.metric("Impacted", f"{len(impact.impacted_symbols)}")
    with m5:
        if analysis.total_tests > 0:
            r = (1 - len(impact.selected_tests) / analysis.total_tests) * 100
            st.metric("Reduction", f"{r:.0f}%")
        else:
            st.metric("Tests", "0")

    st.divider()

    # ── Tabs ──
    tab_graph, tab_tests, tab_details, tab_timings = st.tabs([
        "🕸️ Call Graph",
        "🧪 Selected Tests",
        "📋 Impact Details",
        "⏱️ Timings",
    ])

    # ── TAB 1: Call Graph ──
    with tab_graph:
        st.markdown("### Interactive Call Graph")
        st.caption("**Red** = changed · **Orange** = impacted · **Green** = safe · Hover for details · Scroll to zoom · Drag to pan")

        st.markdown('<div class="graph-frame">', unsafe_allow_html=True)
        from graph_viz import render_call_graph
        render_call_graph(result.graph, impact)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── TAB 2: Selected Tests ──
    with tab_tests:
        if impact.selected_tests:
            tc = len(impact.selected_tests)
            tot = analysis.total_tests
            red = (1 - tc / tot) * 100 if tot > 0 else 0

            st.markdown(f"### {tc} of {tot} tests selected ({red:.0f}% reduction)")

            # Score lookup
            score_map = {}
            for s in result.scored_tests:
                score_map[s.test.id] = (s.confidence, s.match_method)

            # Pagination
            PAGE = 25
            pages = (tc + PAGE - 1) // PAGE
            if pages > 1:
                page = st.number_input("Page", 1, pages, 1)
                start = (page - 1) * PAGE
                end = min(start + PAGE, tc)
                st.caption(f"Showing {start+1}–{end} of {tc}")
            else:
                start, end = 0, tc

            for i, t in enumerate(impact.selected_tests[start:end], start + 1):
                conf, method = score_map.get(t.id, (0.0, "unknown"))
                justification = impact.reasoning.get(t.id, "")

                # Confidence color
                if conf >= 0.85:
                    badge = "🟢"
                elif conf >= 0.65:
                    badge = "🟡"
                else:
                    badge = "🔴"

                preview = justification[:100] + "..." if len(justification) > 100 else justification

                with st.expander(f"{badge} **{i}. {t.name}** — {conf:.0%} ({method})"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.markdown(f"**Test ID:** `{t.id}`")
                        st.markdown(f"**Confidence:** {conf:.0%}")
                        st.markdown(f"**Method:** {method}")
                        st.markdown(f"**File:** `{Path(t.file_path).name}`")
                    with c2:
                        st.markdown("**Why this test was selected:**")
                        st.info(justification if justification else "No justification generated.")
        else:
            st.warning("No tests were selected for this change.")

    # ── TAB 3: Impact Details ──
    with tab_details:
        st.markdown("### Changed Regions")
        if analysis.changed_regions:
            rows = []
            for r in analysis.changed_regions:
                rows.append({
                    "File": r.file_path.split("/")[-1],
                    "Path": r.file_path,
                    "Change": r.change_type.value,
                    "Old": f"{r.old_range.start}-{r.old_range.end}" if r.old_range else "—",
                    "New": f"{r.new_range.start}-{r.new_range.end}" if r.new_range else "—",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

        col_changed, col_impacted = st.columns(2)

        with col_changed:
            st.markdown("### Changed Symbols")
            for sid in impact.changed_symbols:
                sym = result.graph.get_symbol(sid)
                if sym:
                    st.markdown(f"🔴 `{sym.name}` _{sym.kind.value}_ in `{Path(sym.file_path).name}`")

        with col_impacted:
            st.markdown("### Impacted (transitive)")
            transitive = sorted(set(impact.impacted_symbols) - set(impact.changed_symbols))
            if transitive:
                for sid in transitive[:30]:
                    sym = result.graph.get_symbol(sid)
                    if sym:
                        st.markdown(f"🟠 `{sym.name}` _{sym.kind.value}_")
                if len(transitive) > 30:
                    st.caption(f"... and {len(transitive) - 30} more")
            else:
                st.info("No transitive impact — changes are isolated.")

    # ── TAB 4: Timings ──
    with tab_timings:
        st.markdown("### Pipeline Performance")

        t = result.timings
        timing_rows = [
            {"Stage": "Diff Extraction", "Duration (ms)": round(t.diff_ms)},
            {"Stage": "Parsing", "Duration (ms)": round(t.parse_ms)},
            {"Stage": "Graph Building", "Duration (ms)": round(t.graph_ms)},
            {"Stage": "Impact Analysis", "Duration (ms)": round(t.impact_ms)},
            {"Stage": "Test Mapping", "Duration (ms)": round(t.mapping_ms)},
            {"Stage": "Total", "Duration (ms)": round(t.total_ms)},
        ]
        st.dataframe(timing_rows, use_container_width=True, hide_index=True)

        import pandas as pd
        chart = pd.DataFrame({
            "Stage": ["Diff", "Parse", "Graph", "Impact", "Mapping"],
            "Time (ms)": [t.diff_ms, t.parse_ms, t.graph_ms, t.impact_ms, t.mapping_ms],
        })
        st.bar_chart(chart.set_index("Stage"))

        if analysis.total_tests > 0:
            st.markdown("### Test Reduction")
            sel = len(impact.selected_tests)
            skip = analysis.total_tests - sel
            red_df = pd.DataFrame({
                "Category": ["Will Run", "Skipped"],
                "Tests": [sel, skip],
            })
            st.bar_chart(red_df.set_index("Category"))

        # Export
        st.divider()
        export = {
            "repo": str(repo_path),
            "changed_symbols": impact.changed_symbols,
            "impacted_files": impact.impacted_files,
            "selected_tests": [{"id": t.id, "confidence": score_map.get(t.id, (0,))[0]} for t in impact.selected_tests],
            "timings": result.timings.summary(),
        }
        st.download_button("Download JSON", json.dumps(export, indent=2), "impactlens_results.json", "application/json")

else:
    # ── Landing Page ──
    st.markdown("""
    ### Getting Started

    1. **Select a repository** from the sidebar — or paste a GitHub URL to clone one
    2. **Pick two commits** — base (before) and head (after)
    3. **Click "Analyze Impact"** to run the pipeline
    4. **Explore** — call graph, tests, impact details, timings

    Use the **Quick demo** buttons for instant pre-configured scenarios.

    ---

    **What ImpactLens does:** Given a code change in a Java repository, ImpactLens traces
    the blast radius through the call graph, selects only the tests that exercise affected code,
    and explains why each test was chosen — reducing test suite runtime by up to 73%.
    """)