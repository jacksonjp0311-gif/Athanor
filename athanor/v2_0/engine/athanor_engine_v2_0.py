#!/usr/bin/env python3
# 𓂀 ATHANOR v2.0 — COHERENCE FORGE (ΔΦ → Ω → H7 GATE)
# Author: James Jackson (@jacksonjp0311-gif)

import os, sys, json, math, time
from datetime import datetime, timezone

import numpy as np

H7 = 0.70

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def safe_mkdir(p):
    os.makedirs(p, exist_ok=True)

def load_input(path, N=256):
    if not path:
        return None

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return None

    ext = os.path.splitext(path)[1].lower()

    if ext in [".npy"]:
        arr = np.load(path)
        arr = np.array(arr, dtype=np.float32)
        if arr.ndim == 1:
            # reshape 1D to square-ish
            m = int(np.sqrt(arr.size))
            m = max(32, min(m, N))
            arr = arr[:m*m].reshape(m, m)
        if arr.ndim > 2:
            # take a representative slice
            arr = arr.reshape(arr.shape[0], -1)
            arr = arr[:,:min(arr.shape[1], N)]
        if arr.ndim == 2:
            return norm01(arr)
        return norm01(arr[:N,:N])

    if ext in [".npz"]:
        z = np.load(path)
        k0 = z.files[0]
        arr = np.array(z[k0], dtype=np.float32)
        if arr.ndim >= 2:
            arr = arr[...,0] if arr.ndim == 3 else arr
            if arr.ndim > 2:
                arr = arr.reshape(arr.shape[0], -1)
            return norm01(arr[:N,:N])
        return None

    if ext in [".csv", ".txt"]:
        try:
            arr = np.loadtxt(path, delimiter=",", dtype=np.float32)
        except Exception:
            arr = np.loadtxt(path, dtype=np.float32)
        if arr.ndim == 1:
            m = int(np.sqrt(arr.size))
            m = max(32, min(m, N))
            arr = arr[:m*m].reshape(m, m)
        return norm01(arr[:N,:N])

    return None

def norm01(x):
    x = np.array(x, dtype=np.float32)
    mn = float(np.nanmin(x))
    mx = float(np.nanmax(x))
    d = mx - mn
    if d <= 0:
        return np.zeros_like(x, dtype=np.float32)
    x = (x - mn) / d
    x = np.nan_to_num(x, nan=0.0, posinf=1.0, neginf=0.0)
    return x.astype(np.float32)

def synth_base(N=256, seed=11):
    rng = np.random.default_rng(seed)
    x = np.linspace(-1.0, 1.0, N, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, N, dtype=np.float32)
    X, Y = np.meshgrid(x, y, indexing="xy")
    R = np.sqrt(X*X + Y*Y)

    # harmonic base: ring + swirl + subtle noise
    ring = np.exp(-0.5*((R-0.55)/0.10)**2)
    swirl = 0.5*np.sin(10.0*(X*np.cos(2.2)+Y*np.sin(2.2))) + 0.35*np.cos(8.0*R + 3.0*X)
    noise = 0.08 * rng.normal(size=(N,N)).astype(np.float32)

    base = 0.55*ring + 0.45*(swirl - swirl.min())/(swirl.max()-swirl.min()+1e-9) + noise
    return norm01(base)

def grad_dphi(F):
    gx, gy = np.gradient(F.astype(np.float32))
    dphi = np.sqrt(gx*gx + gy*gy).astype(np.float32)
    return dphi

def omega_from_dphi(dphi):
    return (1.0 / (1.0 + np.abs(dphi))).astype(np.float32)

def coherence_field(F, dphi):
    # toy E & I fields
    # E proxy: |F|
    # I proxy: dphi (mean gradient magnitude)
    E = np.abs(F).astype(np.float32)
    I = dphi.astype(np.float32)
    C = (E * I) / (1.0 + np.abs(dphi))
    return C.astype(np.float32)

