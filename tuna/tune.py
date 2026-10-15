"""Parameter search for tuna/my_driver.py (evolution strategy around the best set so far).

Each trial runs one headless lap with tuna/run_lap.py (~12 s). A lap only counts as good when it is
clean (finished, damage 0, never off track). The best clean set is written to --out after every
improvement, so the search can be stopped at any time with Ctrl+C.

    py tuna/tune.py --trials 300
    py tuna/tune.py --trials 300 --start tuna/params.json --out tuna/params_tuned.json

Every trial is logged to tuna/tune_log.csv.
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from my_driver import DEFAULTS  # noqa: E402

# (low, high) bounds of the searched parameters
SPACE = {
    "max_speed": (150.0, 330.0),
    "min_speed": (25.0, 90.0),
    "decel": (5.0, 45.0),
    "margin": (0.0, 40.0),
    "center_k": (0.05, 2.0),
    "brake_gain": (0.005, 0.5),
    "accel_gain": (0.01, 0.5),
    "aim_w": (0.0, 1.0),
    "mix": (0.0, 1.0),
    "smooth": (0.0, 0.9),
    "up_rpm": (12000.0, 18500.0),
    "down_rpm": (6000.0, 14000.0),
    "tc_thresh": (1.0, 25.0),
    "tc_cut": (0.05, 0.8),
    "steer_slow": (0.0, 0.6),
    "abs_slip": (0.0, 0.6),
    "abs_range": (0.05, 0.6),
    "full_band": (0.0, 60.0),
    "mu": (0.0, 3.0),
    "chord_k": (10.0, 150.0),
    "brake_steer": (0.0, 1.0),
    "line_out": (0.0, 0.7),
    "line_in": (0.0, 0.7),
    "line_dist": (20.0, 150.0),
    "line_min_deg": (1.0, 20.0),
}
# values below these thresholds switch the feature off (0)
OFF_BELOW = {"abs_slip": 0.05, "full_band": 2.0, "mu": 0.3, "line_out": 0.03, "line_in": 0.03}
BELOW_NORMAL = 0x00004000  # Windows process priority


def run_lap(params):
    cmd = [sys.executable, os.path.join(HERE, "run_lap.py"), "--quiet", "--no-save",
           "--set", json.dumps(params), "--tag", "tune"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                             creationflags=BELOW_NORMAL if os.name == "nt" else 0).stdout
    except subprocess.TimeoutExpired:
        return None
    for line in out.splitlines():
        if line.startswith("RESULT_JSON "):
            return json.loads(line[len("RESULT_JSON "):])
    return None


def score(r):
    """Lower is better. Unclean laps are always worse than any clean lap."""
    if r is None:
        return 10000.0
    if r["result"] != "finished" or not r["lap_time_s"]:
        return 5000.0 - float(r["dist_m"]) / 4.0
    s = float(r["lap_time_s"])
    if not r["clean"]:
        s += 1000.0 + 10.0 * float(r["off_track_s"]) + float(r["max_damage"])
    return s


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def tidy(p):
    for k, lim in OFF_BELOW.items():
        if p.get(k, 0) < lim:
            p[k] = 0.0
    return p


def mutate(best, sigma, fixed):
    p = dict(best)
    keys = [k for k in SPACE if k not in fixed]
    for k in random.sample(keys, random.randint(1, 4)):
        lo, hi = SPACE[k]
        cur = p.get(k, lo)
        if k in OFF_BELOW and cur == 0.0 and random.random() < 0.5:
            cur = OFF_BELOW[k] + random.random() * (hi - OFF_BELOW[k]) * 0.3  # switch a feature on
        p[k] = round(clip(cur + random.gauss(0, sigma * (hi - lo)), lo, hi), 4)
    return tidy(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--start", default=os.path.join(HERE, "params.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "params_tuned.json"))
    ap.add_argument("--sigma", type=float, default=0.08, help="mutation size as a share of each range")
    ap.add_argument("--fix", default="{}", help="JSON of parameters to hold constant")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    random.seed(args.seed or time.time())
    fixed = json.loads(args.fix)

    with open(args.start, encoding="utf-8") as f:
        best = json.load(f)
    best = best.get("params", best)
    best = {**DEFAULTS, **best, **fixed}  # missing keys get the driver defaults
    best = tidy(best)

    r = run_lap(best)
    best_s = score(r)
    print(f"start: {best_s:.2f} {r}", flush=True)
    log_path = os.path.join(HERE, "tune_log.csv")
    new = not os.path.exists(log_path)
    log = open(log_path, "a", newline="", encoding="utf-8")
    w = csv.writer(log)
    if new:
        w.writerow(["time", "trial", "score", "lap_time_s", "clean", "sigma", "params"])

    sigma, fails = args.sigma, 0
    for t in range(1, args.trials + 1):
        cand = mutate(best, sigma, fixed)
        r = run_lap(cand)
        s = score(r)
        w.writerow([time.strftime("%H:%M:%S"), t, round(s, 2), r and r["lap_time_s"], r and r["clean"],
                    round(sigma, 4), json.dumps(cand)])
        log.flush()
        if s < best_s:
            best, best_s, fails = cand, s, 0
            print(f"[{t}] new best {s:.2f}", flush=True)
            if s < 1000:
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump({"score": s, "params": best}, f, indent=2)
        else:
            fails += 1
            if fails >= 25:  # shrink the steps when nothing improves for a while
                sigma, fails = max(0.01, sigma * 0.7), 0
                print(f"[{t}] sigma -> {sigma:.3f}", flush=True)
    print(f"done. best {best_s:.2f} -> {args.out}")


if __name__ == "__main__":
    main()
