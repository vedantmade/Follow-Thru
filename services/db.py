"""SQLite memory: meetings, decisions, action items, people, reminders, outbox.

DB file: DB_PATH env var (default data/meetings.db). Call init_db() once at startup.
All functions return plain dicts so they can go straight to the LLM or the UI.
"""
import json
import os
import re
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "meetings.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY, title TEXT, date TEXT, attendees TEXT, transcript TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, meeting_id INTEGER, topic TEXT, text TEXT, speaker TEXT, quote TEXT,
    turn_ids TEXT, status TEXT DEFAULT 'active',          -- active | superseded | disputed
    superseded_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY, meeting_id INTEGER, task TEXT, owner TEXT, deadline TEXT,
    quote TEXT, turn_ids TEXT, decision_id INTEGER,
    status TEXT DEFAULT 'draft',                           -- draft | approved | done | rejected
    completed_at TEXT, issue_number INTEGER, issue_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS people (name TEXT PRIMARY KEY, email TEXT);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY, action_id INTEGER, send_at TEXT, sent INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY, new_decision_id INTEGER, old_decision_id INTEGER, choice TEXT,
    explanation TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY, recipient TEXT, email TEXT, subject TEXT, body TEXT,
    status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as c:
        c.executescript(SCHEMA)


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def _q(sql, args=()):
    with connect() as c:
        return _rows(c.execute(sql, args))


def _x(sql, args=()):
    with connect() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


# ---------------- meetings ----------------
def save_meeting(title, date, attendees, transcript) -> int:
    return _x("INSERT INTO meetings (title, date, attendees, transcript) VALUES (?,?,?,?)",
              (title, date, json.dumps(attendees), transcript))


def get_meeting(meeting_id):
    r = _q("SELECT * FROM meetings WHERE id=?", (meeting_id,))
    return r[0] if r else None


def list_meetings():
    return _q("SELECT id, title, date, attendees FROM meetings ORDER BY date, id")


# ---------------- decisions ----------------
def add_decision(meeting_id, topic, text, speaker, quote, turn_ids=None, status="active") -> int:
    return _x("INSERT INTO decisions (meeting_id, topic, text, speaker, quote, turn_ids, status) VALUES (?,?,?,?,?,?,?)",
              (meeting_id, topic, text, speaker, quote, json.dumps(turn_ids or []), status))


def list_decisions(status="active"):
    sql = """SELECT d.*, m.title AS meeting_title, m.date AS meeting_date, m.attendees AS meeting_attendees
             FROM decisions d JOIN meetings m ON m.id = d.meeting_id"""
    if status:
        return _q(sql + " WHERE d.status=? ORDER BY m.date", (status,))
    return _q(sql + " ORDER BY m.date")


def search_decisions(query, status="active", limit=5):
    """Simple keyword search over topic + text + quote. Good enough for a small memory."""
    words = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}
    scored = []
    for d in list_decisions(status):
        hay = f"{d['topic']} {d['text']} {d['quote']}".lower()
        score = sum(w in hay for w in words) + (3 if d["topic"] and d["topic"].lower() in query.lower() else 0)
        if score:
            scored.append((score, d))
    return [d for _, d in sorted(scored, key=lambda s: -s[0])[:limit]]


def set_decision_status(decision_id, status, superseded_by=None):
    _x("UPDATE decisions SET status=?, superseded_by=? WHERE id=?", (status, superseded_by, decision_id))


# ---------------- action items ----------------
def add_action_item(meeting_id, task, owner, deadline, quote, turn_ids=None, decision_id=None, status="draft") -> int:
    return _x("""INSERT INTO action_items (meeting_id, task, owner, deadline, quote, turn_ids, decision_id, status)
                 VALUES (?,?,?,?,?,?,?,?)""",
              (meeting_id, task, owner, deadline, quote, json.dumps(turn_ids or []), decision_id, status))


