"""LLM client. Groq and Gemini both expose OpenAI-compatible endpoints,
so one SDK works for both. If the primary provider fails (rate limit etc.)
we automatically fall back to the other one.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
    },
}


def _available():
    primary = os.getenv("LLM_PROVIDER", "groq")
    order = [primary] + [p for p in PROVIDERS if p != primary]
    return [p for p in order if os.getenv(PROVIDERS[p]["key_env"])]


def chat(messages, tools=None, json_mode=False):
    """Returns the assistant message object (has .content and .tool_calls)."""
    providers = _available()
    if not providers:
        raise RuntimeError("No API key found. Copy .env.example to .env and add GROQ_API_KEY or GEMINI_API_KEY.")
    last_err = None
    for name in providers:
        cfg = PROVIDERS[name]
        try:
            client = OpenAI(api_key=os.getenv(cfg["key_env"]), base_url=cfg["base_url"])
            kwargs = {"model": os.getenv(cfg["model_env"]), "messages": messages, "temperature": 0.2}
            if tools:
                kwargs["tools"] = tools
            if json_mode:
                try:
                    return client.chat.completions.create(
                        **kwargs, response_format={"type": "json_object"}).choices[0].message
                except Exception as e:  # noqa: BLE001 — some models reject json mode; retry plain
                    print(f"[llm] {name} json mode failed, retrying plain: {e}")
            return client.chat.completions.create(**kwargs).choices[0].message
        except Exception as e:  # noqa: BLE001 — try the next provider
            last_err = e
            print(f"[llm] {name} failed: {e}")
    raise RuntimeError(f"All LLM providers failed. Last error: {last_err}")
