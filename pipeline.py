"""FollowThru pipeline — the real version of mock_pipeline.py (same functions, same dict keys).

Flow:  process_transcript()  ->  (human reviews in UI)  ->  execute()
       process_transcript saves NOTHING and posts NOTHING. execute() runs only after approval.
"""
import json
from concurrent.futures import ThreadPoolExecutor
import os
import re
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from agent import llm  # noqa: E402
from agent.core import Agent  # noqa: E402
from agent.prompts import CONFLICT_PROMPT, EXTRACTION_PROMPT, MEMORY_PROMPT  # noqa: E402
from services import db, extraction, mailer, system1, tracker  # noqa: E402
from services import transcript as tx  # noqa: E402

db.init_db()
system1.warm_up()  # no-op unless LAYA_MODE=local
_s1_pool = ThreadPoolExecutor(max_workers=1)
if not db.list_meetings():  # fresh deploy -> load the 14 Nov meeting so conflicts can be demoed
    import seed
    seed.seed()


def today() -> str:
    return date.today().isoformat()


def _fill(prompt: str, **values) -> str:
    for k, v in values.items():
        prompt = prompt.replace("{{" + k + "}}", str(v))
    return prompt


def _date_table(meeting_date: str) -> str:
    """Pre-computed dates so the LLM never does calendar arithmetic."""
    d0 = datetime.strptime(meeting_date, "%Y-%m-%d").date()
    rows = [f"- today = {d0.isoformat()}", f"- tomorrow / kal = {(d0 + timedelta(days=1)).isoformat()}"]
    for i in range(1, 8):
        d = d0 + timedelta(days=i)
        rows.append(f"- {d.strftime('%A')} (this coming) = {d.isoformat()}")
    rows.append(f"- next week = {(d0 + timedelta(days=7)).isoformat()}")
    return "\n".join(rows)


def _llm_json(system: str, user: str) -> dict:
    msg = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True)
    return extraction.parse_json(msg.content)


def _parse_header(text: str):
    """Optional first line: '# Title | 2026-11-21 | Attendees: A, B, C'."""
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if not first.startswith("#"):
        return {}
    parts = [p.strip() for p in first.lstrip("#").split("|")]
    out = {"title": parts[0]} if parts else {}
    for p in parts[1:]:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
            out["date"] = p
        elif p.lower().startswith("attendees:"):
            names = re.sub(r"\(.*?\)", "", p.split(":", 1)[1])
            out["attendees"] = [n.strip() for n in names.split(",") if n.strip()]
    return out


