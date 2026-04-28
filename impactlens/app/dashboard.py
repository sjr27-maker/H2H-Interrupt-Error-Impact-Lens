"""
ImpactLens Web Dashboard
Launch: streamlit run app/dashboard.py
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

# ── Paths ──
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

# ── Setup sample repo on cloud ──
try:
    from setup_for_cloud import ensure_sample_repo
    ensure_sample_repo()
except Exception as e:
    print(f"Setup: {e}")

from impactlens.core.registry import register_all_adapters
register_all_adapters()

# ── Config ──
st.set_page_config(page_title="ImpactLens", page_icon="AS", layout="wide", initial_sidebar_state="expanded")

CLONE_DIR = Path(tempfile.gettempdir()) / "impactlens_clones"
CLONE_DIR.mkdir(exist_ok=True)

# Small repos that actually work for demos
SUGGESTED_REPOS = {
    "Apache Commons Text": "https://github.com/apache/commons-text.git",
    "Google Gson": "https://github.com/google/gson.git",
    "Square Moshi": "https://github.com/square/moshi.git",
    "Joda Money": "https://github.com/JodaOrg/joda-money.git",
}

# ── CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }

/* Header */
.hero { text-align:center; padding:10px 0 20px; }
.hero h1 {
    font-size:2.6rem; font-weight:700;
    background:linear-gradient(135deg,#e17055,#fdcb6e,#00b894);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    margin:0;
}
.hero p { color:#888; font-size:1rem; margin-top:-4px; }

/* Metrics */
div[data-testid="metric-container"] {
    background:linear-gradient(145deg,#141422,#1a1a2e);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:14px; padding:18px;
    box-shadow:0 8px 25px rgba(0,0,0,0.3);
}
div[data-testid="metric-container"] label { color:#999 !important; font-size:0.78rem !important; text-transform:uppercase; letter-spacing:0.5px; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size:1.9rem !important; font-weight:700 !important; }

/* Sidebar */
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#080810,#0e1117) !important; }
section[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,0.06) !important; }

/* Tabs */
button[data-baseweb="tab"] { font-weight:600 !important; }

/* Cards */
.card {
    background:linear-gradient(145deg,#141422,#1a1a2e);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:14px; padding:20px;
    box-shadow:0 4px 20px rgba(0,0,0,0.25);
    margin-bottom:16px;
}

/* Expanders */
details { border:1px solid rgba(255,255,255,0.08) !important; border-radius:10px !important; margin-bottom:6px !important; }
details[open] { border-color:rgba(225,112,85,0.3) !important; }

/* Buttons */
.stButton>button { border-radius:10px !important; font-weight:600 !important; transition:all 0.2s !important; }
.stButton>button:hover { transform:translateY(-1px) !important; box-shadow:0 6px 20px rgba(0,0,0,0.3) !important; }

/* Graph frame */
.graph-wrap {
    border:1px solid rgba(255,255,255,0.08);
    border-radius:14px; overflow:hidden;
    box-shadow:0 8px 30px rgba(0,0,0,0.4);
}

/* Quick demo chips */
.demo-chip {
    display:inline-block; padding:6px 14px;
    background:rgba(225,112,85,0.15); border:1px solid rgba(225,112,85,0.3);
    border-radius:20px; color:#e17055; font-size:0.8rem; font-weight:600;
    margin:2px;
}

/* Reduce top padding */
.block-container { padding-top:1.5rem !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def clone_repo(url: str, progress_bar=None) -> Path | None:
    """Clone with depth limit, timeout, and progress feedback."""
    name = url.rstrip("/").split("/")[-1].replace(".git", "")
    folder = f"{name}_{hashlib.md5(url.encode()).hexdigest()[:6]}"
    dest = CLONE_DIR / folder

    if (dest / ".git").exists():
        return dest

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    try:
        if progress_bar:
            progress_bar.progress(10, "Starting clone...")

        proc = subprocess.Popen(
            ["git", "clone", "--depth", "15", "--single-branch", "--no-tags", url, str(dest)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        # Wait with timeout
        start = time.time()
        while proc.poll() is None:
            elapsed = time.time() - start
            if elapsed > 45:
                proc.kill()
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                return None
            if progress_bar:
                pct = min(80, int(10 + elapsed * 1.5))
                progress_bar.progress(pct, f"Cloning... ({elapsed:.0f}s)")
            time.sleep(0.5)

        if progress_bar:
            progress_bar.progress(90, "Verifying...")

        if proc.returncode == 0 and (dest / ".git").exists():
            if progress_bar:
                progress_bar.progress(100, "Done!")
            return dest

        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        return None

    except Exception:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        return None


def get_repos() -> dict[str, Path]:
    repos = {}
    sd = project_root / "sample_repos"
    if sd.exists():
        for c in sorted(sd.iterdir()):
            if c.is_dir() and (c / ".git").exists():
                repos[c.name] = c
    if CLONE_DIR.exists():
        for c in sorted(CLONE_DIR.iterdir()):
            if c.is_dir() and (c / ".git").exists():
                repos[f"{c.name} (cloned)"] = c
    return repos


def get_commits(repo_path: Path, n: int = 20) -> list[dict]:
    try:
        from git import Repo
        return [
            {"hash": str(c)[:8], "full": str(c), "msg": c.summary[:55]}
            for c in Repo(str(repo_path)).iter_commits("HEAD", max_count=n)
        ]
    except Exception as e:
        return []


def run_pipeline(repo_path, base, head):
    from impactlens.core.pipeline import run_analysis
    return run_analysis(repo_path, base, head, run_tests=False)


# ══════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🎯 ImpactLens")
    st.caption("Change anything. Test only what matters.")
    st.divider()

    # ── Clone Section ──
    st.markdown("**Analyze external repo**")

    # Suggested repos dropdown
    selected_suggestion = st.selectbox(
        "Quick pick a repo",
        options=["(paste your own)"] + list(SUGGESTED_REPOS.keys()),
        label_visibility="collapsed",
    )

    if selected_suggestion != "(paste your own)":
        clone_url = SUGGESTED_REPOS[selected_suggestion]
    else:
        clone_url = ""

    git_url = st.text_input(
        "Or paste GitHub URL",
        value=clone_url,
        placeholder="https://github.com/user/repo.git",
        label_visibility="collapsed",
    )

    clone_btn = st.button("Clone & Load", use_container_width=True, disabled=not git_url)

    if clone_btn and git_url:
        progress = st.progress(0, "Preparing...")
        cloned = clone_repo(git_url, progress)
        if cloned:
            st.success("Repository cloned!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Clone failed — repo may be too large (>100MB) or URL is invalid. Try one of the suggested repos.")

    st.divider()

    # ── Repo Selector ──
    repos = get_repos()

    if not repos:
        st.warning("No repos available yet.")
        st.caption("Use the clone feature above, or the setup will create a demo repo on next reload.")
        if st.button("Reload", use_container_width=True):
            st.rerun()
        st.stop()

    st.markdown("**Repository**")
    repo_name = st.selectbox("Repo", options=list(repos.keys()), label_visibility="collapsed")
    repo_path = repos[repo_name]

    # ── Commits ──
    commits = get_commits(repo_path)
    if len(commits) < 2:
        st.warning("Need at least 2 commits to diff.")
        st.stop()

    st.markdown("**Base** _(before change)_")
    base_idx = st.selectbox(
        "base", range(len(commits)), index=min(1, len(commits)-1),
        format_func=lambda i: f"{commits[i]['hash']} — {commits[i]['msg']}",
        label_visibility="collapsed",
    )

    st.markdown("**Head** _(after change)_")
    head_idx = st.selectbox(
        "head", range(len(commits)), index=0,
        format_func=lambda i: f"{commits[i]['hash']} — {commits[i]['msg']}",
        label_visibility="collapsed",
    )

    if base_idx <= head_idx:
        st.error("Base must be older than Head.")
        st.stop()

    base_ref = commits[base_idx]["full"]
    head_ref = commits[head_idx]["full"]

    st.divider()

    # ── Quick Demos (always show for java_demo) ──
    quick_demo = None
    if "java_demo" in repo_name and len(commits) >= 5:
        st.markdown("**Quick demos**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🍃 Leaf", use_container_width=True, help="PriceFormatter change → 73% reduction"):
                quick_demo = ("HEAD~4", "HEAD~3")
            if st.button("📄 New file", use_container_width=True, help="CurrencyConverter added"):
                quick_demo = ("HEAD~2", "HEAD~1")
        with c2:
            if st.button("🌊 Ripple", use_container_width=True, help="DiscountCalculator mid-level change"):
                quick_demo = ("HEAD~3", "HEAD~2")
            if st.button("⚡ Multi", use_container_width=True, help="TaxCalculator + CheckoutHandler"):
                quick_demo = ("HEAD~1", "HEAD")

        if quick_demo:
            base_ref, head_ref = quick_demo

        st.divider()

    # ── Analyze ──
    analyze_btn = st.button("Analyze Impact", type="primary", use_container_width=True)

    # LLM status
    from impactlens.ai.llm_client import get_llm_client
    llm = get_llm_client()
    if llm.is_available():
        st.success(f"AI: {llm.provider_name}", icon="🤖")
    else:
        st.info("AI: templates only", icon="📝")


# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════

# Header
st.markdown("""
<div class="hero">
    <h1>ImpactLens</h1>
    <p>Impact analysis and selective test execution for Java codebases</p>
