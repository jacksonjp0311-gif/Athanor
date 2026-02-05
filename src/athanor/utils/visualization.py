from __future__ import annotations
import json, os
import numpy as np
import matplotlib.pyplot as plt

def load_ledger(path: str):
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def plot_h7(path_ledger: str, out_png: str, h7_threshold: float = 0.70):
    rows = load_ledger(path_ledger)
    h7 = np.array([r.get('h7',0.0) for r in rows], dtype=np.float32)
    plt.figure()
    plt.plot(h7)
    plt.axhline(float(h7_threshold), linestyle='--')
    plt.title('ATHANOR: H7 over candidates')
    plt.xlabel('candidate index')
    plt.ylabel('H7')
    plt.savefig(out_png, bbox_inches='tight')
    plt.close()

def plot_fitness(path_ledger: str, out_png: str):
    rows = load_ledger(path_ledger)
    f = np.array([r.get('f',0.0) for r in rows], dtype=np.float32)
    plt.figure()
    plt.plot(f)
    plt.title('ATHANOR: fitness F over candidates')
    plt.xlabel('candidate index')
    plt.ylabel('F')
    plt.savefig(out_png, bbox_inches='tight')
    plt.close()

def render_dashboard(run_path: str, threshold_h7: float = 0.70):
    stats_path = os.path.join(run_path, 'archive_stats.json')
    ledger_path = os.path.join(run_path, 'ledger.jsonl')
    dash   = os.path.join(run_path, 'dashboard.html')

    stats = {}
    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            stats = json.load(f) or {}
    except Exception:
        stats = {}

    last = {}
    try:
        with open(ledger_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    last = json.loads(line)
    except Exception:
        last = {}

    def esc(s: str) -> str:
        return (str(s)
                .replace('&','&amp;')
                .replace('<','&lt;')
                .replace('>','&gt;')
                .replace('"','&quot;')
                .replace("'","&#39;"))

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ATHANOR — Run Dashboard</title>
<style>
  :root {{
    --bg: #000;
    --fg: #e8e8e8;
    --mut: #9aa0a6;
    --card: #0b0b0b;
    --line: #151515;
  }}
  html, body {{ background: var(--bg); color: var(--fg); font-family: ui-sans-serif, system-ui; margin: 0; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
  .title {{ display:flex; align-items:baseline; gap:12px; border-bottom:1px solid var(--line); padding-bottom:12px; }}
  .title h1 {{ margin:0; font-size: 22px; letter-spacing: .08em; }}
  .title .sub {{ color: var(--mut); font-size: 12px; }}
  .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }}
  .card {{ background: var(--card); border:1px solid var(--line); border-radius: 12px; padding: 14px; }}
  img {{ width:100%; border-radius: 10px; border:1px solid var(--line); background:#000; }}
  pre {{ white-space: pre-wrap; color: var(--mut); }}
</style>
</head>
<body>
<div class="wrap">
  <div class="title">
    <h1>𓂀 ATHANOR</h1>
    <div class="sub">Coherence Verifier • ΔΦ → C → H7 gate • threshold={threshold_h7:.2f}</div>
  </div>

  <div class="grid">
    <div class="card">
      <div><b>Archive filled:</b> {esc(stats.get('filled',0))}</div>
      <div><b>Mean H7:</b> {float(stats.get('mean_H7',0.0)):.4f}</div>
      <div><b>Mean F:</b> {float(stats.get('mean_F',0.0)):.4f}</div>
      <div><b>Max best F:</b> {float(stats.get('max_best_f',0.0)):.4f}</div>
      <div style="margin-top:12px"><b>Last candidate</b></div>
      <pre>{esc(json.dumps(last, indent=2))}</pre>
    </div>

    <div class="card">
      <div><b>Artifacts</b></div>
      <div style="margin-top:8px">H7 trace</div>
      <img src="h7_trace.png" alt="H7 trace"/>
      <div style="margin-top:10px">Fitness trace</div>
      <img src="fitness_trace.png" alt="Fitness trace"/>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <div><b>Run folder</b></div>
    <div>{esc(run_path)}</div>
  </div>
</div>
</body>
</html>
"""

    with open(dash, 'w', encoding='utf-8') as f:
        f.write(html)