def curvature_proxy(dphi):
    return float(np.mean(np.abs(dphi - float(np.mean(dphi)))))

def fractal_dim_boxcount(A):
    # light 2D boxcount on thresholded field
    B = (A > np.median(A)).astype(np.uint8)
    sizes = [2,4,8,16,32]
    counts = []
    invs = []
    for s in sizes:
        if s >= min(B.shape):
            continue
        bx = B.shape[0]//s
        by = B.shape[1]//s
        if bx <= 1 or by <= 1:
            continue
        view = B[:bx*s, :by*s].reshape(bx, s, by, s)
        occ = (view.sum(axis=(1,3)) > 0).sum()
        counts.append(float(occ) + 1e-9)
        invs.append(math.log(1.0/float(s)))
    if len(counts) < 2:
        return 1.90
    y = np.log(np.array(counts, dtype=np.float64))
    x = np.array(invs, dtype=np.float64)
    p = np.polyfit(x, y, 1)
    return float(abs(p[0]))

def cusp_params(EI=1.0, gamma=0.35):
    Dc_sq = ((EI**4) + 27.0*gamma*(EI**3)) / (8.0*gamma)
    Dc = math.sqrt(max(Dc_sq, 1e-12))
    phi_c = (EI**2) / (3.0*gamma)
    C_cusp = (3.0*gamma) / (EI + 3.0*gamma)
    return Dc, phi_c, C_cusp

def propose(F, mode, rng):
    # proposals are numeric transforms (no classes)
    if mode == "smooth":
        # simple 3x3 box blur (no scipy)
        K = np.array([[1,1,1],[1,2,1],[1,1,1]], dtype=np.float32)
        K = K / float(K.sum())
        P = pad2(F)
        out = (
            K[0,0]*P[:-2,:-2] + K[0,1]*P[:-2,1:-1] + K[0,2]*P[:-2,2:] +
            K[1,0]*P[1:-1,:-2] + K[1,1]*P[1:-1,1:-1] + K[1,2]*P[1:-1,2:] +
            K[2,0]*P[2:,:-2] + K[2,1]*P[2:,1:-1] + K[2,2]*P[2:,2:]
        )
        return norm01(out)

    if mode == "sharpen":
        P = pad2(F)
        lap = (
            -1.0*P[:-2,1:-1] -1.0*P[1:-1,:-2] + 4.0*P[1:-1,1:-1] -1.0*P[1:-1,2:] -1.0*P[2:,1:-1]
        )
        out = F + 0.35*lap.astype(np.float32)
        return norm01(out)

    if mode == "twist":
        # phase-like warp approximation: rotate quadrants slightly
        n = F.shape[0]
        half = n//2
        A = F.copy()
        A[:half,:half] = np.rot90(A[:half,:half], 1)
        A[:half,half:] = np.rot90(A[:half,half:], 3)
        return norm01(A)

    if mode == "noise":
        out = F + 0.06*rng.normal(size=F.shape).astype(np.float32)
        return norm01(out)

    if mode == "ring_boost":
        n = F.shape[0]
        x = np.linspace(-1.0, 1.0, n, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, n, dtype=np.float32)
        X, Y = np.meshgrid(x, y, indexing="xy")
        R = np.sqrt(X*X + Y*Y)
        ring = np.exp(-0.5*((R-0.55)/0.12)**2).astype(np.float32)
        out = 0.75*F + 0.25*ring
        return norm01(out)

    return F

def pad2(F):
    return np.pad(F, ((1,1),(1,1)), mode="edge").astype(np.float32)

