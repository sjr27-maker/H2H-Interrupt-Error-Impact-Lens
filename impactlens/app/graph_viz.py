"""
Interactive call graph visualization with pyvis.

Features:
- Color-coded nodes (red=changed, orange=impacted, green=safe, blue=test)
- Hover highlights connected edges with animated flow effect
- Smooth zoom in/out with scroll
- Tooltips with full symbol details
- Shapes by symbol kind (diamond=class, dot=method, triangle=constructor)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from impactlens.core.models import ImpactResult, SymbolKind
from impactlens.graph.call_graph import CallGraph


def render_call_graph(
    graph: CallGraph,
    impact: ImpactResult,
    height: int = 550,
) -> None:
    """Render an interactive call graph in Streamlit."""

    changed_set = set(impact.changed_symbols)
    impacted_set = set(impact.impacted_symbols)
    nx_graph = graph.graph

    # ── Determine which nodes to show ──
    MAX_NODES = 120
    nodes_to_show: set[str] = set()

    # Always show changed and impacted
    nodes_to_show.update(changed_set)
    nodes_to_show.update(impacted_set)

    # Add their neighbors
    for node in list(nodes_to_show):
        if node in nx_graph:
            nodes_to_show.update(nx_graph.predecessors(node))
            nodes_to_show.update(nx_graph.successors(node))

    # Fill remaining slots
    if len(nodes_to_show) < MAX_NODES:
        for node in nx_graph.nodes():
            if len(nodes_to_show) >= MAX_NODES:
                break
            nodes_to_show.add(node)

    # ── Build HTML directly for full control ──
    nodes_js = []
    edges_js = []

    for node_id in nodes_to_show:
        if node_id not in nx_graph:
            continue

        sym = graph.get_symbol(node_id)
        if not sym:
            continue

        # Color and size
        if node_id in changed_set:
            color = "#d63031"
            border = "#ff7675"
            size = 28
            status = "CHANGED"
            shadow_color = "rgba(214,48,49,0.6)"
        elif node_id in impacted_set:
            color = "#e17055"
            border = "#fab1a0"
            size = 22
            status = "IMPACTED"
            shadow_color = "rgba(225,112,85,0.4)"
        elif "test" in sym.file_path.lower() or "Test" in sym.name:
            color = "#0984e3"
            border = "#74b9ff"
            size = 18
            status = "TEST"
            shadow_color = "rgba(9,132,227,0.3)"
        else:
            color = "#00b894"
            border = "#55efc4"
            size = 16
            status = "SAFE"
            shadow_color = "rgba(0,184,148,0.3)"

        # Shape
        if sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE):
            shape = "diamond"
        elif sym.kind == SymbolKind.CONSTRUCTOR:
            shape = "triangle"
        else:
            shape = "dot"

        # Tooltip
        title = (
            f"<div style='font-family:Inter,sans-serif;padding:8px;'>"
            f"<b style='font-size:13px;'>{sym.qualified_name}</b><br>"
            f"<span style='color:#aaa;'>Kind:</span> {sym.kind.value}<br>"
            f"<span style='color:#aaa;'>File:</span> {sym.file_path.split('/')[-1]}<br>"
            f"<span style='color:#aaa;'>Lines:</span> {sym.start_line}–{sym.end_line}<br>"
            f"<span style='color:{'#ff7675' if status in ('CHANGED','IMPACTED') else '#55efc4'};font-weight:bold;'>"
            f"Status: {status}</span></div>"
        )

        # Escape for JS
        safe_title = title.replace("'", "\\'").replace("\n", "")
        safe_label = sym.name.replace("'", "\\'")

        nodes_js.append(
            f"{{id:'{node_id}', label:'{safe_label}', title:'{safe_title}', "
            f"color:{{background:'{color}',border:'{border}',highlight:{{background:'{border}',border:'#fff'}},hover:{{background:'{border}',border:'#fff'}}}},"
            f"size:{size}, shape:'{shape}', shadow:{{enabled:true,color:'{shadow_color}',size:10}}, "
            f"font:{{color:'#eee',size:11,face:'Inter'}}}}"
        )

    # Edges
    for u, v in nx_graph.edges():
        if u in nodes_to_show and v in nodes_to_show:
            # Color edges in blast radius
            if u in changed_set or v in changed_set:
                ecolor = "#d63031"
                width = 2.5
            elif u in impacted_set and v in impacted_set:
                ecolor = "#e17055"
                width = 2
            elif u in impacted_set or v in impacted_set:
                ecolor = "#fdcb6e"
                width = 1.5
            else:
                ecolor = "rgba(100,100,100,0.4)"
                width = 0.8

            edges_js.append(
                f"{{from:'{u}',to:'{v}',color:{{color:'{ecolor}',highlight:'{ecolor}',hover:'{ecolor}'}},"
                f"width:{width},arrows:{{to:{{enabled:true,scaleFactor:0.5}}}},smooth:{{type:'continuous'}}}}"
            )

    nodes_str = ",\n".join(nodes_js)
    edges_str = ",\n".join(edges_js)

    # ── Complete HTML with vis.js, animations, and controls ──
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/vis-network.min.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/vis-network.min.css" rel="stylesheet">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ background:#0e1117; overflow:hidden; }}
            #graph {{ width:100%; height:{height}px; }}

            /* Zoom controls */
            .controls {{
                position:absolute; top:12px; right:12px; z-index:10;
                display:flex; flex-direction:column; gap:6px;
            }}
            .ctrl-btn {{
                width:36px; height:36px; border-radius:8px;
                background:rgba(30,30,46,0.9); border:1px solid #444;
                color:#fff; font-size:18px; cursor:pointer;
                display:flex; align-items:center; justify-content:center;
                transition:all 0.15s ease;
                backdrop-filter:blur(8px);
            }}
            .ctrl-btn:hover {{
                background:rgba(225,112,85,0.8); border-color:#e17055;
                transform:scale(1.08);
            }}

            /* Info panel */
            .info {{
                position:absolute; bottom:12px; left:12px; z-index:10;
                background:rgba(14,17,23,0.85); border:1px solid #333;
                border-radius:8px; padding:8px 14px;
                color:#aaa; font-size:12px; font-family:Inter,sans-serif;
                backdrop-filter:blur(8px);
            }}
            .info b {{ color:#eee; }}
        </style>
    </head>
    <body>
        <div style="position:relative;">
            <div id="graph"></div>
            <div class="controls">
                <button class="ctrl-btn" onclick="zoomIn()" title="Zoom in">+</button>
                <button class="ctrl-btn" onclick="zoomOut()" title="Zoom out">−</button>
                <button class="ctrl-btn" onclick="fitAll()" title="Fit all">⊞</button>
                <button class="ctrl-btn" onclick="togglePhysics()" title="Toggle physics" id="physBtn">◎</button>
            </div>
            <div class="info">
                <b>{len(nodes_js)}</b> nodes · <b>{len(edges_js)}</b> edges ·
                <b>{len(changed_set)}</b> changed · <b>{len(impacted_set - changed_set)}</b> impacted
            </div>
        </div>

        <script>
            var nodes = new vis.DataSet([{nodes_str}]);
            var edges = new vis.DataSet([{edges_str}]);

            var container = document.getElementById('graph');
            var data = {{ nodes: nodes, edges: edges }};

            var options = {{
                physics: {{
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {{
                        gravitationalConstant: -60,
                        centralGravity: 0.008,
                        springLength: 100,
                        springConstant: 0.06,
                        damping: 0.4
                    }},
                    stabilization: {{ iterations: 150, fit: true }},
                    adaptiveTimestep: true
                }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 80,
                    zoomView: true,
                    dragView: true,
                    zoomSpeed: 0.3,
                    navigationButtons: false,
                    keyboard: {{ enabled: true }}
                }},
                edges: {{
                    smooth: {{ type: 'continuous', roundness: 0.2 }}
                }},
                nodes: {{
                    borderWidth: 2,
                    borderWidthSelected: 3
                }}
            }};

            var network = new vis.Network(container, data, options);

            // ── Hover highlight with flow animation ──
            var originalColors = {{}};
            var animInterval = null;

            network.on('hoverNode', function(params) {{
                var nodeId = params.node;
                var connected = network.getConnectedEdges(nodeId);
                var connectedNodes = network.getConnectedNodes(nodeId);

                // Dim all non-connected nodes
                nodes.forEach(function(n) {{
                    if (n.id !== nodeId && connectedNodes.indexOf(n.id) === -1) {{
                        originalColors[n.id] = n.color;
                        nodes.update({{id: n.id, opacity: 0.15}});
                    }}
                }});

                // Animate connected edges with flow effect
                clearInterval(animInterval);
                var phase = 0;
                animInterval = setInterval(function() {{
                    phase = (phase + 1) % 20;
                    connected.forEach(function(edgeId) {{
                        var dashOffset = phase * 3;
                        edges.update({{
                            id: edgeId,
                            width: 4,
                            dashes: [8, 4],
                            color: {{ color: '#fdcb6e', highlight: '#fdcb6e' }}
                        }});
                    }});
                }}, 60);
            }});

            network.on('blurNode', function(params) {{
                // Restore all nodes
                nodes.forEach(function(n) {{
                    nodes.update({{id: n.id, opacity: 1.0}});
                }});

                // Stop animation and restore edges
                clearInterval(animInterval);
                edges.forEach(function(e) {{
                    edges.update({{
                        id: e.id,
                        width: e.originalWidth || 1,
                        dashes: false
                    }});
                }});
            }});

            // ── Zoom controls ──
            function zoomIn() {{
                var scale = network.getScale();
                network.moveTo({{ scale: scale * 1.4, animation: {{ duration: 300, easingFunction: 'easeInOutQuad' }} }});
            }}
            function zoomOut() {{
                var scale = network.getScale();
                network.moveTo({{ scale: scale / 1.4, animation: {{ duration: 300, easingFunction: 'easeInOutQuad' }} }});
            }}
            function fitAll() {{
                network.fit({{ animation: {{ duration: 500, easingFunction: 'easeInOutQuad' }} }});
            }}

            var physicsOn = true;
            function togglePhysics() {{
                physicsOn = !physicsOn;
                network.setOptions({{ physics: {{ enabled: physicsOn }} }});
                document.getElementById('physBtn').style.background = physicsOn ? 'rgba(30,30,46,0.9)' : 'rgba(214,48,49,0.5)';
            }}

            // Fit after stabilization
            network.once('stabilizationIterationsDone', function() {{
                network.fit({{ animation: true }});
            }});
        </script>
    </body>
    </html>
    """

    components.html(html, height=height + 50)