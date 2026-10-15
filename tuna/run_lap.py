"""Runs one lap of the tuna/ driver (my_driver.py + params.json) on Corkscrew and measures it.

By default it starts TORCS without menus (-r) and closes it after the lap. One lap takes ~12 s.
    py tuna/run_lap.py
    py tuna/run_lap.py --params tuna/params.json --tag "first try"
    py tuna/run_lap.py --trace        # tuna/trace.csv: per-step telemetry
    py tuna/run_lap.py --segments     # summary per 100 m section
    py tuna/run_lap.py --gui          # start TORCS yourself: Race -> Quick Race -> New Race (to watch)

Each result is appended to tuna/results.csv. "clean" = lap finished, damage 0, never off track.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ap = argparse.ArgumentParser()
ap.add_argument("--params", default=os.path.join(HERE, "params.json"))
ap.add_argument("--torcs", default=r"C:\torcs", help="TORCS folder")
ap.add_argument("--gui", action="store_true", help="do not start TORCS; wait for New Race in an open TORCS")
ap.add_argument("--trace", action="store_true", help="write tuna/trace.csv")
ap.add_argument("--segments", action="store_true", help="print a summary per 100 m section")
ap.add_argument("--max-seconds", type=float, default=200.0)
ap.add_argument("--tag", default="")
args = ap.parse_args()

sys.path.insert(0, HERE)  # tuna/my_driver.py
sys.path.insert(1, ROOT)  # torcs_jm_par.py (Client)
sys.argv = [sys.argv[0], "-p", "3001"]  # torcs_jm_par parses its own arguments

import warnings  # noqa: E402
warnings.filterwarnings("ignore", category=SyntaxWarning)
import torcs_jm_par as drv  # noqa: E402
import my_driver  # noqa: E402

with open(args.params, encoding="utf-8") as f:
    p = json.load(f)
p = p.get("params", p)

STEP_DT = 0.02
torcs = None
if not args.gui:
    torcs = subprocess.Popen([os.path.join(args.torcs, "wtorcs.exe"), "-r", r"config\raceman\quickrace.xml"],
                             cwd=args.torcs, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
else:
    print("In TORCS press Race -> Quick Race -> New Race...")

rows = []
result, lap_time = "timeout", ""
off_steps, max_damage, stuck, prev_dist, last_cur, S = 0, 0.0, 0, None, 0.0, {}
try:
    C = drv.Client(p=3001)
    for step in range(1, int(args.max_seconds / STEP_DT) + 1):
        C.get_servers_input()
        if C.so is None:
            result = "finished"
            break
        S = C.S.d
        if prev_dist is not None and step > 500 and prev_dist - S["distFromStart"] > 1500:
            result, lap_time = "finished", round(last_cur, 2)  # crossed the start line
            break
        prev_dist = S["distFromStart"]
        my_driver.drive(C, p)
        C.respond_to_server()
        R = C.R.d
        rows.append([round(S["distFromStart"], 1), round(S["speedX"], 1), round(S["trackPos"], 3), round(S["angle"], 3),
                     round(R["steer"], 3), round(R["accel"], 3), round(R["brake"], 3), R["gear"], int(S["rpm"]),
                     round(S["track"][9], 1), S["damage"]])
        if abs(S["trackPos"]) > 1.0:
            off_steps += 1
        max_damage = max(max_damage, S.get("damage", 0))
        last_cur = S.get("curLapTime", last_cur)
        stuck = stuck + 1 if step * STEP_DT > 3 and abs(S["speedX"]) < 2 else 0
        if stuck * STEP_DT > 6:
            result = "stuck"
            break
    try:
        C.R.d["meta"] = 1
        C.respond_to_server()
        C.shutdown()
    except Exception:
        pass
finally:
    if torcs:
        torcs.kill()

off_s = round(off_steps * STEP_DT, 2)
clean = result == "finished" and max_damage == 0 and off_s == 0
out = {
    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "result": result,
    "lap_time_s": lap_time,
    "clean": clean,
    "off_track_s": off_s,
    "max_damage": max_damage,
    "dist_m": round(S.get("distRaced", 0), 1),
    "tag": args.tag,
    "params": json.dumps(p),
}
print("\n=== RESULT ===")
for k, v in out.items():
    if k != "params":
        print(f"{k}: {v}")

res = os.path.join(HERE, "results.csv")
new = not os.path.exists(res)
with open(res, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out))
    if new:
        w.writeheader()
    w.writerow(out)

if args.trace:
    with open(os.path.join(HERE, "trace.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dist", "speedX", "trackPos", "angle", "steer", "accel", "brake", "gear", "rpm", "front", "damage"])
        w.writerows(rows)
    print("trace: tuna/trace.csv")

if args.segments:
    print("\n  dist  time_s  avg_kmh  min_kmh  brake_s  max|pos|")
    seg = {}
    for r in rows:
        if r[0] > 3500 and len(seg) == 0:
            continue  # standing start behind the start line
        s = seg.setdefault(int(r[0] // 100), [0, 0.0, 1e9, 0, 0.0])
        s[0] += 1
        s[1] += r[1]
        s[2] = min(s[2], r[1])
        s[3] += r[6] > 0
        s[4] = max(s[4], abs(r[2]))
    for k in sorted(seg):
        n, sv, mn, b, tp = seg[k]
        print(f"{k * 100:6d}  {n * STEP_DT:6.2f}  {sv / n:7.1f}  {mn:7.1f}  {b * STEP_DT:7.2f}  {tp:7.2f}")
