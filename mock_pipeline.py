"""MOCK of pipeline.py — same function names and return shapes, fake data.

The UI (app.py) imports this while the real pipeline is being built:
    import mock_pipeline as pipeline        # now
    import pipeline                          # after merge (one-line change)

DO NOT change these signatures or dict keys without telling the other person.
"""
from datetime import date

_PROPOSAL = {
    "meeting": {"title": "Sprint Sync — FitTrack launch", "date": "2026-11-21",
                "attendees": ["Rahul", "Amit", "Neha"], "absent": ["Priya"]},
    "turns": [
        {"id": "T2", "speaker": "Rahul", "ts": "00:00:15", "text": "We should switch to MongoDB instead of Postgres..."},
        {"id": "T4", "speaker": "Rahul", "ts": "00:00:52", "text": "Cool, let's go with MongoDB then."},
    ],
    "decisions": [
        {"idx": 0, "topic": "database", "text": "Switch to MongoDB", "speaker": "Rahul",
         "quote": "Cool, let's go with MongoDB then.", "turn_ids": ["T2", "T3", "T4"]},
        {"idx": 1, "topic": "launch date", "text": "Launch on December 5th", "speaker": "Rahul",
         "quote": "Yeah, December 5th works. Let's do that.", "turn_ids": ["T5", "T6"]},
    ],
    "action_items": [
        {"idx": 0, "task": "Migrate user service to MongoDB driver", "owner": "Amit", "deadline": "2026-11-27",
         "quote": "Yes, I'll have it done by Friday.", "turn_ids": ["T7", "T8"],
         "owner_reason": "Rahul asked Amit by name; Amit accepted in T8", "confidence": "high",
         "vague": False, "needs_review": False, "related_decision_topic": "database"},
        {"idx": 1, "task": "Build beta signup form on landing page", "owner": "Neha", "deadline": "2026-11-25",
         "quote": "On it, I'll ship it by Wednesday EOD.", "turn_ids": ["T9", "T10"],
         "owner_reason": "Unnamed 'you' in T9, accepted by Neha in T10", "confidence": "high",
         "vague": False, "needs_review": False, "related_decision_topic": None},
        {"idx": 2, "task": "Check Razorpay refund flow before launch", "owner": "Amit", "deadline": None,
         "quote": "He should also check the refund flow before launch.", "turn_ids": ["T11"],
         "owner_reason": "'He' refers to Amit, named earlier in T11", "confidence": "medium",
         "vague": True, "needs_review": True, "related_decision_topic": None},
        {"idx": 3, "task": "Send load-testing script", "owner": "Rahul", "deadline": "2026-11-22",
         "quote": "Main kal tak load testing script bhej dunga", "turn_ids": ["T12"],
         "owner_reason": "Speaker said 'main ... bhej dunga' (I will send)", "confidence": "high",
         "vague": False, "needs_review": False, "related_decision_topic": None},
        {"idx": 4, "task": "Fix slow dashboard API", "owner": None, "deadline": None,
         "quote": "We should fix the API soon. / Yeah, someone should look into that.", "turn_ids": ["T13", "T14"],
         "owner_reason": "'we' / 'someone': no owner named", "confidence": "low",
         "vague": True, "needs_review": True, "related_decision_topic": None},
    ],
    "conflicts": [
        {"idx": 0, "topic": "database",
         "new": {"text": "Switch to MongoDB", "speaker": "Rahul", "quote": "Cool, let's go with MongoDB then.",
                 "turn_ids": ["T4"], "meeting_date": "2026-11-21"},
         "old": {"id": 1, "text": "Use PostgreSQL as the main database", "speaker": "Priya",
                 "quote": "we should go with PostgreSQL. Our workout and payment data is very relational",
                 "meeting_title": "Sprint Sync — FitTrack launch", "meeting_date": "2026-11-14"},
         "explanation": "Today's switch to MongoDB reverses the 14 Nov decision to use PostgreSQL.",
         "impact": [{"action_id": 1, "task": "Set up Postgres schema and migrations", "owner": "Priya",
                     "deadline": "2026-11-18", "issue_number": 12, "issue_url": "https://github.com/x/meeting-tasks/issues/12"}],
         "original_decider_absent": True,
         "recommendation": "flag", "reason": "Priya made the original decision for relational data and was absent today."},
        {"idx": 1, "topic": "launch date",
         "new": {"text": "Launch on December 5th", "speaker": "Rahul", "quote": "Yeah, December 5th works.",
                 "turn_ids": ["T6"], "meeting_date": "2026-11-21"},
         "old": {"id": 2, "text": "Public launch on December 10th", "speaker": "Rahul",
                 "quote": "let's fix the public launch on December 10th. Final.",
                 "meeting_title": "Sprint Sync — FitTrack launch", "meeting_date": "2026-11-14"},
         "explanation": "Launch moved 5 days earlier than the date fixed on 14 Nov.",
         "impact": [{"action_id": 2, "task": "Write launch blog post", "owner": "Neha", "deadline": "2026-11-30",
                     "issue_number": 13, "issue_url": "https://github.com/x/meeting-tasks/issues/13"}],
         "original_decider_absent": False,
         "recommendation": "replace", "reason": "Same person made both decisions; the blog post deadline must move before Dec 5."},
    ],
    "warnings": ["'Fix slow dashboard API' has no owner or deadline."],
    "trace": [
        {"type": "tool", "tool": "extract_meeting", "args": {"turns": 15}, "result": "2 decisions, 5 action items"},
        {"type": "tool", "tool": "search_past_decisions", "args": {"topic": "database"}, "result": "1 match: PostgreSQL (14 Nov)"},
        {"type": "tool", "tool": "check_impact", "args": {"decision_id": 1}, "result": "1 open task affected"},
    ],
}


