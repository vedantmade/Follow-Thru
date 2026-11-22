"""System 1: Laya, a fast non-generative decision model (optional, post-hackathon v2).

Laya answers typed questions ("is this line a commitment?") with probabilities in one forward pass.
FollowThru uses it ONLY as a safety net on top of the LLM (System 2):
  - it can ADD "needs review" flags (possibly vague commitment, possibly missed action item),
  - it never removes, edits or approves anything the LLM extracted.
Laya's own docs warn its shipped confidences are over-confident, so thresholds are strict.

Enable locally:  pip install -r requirements-laya.txt   and set  LAYA_MODE=local  in .env
Disabled (default) or unavailable -> every function returns None and the app runs exactly as before.
"""
import os
import time

MODE = os.getenv("LAYA_MODE", "off").lower()          # off | local
CHECKPOINT = os.getenv("LAYA_CHECKPOINT", "multilingual")  # multilingual handles Hinglish lines
THRESHOLD = float(os.getenv("LAYA_THRESHOLD", "0.85"))

QUESTIONS = {
    "kind": {
        "type": "choice",
        "instructions": "What does this meeting line contain?",
        "criteria": {
            "commitment": "someone agrees or promises to do a task, or is asked to and accepts",
            "decision": "the group settles or agrees on a choice, date, price or plan",
            "other": "discussion, opinion, question, greeting or small talk",
        },
    },
    "clarity": {
        "type": "choice",
        "instructions": "If this line contains a task, is it clearly owned and time-bound?",
        "criteria": {
            "specific": "a specific person owns it and a specific time or day is given",
            "vague": "says we, someone, the team, soon or later, or gives no person or no time",
            "no_task": "the line contains no task",
        },
    },
}

_router = None
_error = None


def _load():
    global _router, _error
    if _router is not None or _error is not None:
        return _router
    try:
        from laya import Router
        _router = Router(default=CHECKPOINT, preload=True)
    except Exception as e:  # noqa: BLE001 — missing package, no RAM, no download: just stay off
        _error = f"{type(e).__name__}: {e}"
        print(f"[system1] Laya unavailable, continuing without it: {_error}")
    return _router


def status() -> str:
    if MODE != "local":
        return "off"
    return "on" if _load() else f"unavailable ({_error})"


def _top(answer: dict):
    return (answer or {}).get("choice"), float((answer or {}).get("confidence") or 0.0)


def screen(turns: list[dict]) -> dict | None:
    """Classify every transcript turn. Returns None when Laya is off/unavailable."""
    if MODE != "local" or not _load():
        return None
    t0 = time.perf_counter()
    requests = [{"state": f"{t['speaker']}: {t['text']}", "questions": QUESTIONS} for t in turns]
    try:
        results = _router.predict_batch(requests)
    except Exception as e:  # noqa: BLE001
        print(f"[system1] predict_batch failed, skipping: {e}")
        return None
    labels = {}
    for t, r in zip(turns, results):
        ans = (r or {}).get("answers") or {}
        kind, kind_conf = _top(ans.get("kind"))
        clarity, clarity_conf = _top(ans.get("clarity"))
        labels[t["id"]] = {"kind": kind, "kind_conf": kind_conf, "clarity": clarity, "clarity_conf": clarity_conf}
    return {"labels": labels, "ms": round((time.perf_counter() - t0) * 1000), "checkpoint": CHECKPOINT}


def cross_check(screened: dict | None, action_items: list[dict], turns: list[dict]) -> list[str]:
    """Compare System 1 with the LLM's extraction. Only ever adds review flags. Mutates items in place."""
    if not screened:
        return []
    labels, warnings = screened["labels"], []
    text = {t["id"]: f"{t['speaker']}: {t['text']}" for t in turns}

    # 1. LLM gave an owner + date, but Laya is confident the commitment itself is vague
    for a in action_items:
        if a.get("vague"):
            continue
        hits = [tid for tid in a.get("turn_ids", [])
                if labels.get(tid, {}).get("clarity") == "vague" and labels[tid]["clarity_conf"] >= THRESHOLD]
        if hits:
            a["needs_review"] = True
            a["system1_flag"] = f"System 1 thinks {', '.join(hits)} is a vague commitment"
            warnings.append(f"System 1 (Laya): '{a['task']}' may be vaguer than extracted ({', '.join(hits)}). Please confirm owner and date.")

    # 2. Laya sees a commitment the LLM did not turn into any action item
    covered = {tid for a in action_items for tid in a.get("turn_ids", [])}
    for tid, lab in labels.items():
        if lab["kind"] == "commitment" and lab["kind_conf"] >= THRESHOLD and tid not in covered:
            warnings.append(f"System 1 (Laya): possible missed action item at {tid}: \"{text.get(tid, '')[:90]}\"")
    return warnings
