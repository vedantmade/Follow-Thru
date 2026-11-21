"""The JSON contract between the extraction prompt (agent/prompts.py) and the app.

The LLM must return exactly this shape:

{
  "decisions": [
    {"topic": "database", "text": "Use MongoDB instead of PostgreSQL",
     "speaker": "Rahul", "quote": "let's go with MongoDB then", "turn_ids": ["T2", "T4"]}
  ],
  "action_items": [
    {"task": "Migrate user service to MongoDB driver", "owner": "Amit", "deadline": "2026-11-27",
     "quote": "Yes, I'll have it done by Friday", "turn_ids": ["T7", "T8"],
     "owner_reason": "Rahul asked Amit by name; Amit accepted in T8",
     "confidence": "high", "related_decision_topic": "database"}
  ]
}

Rules the prompt must enforce:
- topic: short lowercase noun ("database", "launch date", "pricing"), so conflicts can be matched.
- owner: an attendee name or null. deadline: YYYY-MM-DD or null (resolve "Friday" from the meeting date).
- confidence: high | medium | low.  quote: exact words from the transcript.

validate() cleans the LLM output and adds the flags the UI needs.
"""
import json
import re

CONFIDENCE = {"high", "medium", "low"}


def parse_json(raw: str) -> dict:
    """Accepts plain JSON or JSON wrapped in ```json fences."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        raise ValueError("LLM did not return JSON")
    return json.loads(m.group(0))


def validate(data: dict, attendees: list[str]) -> tuple[dict, list[str]]:
    warnings = []
    names = {a.lower(): a for a in attendees}

    decisions = []
    for d in data.get("decisions", []) or []:
        if not d.get("text"):
            continue
        decisions.append({
            "topic": (d.get("topic") or "general").strip().lower(),
            "text": d["text"].strip(),
            "speaker": d.get("speaker"),
            "quote": d.get("quote", ""),
            "turn_ids": d.get("turn_ids") or [],
        })

    items = []
    for a in data.get("action_items", []) or []:
        if not a.get("task"):
            continue
        owner = a.get("owner")
        owner = names.get(owner.strip().lower()) if isinstance(owner, str) else None
        if a.get("owner") and owner is None:
            warnings.append(f"Owner '{a['owner']}' for '{a['task']}' is not an attendee; asking the human.")
        deadline = a.get("deadline")
        if deadline and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(deadline)):
            warnings.append(f"Deadline '{deadline}' for '{a['task']}' is not a date; asking the human.")
            deadline = None
        conf = a.get("confidence") if a.get("confidence") in CONFIDENCE else "low"
        if owner is None:
            conf = "low"
        items.append({
            "task": a["task"].strip(),
            "owner": owner,
            "deadline": deadline,
            "quote": a.get("quote", ""),
            "turn_ids": a.get("turn_ids") or [],
            "owner_reason": a.get("owner_reason", ""),
            "confidence": conf,
            "related_decision_topic": (a.get("related_decision_topic") or "").lower() or None,
            # vague = needs a human before it can become a task
            "vague": owner is None or deadline is None,
            "needs_review": owner is None or deadline is None or conf != "high",
        })

    return {"decisions": decisions, "action_items": items}, warnings