def list_action_items(owner=None, status=None):
    sql = """SELECT a.*, m.title AS meeting_title, m.date AS meeting_date
             FROM action_items a JOIN meetings m ON m.id = a.meeting_id WHERE 1=1"""
    args = []
    if owner:
        sql += " AND lower(a.owner)=lower(?)"
        args.append(owner)
    if status:
        statuses = [status] if isinstance(status, str) else list(status)
        sql += f" AND a.status IN ({','.join('?' * len(statuses))})"
        args += statuses
    return _q(sql + " ORDER BY a.deadline", args)


def tasks_for_decision(decision_id):
    return _q("SELECT * FROM action_items WHERE decision_id=? AND status IN ('approved','draft')", (decision_id,))


def update_action_item(action_id, **fields):
    allowed = {"task", "owner", "deadline", "status", "issue_number", "issue_url", "completed_at", "decision_id"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        _x(f"UPDATE action_items SET {sets} WHERE id=?", (*fields.values(), action_id))


# ---------------- people ----------------
def upsert_person(name, email=None):
    _x("INSERT INTO people (name, email) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET email=COALESCE(excluded.email, people.email)",
       (name, email))


def get_email(name):
    r = _q("SELECT email FROM people WHERE lower(name)=lower(?)", (name,))
    return r[0]["email"] if r and r[0]["email"] else None


def list_people():
    return _q("SELECT * FROM people ORDER BY name")


# ---------------- reminders ----------------
def add_reminder(action_id, send_at):
    return _x("INSERT INTO reminders (action_id, send_at) VALUES (?,?)", (action_id, send_at))


def due_reminders(now: str):
    """Unsent reminders whose send_at <= now (ISO strings compare correctly)."""
    return _q("""SELECT r.id AS reminder_id, r.send_at, a.* FROM reminders r
                 JOIN action_items a ON a.id = r.action_id
                 WHERE r.sent=0 AND r.send_at<=? AND a.status='approved'""", (now,))


def mark_reminder_sent(reminder_id):
    _x("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))


# ---------------- conflicts ----------------
def add_conflict(new_decision_id, old_decision_id, choice, explanation):
    return _x("INSERT INTO conflicts (new_decision_id, old_decision_id, choice, explanation) VALUES (?,?,?,?)",
              (new_decision_id, old_decision_id, choice, explanation))


def list_conflicts():
    return _q("SELECT * FROM conflicts ORDER BY id")


def get_reminder(reminder_id):
    r = _q("""SELECT r.id AS reminder_id, r.send_at, r.sent, a.* FROM reminders r
              JOIN action_items a ON a.id = r.action_id WHERE r.id=?""", (reminder_id,))
    return r[0] if r else None


# ---------------- outbox (every email is logged here, sent or not) ----------------
def log_outbox(recipient, email, subject, body, status):
    return _x("INSERT INTO outbox (recipient, email, subject, body, status) VALUES (?,?,?,?,?)",
              (recipient, email, subject, body, status))


def list_outbox():
    return _q("SELECT * FROM outbox ORDER BY id DESC")


# ---------------- digest ----------------
def digest_data(person, today: str | None = None):
    today = today or datetime.now().strftime("%Y-%m-%d")
    items = list_action_items(owner=person, status=("approved", "done"))
    open_items = [i for i in items if i["status"] == "approved"]
    overdue = [i for i in open_items if i["deadline"] and i["deadline"] < today]
    done = [i for i in items if i["status"] == "done"]
    on_time = [i for i in done if i["completed_at"] and i["deadline"] and i["completed_at"][:10] <= i["deadline"]]
    decisions = [d for d in list_decisions(status=None) if person.lower() in (d["meeting_attendees"] or "").lower()]
    return {
        "person": person, "today": today, "open": open_items, "overdue": overdue, "done": done,
        "on_time_rate": f"{len(on_time)}/{len(done)}" if done else "n/a",
        "decisions": decisions[-10:],
    }


def reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
