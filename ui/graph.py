"""Interactive PyVis Network visualization for FollowThru Enterprise."""
import html
from pyvis.network import Network


def render_graph(data: dict | None = None) -> str:
    """
    Turns pipeline.graph_data() into an interactive enterprise-grade PyVis network:
    - decisions = navy boxes
    - tasks = teal dots
    - status at_risk = red
    - "conflicts" edges = red dashed
    - "supersedes" edges = gray
    Rendered in gr.HTML via an iframe srcdoc.
    """
    if not data or not data.get("nodes"):
        return """
        <div style="padding: 32px; text-align: center; color: #64748B; background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <div style="font-size: 1.8em; margin-bottom: 8px;">🕸️</div>
            <div style="font-weight: 600; color: #334155; font-size: 1.05em;">No Graph Data Loaded</div>
            <div style="font-size: 0.9em; margin-top: 4px;">Process a meeting transcript in the Ingest tab to generate the organizational knowledge graph.</div>
        </div>
        """

    net = Network(
        height="500px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="remote",
        bgcolor="#FAFAFC",
        font_color="#0F1B3D"
    )

    for node in data.get("nodes", []):
        nid = node["id"]
        label = node.get("label", nid)
        ntype = node.get("type", "task")
        status = node.get("status", "")

        # Colors & Shapes:
        # decisions = navy boxes, tasks = teal dots, status at_risk = red
        if status == "at_risk":
            color = {
                "background": "#DC2626",
                "border": "#B91C1C",
                "highlight": {"background": "#EF4444", "border": "#7F1D1D"}
            }
            shape = "dot"
            size = 20
        elif ntype == "decision":
            color = {
                "background": "#0F1B3D",
                "border": "#1B2A55",
                "highlight": {"background": "#2A3B6E", "border": "#0B132B"}
            }
            shape = "box"
            size = 26
        else:
            # task
            color = {
                "background": "#0D9488",
                "border": "#0F766E",
                "highlight": {"background": "#14B8A6", "border": "#115E59"}
            }
            shape = "dot"
            size = 18

        font = {
            "color": "#FFFFFF",
            "size": 13,
            "face": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        }

        status_badge_color = "#DC2626" if status in ("disputed", "at_risk") else ("#64748B" if status == "superseded" else "#0F766E")
        title = (
            f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 6px 8px; font-size: 13px; line-height: 1.4;'>"
            f"<div style='font-weight: 700; color: #0F1B3D; margin-bottom: 4px;'>{html.escape(label)}</div>"
            f"<div style='display: flex; gap: 6px; font-size: 11px;'>"
            f"<span style='background: #E2E8F0; color: #334155; padding: 2px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase;'>{ntype}</span>"
            f"<span style='background: {status_badge_color}; color: #FFFFFF; padding: 2px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase;'>{status}</span>"
            f"</div>"
            f"</div>"
        )

        net.add_node(
            nid,
            label=label,
            title=title,
            shape=shape,
            color=color,
            font=font,
            size=size,
            borderWidth=2,
            shadow={"enabled": True, "color": "rgba(0,0,0,0.12)", "size": 6, "x": 1, "y": 2}
        )

    for edge in data.get("edges", []):
        src = edge["from"]
        dst = edge["to"]
        etype = edge.get("type", "")

        # "conflicts" edges red dashed, "supersedes" gray
        if etype == "conflicts":
            color = "#EF4444"
            dashes = [6, 4]
            width = 2.5
            title = "<span style='color: #DC2626; font-weight: 700;'>CONFLICTS WITH</span>"
        elif etype == "supersedes":
            color = "#94A3B8"
            dashes = False
            width = 1.8
            title = "<span style='color: #475569; font-weight: 600;'>SUPERSEDES</span>"
        else:
            # e.g. "has_task"
            color = "#CBD5E1"
            dashes = False
            width = 1.4
            title = "<span style='color: #64748B;'>Task Assigned</span>"

        net.add_edge(
            src,
            dst,
            color=color,
            dashes=dashes,
            width=width,
            title=title,
            arrows={"to": {"enabled": True, "scaleFactor": 0.85}},
            smooth={"type": "cubicBezier", "roundness": 0.25}
        )

    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -70,
          "centralGravity": 0.012,
          "springLength": 130,
          "springConstant": 0.08,
          "damping": 0.88
        },
        "maxVelocity": 45,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 200, "updateInterval": 25}
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "zoomView": true,
        "multiselect": false
      }
    }
    """)

    html_raw = net.generate_html()
    escaped = html.escape(html_raw, quote=True)

    legend_html = """
    <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: flex-start; padding: 10px 14px; background: #F8FAFC; border: 1px solid #E2E8F0; border-bottom: none; border-radius: 10px 10px 0 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; color: #475569;">
        <span style="font-weight: 700; color: #1E293B; margin-right: 4px;">GRAPH LEGEND:</span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="display: inline-block; width: 12px; height: 12px; background: #0F1B3D; border-radius: 2px;"></span> Decision</span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="display: inline-block; width: 10px; height: 10px; background: #0D9488; border-radius: 50%;"></span> Task</span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="display: inline-block; width: 10px; height: 10px; background: #DC2626; border-radius: 50%;"></span> At-Risk Task</span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="display: inline-block; width: 18px; height: 0; border-top: 2px dashed #EF4444;"></span> Conflict Edge</span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="display: inline-block; width: 18px; height: 0; border-top: 2px solid #94A3B8;"></span> Supersedes Edge</span>
    </div>
    """

    return f"""
    <div style="border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.08); margin: 8px 0 16px 0;">
        {legend_html}
        <iframe srcdoc="{escaped}" style="width: 100%; height: 500px; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 10px 10px; background: #FAFAFC; display: block;" frameborder="0"></iframe>
    </div>
    """
