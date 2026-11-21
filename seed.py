"""Seed the memory with the 14 Nov meeting so conflict detection works on a fresh deploy.

Runs automatically from app.py when the DB is empty. Manual: python seed.py [--reset]
If GitHub is configured, links (or creates) issues for the seeded tasks so the
"impact" demo can comment on real issues.

Optional .env:  PEOPLE_EMAILS=Priya=a@x.com,Rahul=b@x.com,Amit=c@x.com,Neha=d@x.com
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from services import db, tracker  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "data", "samples", "meeting1_sprint_sync_2026-11-14.txt")
TITLE, DATE = "Sprint Sync — FitTrack launch", "2026-11-14"
ATTENDEES = ["Priya", "Rahul", "Amit", "Neha"]

DECISIONS = [
    ("database", "Use PostgreSQL as the main database", "Priya",
     "we should go with PostgreSQL. Our workout and payment data is very relational", ["T2", "T5"]),
    ("launch date", "Public launch on December 10th", "Rahul",
     "let's fix the public launch on December 10th. Final.", ["T9"]),
    ("pricing", "Pro plan at ₹499/month with a 7-day free trial", "Amit",
     "Yes, 499 a month, with a 7 day free trial.", ["T11", "T12"]),
]
TASKS = [  # task, owner, deadline, quote, turn_ids, decision topic
    ("Set up Postgres schema and migrations", "Priya", "2026-11-18",
     "I'll set up the Postgres schema and migrations by next Wednesday.", ["T6"], "database"),
    ("Write launch blog post", "Neha", "2026-11-30",
     "Okay, I'll write the launch blog post by the 30th.", ["T10"], "launch date"),
    ("Update pricing page to ₹499/month + 7-day trial", "Amit", "2026-11-17",
     "Sure, will do.", ["T13", "T14"], "pricing"),
]


def seed(link_github=True):
    db.init_db()
    if db.list_meetings():
        return False
    with open(SAMPLE, encoding="utf-8") as f:
        transcript = f.read()

    for pair in filter(None, os.getenv("PEOPLE_EMAILS", "").split(",")):
        name, _, email = pair.partition("=")
        db.upsert_person(name.strip(), email.strip() or None)
    for name in ATTENDEES:
        db.upsert_person(name)

    mid = db.save_meeting(TITLE, DATE, ATTENDEES, transcript)
    topic_ids = {topic: db.add_decision(mid, topic, text, spk, quote, turns)
                 for topic, text, spk, quote, turns in DECISIONS}

    for task, owner, deadline, quote, turns, topic in TASKS:
        aid = db.add_action_item(mid, task, owner, deadline, quote, turns, topic_ids[topic], status="approved")
        if link_github and tracker.configured():
            try:
                found = tracker.find_issue_by_title(task)
                if not found:
                    body = tracker.issue_body(task, owner, deadline, TITLE, DATE, quote)
                    found = tracker.create_issue(task, body, labels=("meeting-agent", "seed"))
                db.update_action_item(aid, issue_number=found[0], issue_url=found[1])
            except Exception as e:  # noqa: BLE001 — seeding must never break startup
                print(f"[seed] GitHub link skipped: {e}")
    # mark one task done on time so the accountability score has data
    db.update_action_item(3, status="done", completed_at="2026-11-16")
    return True


if __name__ == "__main__":
    if "--reset" in sys.argv:
        db.reset_db()
    print("Seeded." if seed() else "DB already has data (use --reset).")