# ---------------------------------------------------------------------------
# 1. Understand (no side effects)
# ---------------------------------------------------------------------------
def process_transcript(text: str, filename: str = "", title: str = "", meeting_date: str = "",
                       attendees: list[str] | None = None) -> dict:
    if EXTRACTION_PROMPT is None:
        raise RuntimeError("EXTRACTION_PROMPT is not written yet (agent/prompts.py).")
    trace = []
    header = _parse_header(text)
    turns = tx.parse(text, filename)
    title = title or header.get("title") or "Untitled meeting"
    meeting_date = meeting_date or header.get("date") or today()
    attendees = attendees or header.get("attendees") or tx.speakers(turns)
    weekday = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%A")
    trace.append({"type": "tool", "tool": "parse_transcript", "args": {"file": filename or "pasted"},
                  "result": f"{len(turns)} turns, speakers: {', '.join(tx.speakers(turns))}"})

    # who usually attends but was missing today (used for "original decider absent")
    known = {p["name"] for p in db.list_people()}
    absent = sorted(n for n in known if n.lower() not in {a.lower() for a in attendees})

    # --- extraction (System 2 LLM) ---
    system = _fill(EXTRACTION_PROMPT, MEETING_DATE=meeting_date, WEEKDAY=weekday, ATTENDEES=", ".join(attendees),
                   DATE_TABLE=_date_table(meeting_date))
    # System 1 (Laya) runs in parallel with the LLM call, so it adds little or no waiting time
    s1_future = _s1_pool.submit(system1.screen, turns) if system1.MODE == "local" else None
    raw = _llm_json(system, tx.format_for_llm(turns))
    data, warnings = extraction.validate(raw, attendees)
    for i, d in enumerate(data["decisions"]):
        d["idx"] = i
    for i, a in enumerate(data["action_items"]):
        a["idx"] = i
    vague = sum(a["vague"] for a in data["action_items"])
    trace.append({"type": "tool", "tool": "extract_meeting", "args": {"turns": len(turns)},
                  "result": f"{len(data['decisions'])} decisions, {len(data['action_items'])} action items ({vague} vague)"})

    # --- System 1 (Laya) safety net: fast per-line screen, can only ADD review flags ---
    screened = s1_future.result() if s1_future else None
    if screened:
        s1_warnings = system1.cross_check(screened, data["action_items"], turns)
        warnings += s1_warnings
        n_commit = sum(v["kind"] == "commitment" for v in screened["labels"].values())
        trace.append({"type": "tool", "tool": "system1_screen (Laya)", "args": {"turns": len(turns)},
                      "result": f"screened {screened['screened']}/{screened['total']} lines in {screened['ms']} ms (parallel with LLM); "
                                f"{n_commit} commitment(s), {len(s1_warnings)} extra review flag(s)"})

    # --- conflict check against memory ---
    conflicts = []
    candidates = {}
    for d in data["decisions"]:
        hits = db.search_decisions(f"{d['topic']} {d['text']}", status="active", limit=5)
        hits += [p for p in db.list_decisions("active") if p["topic"] == d["topic"]]
        for h in hits:
            candidates[h["id"]] = h
        trace.append({"type": "tool", "tool": "search_past_decisions", "args": {"topic": d["topic"]},
                      "result": f"{len(hits)} candidate(s)" if hits else "no related past decisions"})

    if candidates and data["decisions"]:
        past = [{"id": p["id"], "topic": p["topic"], "text": p["text"], "speaker": p["speaker"],
                 "meeting_date": p["meeting_date"]} for p in candidates.values()]
        new = [{"idx": d["idx"], "topic": d["topic"], "text": d["text"], "speaker": d["speaker"]} for d in data["decisions"]]
        result = _llm_json(_fill(CONFLICT_PROMPT, MEETING_DATE=meeting_date, ATTENDEES=", ".join(attendees)),
                           json.dumps({"new_decisions": new, "past_decisions": past}, ensure_ascii=False))
        for c in result.get("conflicts", []):
            old = candidates.get(c.get("old_id"))
            try:
                new_d = data["decisions"][int(c.get("new_idx"))]
            except (TypeError, ValueError, IndexError):
                continue
            if not old:
                continue
            impact = [{"action_id": t["id"], "task": t["task"], "owner": t["owner"], "deadline": t["deadline"],
                       "issue_number": t["issue_number"], "issue_url": t["issue_url"]}
                      for t in db.tasks_for_decision(old["id"]) if t["status"] == "approved"]
            rec = c.get("recommendation") if c.get("recommendation") in ("replace", "keep_old", "flag") else "flag"
            conflicts.append({
                "idx": len(conflicts), "topic": new_d["topic"],
                "new": {"text": new_d["text"], "speaker": new_d["speaker"], "quote": new_d["quote"],
                        "turn_ids": new_d["turn_ids"], "meeting_date": meeting_date, "decision_idx": new_d["idx"]},
                "old": {"id": old["id"], "text": old["text"], "speaker": old["speaker"], "quote": old["quote"],
                        "meeting_title": old["meeting_title"], "meeting_date": old["meeting_date"]},
                "explanation": c.get("explanation", ""),
                "impact": impact,
                "original_decider_absent": bool(old["speaker"]) and old["speaker"].lower() not in {a.lower() for a in attendees},
                "recommendation": rec, "reason": c.get("reason", ""),
            })
        trace.append({"type": "tool", "tool": "check_conflicts", "args": {"past_decisions": len(past)},
                      "result": f"{len(conflicts)} conflict(s); {sum(len(c['impact']) for c in conflicts)} open task(s) affected"})

    return {"meeting": {"title": title, "date": meeting_date, "attendees": attendees, "absent": absent},
            "turns": turns, "decisions": data["decisions"], "action_items": data["action_items"],
            "conflicts": conflicts, "warnings": warnings, "trace": trace, "_transcript": text,
            "system1": {"status": system1.status(), "ms": screened["ms"] if screened else None}}


