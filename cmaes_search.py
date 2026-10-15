"""my_driver.py parametrelerini CMA-ES ile ayarlar (sadece numpy). Headless calisir, TORCS menusu gerekmez.

Her aday baseline/run_lap.py ile deterministik (-t 1000000) bir tur kosar:
  - tur bitmedi veya hasar > 0  -> ELENIR (puan = 1000 - gidilen_mesafe/10, arama yonunu kaybetmesin diye;
                                   tur ilk hasarda kesilir: --stop-on-damage)
  - temiz tur                    -> puan = tur suresi
Simdiye kadarki en iyiden hizli her aday ayrica --robust-n kez varsayilan timeout ile kosulur;
kaza orani > 0 ise o da ELENIR (puan = 900 + tur suresi/100) ve en iyi olarak kaydedilmez.

Kullanim (repo kokunden):
    ..\\torcs-env\\Scripts\\python cmaes_search.py --gens 3 --popsize 8          # kisa test
    ..\\torcs-env\\Scripts\\python cmaes_search.py --gens 40 --out best_params.json
    ... --fix "{\\"shift_hold\\": 0}"   (sabit tutulacak parametreler)

Kayitlar: cmaes_log.csv (her aday), baseline/runs.csv ve baseline/robust.csv (run_lap.py).
En iyi temiz + saglam aday --out dosyasina yazilir (varsayilan cmaes_best.json).
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_LAP = os.path.join(HERE, "baseline", "run_lap.py")

# (alt, ust) sinirlar; search.py'deki SPACE + vites parametreleri
SPACE = {
    "max_speed": (120.0, 400.0),
    "min_speed": (30.0, 130.0),
    "decel": (5.0, 40.0),
    "margin": (0.0, 40.0),
    "center_k": (0.2, 2.0),
    "brake_gain": (0.02, 0.5),
    "aim_w": (0.0, 1.0),
    "mix": (0.0, 1.0),
    "smooth": (0.0, 0.95),
    "up_rpm": (7000.0, 18500.0),
    "down_rpm": (3000.0, 15000.0),
    "tc_thresh": (1.0, 20.0),
    "tc_cut": (0.05, 0.6),
    "shift_hold": (0.0, 0.5),
    "gear_hyst": (0.0, 5000.0),
    "corner_steer": (0.1, 1.0),
    "corner_down_rpm": (3000.0, 12000.0),
}


def run_lap(params, extra, tag):
    cmd = [sys.executable, "-W", "ignore", RUN_LAP, "--json", "--params-file", "",
           "--params", json.dumps(params), "--tag", tag] + extra
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE).stdout
    lines = [ln for ln in out.splitlines() if ln.startswith("JSON ")]
    return json.loads(lines[-1][5:]) if lines else {"status": "error"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, default=3)
    ap.add_argument("--popsize", type=int, default=0, help="0 = CMA-ES default 4 + 3 ln(n)")
    ap.add_argument("--sigma", type=float, default=0.05,
                    help="initial step size, as a fraction of each range (0.15 crashed most candidates)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", default=os.path.join(HERE, "best_params.json"))
    ap.add_argument("--fix", default="{}", help="JSON of parameters to keep fixed")
    ap.add_argument("--robust-n", type=int, default=5, help="robust laps for each new-best candidate")
    ap.add_argument("--robust-jitter", type=float, default=0.0, help="--jitter for the robust laps")
    ap.add_argument("--out", default=os.path.join(HERE, "cmaes_best.json"))
    ap.add_argument("--log", default=os.path.join(HERE, "cmaes_log.csv"))
    ap.add_argument("--prefix", default="cma")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    with open(args.start, encoding="utf-8") as f:
        start = json.load(f).get("params", {})
    fix = json.loads(args.fix)
    keys = [k for k in SPACE if k not in fix]
    lo = np.array([SPACE[k][0] for k in keys])
    hi = np.array([SPACE[k][1] for k in keys])

    def to_params(x):
        p = dict(start)
        p.update(fix)
        p.update({k: round(float(v), 4) for k, v in zip(keys, lo + np.clip(x, 0, 1) * (hi - lo))})
        return p

    # ---- CMA-ES state (Hansen's standard settings), search space normalised to [0, 1]^n ----
    n = len(keys)
    lam = args.popsize or 4 + int(3 * math.log(n))
    mu = lam // 2
    w = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    w /= w.sum()
    mueff = 1.0 / np.sum(w ** 2)
    cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
    cs = (mueff + 2) / (n + mueff + 5)
    c1 = 2 / ((n + 1.3) ** 2 + mueff)
    cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
    damps = 1 + 2 * max(0.0, math.sqrt((mueff - 1) / (n + 1)) - 1) + cs
    chi_n = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
    m = np.clip((np.array([float(start.get(k, (SPACE[k][0] + SPACE[k][1]) / 2)) for k in keys]) - lo) / (hi - lo), 0, 1)
    sigma = args.sigma
    C = np.eye(n)
    pc = np.zeros(n)
    ps = np.zeros(n)

    new_log = not os.path.exists(args.log)
    log_f = open(args.log, "a", newline="", encoding="utf-8")
    log_w = csv.writer(log_f)
    if new_log:
        log_w.writerow(["time", "tag", "gen", "score", "verdict", "lap_time_s", "damage", "dist_raced_m",
                        "robust_crash_rate", "robust_mean_s", "params"])

    best_score, best_params = None, None
    evals = 0
    t0 = time.time()
    print(f"CMA-ES: n={n} params, popsize={lam}, gens={args.gens}, sigma={sigma}, robust_n={args.robust_n}"
          f" (jitter {args.robust_jitter})", flush=True)

    def evaluate(params, tag, gen):
        nonlocal best_score, best_params
        r = run_lap(params, ["--stop-on-damage"], tag)
        robust = {}
        if r.get("status") != "finished" or float(r.get("damage") or 0) > 0:
            score, verdict = 1000.0 - float(r.get("dist_raced_m") or 0) / 10.0, "reject:crash"
        else:
            score, verdict = float(r["lap_time_s"]), "clean"
            if best_score is None or score < best_score:
                if args.robust_n > 0:
                    robust = run_lap(params, ["--robust", str(args.robust_n), "--jitter", str(args.robust_jitter)],
                                     tag + "_robust")
                if robust.get("crash_rate", 0) > 0:
                    verdict = f"reject:robust({robust['crashes']}/{robust['n']})"
                    score = 900.0 + score / 100.0
                else:
                    verdict = "NEW BEST"
                    best_score, best_params = score, params
                    with open(args.out, "w", encoding="utf-8") as f:
                        json.dump({"score": score, "robust": robust, "params": params}, f, indent=2)
        log_w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), tag, gen, round(score, 3), verdict, r.get("lap_time_s"),
                        r.get("damage"), r.get("dist_raced_m"), robust.get("crash_rate", ""),
                        robust.get("mean_lap_s", ""), json.dumps(params, sort_keys=True)])
        log_f.flush()
        return score, verdict, r

    # start point first, so the search has a reference
    s0, v0, r0 = evaluate(to_params(m), f"{args.prefix}_start", 0)
    evals += 1
    print(f"start: score={s0:.3f} {v0} lap={r0.get('lap_time_s')} damage={r0.get('damage')}", flush=True)

    for gen in range(1, args.gens + 1):
        evals_c, B = np.linalg.eigh(C)
        D = np.sqrt(np.maximum(evals_c, 1e-20))
        inv_sqrt_C = B @ np.diag(1 / D) @ B.T
        xs, ys, scores = [], [], []
        for i in range(lam):
            x = np.clip(m + sigma * (B @ (D * rng.standard_normal(n))), 0, 1)
            s, v, r = evaluate(to_params(x), f"{args.prefix}_g{gen:03d}_{i:02d}", gen)
            evals += 1
            xs.append(x)
            ys.append((x - m) / sigma)
            scores.append(s)
            print(f"  g{gen} #{i:02d} score={s:8.3f} {v:<22} lap={r.get('lap_time_s')} damage={r.get('damage')}",
                  flush=True)
        order = np.argsort(scores)
        y_sel = np.array([ys[i] for i in order[:mu]])
        y_w = w @ y_sel
        m = np.clip(m + sigma * y_w, 0, 1)
        ps = (1 - cs) * ps + math.sqrt(cs * (2 - cs) * mueff) * (inv_sqrt_C @ y_w)
        hsig = np.linalg.norm(ps) / math.sqrt(1 - (1 - cs) ** (2 * gen)) / chi_n < 1.4 + 2 / (n + 1)
        pc = (1 - cc) * pc + hsig * math.sqrt(cc * (2 - cc) * mueff) * y_w
        C = ((1 - c1 - cmu) * C + c1 * (np.outer(pc, pc) + (1 - hsig) * cc * (2 - cc) * C)
             + cmu * (y_sel.T * w) @ y_sel)
        sigma *= math.exp((cs / damps) * (np.linalg.norm(ps) / chi_n - 1))
        print(f"gen {gen}: gen-best={min(scores):.3f} overall-best={best_score} sigma={sigma:.3f} "
              f"evals={evals} elapsed={time.time() - t0:.0f}s", flush=True)

    log_f.close()
    print("\nBEST:", best_score, json.dumps(best_params))
    print("saved to", args.out if best_params else "(nothing clean found)")


if __name__ == "__main__":
    main()
