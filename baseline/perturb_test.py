"""Sensitivity test: run N variants of a parameter set, each parameter scaled by a random factor in [1-rel, 1+rel],
in the deterministic 3-lap headless race (-t 1000000; equals the real-time GUI, see EXPERIMENTS.md E6).

A variant is clean when all 3 laps finish with damage 0 and off-track time 0.
The same seed gives the same factors, so two candidates can be compared on identical perturbations.

    ..\\torcs-env\\Scripts\\python baseline\\perturb_test.py --params "{\\"min_speed\\": 47}" --n 20 --tag A
"""
import argparse
import json
import os
import random
import statistics as st
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

ap = argparse.ArgumentParser()
ap.add_argument("--params-file", default=os.path.join(REPO, "best_params.json"))
ap.add_argument("--params", default="{}", help="JSON overrides applied before perturbing")
ap.add_argument("--n", type=int, default=20)
ap.add_argument("--rel", type=float, default=0.01, help="max relative change per parameter (0.01 = 1%%)")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--race-xml", default=os.path.join(HERE, "corkscrew_3lap.xml"))
ap.add_argument("--code-dir", default=REPO, help="folder with my_driver.py (e.g. tuna)")
ap.add_argument("--fixed", default="", help="comma-separated keys that are not perturbed (constants, integers, signs)")
ap.add_argument("--tag", default="perturb")
ap.add_argument("--out", default=os.path.join(HERE, "perturb.csv"))
args = ap.parse_args()

with open(args.params_file, encoding="utf-8") as f:
    loaded = json.load(f)
base = loaded.get("params", loaded)
base.update(json.loads(args.params))
rng = random.Random(args.seed)
fixed = {k for k in args.fixed.split(",") if k}
keys = sorted(k for k in base if k not in fixed)


def run(p, tag):
    cmd = [sys.executable, "-W", "ignore", os.path.join(HERE, "run_lap.py"), "--json", "--params-file", "",
           "--params", json.dumps(p), "--code-dir", os.path.abspath(args.code_dir), "--race-xml", args.race_xml, "--max-sim-s", "400", "--tag", tag]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    lines = [ln for ln in out.splitlines() if ln.startswith("JSON ")]
    r = json.loads(lines[-1][5:]) if lines else {"status": "error"}
    laps = [float(x) for x in str(r.get("lap_times", "")).split()]
    dmg = float(r.get("damage") or 0)
    off = float(r.get("off_track_s") or 0)
    # TORCS sometimes shuts down at the line before the client sees the last lapTime, so completion is checked by
    # distance: 3 laps from the grid (10 m behind the line) are >= 3 * 3608 + 10 m.
    done = r.get("status") == "finished" and float(r.get("dist_raced_m") or 0) >= 10800
    return {"laps": laps, "damage": dmg, "off": off, "clean": done and dmg == 0 and off == 0, "done": done}


results = []
nominal = run(base, f"{args.tag}_nominal")
print(f"nominal : laps {nominal['laps']} damage {nominal['damage']:g} off {nominal['off']:g} "
      f"{'CLEAN' if nominal['clean'] else 'NOT CLEAN'}", flush=True)
for i in range(args.n):
    p = dict(base)
    p.update({k: round(base[k] * (1 + rng.uniform(-args.rel, args.rel)), 6) for k in keys})
    r = run(p, f"{args.tag}_v{i:02d}")
    results.append(r)
    print(f"  v{i:02d}: laps {' '.join(f'{x:.3f}' for x in r['laps']) or '-':<23} damage {r['damage']:>5g} "
          f"off {r['off']:>5g}  {'clean' if r['clean'] else 'NOT CLEAN'}", flush=True)

clean = [r for r in results if r["clean"]]
lap1 = [r["laps"][0] for r in results if r["laps"]]
summary = {"tag": args.tag, "n": args.n, "rel": args.rel, "seed": args.seed, "clean": len(clean),
           "damaged": sum(r["damage"] > 0 for r in results), "off_track": sum(r["off"] > 0 for r in results),
           "unfinished": sum(not r["done"] for r in results),
           "lap1_mean": round(st.mean(lap1), 3) if lap1 else "", "lap1_worst": max(lap1) if lap1 else "",
           "lap1_best": min(lap1) if lap1 else "", "nominal_lap1": nominal["laps"][0] if nominal["laps"] else "",
           "nominal_clean": nominal["clean"], "params": json.dumps(base, sort_keys=True)}
print("\n=== PERTURB ===")
for k, v in summary.items():
    if k != "params":
        print(f"{k:>14}: {v}")
new = not os.path.exists(args.out)
with open(args.out, "a", encoding="utf-8") as f:
    if new:
        f.write(",".join(summary) + "\n")
    f.write(",".join(json.dumps(v) if k == "params" else str(v) for k, v in summary.items()) + "\n")
