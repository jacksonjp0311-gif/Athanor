"""ATH-B002 verifier: config inheritance must deep-merge nested mappings (2.0.0 used dict.update and dropped nested keys)."""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import athanor
if not os.path.abspath(athanor.__file__).startswith(os.path.join(HERE, "src")):
    print("athanor was not imported from the workspace snapshot: " + athanor.__file__)
    sys.exit(3)

from athanor.experiments.registry import load_config

with tempfile.TemporaryDirectory() as tmp:
    with open(os.path.join(tmp, "base.yaml"), "w", encoding="utf-8") as f:
        f.write("seed: 7\narchive:\n  bins: [8, 8]\n  novelty_eps: 0.05\nrun:\n  out_dir: custom_out\n")
    with open(os.path.join(tmp, "child.yaml"), "w", encoding="utf-8") as f:
        f.write("inherits: base.yaml\narchive:\n  novelty_eps: 0.10\nrun:\n  note: child\n")
    cfg = load_config(os.path.join(tmp, "child.yaml"))
problems = []
if cfg["archive"].get("bins") != [8, 8]:
    problems.append(f"archive.bins={cfg['archive'].get('bins')!r}, expected [8, 8] from base")
if cfg["archive"].get("novelty_eps") != 0.10:
    problems.append(f"archive.novelty_eps={cfg['archive'].get('novelty_eps')!r}, expected child override 0.10")
if cfg["run"].get("out_dir") != "custom_out":
    problems.append(f"run.out_dir={cfg['run'].get('out_dir')!r}, expected 'custom_out' from base")
if cfg.get("seed") != 7:
    problems.append(f"seed={cfg.get('seed')!r}, expected 7 from base")
if problems:
    print("FAIL: " + "; ".join(problems))
    sys.exit(1)
print("PASS: nested keys deep-merged")
