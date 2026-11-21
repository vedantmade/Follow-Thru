"""FollowThru: Enterprise Meeting-to-Execution Agent Gradio UI.

Corporate-grade interface for automated meeting ingestion, entity extraction,
historical conflict resolution, and human-in-the-loop task governance.
"""
import html
import json
import os
import pandas as pd

# Optimize startup & prevent telemetry hang in restricted environments
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
import gradio as gr

import pipeline  # real backend (mock_pipeline.py has the same API)
from ui.graph import render_graph

# Sample transcript path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)  # all relative paths work no matter where you run from
SAMPLE_MEETING_PATH = os.path.join(BASE_DIR, "data", "samples", "demo_meeting_2026-11-21.txt")


# ---------------------------------------------------------------------------
# Corporate CSS Theme Styling
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
/* ===== FollowThru palette =====
   Navy  #0F1B3D  structure: header, headings, text, decisions
   Teal  #0D9488  actions: buttons, links, success, tasks
   Orange #F97316 ONLY for the transcript upload flow
   (red is kept only as a warning signal on conflicts / errors) */
:root { --ft-navy: #0F1B3D; --ft-teal: #0D9488; --ft-orange: #F97316; }
.gradio-container { max-width: 1280px !important; margin: 0 auto !important; }
h1, h2, h3, h4 { color: var(--ft-navy) !important; }
.tab-nav button.selected, button[role="tab"][aria-selected="true"] {
    color: var(--ft-teal) !important; border-bottom: 3px solid var(--ft-teal) !important; font-weight: 700 !important; }
button.primary:not(.upload-accent) { background: var(--ft-teal) !important; border: none !important; color: #fff !important; }
button.primary:not(.upload-accent):hover { background: #0F766E !important; }
button.secondary { border: 1px solid var(--ft-navy) !important; color: var(--ft-navy) !important; background: #fff !important; }
.upload-accent, button.upload-accent {
    background: var(--ft-orange) !important; color: #fff !important; border: none !important;
    font-weight: 700 !important; box-shadow: 0 2px 6px rgba(249, 115, 22, 0.3) !important; }
.upload-accent:hover, button.upload-accent:hover { background: #EA580C !important; }
.upload-zone { border: 2px dashed #FDBA74 !important; background: #FFF7ED !important; border-radius: 12px !important; }
.upload-zone label span, .upload-zone .label-wrap span { color: #C2410C !important; font-weight: 700 !important; }
a { color: var(--ft-teal); }
.corp-header, .corp-header div, .corp-header span, .corp-header strong { color: #FFFFFF !important; }
.corp-header .corp-brand-tag { color: #5EEAD4 !important; }
.corp-header .ft-sub { color: #CBD5E1 !important; }
.upload-zone [data-testid="block-info"], .upload-zone [data-testid="block-label"], .upload-zone label span {
    background: #FFEDD5 !important; color: #C2410C !important; font-weight: 700 !important; }
.upload-zone button, .upload-zone .wrap, .upload-zone svg { color: #EA580C !important; }
.ft-howto { background: #F0FDFA; border: 1px solid #99F6E4; border-left: 4px solid var(--ft-teal);
    border-radius: 10px; padding: 14px 18px; margin: 4px 0 14px 0; color: var(--ft-navy); font-size: 0.95rem; }
.ft-howto b { color: var(--ft-teal); }
/* readable read-only counters + table */
input[type="number"]:disabled, input:disabled { color: var(--ft-navy) !important; -webkit-text-fill-color: var(--ft-navy) !important;
    opacity: 1 !important; font-size: 1.7rem !important; font-weight: 800 !important; }
table td, table th, table td span, table th span, .table-wrap td, .table-wrap th {
    color: var(--ft-navy) !important; opacity: 1 !important; font-family: Inter, "Segoe UI", sans-serif !important; }
table th, table th span { font-weight: 700 !important; background: #F0FDFA !important; }
.ft-howto .orange { color: #EA580C; font-weight: 700; }

/* Enterprise Typography & Layout */
body, .gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    background-color: #F8FAFC !important;
    color: #0F1B3D !important;
}

/* Header & Brand Banner */
.corp-header {
    background: linear-gradient(135deg, #0F1B3D 0%, #1B2A55 100%);
    border-radius: 12px;
    padding: 22px 28px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px -1px rgba(15, 27, 61, 0.15), 0 2px 4px -2px rgba(15, 27, 61, 0.1);
    border: 1px solid #334155;
    color: #FFFFFF;
}

.corp-brand-tag {
    background: rgba(45, 212, 191, 0.18);
    color: #5EEAD4;
    border: 1px solid rgba(45, 212, 191, 0.45);
    padding: 2px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 6px;
}

.corp-env-pill {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    color: #CBD5E1;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.corp-env-dot {
    width: 8px;
    height: 8px;
    background-color: #14B8A6;
    border-radius: 50%;
    box-shadow: 0 0 8px #14B8A6;
}

/* Stepper Workflow */
.corp-stepper {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 14px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
}

.corp-step-item {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.88rem;
    color: #64748B;
    font-weight: 500;
}

.corp-step-badge {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #F1F5F9;
    color: #475569;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.82rem;
    font-weight: 700;
}

.corp-step-item.active {
    color: #0D9488;
    font-weight: 700;
}

.corp-step-item.active .corp-step-badge {
    background: #0D9488;
    color: #FFFFFF;
}

.corp-step-arrow {
    color: #CBD5E1;
    font-size: 1.1rem;
}

/* Corporate Cards */
.corp-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.03);
}

/* KPI Counter Cards */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
}

.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    border-top: 3px solid #64748B;
}

.kpi-card.purple { border-top-color: #0F1B3D; }
.kpi-card.blue { border-top-color: #14B8A6; }
.kpi-card.amber { border-top-color: #0F1B3D; }
.kpi-card.red { border-top-color: #EF4444; }

.kpi-title {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #64748B;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
}

.kpi-value {
    font-size: 1.85rem;
    font-weight: 800;
    color: #0F1B3D;
    line-height: 1.1;
}

.kpi-subtext {
    font-size: 0.78rem;
    color: #94A3B8;
    margin-top: 6px;
}

/* Dataframe & Tables */
.dataframe {
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* Primary Corporate Button */
button.primary-corp {
    background: #0D9488 !important;
    color: white !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 4px rgba(13, 148, 136, 0.2) !important;
    border-radius: 8px !important;
    transition: all 0.15s ease-in-out !important;
}
button.primary-corp:hover {
    background: #0F766E !important;
    box-shadow: 0 4px 6px rgba(13, 148, 136, 0.3) !important;
}
"""


def load_sample_file():
    """Load the sample meeting transcript file."""
    try:
        if os.path.exists(SAMPLE_MEETING_PATH):
            with open(SAMPLE_MEETING_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            return (
                content,
                "Sprint Sync — FitTrack launch",
                "2026-11-21",
                "<div style='color: #0F766E; font-weight: 600; font-size: 0.9em; padding: 6px 12px; background: #F0FDFA; border-radius: 6px; display: inline-block;'>✅ Sample loaded: <code>demo_meeting_2026-11-21.txt</code> (Participants: Rahul, Amit, Neha, Karan | Absent: Priya)</div>"
            )
        return (
            "",
            "Sprint Sync — FitTrack launch",
            "2026-11-21",
            "<div style='color: #DC2626;'>Sample file not found at " + SAMPLE_MEETING_PATH + "</div>"
        )
    except Exception as e:
        return "", "", "", f"<div style='color: #DC2626;'>Error loading sample: {e}</div>"


def handle_file_upload(file):
    """Handle uploaded transcript (.txt or .vtt)."""
    try:
        if file is None:
            return "", "", ""
        path = file.name if hasattr(file, "name") else str(file)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        base_name = os.path.basename(path).rsplit(".", 1)[0]
        title = base_name.replace("_", " ").replace("-", " ").title()
        return content, title, pipeline.today()
    except Exception as e:
        gr.Warning(f"Failed to read uploaded file: {e}")
        return "", "", pipeline.today()


def build_action_items_df(action_items: list[dict]) -> pd.DataFrame:
    """Format action items into an editable pandas DataFrame."""
    rows = []
    for item in action_items:
        idx = item.get("idx", 0)
        task = item.get("task", "")
        owner = item.get("owner") or ""
        deadline = item.get("deadline") or ""
        turns = ", ".join(item.get("turn_ids", []))
        quote = item.get("quote", "")
        quote_turn = f"[{turns}] \"{quote}\"" if turns else quote
        needs_rev = item.get("needs_review", False) or item.get("vague", False) or not owner or not deadline
        
        status_flag = "⚠️ NEEDS OWNER / REVIEW" if needs_rev else "✅ VERIFIED"
        approve = not needs_rev

        rows.append({
            "Idx": idx,
            "Approve": approve,
            "Task Description": task,
            "Owner": owner,
            "Target Deadline": deadline,
            "Verbatim Quote & Turns": quote_turn,
            "Audit Status": status_flag
        })
    if not rows:
        return pd.DataFrame(columns=["Idx", "Approve", "Task Description", "Owner", "Target Deadline", "Verbatim Quote & Turns", "Audit Status"])
    return pd.DataFrame(rows)


def make_conflict_card_html(c: dict) -> str:
    """Create corporate executive card HTML for a decision conflict."""
    topic = html.escape(str(c.get("topic", "Topic")))
    explanation = html.escape(str(c.get("explanation", "")))
    recommendation = html.escape(str(c.get("recommendation", "flag"))).upper()
    reason = html.escape(str(c.get("reason", "")))
    absent = c.get("original_decider_absent", False)
    idx = c.get("idx", 0)

    old_dec = c.get("old", {})
    new_dec = c.get("new", {})

    impact_items = c.get("impact", [])
    if impact_items:
        impact_rows = []
        for imp in impact_items:
            task = html.escape(imp.get("task", ""))
            owner = html.escape(imp.get("owner", ""))
            deadline = html.escape(str(imp.get("deadline", "None")))
            issue_num = imp.get("issue_number")
            issue_url = imp.get("issue_url") or "#"
            link = f'<a href="{html.escape(issue_url)}" target="_blank" style="color: #0D9488; font-weight: 700; text-decoration: none; padding: 2px 6px; background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 4px; font-size: 0.85em;">Issue #{issue_num} ↗</a>' if issue_num else ""
            impact_rows.append(
                f"<div style='display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; margin-bottom: 6px; font-size: 0.88em;'>"
                f"<span><strong>{task}</strong> <span style='color: #64748B;'>&middot; Owner: {owner} &middot; Due: {deadline}</span></span>"
                f"<span>{link}</span>"
                f"</div>"
            )
        impact_html = "".join(impact_rows)
    else:
        impact_html = "<div style='color: #64748B; font-size: 0.88em; font-style: italic;'>No open downstream tasks linked to this decision.</div>"

    absent_alert = ""
    if absent:
        decider = html.escape(str(old_dec.get("speaker", "Original decider")))
        absent_alert = f"""
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 10px; padding: 10px 14px; background: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 8px; color: #991B1B; font-size: 0.88em;">
          <span style="font-size: 1.2em;">⚠️</span>
          <div><strong>Stakeholder Governance Alert:</strong> Original decider <strong>{decider}</strong> was not present at today's meeting. Exercise caution before overriding.</div>
        </div>
        """

    rec_color = "#DC2626" if recommendation == "FLAG" else ("#0D9488" if recommendation == "REPLACE" else "#475569")
    rec_bg = "#FEE2E2" if recommendation == "FLAG" else ("#CCFBF1" if recommendation == "REPLACE" else "#F1F5F9")

    return f"""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 5px solid #EF4444; border-radius: 12px; padding: 22px; margin-bottom: 18px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04), 0 2px 4px -2px rgba(0, 0, 0, 0.03);">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #F1F5F9; padding-bottom: 12px; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="background: #FEE2E2; color: #991B1B; padding: 4px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase;">Conflict #{idx + 1}</span>
          <span style="font-size: 1.15rem; font-weight: 700; color: #0F1B3D;">Decision Divergence on Topic: <code>{topic}</code></span>
        </div>
        <span style="font-size: 0.8rem; color: #64748B; font-weight: 500;">Cross-Meeting Memory Check</span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 14px;">
        <!-- Previous Decision Column -->
        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.04em;">Recorded Decision ({html.escape(str(old_dec.get('meeting_date', '')))})</span>
            <span style="font-size: 0.75rem; color: #94A3B8;">{html.escape(str(old_dec.get('meeting_title', '')))}</span>
          </div>
          <div style="font-size: 1.02rem; font-weight: 700; color: #1B2A55; margin-bottom: 6px;">
            "{html.escape(str(old_dec.get('text', '')))}"
          </div>
          <div style="font-size: 0.82rem; color: #475569; margin-bottom: 8px;">
            Decider: <strong>{html.escape(str(old_dec.get('speaker', '')))}</strong>
          </div>
          <blockquote style="margin: 0; font-size: 0.84rem; font-style: italic; color: #475569; border-left: 3px solid #94A3B8; padding-left: 10px; background: rgba(255,255,255,0.7); padding-top: 4px; padding-bottom: 4px;">
            "{html.escape(str(old_dec.get('quote', '')))}"
          </blockquote>
        </div>

        <!-- Proposed New Decision Column -->
        <div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 14px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-size: 0.75rem; font-weight: 700; color: #B91C1C; text-transform: uppercase; letter-spacing: 0.04em;">Proposed Decision ({html.escape(str(new_dec.get('meeting_date', '')))})</span>
            <span style="font-size: 0.75rem; color: #DC2626; font-weight: 600;">Today's Sync</span>
          </div>
          <div style="font-size: 1.02rem; font-weight: 700; color: #991B1B; margin-bottom: 6px;">
            "{html.escape(str(new_dec.get('text', '')))}"
          </div>
          <div style="font-size: 0.82rem; color: #7F1D1D; margin-bottom: 8px;">
            Speaker: <strong>{html.escape(str(new_dec.get('speaker', '')))}</strong> &middot; Turn {', '.join(new_dec.get('turn_ids', []))}
          </div>
          <blockquote style="margin: 0; font-size: 0.84rem; font-style: italic; color: #991B1B; border-left: 3px solid #EF4444; padding-left: 10px; background: rgba(255,255,255,0.7); padding-top: 4px; padding-bottom: 4px;">
            "{html.escape(str(new_dec.get('quote', '')))}"
          </blockquote>
        </div>
      </div>

      <div style="margin-bottom: 12px; font-size: 0.92rem; color: #334155; line-height: 1.5;">
        <strong>Root Cause Analysis:</strong> {explanation}
      </div>

      <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
        <div style="font-size: 0.82rem; font-weight: 700; color: #475569; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.04em;">Affected Tasks & Downstream Commitments:</div>
        {impact_html}
      </div>

      {absent_alert}

      <div style="margin-top: 14px; padding: 12px 16px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 1.1em;">🤖</span>
          <span style="font-size: 0.9em; color: #1B2A55;"><strong>FollowThru Recommendation:</strong> {reason}</span>
        </div>
        <span style="background: {rec_bg}; color: {rec_color}; padding: 4px 12px; border-radius: 6px; font-size: 0.82rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; border: 1px solid rgba(0,0,0,0.06);">{recommendation}</span>
      </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Gradio UI Construction
# ---------------------------------------------------------------------------
custom_theme = gr.themes.Soft(
    primary_hue=gr.themes.colors.teal,
    secondary_hue=gr.themes.colors.slate,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
)

with gr.Blocks(title="FollowThru Enterprise | Meeting-to-Execution Agent") as demo:

    # State stores
    proposal_state = gr.State({})
    reminders_state = gr.State([])

    # Corporate Executive Header Bar
    gr.HTML(
        """
        <div class="corp-header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div class="corp-brand-tag">Autonomous AI Governance · Linear/GitHub Integrated</div>
                    <div style="font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em; display: flex; align-items: center; gap: 8px;">
                        <span>FollowThru</span>
                        <span style="font-weight: 300; color: #94A3B8;">|</span>
                        <span style="font-weight: 500; font-size: 1.25rem; color: #E2E8F0;">Meeting-to-Execution Agent</span>
                    </div>
                    <div class="ft-sub" style="font-size: 0.9rem; margin-top: 4px;">
                        Transcript entity extraction, cross-meeting conflict detection, and human-in-the-loop task governance.
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
                    <div class="corp-env-pill">
                        <span class="corp-env-dot"></span>
                        <span>Workspace: <strong>FitTrack Product Team</strong> &middot; Sprint 24</span>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    with gr.Row():
        with gr.Column(scale=4):
            # Workflow Stepper Header
            gr.HTML(
                """
                <div class="corp-stepper">
                    <div class="corp-step-item active">
                        <span class="corp-step-badge">1</span>
                        <span>Ingest Transcript</span>
                    </div>
                    <span class="corp-step-arrow">&rarr;</span>
                    <div class="corp-step-item">
                        <span class="corp-step-badge">2</span>
                        <span>Extract Decisions & Tasks</span>
                    </div>
                    <span class="corp-step-arrow">&rarr;</span>
                    <div class="corp-step-item">
                        <span class="corp-step-badge">3</span>
                        <span>Conflict Reconciliation</span>
                    </div>
                    <span class="corp-step-arrow">&rarr;</span>
                    <div class="corp-step-item">
                        <span class="corp-step-badge">4</span>
                        <span>Human Approval</span>
                    </div>
                    <span class="corp-step-arrow">&rarr;</span>
                    <div class="corp-step-item">
                        <span class="corp-step-badge">5</span>
                        <span>GitHub Issues & Emails</span>
                    </div>
                </div>
                """
            )
        with gr.Column(scale=1, min_width=140):
            reset_btn = gr.Button("🔄 Reset Demo State", variant="secondary", size="sm")
            reset_status = gr.Markdown("", visible=False)

    with gr.Tabs() as tabs:
        # -------------------------------------------------------------------
        # TAB 1: Ingest
        # -------------------------------------------------------------------
        with gr.Tab("1. Ingest Meeting", id="tab_ingest"):
            # "How to test" strip at top
            gr.HTML(
                """
                <div class="ft-howto">
                  <div style="font-weight:800; margin-bottom:6px;">How to test FollowThru (2 minutes)</div>
                  <div><b>1.</b> Memory already holds the <b>14 Nov sprint sync</b> (PostgreSQL, launch on 10 Dec, ₹499 pricing) with its GitHub issues.</div>
                  <div><b>2.</b> Click <span class="orange">📂 Load sample: 21 Nov sprint sync</span>, or upload your own <code>.txt</code> / <code>.vtt</code> transcript.</div>
                  <div><b>3.</b> Click <span class="orange">⚡ Process Transcript</span>, review the conflicts and owners, then <b>Approve</b> to create GitHub issues and emails.</div>
                </div>
                """
            )

            with gr.Row():
                load_sample_btn = gr.Button("📂 Load sample: 21 Nov sprint sync", variant="primary", scale=1, elem_classes=["upload-accent"])
                file_upload = gr.File(
                    label="Upload Meeting Transcript (.txt, .vtt)",
                    file_types=[".txt", ".vtt"],
                    file_count="single",
                    scale=1,
                    elem_classes=["upload-zone"]
                )

            with gr.Row():
                meeting_title = gr.Textbox(
                    label="Meeting Title",
                    placeholder="e.g. Sprint Sync — FitTrack launch",
                    scale=2
                )
                meeting_date = gr.Textbox(
                    label="Meeting Date",
                    value=pipeline.today(),
                    placeholder="YYYY-MM-DD",
                    scale=1
                )

            transcript_input = gr.Textbox(
                elem_classes=["upload-zone"],
                label="Meeting Transcript Source (Speaker: Dialogue)",
                placeholder="Paste a transcript (Speaker: text) or click 'Load sample: 21 Nov sprint sync' above...",
                lines=14,
                max_lines=24
            )

            ingest_msg = gr.HTML("")

            with gr.Row():
                process_btn = gr.Button("⚡ Process Transcript with FollowThru AI", variant="primary", size="lg", elem_classes=["upload-accent"])

        # -------------------------------------------------------------------
        # TAB 2: Review & Approve
        # -------------------------------------------------------------------
        with gr.Tab("2. Review & Approve", id="tab_review"):
            # 4 KPI Stat Counters
            with gr.Row():
                count_decisions = gr.Number(label="Decisions Extracted", value=0, interactive=False)
                count_actions = gr.Number(label="Action Items Extracted", value=0, interactive=False)
                count_need_owner = gr.Number(label="Requires Ownership / Review", value=0, interactive=False)
                count_conflicts = gr.Number(label="Historical Conflicts", value=0, interactive=False)

            review_warnings = gr.Markdown("", visible=False)

            # Editable Dataframe of action items
            gr.Markdown("### 📋 Action Item Governance & Assignment")
            gr.Markdown(
                "*Review all extracted commitments below. You can modify the **Owner** and **Target Deadline** cells directly in the table. "
                "Tasks flagged **⚠️ NEEDS OWNER / REVIEW** require human assignment before approval.*"
            )
            action_items_table = gr.Dataframe(
                headers=["Idx", "Approve", "Task Description", "Owner", "Target Deadline", "Verbatim Quote & Turns", "Audit Status"],
                datatype=["number", "bool", "str", "str", "str", "str", "str"],
                interactive=True,
                wrap=True,
                column_widths=["50px", "75px", "300px", "120px", "120px", "300px", "180px"]
            )

            # Conflict cards section
            gr.Markdown("### ⚔️ Cross-Meeting Decision Conflicts (Historical Memory)")
            conflicts_intro = gr.Markdown("No conflicts detected yet. Process a meeting to analyze historical decisions.")

            # Dynamic conflict cards
            c1_group = gr.Group(visible=False)
            with c1_group:
                c1_html = gr.HTML()
                c1_radio = gr.Radio(
                    choices=["replace", "keep_old", "flag"],
                    label="Executive Governance Choice for Conflict #1",
                    value="flag"
                )

            c2_group = gr.Group(visible=False)
            with c2_group:
                c2_html = gr.HTML()
                c2_radio = gr.Radio(
                    choices=["replace", "keep_old", "flag"],
                    label="Executive Governance Choice for Conflict #2",
                    value="replace"
                )

            c3_group = gr.Group(visible=False)
            with c3_group:
                c3_html = gr.HTML()
                c3_radio = gr.Radio(
                    choices=["replace", "keep_old", "flag"],
                    label="Executive Governance Choice for Conflict #3",
                    value="flag"
                )

            # Organizational Graph
            gr.Markdown("### 🕸️ Organizational Decision & Task Topology")
            gr.Markdown("*Interactive PyVis knowledge network showing decision dependencies, downstream tasks, and conflict linkages.*")
            graph_html = gr.HTML(render_graph(pipeline.graph_data()))

            # Execution Gate
            gr.Markdown("### 🛡️ Human-in-the-Loop Execution Gate")
            email_override_input = gr.Textbox(
                label="Your Email to Receive Demo Notifications (Optional Override)",
                placeholder="e.g. executive@yourcompany.com"
            )

            approve_btn = gr.Button("✅ Approve Selected Tasks & Execute Automations", variant="primary", size="lg")

            execution_results_html = gr.HTML("", visible=False)

        # -------------------------------------------------------------------
        # TAB 3: Task Board
        # -------------------------------------------------------------------
        with gr.Tab("3. Task Board & Reminders", id="tab_tasks"):
            gr.Markdown("### 📌 Enterprise Task Registry")
            tasks_board_table = gr.Dataframe(
                headers=["ID", "Task", "Owner", "Deadline", "Status", "Issue URL"],
                datatype=["str", "str", "str", "str", "str", "str"],
                interactive=False,
                wrap=True
            )

            with gr.Row():
                refresh_tasks_btn = gr.Button("🔄 Refresh Task Board", variant="secondary")

            gr.Markdown("---")
            gr.Markdown("### ⏰ Automated Reminder Dispatch Simulator")
            with gr.Row():
                sim_date_input = gr.Textbox(
                    label="Simulate Current Date (YYYY-MM-DD)",
                    value="2026-11-21",
                    scale=2
                )
                run_reminders_btn = gr.Button("🔔 Scan Due Reminders", variant="primary", scale=1)

            reminders_msg = gr.Markdown("")
            reminders_table = gr.Dataframe(
                headers=["Reminder ID", "Action ID", "Task", "Owner", "Deadline", "Message"],
                datatype=["number", "number", "str", "str", "str", "str"],
                interactive=False,
                wrap=True,
                visible=False
            )

            send_reminders_btn = gr.Button("🚀 Approve & Dispatch Due Reminders", variant="primary", visible=False)
            reminders_result_html = gr.HTML("", visible=False)

        # -------------------------------------------------------------------
        # TAB 4: Executive Digest
        # -------------------------------------------------------------------
        with gr.Tab("4. Weekly Digest", id="tab_digest"):
            gr.Markdown("### 📬 Personalized Weekly Status Digest")
            gr.Markdown("*Generates a personalized rollup of open commitments, overdue deliverables, and recent decision impacts for team members.*")
            with gr.Row():
                digest_person = gr.Dropdown(
                    allow_custom_value=True,
                    choices=pipeline.list_people() or ["Rahul", "Amit", "Neha", "Priya"],
                    value="Rahul",
                    label="Select Team Member"
                )
                digest_date = gr.Textbox(
                    label="As of Date",
                    value="2026-11-21"
                )
                build_digest_btn = gr.Button("📑 Generate Digest Preview", variant="primary")

            digest_stats_markdown = gr.Markdown("")
            digest_preview = gr.Markdown("*(Select a team member and click 'Generate Digest Preview' to preview the email)*")

            send_digest_btn = gr.Button("✉️ Dispatch Digest Email", variant="primary")
            send_digest_status = gr.Markdown("")

        # -------------------------------------------------------------------
        # TAB 5: Ask Memory
        # -------------------------------------------------------------------
        with gr.Tab("5. Ask Memory", id="tab_memory"):
            gr.Markdown("### 🧠 Organizational Memory Intelligence")
            gr.Markdown("*Query past and present meetings, decisions, rationale, and turn-level quotes with full transparency into agent reasoning.*")

            chatbot = gr.Chatbot(label="FollowThru Intelligence", height=420)

            with gr.Row():
                chat_msg = gr.Textbox(
                    placeholder="e.g. Why did we decide on MongoDB instead of Postgres?",
                    label="Your Query",
                    scale=4
                )
                chat_send_btn = gr.Button("Ask Memory", variant="primary", scale=1)

            with gr.Accordion("🔍 Agent Reasoning & Tool Invocation Trace", open=True):
                trace_output = gr.Markdown("*(Ask a question to see real-time tool execution trace)*")

    # -----------------------------------------------------------------------
    # Handlers & Callbacks
    # -----------------------------------------------------------------------

    def on_load_sample():
        """Load sample meeting handler."""
        try:
            content, title, date, msg = load_sample_file()
            return content, title, date, msg
        except Exception as e:
            return "", "", "", f"<div style='color: #DC2626;'>Error: {e}</div>"

    load_sample_btn.click(
        fn=on_load_sample,
        outputs=[transcript_input, meeting_title, meeting_date, ingest_msg]
    )

    file_upload.change(
        fn=handle_file_upload,
        inputs=[file_upload],
        outputs=[transcript_input, meeting_title, meeting_date]
    )

    def on_process(text, title, date):
        """Process transcript and update Review tab components."""
        try:
            if not text.strip():
                gr.Warning("Please enter or load a transcript first.")
                return (
                    {},
                    gr.Tabs(selected="tab_ingest"),
                    0, 0, 0, 0,
                    gr.Markdown(visible=False),
                    pd.DataFrame(),
                    "",
                    gr.Group(visible=False), "", "flag",
                    gr.Group(visible=False), "", "replace",
                    gr.Group(visible=False), "", "flag",
                    render_graph(pipeline.graph_data()),
                    "<div style='color: #DC2626; padding: 8px 12px; background: #FEF2F2; border-radius: 6px;'>Please enter or load a transcript first.</div>"
                )

            proposal = pipeline.process_transcript(
                text=text,
                title=title.strip() or "Sprint Sync",
                meeting_date=date.strip() or pipeline.today()
            )

            decisions = proposal.get("decisions", [])
            actions = proposal.get("action_items", [])
            conflicts = proposal.get("conflicts", [])
            warnings = proposal.get("warnings", [])

            # Counters
            n_dec = len(decisions)
            n_act = len(actions)
            n_need_owner = sum(
                1 for a in actions if not a.get("owner") or not a.get("deadline") or a.get("needs_review") or a.get("vague")
            )
            n_conf = len(conflicts)

            # Warnings banner
            warn_md = ""
            if warnings:
                warn_md = "⚠️ **Governance Alerts:**\n" + "\n".join(f"- {w}" for w in warnings)
                warn_visible = True
            else:
                warn_visible = False

            # Action items dataframe
            df_actions = build_action_items_df(actions)

            # Conflict cards & radios
            c1_vis, c1_card, c1_val = False, "", "flag"
            c2_vis, c2_card, c2_val = False, "", "replace"
            c3_vis, c3_card, c3_val = False, "", "flag"

            if len(conflicts) > 0:
                c1_vis = True
                c1_card = make_conflict_card_html(conflicts[0])
                c1_val = conflicts[0].get("recommendation", "flag")
            if len(conflicts) > 1:
                c2_vis = True
                c2_card = make_conflict_card_html(conflicts[1])
                c2_val = conflicts[1].get("recommendation", "replace")
            if len(conflicts) > 2:
                c3_vis = True
                c3_card = make_conflict_card_html(conflicts[2])
                c3_val = conflicts[2].get("recommendation", "flag")

            c_intro = (
                f"⚠️ FollowThru memory identified **{n_conf} conflicting decision(s)** between today's discussion and previous meeting agreements. "
                "Review the analysis below and select an executive governance choice."
            ) if n_conf else "✅ No conflicts detected with previous organizational decisions."

            # Graph update
            g_html = render_graph(pipeline.graph_data())

            success_html = (
                "<div style='color: #0F766E; font-weight: 600; padding: 10px 14px; background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 8px; margin-top: 10px;'>"
                f"⚡ Transcript processed: {n_dec} decision(s), {n_act} action item(s), {n_conf} conflict(s). Opening the Review tab..."
                "</div>"
            )

            return (
                proposal,
                gr.update(selected="tab_review"),
                n_dec, n_act, n_need_owner, n_conf,
                gr.update(value=warn_md, visible=warn_visible),
                df_actions,
                c_intro,
                gr.update(visible=c1_vis), c1_card, c1_val,
                gr.update(visible=c2_vis), c2_card, c2_val,
                gr.update(visible=c3_vis), c3_card, c3_val,
                g_html,
                success_html
            )
        except Exception as e:
            gr.Warning(f"Error processing transcript: {e}")
            return (
                {},
                gr.update(selected="tab_ingest"),
                0, 0, 0, 0,
                gr.update(value="", visible=False),
                pd.DataFrame(),
                f"Error: {e}",
                gr.update(visible=False), "", "flag",
                gr.update(visible=False), "", "replace",
                gr.update(visible=False), "", "flag",
                render_graph(pipeline.graph_data()),
                f"<div style='color: #DC2626;'>Processing error: {e}</div>"
            )

    process_btn.click(
        fn=on_process,
        inputs=[transcript_input, meeting_title, meeting_date],
        outputs=[
            proposal_state,
            tabs,
            count_decisions, count_actions, count_need_owner, count_conflicts,
            review_warnings,
            action_items_table,
            conflicts_intro,
            c1_group, c1_html, c1_radio,
            c2_group, c2_html, c2_radio,
            c3_group, c3_html, c3_radio,
            graph_html,
            ingest_msg
        ]
    )

    def on_approve(proposal, df_actions, c1_choice, c2_choice, c3_choice, email_override):
        """Execute approval with edits and conflict choices."""
        try:
            if not proposal or not proposal.get("action_items"):
                return "<div style='color: #DC2626; font-weight: 600;'>No proposal to execute. Please process a transcript first.</div>", render_graph(pipeline.graph_data())

            approved_items = []
            edits = {}
            if isinstance(df_actions, pd.DataFrame) and not df_actions.empty:
                for _, row in df_actions.iterrows():
                    idx = int(row.get("Idx", 0))
                    if bool(row.get("Approve", False)):
                        approved_items.append(idx)
                    owner_val = str(row.get("Owner", "")).strip() or None
                    deadline_val = str(row.get("Target Deadline", "")).strip() or None
                    edits[idx] = {"owner": owner_val, "deadline": deadline_val}
            else:
                approved_items = [a["idx"] for a in proposal.get("action_items", []) if not a.get("needs_review")]

            conflict_choices = {}
            conflicts = proposal.get("conflicts", [])
            choices = [c1_choice, c2_choice, c3_choice]
            for i, c in enumerate(conflicts):
                choice = choices[i] if i < len(choices) else c.get("recommendation", "flag")
                conflict_choices[c.get("idx", i)] = choice

            email = email_override.strip() if email_override and email_override.strip() else None

            res = pipeline.execute(
                proposal=proposal,
                approved_items=approved_items,
                edits=edits,
                conflict_choices=conflict_choices,
                email_override=email
            )

            # Build HTML summary of results
            results = res.get("results", [])
            errors = res.get("errors", [])

            html_out = [
                "<div style='border: 1px solid #14B8A6; border-radius: 10px; padding: 20px; background: #F0FDFA; margin-top: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>",
                "<div style='display: flex; align-items: center; gap: 8px; margin-bottom: 12px;'>",
                "<span style='font-size: 1.4em;'>🎉</span>",
                "<h3 style='color: #134E4A; margin: 0; font-size: 1.15rem; font-weight: 700;'>Execution Complete — Artifacts & Notifications Dispatched</h3>",
                "</div>",
                "<div style='font-size: 0.88rem; color: #115E59; margin-bottom: 12px;'>The following automated actions were logged into the organizational ledger:</div>",
                "<div style='display: flex; flex-direction: column; gap: 8px;'>"
            ]

            for r in results:
                rtype = r.get("type")
                if rtype == "issue":
                    url = r.get("url")
                    task = html.escape(str(r.get("task", "")))
                    link = f'<a href="{html.escape(url)}" target="_blank" style="color: #0D9488; font-weight: 700; text-decoration: none; padding: 2px 8px; background: #CCFBF1; border-radius: 4px; font-size: 0.82rem;">View GitHub Issue ↗</a>' if url else "Saved in FollowThru DB"
                    html_out.append(
                        f"<div style='background: #FFFFFF; border: 1px solid #99F6E4; border-radius: 6px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;'>"
                        f"<span><strong>GitHub Issue Created:</strong> {task}</span>"
                        f"<span>{link}</span>"
                        f"</div>"
                    )
                elif rtype == "issue_update":
                    url = r.get("url")
                    task = html.escape(str(r.get("task", "")))
                    label = html.escape(str(r.get("label", "")))
                    link = f'<a href="{html.escape(url)}" target="_blank" style="color: #0D9488; text-decoration: none;">Issue Link ↗</a>' if url else ""
                    html_out.append(
                        f"<div style='background: #FFFFFF; border: 1px solid #99F6E4; border-radius: 6px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;'>"
                        f"<span><strong>Issue Label Applied:</strong> <code>{label}</code> on <em>{task}</em></span>"
                        f"<span>{link}</span>"
                        f"</div>"
                    )
                elif rtype == "email":
                    to_person = html.escape(str(r.get("to", "")))
                    status = html.escape(str(r.get("status", "")))
                    html_out.append(
                        f"<div style='background: #FFFFFF; border: 1px solid #99F6E4; border-radius: 6px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;'>"
                        f"<span><strong>Notification Dispatched:</strong> To <strong>{to_person}</strong></span>"
                        f"<code style='color: #0F766E; font-weight: 600;'>{status}</code>"
                        f"</div>"
                    )
                elif rtype == "conflict":
                    topic = html.escape(str(r.get("topic", "")))
                    choice = html.escape(str(r.get("choice", "")))
                    detail = html.escape(str(r.get("detail", "")))
                    html_out.append(
                        f"<div style='background: #FFFFFF; border: 1px solid #99F6E4; border-radius: 6px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;'>"
                        f"<span><strong>Decision Policy Applied ({topic}):</strong> <code>{choice.upper()}</code> &middot; {detail}</span>"
                        f"<span style='color: #0F766E; font-weight: 600;'>RECORDED</span>"
                        f"</div>"
                    )
                else:
                    html_out.append(f"<div style='background: #FFFFFF; border: 1px solid #99F6E4; border-radius: 6px; padding: 10px 14px;'>{html.escape(str(r))}</div>")

            html_out.append("</div>")

            if errors:
                html_out.append("<div style='margin-top: 14px; padding: 10px 14px; background: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 6px; color: #991B1B;'><strong>Governance Notes:</strong><ul style='margin: 4px 0 0 16px;'>")
                for err in errors:
                    html_out.append(f"<li>{html.escape(str(err))}</li>")
                html_out.append("</ul></div>")

            html_out.append("</div>")

            # Refresh graph
            g_html = render_graph(pipeline.graph_data())

            return gr.update(value="".join(html_out), visible=True), g_html
        except Exception as e:
            gr.Warning(f"Error during execution: {e}")
            return gr.update(value=f"<div style='color: #DC2626; font-weight: 600;'>Execution error: {e}</div>", visible=True), render_graph(pipeline.graph_data())

    approve_btn.click(
        fn=on_approve,
        inputs=[proposal_state, action_items_table, c1_radio, c2_radio, c3_radio, email_override_input],
        outputs=[execution_results_html, graph_html]
    ).then(fn=lambda: load_task_board(), outputs=[tasks_board_table])

    # -----------------------------------------------------------------------
    # Task Board Callbacks
    # -----------------------------------------------------------------------
    def load_task_board():
        """Load saved tasks into the task board table."""
        try:
            rows = [{"ID": t["id"], "Task": t["task"], "Owner": t["owner"], "Deadline": t["deadline"],
                     "Status": str(t["status"]).upper(), "Issue URL": t["issue_url"] or "—"}
                    for t in pipeline.list_tasks()]
            if not rows:
                return pd.DataFrame(columns=["ID", "Task", "Owner", "Deadline", "Status", "Issue URL"])
            return pd.DataFrame(rows)
        except Exception as e:
            gr.Warning(f"Failed to load task board: {e}")
            return pd.DataFrame()

    refresh_tasks_btn.click(
        fn=load_task_board,
        outputs=[tasks_board_table]
    )

    def on_run_reminders(sim_date):
        """Run reminder check for simulated date."""
        try:
            today_str = sim_date.strip() or pipeline.today()
            reminders = pipeline.due_reminders(today=today_str)
            if not reminders:
                return (
                    reminders,
                    f"✅ No commitments due within 24 hours of simulated date **{today_str}**.",
                    gr.update(value=pd.DataFrame(columns=["Reminder ID", "Action ID", "Task", "Owner", "Deadline", "Message"]), visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False)
                )

            rows = []
            for r in reminders:
                rows.append({
                    "Reminder ID": r.get("reminder_id"),
                    "Action ID": r.get("action_id"),
                    "Task": r.get("task"),
                    "Owner": r.get("owner"),
                    "Deadline": r.get("deadline"),
                    "Message": r.get("message")
                })
            df = pd.DataFrame(rows)
            msg = f"🔔 Detected **{len(reminders)} deliverable(s)** due within 24 hours of **{today_str}** requiring notification."
            return (
                reminders,
                msg,
                gr.update(value=df, visible=True),
                gr.update(visible=True),
                gr.update(visible=False)
            )
        except Exception as e:
            gr.Warning(f"Error checking reminders: {e}")
            return (
                [],
                f"Error: {e}",
                gr.update(value=pd.DataFrame(), visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )

    run_reminders_btn.click(
        fn=on_run_reminders,
        inputs=[sim_date_input],
        outputs=[reminders_state, reminders_msg, reminders_table, send_reminders_btn, reminders_result_html]
    )

    def on_send_reminders(reminders):
        """Send approved reminders."""
        try:
            if not reminders:
                return gr.update(value="<div style='color: #DC2626;'>No reminders selected.</div>", visible=True)
            ids = [r.get("reminder_id") for r in reminders if r.get("reminder_id") is not None]
            sent_res = pipeline.send_reminders(ids)
            lines = [
                "<div style='background: #F0FDFA; border: 1px solid #14B8A6; border-radius: 8px; padding: 14px; margin-top: 12px;'>",
                "<h4 style='color: #134E4A; margin: 0 0 8px 0;'>✅ Reminder Dispatch Log</h4>",
                "<div style='display: flex; flex-direction: column; gap: 6px;'>"
            ]
            for item in sent_res:
                lines.append(
                    f"<div style='background: white; border: 1px solid #99F6E4; padding: 6px 12px; border-radius: 4px; font-size: 0.88em;'>"
                    f"Reminder #{item.get('reminder_id')}: <strong>{html.escape(str(item.get('status', 'sent')))}</strong>"
                    f"</div>"
                )
            lines.append("</div></div>")
            return gr.update(value="".join(lines), visible=True)
        except Exception as e:
            gr.Warning(f"Error sending reminders: {e}")
            return gr.update(value=f"<div style='color: #DC2626;'>Error sending reminders: {e}</div>", visible=True)

    send_reminders_btn.click(
        fn=on_send_reminders,
        inputs=[reminders_state],
        outputs=[reminders_result_html]
    )

    # -----------------------------------------------------------------------
    # Digest Callbacks
    # -----------------------------------------------------------------------
    def on_build_digest(person, date_str):
        """Build digest preview."""
        try:
            d = pipeline.build_digest(person=person, today=date_str.strip() or pipeline.today())
            stats = d.get("stats", {})
            stats_html = (
                f"<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 12px 0 16px 0;'>"
                f"<div style='background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px; text-align: center;'><div style='font-size: 0.75rem; color: #64748B; font-weight: 700; text-transform: uppercase;'>Open Deliverables</div><div style='font-size: 1.5rem; font-weight: 800; color: #0F1B3D;'>{stats.get('open', 0)}</div></div>"
                f"<div style='background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 10px 14px; text-align: center;'><div style='font-size: 0.75rem; color: #B91C1C; font-weight: 700; text-transform: uppercase;'>Overdue</div><div style='font-size: 1.5rem; font-weight: 800; color: #DC2626;'>{stats.get('overdue', 0)}</div></div>"
                f"<div style='background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 8px; padding: 10px 14px; text-align: center;'><div style='font-size: 0.75rem; color: #115E59; font-weight: 700; text-transform: uppercase;'>Completed</div><div style='font-size: 1.5rem; font-weight: 800; color: #0D9488;'>{stats.get('done', 0)}</div></div>"
                f"<div style='background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 8px; padding: 10px 14px; text-align: center;'><div style='font-size: 0.75rem; color: #0F766E; font-weight: 700; text-transform: uppercase;'>On-Time Rate</div><div style='font-size: 1.5rem; font-weight: 800; color: #0D9488;'>{stats.get('on_time_rate', 'N/A')}</div></div>"
                f"</div>"
            )
            preview_md = f"#### 📧 {d.get('subject', 'Weekly Digest')}\n\n```text\n{d.get('body', '')}\n```"
            return stats_html, preview_md
        except Exception as e:
            gr.Warning(f"Error building digest: {e}")
            return "", f"Error generating digest: {e}"

    build_digest_btn.click(
        fn=on_build_digest,
        inputs=[digest_person, digest_date],
        outputs=[digest_stats_markdown, digest_preview]
    )

    def on_send_digest(person):
        """Send digest email."""
        try:
            status = pipeline.send_digest(person=person)
            return f"✅ **Executive digest dispatched to {person}:** `{status}`"
        except Exception as e:
            gr.Warning(f"Error sending digest: {e}")
            return f"❌ Failed to send digest: {e}"

    send_digest_btn.click(
        fn=on_send_digest,
        inputs=[digest_person],
        outputs=[send_digest_status]
    )

    # -----------------------------------------------------------------------
    # Ask Memory Callbacks
    # -----------------------------------------------------------------------
    def on_ask_memory(question, history):
        """Ask organizational memory with trace output."""
        try:
            if not question.strip():
                return history, "*(Please ask a question)*"

            resp = pipeline.ask_memory(question.strip())
            answer = resp.get("answer", "No answer provided.")
            trace = resp.get("trace", [])

            history = history or []
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})

            # Format trace markdown
            trace_md = []
            if trace:
                trace_md.append("#### 🛠️ Agent Thought Process & Tool Trace\n")
                for i, step in enumerate(trace, 1):
                    tool = step.get("tool", "unknown_tool")
                    args = json.dumps(step.get("args", {}), indent=2)
                    result = step.get("result", "")
                    trace_md.append(f"**Step {i}: Tool Invoked &rarr; `{tool}`**")
                    trace_md.append(f"```json\nArguments:\n{args}\n```")
                    trace_md.append(f"> 📌 **Observation:** `{result}`\n")
            else:
                trace_md.append("*(No tool trace recorded)*")

            return history, "\n".join(trace_md)
        except Exception as e:
            gr.Warning(f"Error in memory retrieval: {e}")
            history = history or []
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": f"Error: {e}"})
            return history, f"Error: {e}"

    chat_send_btn.click(
        fn=on_ask_memory,
        inputs=[chat_msg, chatbot],
        outputs=[chatbot, trace_output]
    ).then(
        fn=lambda: "",
        outputs=[chat_msg]
    )

    chat_msg.submit(
        fn=on_ask_memory,
        inputs=[chat_msg, chatbot],
        outputs=[chatbot, trace_output]
    ).then(
        fn=lambda: "",
        outputs=[chat_msg]
    )

    # -----------------------------------------------------------------------
    # Reset Demo
    # -----------------------------------------------------------------------
    def on_reset():
        """Reset demo pipeline state."""
        try:
            pipeline.reset_demo()
            g_html = render_graph(pipeline.graph_data())
            return (
                {},
                "", "", pipeline.today(), "",
                0, 0, 0, 0,
                pd.DataFrame(),
                g_html,
                gr.update(value="✅ Demo state reset successfully.", visible=True)
            )
        except Exception as e:
            gr.Warning(f"Error resetting demo: {e}")
            return (
                {},
                "", "", pipeline.today(), "",
                0, 0, 0, 0,
                pd.DataFrame(),
                render_graph(pipeline.graph_data()),
                gr.update(value=f"Error resetting: {e}", visible=True)
            )

    reset_btn.click(
        fn=on_reset,
        outputs=[
            proposal_state,
            transcript_input, meeting_title, meeting_date, ingest_msg,
            count_decisions, count_actions, count_need_owner, count_conflicts,
            action_items_table,
            graph_html,
            reset_status
        ]
    ).then(fn=lambda: load_task_board(), outputs=[tasks_board_table])

    # Initial load of task board when app opens
    demo.load(
        fn=load_task_board,
        outputs=[tasks_board_table]
    )


if __name__ == "__main__":
    demo.launch(theme=custom_theme, css=CUSTOM_CSS)  # host/port come from env, so it works locally and on Hugging Face
