"""
Interactive call graph visualization using pyvis.

Renders the call graph with color-coded nodes:
- Red:    directly changed symbols
- Orange: transitively impacted symbols
- Green:  safe (not in blast radius)
- Blue:   test files
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from impactlens.core.models import ImpactResult, SymbolKind
from impactlens.graph.call_graph import CallGraph


def render_call_graph(
    graph: CallGraph,
    impact: ImpactResult,
    height: str = "520px",
) -> None:
    """Render an interactive call graph in Streamlit with fullscreen support."""

    changed_set = set(impact.changed_symbols)
    impacted_set = set(impact.impacted_symbols)

    # Create pyvis network
    net = Network(
        height=height,
        width="100%",
        directed=True,
        bgcolor="#0e1117",
        font_color="white",
        select_menu=False,
        filter_menu=False,
    )

    net.set_options("""
    {
        "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
                "gravitationalConstant": -80,
                "centralGravity": 0.01,
                "springLength": 120,
                "springConstant": 0.08
            },
            "stabilization": { "iterations": 100 }
        },
        "edges": {
            "arrows": { "to": { "enabled": true, "scaleFactor": 0.5 } },
            "color": { "color": "#555", "highlight": "#fff" },
            "smooth": { "type": "continuous" }
        },
        "nodes": {
            "font": { "size": 12, "color": "white" },
            "borderWidth": 2,
            "borderWidthSelected": 3
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "zoomView": true,
            "dragView": true
        }
    }
    """)

    nx_graph = graph.graph

    max_nodes = 100
    nodes_to_show = set()
    nodes_to_show.update(changed_set)
    nodes_to_show.update(impacted_set)

    for node in list(nodes_to_show):
        if node in nx_graph:
            nodes_to_show.update(nx_graph.predecessors(node))
            nodes_to_show.update(nx_graph.successors(node))

    if len(nodes_to_show) < max_nodes:
        for node in nx_graph.nodes():
            if len(nodes_to_show) >= max_nodes:
                break
            nodes_to_show.add(node)

    for node_id in nodes_to_show:
        if node_id not in nx_graph:
            continue
        sym = graph.get_symbol(node_id)
        if not sym:
            continue

        if node_id in changed_set:
            color, size, border_color = "#d63031", 30, "#ff7675"
        elif node_id in impacted_set:
            color, size, border_color = "#e17055", 25, "#fab1a0"
        elif "test" in sym.file_path.lower() or "Test" in sym.name:
            color, size, border_color = "#0984e3", 20, "#74b9ff"
        else:
            color, size, border_color = "#00b894", 18, "#55efc4"

        if sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE):
            shape = "diamond"
        elif sym.kind == SymbolKind.CONSTRUCTOR:
            shape = "triangle"
        else:
            shape = "dot"

        status = "CHANGED" if node_id in changed_set else (
            "IMPACTED" if node_id in impacted_set else "safe")

        title = (
            f"<b>{sym.qualified_name}</b><br>"
            f"Kind: {sym.kind.value}<br>"
            f"File: {sym.file_path}<br>"
            f"Lines: {sym.start_line}-{sym.end_line}<br>"
            f"Status: <b>{status}</b>"
        )

        net.add_node(
            node_id, label=sym.name, title=title,
            color={"background": color, "border": border_color},
            size=size, shape=shape,
        )

    for u, v in nx_graph.edges():
        if u in nodes_to_show and v in nodes_to_show:
            if u in impacted_set and v in impacted_set:
                edge_color, width = "#e17055", 2
            elif u in impacted_set or v in impacted_set:
                edge_color, width = "#fdcb6e", 1.5
            else:
                edge_color, width = "#555", 1
            net.add_edge(u, v, color=edge_color, width=width)

    # Save and read HTML
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        net.save_graph(f.name)
        html_content = Path(f.name).read_text()

    # Count stats
    node_count = len([n for n in nodes_to_show if n in nx_graph and graph.get_symbol(n)])
    edge_count = sum(1 for u, v in nx_graph.edges() if u in nodes_to_show and v in nodes_to_show)
    changed_count = len(changed_set)
    trans_count = len(impacted_set - changed_set)

    # Inject fullscreen button, info bar, legend, and dark background
    injection = f"""
    <style>
        body {{ background-color: #0e1117; margin: 0; padding: 0; }}
        .fs-btn {{
            position: fixed; top: 10px; right: 10px; z-index: 9999;
            width: 38px; height: 38px; border-radius: 8px;
            background: rgba(20,20,34,0.9); border: 1px solid rgba(255,255,255,0.15);
            color: #ddd; font-size: 18px; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.15s ease; backdrop-filter: blur(8px);
        }}
        .fs-btn:hover {{
            background: rgba(225,112,85,0.7); border-color: #e17055;
            color: #fff; transform: scale(1.05);
        }}
        .info-bar {{
            position: fixed; bottom: 10px; left: 10px; z-index: 9999;
            background: rgba(14,17,23,0.85); border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px; padding: 6px 14px; color: #999;
            font: 12px Inter, sans-serif; backdrop-filter: blur(8px);
        }}
        .info-bar b {{ color: #eee; }}
        .legend-bar {{
            position: fixed; bottom: 10px; right: 10px; z-index: 9999;
            background: rgba(14,17,23,0.85); border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px; padding: 6px 14px; color: #bbb;
            font: 11px Inter, sans-serif; backdrop-filter: blur(8px);
            display: flex; gap: 12px;
        }}
        .dot {{
            display: inline-block; width: 8px; height: 8px;
            border-radius: 50%; margin-right: 4px; vertical-align: middle;
        }}
        :fullscreen body, :-webkit-full-screen body {{ background: #0e1117 !important; }}
        :fullscreen #mynetwork, :-webkit-full-screen #mynetwork {{
            width: 100vw !important; height: 100vh !important;
        }}
    </style>

    <button class="fs-btn" onclick="toggleFs()" title="Toggle fullscreen">&#x26F6;</button>

    <div class="info-bar">
        <b>{node_count}</b> nodes &middot; <b>{edge_count}</b> edges &middot;
        <span class="dot" style="background:#d63031"></span><b>{changed_count}</b> changed &middot;
        <span class="dot" style="background:#e17055"></span><b>{trans_count}</b> impacted
    </div>

    <div class="legend-bar">
        <span><span class="dot" style="background:#d63031"></span>Changed</span>
        <span><span class="dot" style="background:#e17055"></span>Impacted</span>
        <span><span class="dot" style="background:#00b894"></span>Safe</span>
        <span><span class="dot" style="background:#0984e3"></span>Test</span>
    </div>

    <script>
    function toggleFs() {{
        var el = document.documentElement;
        if (!document.fullscreenElement && !document.webkitFullscreenElement) {{
            (el.requestFullscreen || el.webkitRequestFullscreen).call(el);
        }} else {{
            (document.exitFullscreen || document.webkitExitFullscreen).call(document);
        }}
    }}
    </script>
    """

    html_content = html_content.replace("<body>", f"<body>{injection}")

    height_int = int(height.replace("px", ""))
    components.html(html_content, height=height_int + 30)