</div>
""", unsafe_allow_html=True)

# Run
if analyze_btn or quick_demo:
    with st.spinner("Analyzing..."):
        try:
            result = run_pipeline(repo_path, base_ref, head_ref)
            st.session_state["result"] = result
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

# Results
if "result" not in st.session_state:
    # Landing
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.markdown("""
        ### How it works

        1. **Select a repository** from the sidebar — or clone one from GitHub
        2. **Pick two commits** — a base (before) and head (after)
        3. **Click "Analyze Impact"** to trace the blast radius
        4. **Explore results** — interactive call graph, selected tests, timing breakdown

        ImpactLens parses your Java codebase, builds a call graph, and uses reverse BFS
        to find every function affected by your change. Then it selects only the tests
        that exercise that code — typically reducing test runtime by **50-73%**.
        """)
    with col_r:
        st.markdown("""
        ### Try a quick demo

        Select **java_demo** in the sidebar and click any quick demo button:

        - **Leaf** — change a utility, see minimal blast radius
        - **Ripple** — change a mid-level class, watch it propagate
        - **New file** — add a class, see isolated impact
        - **Multi** — change two files, see the widest blast radius
        """)
    st.stop()

result = st.session_state["result"]
analysis = result.analysis
impact = analysis.impact

# ── Metrics ──
m1, m2, m3, m4, m5 = st.columns(5)
with m1: st.metric("Symbols", f"{analysis.total_symbols:,}")
with m2: st.metric("Call Edges", f"{result.graph.edge_count:,}")
with m3: st.metric("Changed", f"{len(impact.changed_symbols)}")
with m4: st.metric("Impacted", f"{len(impact.impacted_symbols)}")
with m5:
    if analysis.total_tests > 0:
        r = (1 - len(impact.selected_tests) / analysis.total_tests) * 100
        st.metric("Reduction", f"{r:.0f}%")
    else:
        st.metric("Tests", "0")

st.markdown("")

# ── Tabs ──
tab_graph, tab_tests, tab_details, tab_timings = st.tabs([
    "🕸️  Call Graph", "🧪  Selected Tests", "📋  Impact Details", "⏱️  Timings"
])

# TAB 1: Graph
with tab_graph:
    if result.graph.node_count > 0:
        st.caption("Red = changed · Orange = impacted · Green = safe · **Hover** to highlight connections · **Scroll** to zoom · **Drag** to pan")
        st.markdown('<div class="graph-wrap">', unsafe_allow_html=True)
        from graph_viz import render_call_graph
        render_call_graph(result.graph, impact)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No symbols in the call graph for this diff.")

# TAB 2: Tests
with tab_tests:
    if not impact.selected_tests:
        st.warning("No tests were selected — the change may not affect any Java source code.")
        st.stop()

    tc = len(impact.selected_tests)
    tot = analysis.total_tests
    red = (1 - tc / tot) * 100 if tot > 0 else 0

    st.markdown(f"### {tc} of {tot} tests selected — {red:.0f}% reduction")

    score_map = {s.test.id: (s.confidence, s.match_method) for s in result.scored_tests}

    PAGE = 20
    pages = max(1, (tc + PAGE - 1) // PAGE)
    if pages > 1:
        page = st.number_input("Page", 1, pages, 1)
        start, end = (page-1)*PAGE, min(page*PAGE, tc)
        st.caption(f"Showing {start+1}–{end} of {tc}")
    else:
        start, end = 0, tc

    for i, t in enumerate(impact.selected_tests[start:end], start+1):
        conf, method = score_map.get(t.id, (0.0, "?"))
        justification = impact.reasoning.get(t.id, "No justification available.")
        badge = "🟢" if conf >= 0.85 else ("🟡" if conf >= 0.65 else "🔴")

        with st.expander(f"{badge}  **{i}. {t.name}** — {conf:.0%} · {method}"):
            left, right = st.columns([2, 3])
            with left:
                st.markdown(f"`{t.id}`")
                st.markdown(f"**Confidence:** {conf:.0%}  \n**Method:** {method}  \n**File:** `{Path(t.file_path).name}`")
            with right:
                st.markdown("**Why this test was selected:**")
                st.info(justification)

# TAB 3: Details
with tab_details:
    if analysis.changed_regions:
        st.markdown("### Changed Regions")
        st.dataframe(
            [{"File": r.file_path.split("/")[-1], "Change": r.change_type.value,
              "Old": f"{r.old_range.start}-{r.old_range.end}" if r.old_range else "—",
              "New": f"{r.new_range.start}-{r.new_range.end}" if r.new_range else "—"}
             for r in analysis.changed_regions],
            use_container_width=True, hide_index=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Changed Symbols")
        for sid in impact.changed_symbols[:20]:
            sym = result.graph.get_symbol(sid)
            st.markdown(f"🔴 `{sym.name}` _{sym.kind.value}_" if sym else f"🔴 `{sid}`")

    with c2:
        st.markdown("### Transitive Impact")
        trans = sorted(set(impact.impacted_symbols) - set(impact.changed_symbols))
        for sid in trans[:20]:
            sym = result.graph.get_symbol(sid)
            st.markdown(f"🟠 `{sym.name}` _{sym.kind.value}_" if sym else f"🟠 `{sid}`")
        if len(trans) > 20:
            st.caption(f"+ {len(trans)-20} more")
        if not trans:
            st.info("No transitive impact — changes are isolated.")

# TAB 4: Timings
# ═══════════════════════════════════════════
# REPLACE YOUR ENTIRE TIMINGS TAB WITH THIS
# Find: "# TAB 4: Timings" or "with tab_timings:"
# Replace everything inside that tab block
# ═══════════════════════════════════════════

# TAB 4: Timings
with tab_timings:
    t = result.timings

    st.markdown("### Pipeline Performance")

    # Timing table — use a simple list of dicts
    timing_rows = [
        {"Stage": "Diff Extraction", "Duration (ms)": int(t.diff_ms)},
        {"Stage": "Parsing", "Duration (ms)": int(t.parse_ms)},
        {"Stage": "Graph Building", "Duration (ms)": int(t.graph_ms)},
        {"Stage": "Impact Analysis", "Duration (ms)": int(t.impact_ms)},
        {"Stage": "Test Mapping", "Duration (ms)": int(t.mapping_ms)},
        {"Stage": "**Total**", "Duration (ms)": int(t.total_ms)},
    ]
    st.dataframe(timing_rows, use_container_width=True, hide_index=True)

    # Bar chart — use st.columns with st.progress bars instead of st.bar_chart
    # This avoids the Altair/vega compatibility crash entirely
    st.markdown("### Stage Breakdown")

    max_time = max(t.diff_ms, t.parse_ms, t.graph_ms, t.impact_ms, t.mapping_ms, 1)
    stages = [
        ("Diff", t.diff_ms, "#74b9ff"),
        ("Parse", t.parse_ms, "#a29bfe"),
        ("Graph", t.graph_ms, "#55efc4"),
        ("Impact", t.impact_ms, "#fdcb6e"),
        ("Mapping", t.mapping_ms, "#fab1a0"),
    ]

    for name, ms, color in stages:
        pct = ms / max_time
        col_label, col_bar, col_val = st.columns([1, 4, 1])
        with col_label:
            st.markdown(f"**{name}**")
        with col_bar:
            st.progress(min(pct, 1.0))
        with col_val:
            st.markdown(f"`{int(ms)}ms`")

    # Test reduction — also use progress bars
    if analysis.total_tests > 0:
        st.markdown("### Test Reduction")
        sel = len(impact.selected_tests)
        total = analysis.total_tests
        skipped = total - sel
        red_pct = (1 - sel / total) * 100

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Tests to Run", f"{sel}")
            st.caption(f"of {total} total")
        with col_b:
            st.metric("Tests Skipped", f"{skipped}")
            st.caption(f"{red_pct:.0f}% reduction")

    # Export
    st.divider()
    export = {
        "changed": impact.changed_symbols,
        "impacted_files": impact.impacted_files,
        "tests": [{"id": tc.id, "conf": score_map.get(tc.id, (0,))[0]} for tc in impact.selected_tests],
        "timings": result.timings.summary(),
    }
    st.download_button("Download JSON", json.dumps(export, indent=2), "results.json", "application/json")