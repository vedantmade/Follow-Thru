"""Parse meeting transcripts into numbered speaker turns.

Supported:
  .txt  ->  "[00:04:12] Rahul: text"  or  "00:04:12 Rahul: text"  or  "Rahul: text"
            (lines without a "Name:" prefix are joined to the previous turn)
  .vtt  ->  Zoom / Google Meet / Teams exports, with "<v Rahul>text</v>" or "Rahul: text" cues

Output: [{"id": "T1", "speaker": "Rahul", "ts": "00:04:12", "text": "..."}, ...]
"""
import re

_TXT_LINE = re.compile(
    r"^\s*(?:\[?(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-–]?\s*)?"   # optional [hh:mm:ss]
    r"(?P<speaker>[A-Z][\w .'-]{0,40}?)\s*:\s+(?P<text>.+)$"           # Name: text
)
_VTT_TIME = re.compile(r"^(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\s*-->\s*\S+")
_VTT_VOICE = re.compile(r"<v\s+(?P<speaker>[^>]+)>(?P<text>.*?)(?:</v>)?$")
_TAG = re.compile(r"<[^>]+>")


def _short_ts(ts: str | None) -> str:
    return ts.split(".")[0] if ts else ""


def _merge(turns):
    """Join a speaker's consecutive lines only when the previous one was cut mid-sentence
    (Zoom/Meet split long utterances across cues)."""
    merged = []
    for t in turns:
        prev = merged[-1] if merged else None
        if prev and prev["speaker"] == t["speaker"] and not prev["text"].rstrip().endswith((".", "?", "!")):
            merged[-1]["text"] += " " + t["text"]
        else:
            merged.append(dict(t))
    for i, t in enumerate(merged, 1):
        t["id"] = f"T{i}"
    return merged


def parse_txt(text: str):
    turns = []
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = _TXT_LINE.match(line)
        if m:
            turns.append({"speaker": m["speaker"].strip(), "ts": _short_ts(m["ts"]), "text": m["text"].strip()})
        elif turns:  # continuation of the previous speaker's turn
            turns[-1]["text"] += " " + line.strip()
    return _merge(turns)


def parse_vtt(text: str):
    turns, ts = [], ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or line.isdigit() or line.startswith("NOTE"):
            continue
        tm = _VTT_TIME.match(line)
        if tm:
            ts = _short_ts(tm["start"])
            continue
        vm = _VTT_VOICE.match(line)
        if vm:
            speaker, said = vm["speaker"].strip(), _TAG.sub("", vm["text"]).strip()
        else:
            plain = _TAG.sub("", line)
            m = re.match(r"^([A-Z][\w .'-]{0,40}?):\s+(.+)$", plain)
            if m:
                speaker, said = m[1].strip(), m[2].strip()
            elif turns:
                turns[-1]["text"] += " " + plain
                continue
            else:
                continue
        turns.append({"speaker": speaker, "ts": ts, "text": said})
    return _merge(turns)


def parse(text: str, filename: str = "") -> list[dict]:
    """Auto-detects the format. Raises ValueError if no speaker turns are found."""
    is_vtt = filename.lower().endswith(".vtt") or text.lstrip().startswith("WEBVTT")
    turns = parse_vtt(text) if is_vtt else parse_txt(text)
    if not turns:
        raise ValueError("No speaker turns found. Expected lines like 'Rahul: text' or a .vtt export with speaker names.")
    return turns


def speakers(turns) -> list[str]:
    return list(dict.fromkeys(t["speaker"] for t in turns))


def format_for_llm(turns) -> str:
    """Numbered lines the LLM can cite as evidence, e.g. 'T14 [00:04:12] Rahul: ...'"""
    return "\n".join(f"{t['id']} [{t['ts']}] {t['speaker']}: {t['text']}" if t["ts"]
                     else f"{t['id']} {t['speaker']}: {t['text']}" for t in turns)