def process_transcript(text: str, filename: str = "", title: str = "", meeting_date: str = "",
                       attendees: list[str] | None = None) -> dict:
    """Parse + extract + conflict check. Saves NOTHING; returns a proposal for the Review screen."""
    return _PROPOSAL


def execute(proposal: dict, approved_items: list[int], edits: dict | None = None,
            conflict_choices: dict | None = None, email_override: str | None = None) -> dict:
    """Runs ONLY after the human clicks Approve.
    approved_items: action-item idx list.  edits: {idx: {"owner": .., "deadline": ..}}
    conflict_choices: {conflict_idx: "replace" | "keep_old" | "flag"}
    """
    return {"meeting_id": 2, "results": [
        {"type": "issue", "task": "Migrate user service to MongoDB driver", "url": "https://github.com/x/meeting-tasks/issues/14"},
        {"type": "email", "to": "Amit", "status": "sent to amit@example.com"},
        {"type": "conflict", "topic": "database", "choice": "flag", "detail": "Issue #12 labelled 'disputed', Priya notified"},
    ], "errors": []}


def due_reminders(today: str | None = None) -> list[dict]:
    """Tasks due within 24h of `today` (YYYY-MM-DD). Shown for approval, not sent."""
    return [{"reminder_id": 1, "action_id": 3, "task": "Send load-testing script", "owner": "Rahul",
             "deadline": "2026-11-22", "issue_url": None,
             "message": "Reminder: 'Send load-testing script' is due tomorrow (22 Nov)."}]


def send_reminders(reminder_ids: list[int], email_override: str | None = None) -> list[dict]:
    return [{"reminder_id": i, "status": "sent to rahul@example.com"} for i in reminder_ids]


def build_digest(person: str, today: str | None = None) -> dict:
    return {"person": person, "subject": f"Your weekly digest — {person}",
            "body": f"Hi {person},\n\nOpen tasks: 2 (1 overdue)\nOn-time rate: 1/1\n\nDecisions this week: Switch to MongoDB (disputed)\n",
            "stats": {"open": 2, "overdue": 1, "done": 1, "on_time_rate": "1/1"}}


def send_digest(person: str, email_override: str | None = None) -> str:
    return "sent to someone@example.com"


def ask_memory(question: str) -> dict:
    """Agent answers from memory with meeting, speaker and quote."""
    return {"answer": "On 21 Nov Rahul proposed MongoDB for scaling (T2): \"Mongo scales out more easily.\" "
                      "This conflicts with Priya's 14 Nov PostgreSQL decision and is currently flagged for discussion.",
            "trace": _PROPOSAL["trace"]}


def graph_data() -> dict:
    """Nodes/edges for the decision -> task graph."""
    return {
        "nodes": [
            {"id": "d1", "label": "PostgreSQL", "type": "decision", "status": "disputed"},
            {"id": "d4", "label": "MongoDB", "type": "decision", "status": "disputed"},
            {"id": "d2", "label": "Launch Dec 10", "type": "decision", "status": "superseded"},
            {"id": "d5", "label": "Launch Dec 5", "type": "decision", "status": "active"},
            {"id": "a1", "label": "Postgres schema (Priya)", "type": "task", "status": "at_risk"},
            {"id": "a4", "label": "Mongo migration (Amit)", "type": "task", "status": "approved"},
            {"id": "a2", "label": "Launch blog (Neha)", "type": "task", "status": "at_risk"},
        ],
        "edges": [
            {"from": "d1", "to": "a1", "type": "has_task"},
            {"from": "d4", "to": "a4", "type": "has_task"},
            {"from": "d2", "to": "a2", "type": "has_task"},
            {"from": "d4", "to": "d1", "type": "conflicts"},
            {"from": "d5", "to": "d2", "type": "supersedes"},
        ],
    }


def list_tasks() -> list[dict]:
    return [{"id": 1, "task": "Set up Postgres schema and migrations", "owner": "Priya", "deadline": "2026-11-18",
             "status": "approved", "issue_url": None, "meeting_date": "2026-11-14"}]


def list_people() -> list[str]:
    return ["Amit", "Neha", "Priya", "Rahul"]


def reset_demo() -> None:
    pass


def today() -> str:
    return date.today().isoformat()
