"""Tool registry.

Add a tool = write a Python function + decorate it with @tool(...).
The decorator builds the JSON schema the LLM sees, so you only describe
each parameter once.

risky=True  -> the agent pauses and asks the human to approve before running it
               (use for anything with side effects: sending email, writing data, payments).
"""
import ast
import json
import operator
from datetime import datetime
from zoneinfo import ZoneInfo

TOOLS = {}  # name -> {"fn": callable, "schema": dict, "risky": bool}


def tool(description: str, params: dict | None = None, required: list | None = None, risky: bool = False):
    """params: {"name": {"type": "string", "description": "..."}}"""
    params = params or {}

    def wrap(fn):
        TOOLS[fn.__name__] = {
            "fn": fn,
            "risky": risky,
            "schema": {
                "type": "function",
                "function": {
                    "name": fn.__name__,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": params,
                        "required": required if required is not None else list(params),
                    },
                },
            },
        }
        return fn

    return wrap


def tool_schemas():
    return [t["schema"] for t in TOOLS.values()]


def run_tool(name: str, args: dict) -> str:
    """Never raises: errors go back to the LLM as text so it can recover."""
    if name not in TOOLS:
        return f"ERROR: unknown tool '{name}'. Available: {list(TOOLS)}"
    try:
        result = TOOLS[name]["fn"](**args)
        return result if isinstance(result, str) else json.dumps(result, default=str)
    except Exception as e:  # noqa: BLE001
        return f"ERROR running {name}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Sample tools — replace/extend these once the problem statement is out.
# ---------------------------------------------------------------------------

@tool(
    "Get the current date and time in a timezone.",
    {"timezone": {"type": "string", "description": "IANA timezone, e.g. Asia/Kolkata"}},
)
def get_current_time(timezone: str = "Asia/Kolkata"):
    return datetime.now(ZoneInfo(timezone)).strftime("%A %d %B %Y, %H:%M %Z")


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("only numbers and + - * / ** % are allowed")


@tool(
    "Evaluate an arithmetic expression exactly. Use this instead of doing maths yourself.",
    {"expression": {"type": "string", "description": "e.g. (1200*0.18)+50"}},
)
def calculate(expression: str):
    return str(_safe_eval(ast.parse(expression, mode="eval").body))


# ---------------------------------------------------------------------------
# Memory tools used by "Ask memory" (read-only, so no approval needed)
# ---------------------------------------------------------------------------
def _slim(d, keys):
    return {k: d.get(k) for k in keys}


@tool(
    "Search past decisions by keywords (topic, technology, date...). Includes superseded and disputed ones.",
    {"query": {"type": "string", "description": "keywords, e.g. 'database mongodb'"}},
)
def search_past_decisions(query: str):
    from services import db
    hits = db.search_decisions(query, status=None, limit=8)
    return [_slim(d, ["id", "topic", "text", "speaker", "quote", "status", "superseded_by",
                      "meeting_title", "meeting_date"]) for d in hits] or "No matching decisions."


@tool("List every decision in memory with its status (active / superseded / disputed / discussion).")
def list_all_decisions():
    from services import db
    return [_slim(d, ["id", "topic", "text", "speaker", "status", "meeting_date"]) for d in db.list_decisions(status=None)]


@tool(
    "List action items, optionally for one owner.",
    {"owner": {"type": "string", "description": "person name, or empty for everyone"}},
    required=[],
)
def list_tasks(owner: str = ""):
    from services import db
    return [_slim(a, ["id", "task", "owner", "deadline", "status", "issue_url", "quote", "meeting_date"])
            for a in db.list_action_items(owner=owner or None)] or "No tasks."


@tool("List detected conflicts between decisions and how the team resolved them.")
def list_conflicts():
    from services import db
    return db.list_conflicts() or "No conflicts recorded."
