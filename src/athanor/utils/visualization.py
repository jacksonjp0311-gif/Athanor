from __future__ import annotations
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load_ledger(path: str):
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def plot_h7(path_ledger: str, out_png: str):
    rows = load_ledger(path_ledger)
    h7 = np.array([r.get('h7',0.0) for r in rows], dtype=np.float32)
    plt.figure()
    plt.plot(h7)
    plt.axhline(0.70, linestyle='--')
    plt.title('ATHANOR H7 over candidates')
    plt.xlabel('candidate index')
    plt.ylabel('H7')
    plt.savefig(out_png, bbox_inches='tight')
    plt.close()
