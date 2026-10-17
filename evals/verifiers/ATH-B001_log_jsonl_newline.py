"""ATH-B001 verifier: log_jsonl must write one JSON object per line (2.0.0 wrote a literal backslash-n)."""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import athanor
if not os.path.abspath(athanor.__file__).startswith(os.path.join(HERE, "src")):
    print("athanor was not imported from the workspace snapshot: " + athanor.__file__)
    sys.exit(3)

from athanor.utils.logging import log_jsonl

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "log.jsonl")
    rows = [{"seq": 0, "verdict": "APPROVE"}, {"seq": 1, "verdict": "REJECT"}]
    for r in rows:
        log_jsonl(path, r)
    with open(path, encoding="utf-8") as f:
        text = f.read()
lines = [l for l in text.split("\n") if l]
try:
    parsed = [json.loads(l) for l in lines]
except ValueError as exc:
    print(f"FAIL: a line is not valid JSON: {exc}; raw={text!r}")
    sys.exit(1)
if parsed != rows:
    print(f"FAIL: expected {len(rows)} JSON lines, got {len(lines)}: {text!r}")
    sys.exit(1)
print("PASS: one JSON object per line")
