"""CMA-ES parameter search for fast/my_driver.py (numpy only). Headless, one TORCS at a time.

Score of a candidate = its deterministic 1-lap time (baseline/run_lap.py, -t 1000000, standing start).
  - lap not finished or damage > 0 -> 1000 - distance/10 (keeps a direction for the search)
  - finished but off track > 0      -> lap + 100 + 10 * off-track seconds
  - clean                           -> lap time
Robustness screen (the acceptance gate needs >= 19/20 clean under +-1 %): every generation, up to --screen-max clean
candidates that are close to the best screened lap run the 3-lap race nominally and with --screen-k fixed +-1 %
perturbations (the same multiplier sets for every candidate). One unclean 3-lap race fails the screen and the
candidate's score becomes 900 + lap/100, so the search moves away from knife-edge regions.
Candidates that pass go to --out (sorted by lap); the full gate (baseline/perturb_test.py, 20 variants) is run
separately on the best of them.

    ..\\torcs-env\\Scripts\\python fast\\cmaes_fast.py --gens 40 --out results\\e9_cmaes.json
"""
import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RUN_LAP = os.path.join(REPO, "baseline", "run_lap.py")
XML_3LAP = os.path.join(REPO, "baseline", "corkscrew_3lap.xml")

# (low, high) bounds of the searched parameters. Features that are off (abs_slip, rise_rate, edge_pos, line_in)
# stay off; steer_lock, max_gear and aim_sign are constants.
SPACE = {
    "max_speed": (200.0, 330.0),
    "min_speed": (30.0, 70.0),
    "decel": (8.0, 35.0),
    "margin": (0.0, 25.0),
    "center_k": (0.05, 1.0),
    "brake_gain": (0.005, 0.2),
    "aim_w": (0.4, 1.0),
    "mix": (0.0, 1.0),
    "smooth": (0.0, 0.6),
    "up_rpm": (14000.0, 18500.0),
    "down_rpm": (7000.0, 13000.0),
    "tc_thresh": (3.0, 25.0),
    "tc_cut": (0.1, 0.9),
    "steer_slow": (0.0, 0.5),
    "full_band": (2.0, 40.0),
    "mu": (0.2, 1.2),
    "chord_k": (10.0, 120.0),
    "brake_steer": (0.0, 0.5),
    "slide_k": (0.0, 0.05),
    "slide_thresh": (1.0, 15.0),
    "line_out": (0.0, 0.5),
    "line_dist": (20.0, 150.0),
}
NOT_PERTURBED = {"steer_lock", "max_gear", "aim_sign"}  # same as the E8 perturb_test --fixed


def run_lap(params, extra, tag):
    cmd = [sys.executable, "-W", "ignore", RUN_LAP, "--json", "--code-dir", HERE, "--params-file", "",
           "--params", json.dumps(params), "--out", os.path.join(HERE, "runs.csv"), "--tag", tag] + extra
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    lines = [ln for ln in out.splitlines() if ln.startswith("JSON ")]
    return json.loads(lines[-1][5:]) if lines else {"status": "error"}


