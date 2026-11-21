"""The agent loop: think -> pick a tool -> run it -> look at the result -> repeat.

Agent.step() runs until one of:
  - "done"      : the LLM answered without asking for a tool
  - "approval"  : the LLM wants a risky tool; call approve(True/False) to continue
  - "max_steps" : safety cap reached
Every action is recorded in self.trace so the UI can show the reasoning.
"""
import json

from . import llm
from .tools import TOOLS, run_tool, tool_schemas

SYSTEM_PROMPT = """You are a helpful autonomous agent.
Break the user's goal into steps and use the available tools to complete it.
Call tools whenever they give you real data; do not invent facts or numbers.
If a tool returns an ERROR, read it and try a different approach.
When the task is complete, reply with a short final answer summarising what you did."""

MAX_STEPS = 8


class Agent:
    def __init__(self, system_prompt: str = SYSTEM_PROMPT, chat_fn=llm.chat):
        self.messages = [{"role": "system", "content": system_prompt}]
        self.trace = []          # list of dicts for the UI
        self.pending = []        # tool calls waiting for human approval
        self.chat_fn = chat_fn   # swappable, e.g. a fake LLM in tests

    # -- public API ---------------------------------------------------------
    def send(self, user_text: str):
        self.messages.append({"role": "user", "content": user_text})
        self.trace.append({"type": "user", "text": user_text})
        return self.step()

    def approve(self, ok: bool):
        calls, self.pending = self.pending, []
        for call in calls:
            if ok:
                self._execute(call)
            else:
                self._record_result(call, "REJECTED by the human. Do not retry this action; ask or choose another approach.")
        return self.step()

    # -- loop ---------------------------------------------------------------
    def step(self):
        for _ in range(MAX_STEPS):
            msg = self.chat_fn(self.messages, tools=tool_schemas())
            calls = msg.tool_calls or []
            self.messages.append(self._assistant_dict(msg))

            if not calls:
                self.trace.append({"type": "answer", "text": msg.content or ""})
                return {"status": "done", "answer": msg.content or ""}

            if msg.content:
                self.trace.append({"type": "thought", "text": msg.content})

            for call in calls:
                name, args = call.function.name, self._parse_args(call)
                if name in TOOLS and TOOLS[name]["risky"]:
                    self.pending.append(call)
                    self.trace.append({"type": "approval", "tool": name, "args": args})
                else:
                    self._execute(call)

            if self.pending:
                return {"status": "approval", "pending": [
                    {"tool": c.function.name, "args": self._parse_args(c)} for c in self.pending]}

        self.trace.append({"type": "answer", "text": "Stopped: reached the step limit."})
        return {"status": "max_steps", "answer": "Stopped: reached the step limit."}

    # -- helpers ------------------------------------------------------------
    def _execute(self, call):
        name, args = call.function.name, self._parse_args(call)
        result = run_tool(name, args) if not isinstance(args, str) else f"ERROR: bad JSON arguments: {args}"
        self.trace.append({"type": "tool", "tool": name, "args": args, "result": result})
        self._record_result(call, result)

    def _record_result(self, call, result: str):
        self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result[:6000]})

    @staticmethod
    def _parse_args(call):
        try:
            return json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            return call.function.arguments  # returned as str -> reported as error

    @staticmethod
    def _assistant_dict(msg):
        d = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            d["tool_calls"] = [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name, "arguments": c.function.arguments}}
                               for c in msg.tool_calls]
        return d
