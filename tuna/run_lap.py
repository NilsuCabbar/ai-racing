"""Runs one lap of the tuna/ driver (my_driver.py + params.json) and measures it (Corkscrew by default).

By default it starts TORCS without menus (-r) and closes it after the lap. One lap takes ~12 s.
    py tuna/run_lap.py
    py tuna/run_lap.py --params tuna/params.json --tag "first try"
    py tuna/run_lap.py --trace        # tuna/trace.csv: per-step telemetry
    py tuna/run_lap.py --segments     # summary per 100 m section
    py tuna/run_lap.py --track e-track-2   # another track, to check the driver is not overfitted
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
ap.add_argument("--set", default="{}", help='JSON overrides on top of --params, e.g. \'{"decel": 20}\'')
ap.add_argument("--quiet", action="store_true", help="print only one summary line")
ap.add_argument("--no-save", action="store_true", help="do not append to tuna/results.csv")
ap.add_argument("--torcs", default=r"C:\torcs", help="TORCS folder")
ap.add_argument("--gui", action="store_true", help="do not start TORCS; wait for New Race in an open TORCS")
ap.add_argument("--trace", action="store_true", help="write tuna/trace.csv")
ap.add_argument("--segments", action="store_true", help="print a summary per 100 m section")
ap.add_argument("--max-seconds", type=float, default=200.0)
ap.add_argument("--tag", default="")
ap.add_argument("--track", default="corkscrew", help="any folder name under C:\\torcs\\tracks\\*, e.g. e-track-2")
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
p.update(json.loads(args.set))

STEP_DT = 0.02


def race_file(track):
    """Quick race config for the track: the normal one for corkscrew, otherwise a copy with the track swapped."""
    base = r"config\raceman\quickrace.xml"
    if track == "corkscrew":
        return base
    cats = [c for c in os.listdir(os.path.join(args.torcs, "tracks"))
            if os.path.isdir(os.path.join(args.torcs, "tracks", c, track))]
    if not cats:
        sys.exit(f"unknown track: {track}")
    with open(os.path.join(args.torcs, base), encoding="utf-8") as f:
        xml = f.read()
    xml = xml.replace('val="corkscrew"', f'val="{track}"').replace('<attstr name="category" val="road"/>',
                                                                   f'<attstr name="category" val="{cats[0]}"/>')
    name = rf"config\raceman\tuna_{track}.xml"
    with open(os.path.join(args.torcs, name), "w", encoding="utf-8") as f:
        f.write(xml)
    return name


def port_free(port=3001):
    """True when no other TORCS is listening on the scr_server port (it would steal the connection)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


torcs = None
if not args.gui:
    if not port_free():
        sys.exit("UDP port 3001 is in use: another TORCS is running. Close it and try again.")
    torcs = subprocess.Popen([os.path.join(args.torcs, "wtorcs.exe"), "-r", race_file(args.track)],
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
        if prev_dist is not None and step > 500 and prev_dist > 500 and S["distFromStart"] < 0.5 * prev_dist:
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
if args.quiet:
    print(f"\n{result} lap={lap_time} clean={clean} off={off_s} dmg={max_damage} tag={args.tag}")
else:
    print("\n=== RESULT ===")
    for k, v in out.items():
        if k != "params":
            print(f"{k}: {v}")
print("RESULT_JSON " + json.dumps({k: out[k] for k in ("result", "lap_time_s", "clean", "off_track_s", "max_damage", "dist_m")}))

if not args.no_save:
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
    start = rows[0][0] if rows else 0.0
    for r in rows:
        if len(seg) == 0 and start > 500 and r[0] > 0.5 * start:
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
