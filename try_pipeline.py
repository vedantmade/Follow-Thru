"""Terminal test: python try_pipeline.py  -> runs extraction + conflict check on meeting 2 (no side effects)."""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

import pipeline  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "data", "samples", "demo_meeting_2026-11-21.txt")
p = pipeline.process_transcript(open(path, encoding="utf-8").read(), path)
print("MEETING:", p["meeting"])
print("\nDECISIONS:")
for d in p["decisions"]:
    print(f"  [{d['topic']}] {d['text']} — {d['speaker']} {d['turn_ids']}")
print("\nACTION ITEMS:")
for a in p["action_items"]:
    flag = " ⚠ VAGUE" if a["vague"] else ""
    print(f"  {a['task']} | owner={a['owner']} | due={a['deadline']} | {a['confidence']}{flag}\n      why: {a['owner_reason']}")
print("\nCONFLICTS:")
for c in p["conflicts"]:
    print(f"  {c['old']['text']}  →  {c['new']['text']}  | rec={c['recommendation']} ({c['reason']})"
          f" | impact={[i['task'] for i in c['impact']]} | decider absent={c['original_decider_absent']}")
print("\nWARNINGS:", json.dumps(p["warnings"], indent=1))
print("\nTRACE:")
for t in p["trace"]:
    print(f"  🔧 {t['tool']}: {t['result']}")
