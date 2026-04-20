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
    height: str = "500px",
) -> None:
    """Render an interactive call graph in Streamlit."""

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

    # Physics settings for better layout
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
            "stabilization": {
                "iterations": 100
            }
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

    # Limit nodes for large graphs
    max_nodes = 100
    nodes_to_show = set()

    # Always show changed and impacted nodes
    nodes_to_show.update(changed_set)
    nodes_to_show.update(impacted_set)

    # Add neighbors of impacted nodes
    for node in list(nodes_to_show):
        if node in nx_graph:
            nodes_to_show.update(nx_graph.predecessors(node))
            nodes_to_show.update(nx_graph.successors(node))

    # If still under limit, add more nodes
    if len(nodes_to_show) < max_nodes:
        for node in nx_graph.nodes():
            if len(nodes_to_show) >= max_nodes:
                break
            nodes_to_show.add(node)

    # Add nodes
    for node_id in nodes_to_show:
        if node_id not in nx_graph:
            continue

        sym = graph.get_symbol(node_id)
        if not sym:
            continue

        # Determine color and size
        if node_id in changed_set:
            color = "#d63031"       # Red — changed
            size = 30
            border_color = "#ff7675"
        elif node_id in impacted_set:
            color = "#e17055"       # Orange — impacted
            size = 25
            border_color = "#fab1a0"
        elif "test" in sym.file_path.lower() or "Test" in sym.name:
            color = "#0984e3"       # Blue — test
            size = 20
            border_color = "#74b9ff"
        else:
            color = "#00b894"       # Green — safe
            size = 18
            border_color = "#55efc4"

        # Shape by kind
        if sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE):
            shape = "diamond"
        elif sym.kind == SymbolKind.CONSTRUCTOR:
            shape = "triangle"
        else:
            shape = "dot"

        # Label — short name only
        label = sym.name

        # Tooltip — full details
        status = "CHANGED" if node_id in changed_set else (
            "IMPACTED" if node_id in impacted_set else "safe"
        )
        title = (
            f"<b>{sym.qualified_name}</b><br>"
            f"Kind: {sym.kind.value}<br>"
            f"File: {sym.file_path}<br>"
            f"Lines: {sym.start_line}-{sym.end_line}<br>"
            f"Status: <b>{status}</b>"
        )

        net.add_node(
            node_id,
            label=label,
            title=title,
            color={"background": color, "border": border_color},
            size=size,
            shape=shape,
        )

    # Add edges (only between visible nodes)
    for u, v in nx_graph.edges():
        if u in nodes_to_show and v in nodes_to_show:
            # Color edge red if it's part of the blast radius path
            if u in impacted_set and v in impacted_set:
                edge_color = "#e17055"
                width = 2
            elif u in impacted_set or v in impacted_set:
                edge_color = "#fdcb6e"
                width = 1.5
            else:
                edge_color = "#555"
                width = 1

            net.add_edge(u, v, color=edge_color, width=width)

    # Render
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        net.save_graph(f.name)
        html_content = Path(f.name).read_text()

        # Inject dark background fix
        html_content = html_content.replace(
            "<body>",
            '<body style="background-color: #0e1117; margin: 0; padding: 0;">'
        )

        components.html(html_content, height=int(height.replace("px", "")) + 20)

    # Legend
    legend_col1, legend_col2, legend_col3, legend_col4 = st.columns(4)
    with legend_col1:
        st.markdown("🔴 **Changed** — directly modified")
    with legend_col2:
        st.markdown("🟠 **Impacted** — transitively affected")
    with legend_col3:
        st.markdown("🟢 **Safe** — not in blast radius")
    with legend_col4:
        st.markdown("🔵 **Test** — test file")