def score_metrics(F):
    dphi = grad_dphi(F)
    Om = omega_from_dphi(dphi)
    C = coherence_field(F, dphi)

    omega_mean = float(np.mean(Om))
    omega_std  = float(np.std(Om))
    I_global   = float(np.mean(dphi))
    E_global   = float(np.mean(np.abs(F)))
    C_avg      = float(np.mean(C))
    H7_frac    = float(np.mean(C >= H7))
    curv       = curvature_proxy(dphi)
    fd         = fractal_dim_boxcount(F)

    # scalar score: prefer high Ω, high H7 fraction, low curvature
    score = (1.40*omega_mean + 0.90*H7_frac + 0.20*C_avg) - (0.45*curv) - (0.05*omega_std)

    return {
        "dphi": dphi, "omega": Om, "C": C,
        "omega_mean": omega_mean, "omega_std": omega_std,
        "I_global": I_global, "E_global": E_global, "C_avg": C_avg,
        "H7_fraction": H7_frac, "curvature_proxy": curv,
        "fractal_dim_H16B": fd,
        "score": float(score)
    }

def save_png(path, A, title, cmap="inferno"):
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(6,6), dpi=160)
        plt.imshow(A, origin="lower", cmap=cmap)
        plt.title(title)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(path, bbox_inches="tight", pad_inches=0.02)
        plt.close()
        return True
    except Exception:
        return False

def save_curve(path, y, title):
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(7,3), dpi=160)
        plt.plot(np.arange(len(y)), y)
        plt.title(title)
        plt.xlabel("t")
        plt.ylabel("value")
        plt.tight_layout()
        plt.savefig(path, bbox_inches="tight", pad_inches=0.05)
        plt.close()
        return True
    except Exception:
        return False

def write_true_black_report(path, payload):
    # minimal, self-contained, shareable
    css = """
    body{margin:0;background:#000;color:#e8e8e8;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial;}
    .wrap{max-width:1100px;margin:0 auto;padding:28px;}
    .h{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap}
    .title{font-size:28px;font-weight:800;letter-spacing:0.5px}
    .tag{opacity:0.85;font-family:ui-monospace,Menlo,Consolas,monospace}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:16px}
    .card{border:1px solid rgba(255,255,255,0.10);border-radius:14px;padding:14px;background:rgba(255,255,255,0.03)}
    .k{opacity:0.75;font-size:12px}
    .v{font-size:18px;font-weight:700}
    img{width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.08)}
    .imgs{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:14px}
    .foot{opacity:0.7;margin-top:18px;font-size:12px}
    """
    def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    m = payload["metrics"]
    imgs = payload["visuals"]
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Athanor v2.0 Report</title><style>{css}</style></head><body><div class="wrap">
      <div class="h">
        <div class="title">𓂀 ATHANOR v2.0 — Coherence Forge</div>
        <div class="tag">{esc(payload["tag"])} · {esc(payload["timestamp"])}</div>
      </div>
      <div class="grid">
        <div class="card"><div class="k">score</div><div class="v">{m["score"]:.6f}</div></div>
        <div class="card"><div class="k">Ω mean</div><div class="v">{m["omega_mean"]:.6f}</div></div>
        <div class="card"><div class="k">Ω std</div><div class="v">{m["omega_std"]:.6f}</div></div>
        <div class="card"><div class="k">H₇ fraction (C≥0.70)</div><div class="v">{m["H7_fraction"]:.4f}</div></div>
        <div class="card"><div class="k">ΔΦ global (mean |∇F|)</div><div class="v">{m["I_global"]:.6f}</div></div>
        <div class="card"><div class="k">curvature proxy</div><div class="v">{m["curvature_proxy"]:.6f}</div></div>
        <div class="card"><div class="k">fractal_dim (H16B)</div><div class="v">{m["fractal_dim_H16B"]:.4f}</div></div>
        <div class="card"><div class="k">C avg</div><div class="v">{m["C_avg"]:.6f}</div></div>
      </div>
      <div class="imgs">
        <div><div class="k">ΔΦ field</div><img src="{esc(os.path.basename(imgs["dphi_png"]))}"></div>
        <div><div class="k">Ω field</div><img src="{esc(os.path.basename(imgs["omega_png"]))}"></div>
        <div><div class="k">Coherence field</div><img src="{esc(os.path.basename(imgs["coherence_png"]))}"></div>
        <div><div class="k">Resonance</div><img src="{esc(os.path.basename(imgs["resonance_png"]))}"></div>
      </div>
      <div class="foot">
        Laws: Ω=1/(1+|ΔΦ|), H₇=0.70, ΔΦ Cusp v2.8 tracked · Author: James Jackson
      </div>
    </div></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