# ---------------------------------------------------------------------------
# 2. Act (only after human approval)
# ---------------------------------------------------------------------------
def _safe(results, errors, label, fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — one failure must not stop the rest
        errors.append(f"{label}: {e}")


def execute(proposal: dict, approved_items: list[int], edits: dict | None = None,
            conflict_choices: dict | None = None, email_override: str | None = None) -> dict:
    edits = {int(k): v for k, v in (edits or {}).items()}
    conflict_choices = {int(k): v for k, v in (conflict_choices or {}).items()}
    approved = {int(i) for i in approved_items}
    m = proposal["meeting"]
    results, errors = [], []

    mid = db.save_meeting(m["title"], m["date"], m["attendees"], proposal.get("_transcript", ""))
    for name in m["attendees"]:
        db.upsert_person(name)

    # decisions
    conflict_by_decision = {c["new"]["decision_idx"]: c for c in proposal["conflicts"]}
    decision_ids = {}
    for d in proposal["decisions"]:
        c = conflict_by_decision.get(d["idx"])
        choice = conflict_choices.get(c["idx"], c["recommendation"]) if c else None
        status = {"replace": "active", "keep_old": "discussion", "flag": "disputed"}.get(choice, "active")
        decision_ids[d["topic"]] = new_id = db.add_decision(mid, d["topic"], d["text"], d["speaker"], d["quote"],
                                                            d["turn_ids"], status=status)
        if not c:
            continue
        old_id = c["old"]["id"]
        db.add_conflict(new_id, old_id, choice, c["explanation"])
        if choice == "replace":
            db.set_decision_status(old_id, "superseded", superseded_by=new_id)
            note, label = (f"⚠️ Decision changed on {m['date']}: \"{c['old']['text']}\" → \"{d['text']}\" "
                           f"({d['speaker']}). This task may need updating."), "needs-update"
        elif choice == "flag":
            db.set_decision_status(old_id, "disputed")
            note, label = (f"⚠️ Disputed on {m['date']}: \"{d['text']}\" ({d['speaker']}) conflicts with "
                           f"\"{c['old']['text']}\" ({c['old']['speaker']}, {c['old']['meeting_date']}). "
                           "Hold until the team decides."), "disputed"
        else:
            note = label = None
        results.append({"type": "conflict", "topic": c["topic"], "choice": choice,
                        "detail": f"{c['old']['text']} → {d['text']}"})
        if note:
            for t in c["impact"]:
                if t.get("issue_number") and tracker.configured():
                    _safe(results, errors, f"comment #{t['issue_number']}",
                          lambda t=t: (tracker.comment(t["issue_number"], note),
                                       tracker.add_labels(t["issue_number"], [label])))
                    results.append({"type": "issue_update", "task": t["task"], "url": t["issue_url"], "label": label})
                status = _safe(results, errors, f"email {t['owner']}", lambda t=t: mailer.send(
                    t["owner"], f"[FollowThru] Decision change affects: {t['task']}",
                    f"Hi {t['owner']},\n\n{note}\n\nYour task: {t['task']} (due {t['deadline']})\n"
                    f"{t.get('issue_url') or ''}\n", email_override))
                results.append({"type": "email", "to": t["owner"], "status": status})

    # action items
    for a in proposal["action_items"]:
        a = {**a, **edits.get(a["idx"], {})}
        if a["idx"] not in approved:
            db.add_action_item(mid, a["task"], a["owner"], a["deadline"], a["quote"], a["turn_ids"], status="rejected")
            continue
        if not a.get("owner") or not a.get("deadline"):
            errors.append(f"'{a['task']}' needs an owner and a deadline before it can be approved.")
            continue
        aid = db.add_action_item(mid, a["task"], a["owner"], a["deadline"], a["quote"], a["turn_ids"],
                                 decision_ids.get(a.get("related_decision_topic")), status="approved")
        url = None
        if tracker.configured():
            created = _safe(results, errors, f"issue '{a['task']}'", lambda a=a: tracker.create_issue(
                a["task"], tracker.issue_body(a["task"], a["owner"], a["deadline"], m["title"], m["date"],
                                              a["quote"])))
            if created:
                db.update_action_item(aid, issue_number=created[0], issue_url=created[1])
                url = created[1]
        else:
            errors.append("GitHub not configured: task saved in FollowThru only.")
        results.append({"type": "issue", "task": a["task"], "owner": a["owner"], "url": url})
        due = datetime.strptime(a["deadline"], "%Y-%m-%d") - timedelta(days=1)
        db.add_reminder(aid, due.strftime("%Y-%m-%dT09:00"))
        status = _safe(results, errors, f"email {a['owner']}", lambda a=a, url=url: mailer.send(
            a["owner"], f"[FollowThru] New task: {a['task']} (due {a['deadline']})",
            f"Hi {a['owner']},\n\nYou were assigned a task in \"{m['title']}\" ({m['date']}):\n\n"
            f"  {a['task']}\n  Due: {a['deadline']}\n  You said: \"{a['quote']}\"\n\n{url or ''}\n", email_override))
        results.append({"type": "email", "to": a["owner"], "status": status})

    return {"meeting_id": mid, "results": results, "errors": list(dict.fromkeys(errors))}


# ---------------------------------------------------------------------------
# 3. Follow-up
# ---------------------------------------------------------------------------
def due_reminders(today: str | None = None) -> list[dict]:
    now = f"{today or date.today().isoformat()}T23:59"
    return [{"reminder_id": r["reminder_id"], "action_id": r["id"], "task": r["task"], "owner": r["owner"],
             "deadline": r["deadline"], "issue_url": r["issue_url"],
             "message": f"Reminder: '{r['task']}' is due {r['deadline']}."} for r in db.due_reminders(now)]


def send_reminders(reminder_ids: list[int], email_override: str | None = None) -> list[dict]:
    out = []
    for rid in reminder_ids:
        r = db.get_reminder(int(rid))
        if not r or r["sent"]:
            continue
        status = mailer.send(r["owner"], f"[FollowThru] Reminder: {r['task']} is due {r['deadline']}",
                             f"Hi {r['owner']},\n\nFriendly reminder: \"{r['task']}\" is due on {r['deadline']}.\n"
                             f"{r['issue_url'] or ''}\n", email_override)
        db.mark_reminder_sent(r["reminder_id"])
        out.append({"reminder_id": r["reminder_id"], "status": status})
    return out


def build_digest(person: str, today: str | None = None) -> dict:
    d = db.digest_data(person, today)
    lines = [f"Hi {person},", "", f"Your FollowThru weekly digest ({d['today']})", ""]
    lines.append(f"Open tasks ({len(d['open'])}):")
    for t in d["open"]:
        flag = "  ⚠️ OVERDUE" if t in d["overdue"] else ""
        lines.append(f"  • {t['task']} (due {t['deadline']}){flag} {t['issue_url'] or ''}")
    lines += ["", f"Completed: {len(d['done'])} · On-time rate: {d['on_time_rate']}", "", "Recent decisions:"]
    for dec in d["decisions"]:
        tag = "" if dec["status"] == "active" else f" [{dec['status']}]"
        lines.append(f"  • {dec['meeting_date']}: {dec['text']}{tag}")
    return {"person": person, "subject": f"[FollowThru] Your weekly digest — {person}", "body": "\n".join(lines),
            "stats": {"open": len(d["open"]), "overdue": len(d["overdue"]), "done": len(d["done"]),
                      "on_time_rate": d["on_time_rate"]}}


def send_digest(person: str, email_override: str | None = None) -> str:
    dg = build_digest(person)
    return mailer.send(person, dg["subject"], dg["body"], email_override)


def ask_memory(question: str) -> dict:
    agent = Agent(system_prompt=MEMORY_PROMPT)
    out = agent.send(question)
    return {"answer": out.get("answer", ""), "trace": agent.trace}


# ---------------------------------------------------------------------------
# 4. Graph + demo helpers
# ---------------------------------------------------------------------------
def graph_data() -> dict:
    nodes, edges = [], []
    decisions = {d["id"]: d for d in db.list_decisions(status=None)}
    for d in decisions.values():
        nodes.append({"id": f"d{d['id']}", "label": d["text"][:80], "type": "decision", "status": d["status"]})
        if d["superseded_by"]:
            edges.append({"from": f"d{d['superseded_by']}", "to": f"d{d['id']}", "type": "supersedes"})
    for c in db.list_conflicts():
        if c["choice"] != "replace":
            edges.append({"from": f"d{c['new_decision_id']}", "to": f"d{c['old_decision_id']}", "type": "conflicts"})
    for a in db.list_action_items(status=("approved", "done")):
        dec = decisions.get(a["decision_id"])
        at_risk = a["status"] == "approved" and dec and dec["status"] in ("superseded", "disputed")
        nodes.append({"id": f"a{a['id']}", "label": f"{a['task'][:60]} ({a['owner']})", "type": "task",
                      "status": "at_risk" if at_risk else a["status"]})
        if dec:
            edges.append({"from": f"d{dec['id']}", "to": f"a{a['id']}", "type": "has_task"})
    return {"nodes": nodes, "edges": edges}


def list_tasks() -> list[dict]:
    """All saved tasks (approved / done) for the Task Board."""
    return [{"id": a["id"], "task": a["task"], "owner": a["owner"], "deadline": a["deadline"],
             "status": a["status"], "issue_url": a["issue_url"], "meeting_date": a["meeting_date"]}
            for a in db.list_action_items(status=("approved", "done"))]


def list_people() -> list[str]:
    return [p["name"] for p in db.list_people()]


def reset_demo() -> None:
    """Restore the 14 Nov memory and close demo issues from earlier runs (seed issues stay open)."""
    import seed
    if tracker.configured():
        try:
            for issue in tracker.list_open_issues("meeting-agent"):
                if "seed" not in issue["labels"]:
                    tracker.close_issue(issue["number"], reason="not_planned")
        except Exception as e:  # noqa: BLE001 — cleanup must never block the reset
            print(f"[reset] closing old demo issues skipped: {e}")
    db.reset_db()
    seed.seed()
