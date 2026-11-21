---
title: FollowThru
emoji: ✅
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 6.32.0
app_file: app.py
pinned: false
short_description: Meeting-to-Execution agent with conflict detection
---

# FollowThru — Meeting-to-Execution Agent

> Meeting tools tell you what was said. **FollowThru tells you what changed, what it breaks, and who needs to act** — and waits for your approval before touching anything.

**Live demo:** `<Hugging Face Space link>` · **Demo video:** `<Drive link>` · **Task tracker:** `<github.com/you/meeting-tasks>`

---

## 1. Problem
Decisions made in meetings get lost. A later meeting quietly reverses an earlier decision, nobody notices which tasks it breaks, and commitments like *"someone should fix the API soon"* never get an owner. Meeting summarisers list action items, but they look at **one meeting at a time** and don't connect decisions across meetings.

## 2. Solution
FollowThru is an agent that turns a meeting transcript into tracked work **and** checks it against the team's decision memory:

- **Extracts** decisions and action items with owner, deadline, exact quote and turn numbers.
- **Resolves owners** from "I'll", a named "you", an unnamed "you" that someone accepts, "he/she", and **Hinglish** ("kal tak bhej dunga").
- **Flags vague commitments** ("we / someone / soon") instead of guessing.
- **Detects conflicts** with past decisions, shows **which open tasks and GitHub issues they break**, and checks whether the **original decision-maker was absent**.
- **Recommends** replace / keep old / flag, but **a human approves** every action.
- **Acts** after approval: creates GitHub issues, comments on and labels affected issues, emails owners, schedules reminders, builds weekly digests.
- **Visualises** decisions → tasks as a graph, with conflicts and at-risk work in red, and answers *"Why did we switch to MongoDB?"* with who said it and when.

## 3. Architecture
```
 .txt / .vtt transcript (Zoom, Meet, Teams export)
          │
          ▼
 ① Parse ── speaker turns T1…Tn, attendees, absentees          services/transcript.py
          ▼
 ② Extract ── Gemini + extraction prompt + pre-computed dates   agent/prompts.py, services/extraction.py
          ▼
 ③ Memory check ── search past decisions (SQLite) → Gemini judges conflict
                   → impact on open tasks → original decider absent?   pipeline.py, services/db.py
          ▼
 ④ Review (human) ── edit owners/dates, pick conflict resolution, approve   app.py
          ▼
 ⑤ Execute ── GitHub Issues · Gmail · reminders · decision status updates   services/tracker.py, mailer.py
          ▼
 ⑥ Follow-up ── task board · reminders · weekly digest · graph · Ask Memory (agent loop + tools)
```
Code handles what must be reliable (parsing, dates, validation, posting). The LLM handles what needs judgment (extraction, conflict reasoning, answering questions). **Nothing is saved or posted before approval.**

## 4. Try it (2 minutes)
1. Memory is pre-loaded with the **14 Nov sprint sync** (PostgreSQL, launch on 10 Dec, ₹499 pricing) and its GitHub issues.
2. Click **Load sample: 21 Nov sprint sync** → **Process Transcript**.
3. On **Review & Approve**: see 2 conflicts (Postgres → MongoDB is flagged because Priya was absent; 10 Dec → 5 Dec is replaced), assign the vague task, then **Approve**.
4. Check the new issues in the tracker repo, the **graph**, **Task Board** reminders, **Weekly Digest** and **Ask Memory**.

**Reset Demo State** restores the original memory. Expected output: `data/samples/EXPECTED_demo_meeting.md`.

## 5. Run locally
```bash
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                               # macOS/Linux: cp — then add your keys
python seed.py --reset                               # loads the 14 Nov meeting + its GitHub issues
python try_pipeline.py data/samples/demo_meeting_2026-11-21.txt   # terminal test, no side effects
python app.py                                        # http://127.0.0.1:7860
```
Keys in `.env`: `GEMINI_API_KEY` (required), `GITHUB_TOKEN` + `GITHUB_REPO` (fine-grained token, Issues read/write), optional `GROQ_API_KEY` (fallback LLM) and `GMAIL_USER` + `GMAIL_APP_PASSWORD`. Without Gmail, emails are kept in the app's outbox.

## 6. Tech stack
| Layer | Technology |
|---|---|
| UI | Gradio (custom CSS), pyvis graph |
| LLM | Gemini Flash (OpenAI-compatible API), Groq as automatic fallback |
| Agent | Custom tool-calling loop with human-approval step (`agent/core.py`) |
| Memory | SQLite |
| Integrations | GitHub Issues REST API, Gmail SMTP |
| Hosting | Hugging Face Spaces |

## 7. Project structure
```
app.py              Gradio UI (5 tabs)            pipeline.py        orchestration (process → execute → follow-up)
agent/              LLM client, agent loop, prompts, memory tools
services/           transcript parser, SQLite, extraction checks, GitHub, Gmail
ui/graph.py         decision → task graph         seed.py            loads the 14 Nov meeting
data/samples/       demo transcripts + expected outputs
```

## 8. Contribution vs AI-generated output
| Part | By |
|---|---|
| Problem choice, scope, product design, demo script, testing, video | Vedant Made & Siddhart Gupta |
| Architecture, backend services, pipeline, prompts | Vedant Made, AI-assisted (Claude) |
| Gradio UI, graph, AI integration in the UI | Siddhart Gupta, AI-assisted (Gemini Pro) |
| Starter template (agent loop, LLM client) | AI-generated, prepared before the problem statement |

## 9. Future scope
- **Live mode:** run the same agent on transcript chunks during the call: *"Before you leave: 2 action items have no owner."*
- **System 1 + System 2:** a fast decision model (e.g. Laya) screens every line in milliseconds; the LLM handles only reasoning.
- Direct audio upload with speaker diarisation; Jira, Linear and Notion trackers; Slack reminders.

## 10. Team
- **Vedant Made** — Architecture and Backend ([GitHub](https://github.com/vedantmade) · [LinkedIn](https://linkedin.com/in/vedant-made))
- **Siddhart Gupta** — UI and AI