def main(argv):
    # argv: ROOT STATE VISUALS LEDGER LOGS PUBLIC INPUT T N ETA0
    if len(argv) != 12:
        print("Usage: engine.py ROOT STATE VISUALS LEDGER LOGS PUBLIC INPUT T N ETA0", file=sys.stderr)
        return 1

    root, state_dir, vis_dir, led_dir, logs_dir, pub_dir, input_path, T, N, eta0 = (
        argv[1], argv[2], argv[3], argv[4], argv[5], argv[6], argv[7], int(argv[8]), int(argv[9]), float(argv[10])
    )

    safe_mkdir(state_dir); safe_mkdir(vis_dir); safe_mkdir(led_dir); safe_mkdir(logs_dir); safe_mkdir(pub_dir)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tag = f"athanor_v2_0_{ts}"
    log_path = os.path.join(logs_dir, f"{tag}.log")

    def log(msg):
        line = (msg.encode("ascii","replace").decode("ascii"))
        print(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log("ATHANOR v2.0 starting…")
    log(f"tag={tag}")
    log(f"input={input_path}")

    base = load_input(input_path, N=N)
    if base is None:
        base = synth_base(N=N, seed=11)
        log("using synthetic base field (no input provided or file unsupported)")
    if base is not None:
        log(f"base shape={base.shape}")

    rng = np.random.default_rng(22)

    # initialize
    F = base.copy()
    metrics0 = score_metrics(F)
    omega_bar = metrics0["omega_mean"]
    eta_series = [0.0]
    score_series = [metrics0["score"]]

    modes = ["smooth","sharpen","twist","noise","ring_boost"]

    best = {"score": -1e9}
    best_frame = None

    # evolution loop: proposals + adaptive damping
    for t in range(1, max(4, T)):
        mode = modes[t % len(modes)]
        P = propose(F, mode, rng)

        # compute Ω̄ from current field
        cur = score_metrics(F)
        omega_bar = float(cur["omega_mean"])

        eta = float(eta0 * (1.0 - omega_bar))
        eta = max(0.0, min(0.95, eta))
        eta_series.append(eta)

        # damped update toward proposal
        F = (F + (1.0 - eta)*(P - F)).astype(np.float32)
        F = norm01(F)

        met = score_metrics(F)
        score_series.append(met["score"])

        if met["score"] > best["score"]:
            best = {
                "score": met["score"],
                "omega_mean": met["omega_mean"],
                "omega_std": met["omega_std"],
                "I_global": met["I_global"],
                "E_global": met["E_global"],
                "C_avg": met["C_avg"],
                "H7_fraction": met["H7_fraction"],
                "curvature_proxy": met["curvature_proxy"],
                "fractal_dim_H16B": met["fractal_dim_H16B"],
                "t_best": t,
                "mode_best": mode
            }
            best_frame = {
                "dphi": met["dphi"],
                "omega": met["omega"],
                "C": met["C"],
                "F": F.copy()
            }

    # cusp metrics (tracked kernel)
    EI = float(best["E_global"] * max(best["I_global"], 1e-9))
    gamma = 0.35
    Dc, phi_c, C_cusp = cusp_params(EI=EI, gamma=gamma)
    D = float(best["I_global"])  # toy imperfection proxy
    lam = float(D / (Dc + 1e-12))
    lam = float(max(0.0, min(2.0, lam)))

    # visuals
    dphi_png = os.path.join(vis_dir, f"{tag}_dphi.png")
    omega_png = os.path.join(vis_dir, f"{tag}_omega.png")
    coh_png  = os.path.join(vis_dir, f"{tag}_coherence.png")
    res_png  = os.path.join(vis_dir, f"{tag}_resonance.png")
    base_png = os.path.join(vis_dir, f"{tag}_field.png")

    if best_frame is None:
        best_frame = {"dphi": metrics0["dphi"], "omega": metrics0["omega"], "C": metrics0["C"], "F": F.copy()}

    save_png(base_png, best_frame["F"], "Athanor v2.0 Field (best)", cmap="magma")
    save_png(dphi_png, best_frame["dphi"], "ΔΦ field", cmap="inferno")
    save_png(omega_png, best_frame["omega"], "Ω = 1/(1+|ΔΦ|)", cmap="viridis")
    save_png(coh_png, best_frame["C"], "Coherence field C", cmap="plasma")
    save_curve(res_png, np.array(score_series, dtype=np.float32), "Athanor v2.0 score trajectory")

    # report
    report_path = os.path.join(pub_dir, f"{tag}_report.html")

    # state + ledger
    state_path = os.path.join(state_dir, f"{tag}_state.json")
    ledger_path = os.path.join(led_dir, "athanor_v2_0_ledger.jsonl")

    payload = {
        "protocol": "AthanorCoherenceForge",
        "version": "2.0",
        "timestamp": now_iso(),
        "tag": tag,
        "tesseract_tag": "⧉ATH-v2.0⧉forge⧉delta-phi⧉omega⧉H7⧉adaptive-damping⧉ledger⧉",
        "input_path": os.path.abspath(input_path) if input_path else "",
        "params": {"T": int(T), "N": int(best_frame["F"].shape[0]), "eta0": float(eta0), "H7": H7},
        "metrics": {
            **best,
            "eta_mean": float(np.mean(np.array(eta_series, dtype=np.float32))),
            "eta_min": float(np.min(np.array(eta_series, dtype=np.float32))),
            "eta_max": float(np.max(np.array(eta_series, dtype=np.float32))),
            "coherence_memory_index": float(np.mean(score_series[int(len(score_series)*0.6):]) / (np.mean(score_series[:max(4,int(len(score_series)*0.4))]) + 1e-9)),
            "cusp_v2_8": {
                "EI": EI, "gamma": gamma, "D": D,
                "Dc": Dc, "lambda": lam, "phi_c": phi_c, "C_cusp": C_cusp,
                "H7_horizon": 0.70
            }
        },
        "series": {
            "eta": [float(x) for x in eta_series],
            "score": [float(x) for x in score_series]
        },
        "visuals": {
            "field_png": base_png,
            "dphi_png": dphi_png,
            "omega_png": omega_png,
            "coherence_png": coh_png,
            "resonance_png": res_png
        },
        "public": {
            "report_html": report_path
        },
        "codex": {
            "laws": {
                "universal_truth": "C = (E·I)/(1+|ΔΦ|)",
                "error_geometry": "Ω = 1/(1+|ΔΦ|)",
                "cusp_v2_8": "track EI, γ, D, D_c, λ, Φ_c, C_cusp"
            },
            "H_layers": {"H7": 0.70, "H16B": "fractal dimension", "GEO": "Ω-field"}
        }
    }

    write_true_black_report(report_path, payload)

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    row = {
        "timestamp": payload["timestamp"],
        "tag": tag,
        "score": payload["metrics"]["score"],
        "omega_mean": payload["metrics"]["omega_mean"],
        "H7_fraction": payload["metrics"]["H7_fraction"],
        "I_global": payload["metrics"]["I_global"],
        "curvature_proxy": payload["metrics"]["curvature_proxy"],
        "fractal_dim_H16B": payload["metrics"]["fractal_dim_H16B"],
        "eta_mean": payload["metrics"]["eta_mean"],
        "lambda": payload["metrics"]["cusp_v2_8"]["lambda"],
        "C_cusp": payload["metrics"]["cusp_v2_8"]["C_cusp"],
        "state_path": state_path,
        "report_html": report_path
    }
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")

    out = {"state_path": state_path, "report_html": report_path, "ledger_path": ledger_path, "tag": tag}
    print(json.dumps(out))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