def clean_3lap(r):
    return (r.get("status") == "finished" and float(r.get("dist_raced_m") or 0) >= 10800
            and float(r.get("damage") or 0) == 0 and float(r.get("off_track_s") or 0) == 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, default=40)
    ap.add_argument("--popsize", type=int, default=0, help="0 = CMA-ES default 4 + 3 ln(n)")
    ap.add_argument("--sigma", type=float, default=0.05, help="initial step size as a fraction of each range")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", default=os.path.join(HERE, "params.json"))
    ap.add_argument("--fix", default="{}", help="JSON of parameters to keep fixed")
    ap.add_argument("--screen-k", type=int, default=4, help="perturbed 3-lap races per screened candidate")
    ap.add_argument("--screen-max", type=int, default=2, help="screened candidates per generation")
    ap.add_argument("--screen-window", type=float, default=0.3,
                    help="screen clean candidates up to this many s slower than the best screened lap")
    ap.add_argument("--out", default=os.path.join(REPO, "results", "e9_cmaes.json"))
    ap.add_argument("--prefix", default="e9")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    log_path = os.path.splitext(args.out)[0] + "_log.csv"

    with open(args.start, encoding="utf-8") as f:
        loaded = json.load(f)
    start = loaded.get("params", loaded)
    fix = json.loads(args.fix)
    keys = [k for k in SPACE if k not in fix]
    lo = np.array([SPACE[k][0] for k in keys])
    hi = np.array([SPACE[k][1] for k in keys])

    def to_params(x):
        p = dict(start)
        p.update(fix)
        p.update({k: round(float(v), 4) for k, v in zip(keys, lo + np.clip(x, 0, 1) * (hi - lo))})
        return p

    prng = random.Random(12345)
    pert_keys = sorted(k for k in start if k not in NOT_PERTURBED)
    perturbs = [{k: prng.uniform(0.99, 1.01) for k in pert_keys} for _ in range(args.screen_k)]

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
    m = np.clip((np.array([float(start[k]) for k in keys]) - lo) / (hi - lo), 0, 1)
    sigma = args.sigma
    C = np.eye(n)
    pc = np.zeros(n)
    ps = np.zeros(n)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    log_f = open(log_path, "a", newline="", encoding="utf-8")
    log_w = csv.writer(log_f)
    log_w.writerow(["time", "tag", "gen", "kind", "score", "verdict", "lap_time_s", "damage", "off_track_s",
                    "dist_raced_m", "params"])
    passed = []  # screened candidates that passed: {"lap", "tag", "laps3", "params"}
    fastest = None
    evals = screens = 0
    t0 = time.time()

    def log(tag, gen, kind, score, verdict, r, params):
        log_w.writerow([time.strftime("%H:%M:%S"), tag, gen, kind, round(score, 3), verdict, r.get("lap_time_s"),
                        r.get("damage"), r.get("off_track_s"), r.get("dist_raced_m"), json.dumps(params, sort_keys=True)])
        log_f.flush()

    def lap1(params, tag, gen):
        nonlocal evals, fastest
        r = run_lap(params, ["--stop-on-damage"], tag)
        evals += 1
        dmg, off = float(r.get("damage") or 0), float(r.get("off_track_s") or 0)
        if r.get("status") != "finished" or dmg > 0 or not r.get("lap_time_s"):
            s, v = 1000.0 - float(r.get("dist_raced_m") or 0) / 10.0, "crash"
        elif off > 0:
            s, v = float(r["lap_time_s"]) + 100.0 + 10.0 * off, "off-track"
        else:
            s, v = float(r["lap_time_s"]), "clean"
            if fastest is None or s < fastest["lap"]:
                fastest = {"lap": s, "tag": tag, "params": params}
        log(tag, gen, "lap1", s, v, r, params)
        return s, v

    def screen(params, lap, tag, gen):
        nonlocal screens
        screens += 1
        runs = [params] + [{k: (round(v * f[k], 6) if k in f else v) for k, v in params.items()} for f in perturbs]
        laps3 = None
        for j, p in enumerate(runs):
            r = run_lap(p, ["--race-xml", XML_3LAP, "--max-sim-s", "400", "--stop-on-damage"], f"{tag}_s{j}")
            ok = clean_3lap(r)
            log(f"{tag}_s{j}", gen, "screen", 0.0, "clean" if ok else "unclean", r, p)
            if j == 0:
                laps3 = r.get("lap_times")
            if not ok:
                return False, j, laps3
        passed.append({"lap": lap, "tag": tag, "laps3": laps3, "params": params})
        passed.sort(key=lambda e: e["lap"])
        return True, len(runs), laps3

    def save():
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"settings": {"gens": args.gens, "popsize": lam, "sigma0": args.sigma, "seed": args.seed,
                                    "screen_k": args.screen_k, "keys": keys, "fix": fix, "evals": evals,
                                    "screens": screens},
                       "fastest_clean_1lap": fastest, "passed": passed[:10]}, f, indent=2)

    print(f"CMA-ES: n={n}, popsize={lam}, gens={args.gens}, sigma={sigma}; screen: 3-lap nominal + "
          f"{args.screen_k} x +-1 %", flush=True)
    p0 = to_params(m)
    s0, v0 = lap1(p0, f"{args.prefix}_start", 0)
    ok0, _, l3 = screen(p0, s0, f"{args.prefix}_start", 0) if v0 == "clean" else (False, 0, None)
    print(f"start: {s0:.3f} {v0}, screen {'pass' if ok0 else 'FAIL'} ({l3})", flush=True)
    save()

    for gen in range(1, args.gens + 1):
        ev, B = np.linalg.eigh(C)
        D = np.sqrt(np.maximum(ev, 1e-20))
        inv_sqrt_C = B @ np.diag(1 / D) @ B.T
        xs, ys, scores, verdicts = [], [], [], []
        for i in range(lam):
            x = np.clip(m + sigma * (B @ (D * rng.standard_normal(n))), 0, 1)
            s, v = lap1(to_params(x), f"{args.prefix}_g{gen:03d}_{i:02d}", gen)
            xs.append(x)
            ys.append((x - m) / sigma)
            scores.append(s)
            verdicts.append(v)

        ref = passed[0]["lap"] if passed else s0
        cand = sorted((scores[i], i) for i in range(lam) if verdicts[i] == "clean" and scores[i] < ref + args.screen_window)
        notes = []
        for s, i in cand[:args.screen_max]:
            ok, j, _ = screen(to_params(xs[i]), s, f"{args.prefix}_g{gen:03d}_{i:02d}", gen)
            notes.append(f"#{i:02d} {s:.3f} {'pass' if ok else f'fail@{j}'}")
            if not ok:
                scores[i] = 900.0 + s / 100.0

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
        save()
        n_clean = sum(v == "clean" for v in verdicts)
        gen_best = min((scores[i] for i in range(lam) if verdicts[i] == "clean"), default=None)
        print(f"gen {gen:2d}: clean {n_clean}/{lam} gen-best={gen_best} screened [{'; '.join(notes)}] "
              f"best-passed={passed[0]['lap'] if passed else '-'} fastest={fastest and fastest['lap']} "
              f"sigma={sigma:.3f} {time.time() - t0:.0f}s", flush=True)

    log_f.close()
    print("\n=== RESULT ===")
    print("fastest clean 1-lap:", fastest and f"{fastest['lap']} ({fastest['tag']})")
    for e in passed[:5]:
        print(f"passed screen: {e['lap']} ({e['tag']}) 3 laps {e['laps3']}")
    print("saved:", args.out)


if __name__ == "__main__":
    main()
