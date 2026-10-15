"""Headless TORCS lap measurement: Corkscrew, 1 lap, standing start.

Starts wtorcs.exe in text mode (-r <race xml>, no menus/graphics), connects the Python
driver from this repo to scr_server on UDP 3001, drives until TORCS ends the race,
then reads the lap time / damage that TORCS itself reports. Driver code is imported, never modified.

Usage (from the repo root; the venv lives next to the repo in ../torcs-env):
    ..\\torcs-env\\Scripts\\python baseline\\run_lap.py             # my_driver + best_params.json
    ..\\torcs-env\\Scripts\\python baseline\\run_lap.py --driver jm  # IBM sample driver
    ... --params "{\\"decel\\": 18}"  --trace  --tag note

Every run is appended to baseline/runs.csv.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)                       # RaceYourCode
WS = os.path.dirname(REPO)                         # working_space (holds torch/torcs)

ap = argparse.ArgumentParser()
ap.add_argument("--driver", choices=["mine", "jm"], default="mine", help="mine=my_driver.py, jm=torcs_jm_par.drive_modular")
ap.add_argument("--params-file", default=None, help="default: <code-dir>/best_params.json for --driver mine")
ap.add_argument("--params", default=None, help="JSON, overrides keys from --params-file")
ap.add_argument("--code-dir", default=REPO)
ap.add_argument("--torcs-dir", default=os.path.join(WS, "torch", "torcs"))
ap.add_argument("--race-xml", default=os.path.join(HERE, "corkscrew_1lap.xml"))
ap.add_argument("--port", type=int, default=3001)
ap.add_argument("--udp-timeout-us", type=int, default=1000000,
                help="wtorcs -t: how long scr_server waits for the client each step. TORCS default is 10000 (10 ms); "
                     "in fast headless mode Windows scheduling jitter exceeds that, the server then reuses the old "
                     "command and runs become non-deterministic. 0 = do not pass -t")
ap.add_argument("--max-sim-s", type=float, default=300.0, help="simulated-time limit")
ap.add_argument("--wall-timeout", type=float, default=600.0, help="kill everything after this many real seconds")
ap.add_argument("--trace", action="store_true", help="write baseline/trace.csv every 5 steps")
ap.add_argument("--tag", default="")
ap.add_argument("--out", default=os.path.join(HERE, "runs.csv"))
args = ap.parse_args()

STEP_DT = 0.02  # scr_server: 50 control steps per simulated second

# ---------- parameters ----------
params = {}
pf = args.params_file
if pf is None and args.driver == "mine":
    pf = os.path.join(args.code_dir, "best_params.json")
if pf:
    with open(pf, encoding="utf-8") as f:
        loaded = json.load(f)
    params = loaded.get("params", loaded)
if args.params:
    params.update(json.loads(args.params))

# ---------- start TORCS headless ----------
wtorcs = os.path.join(args.torcs_dir, "wtorcs.exe")
log_path = os.path.join(HERE, "wtorcs_last.log")
log_f = open(log_path, "w")
cmd = [wtorcs, "-r", os.path.abspath(args.race_xml)]
if args.udp_timeout_us:
    cmd += ["-t", str(args.udp_timeout_us)]
torcs = subprocess.Popen(cmd, cwd=args.torcs_dir,
                         stdout=log_f, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def watchdog():
    time.sleep(args.wall_timeout)
    print(f"\n[watchdog] {args.wall_timeout}s wall time exceeded, killing TORCS", flush=True)
    torcs.kill()
    os._exit(2)


threading.Thread(target=watchdog, daemon=True).start()
time.sleep(1.0)
if torcs.poll() is not None:
    sys.exit(f"wtorcs.exe exited immediately (code {torcs.returncode}), see {log_path}")

# ---------- client + driver from the team repo (imported as-is) ----------
sys.path.insert(0, args.code_dir)
sys.argv = [sys.argv[0], "-p", str(args.port)]  # torcs_jm_par parses sys.argv itself
import torcs_jm_par as drv  # noqa: E402

if args.driver == "mine":
    import my_driver  # noqa: E402

    def drive_fn(c):
        my_driver.drive(c, params)
else:
    for k, attr, cast in [("target_speed", "TARGET_SPEED", int), ("steer_gain", "STEER_GAIN", float),
                          ("centering_gain", "CENTERING_GAIN", float), ("brake_threshold", "BRAKE_THRESHOLD", float),
                          ("traction_control", "ENABLE_TRACTION_CONTROL", bool)]:
        if k in params:
            setattr(drv, attr, cast(params[k]))
    if "gear_thresholds" in params:
        drv.GEAR_SPEEDS = [int(x) for x in params["gear_thresholds"]]
    drive_fn = drv.drive_modular

wall0 = time.time()
C = drv.Client(p=args.port)

trace_f = open(os.path.join(HERE, "trace.csv"), "w", newline="", encoding="utf-8") if args.trace else None
trace_w = csv.writer(trace_f) if trace_f else None
if trace_w:
    trace_w.writerow(["step", "curLapTime", "distFromStart", "distRaced", "speedX", "trackPos", "angle",
                      "rpm", "steer", "accel", "brake", "gear", "damage"])

status = "timeout"
steps = off_steps = 0
max_damage = 0.0
cur_lap = 0.0
last_lap = 0.0
dist_raced = 0.0
top_speed = 0.0
for steps in range(1, int(args.max_sim_s / STEP_DT) + 1):
    C.get_servers_input()
    if C.so is None:  # ***shutdown***: TORCS finished the 1-lap race
        status = "finished"
        break
    S = C.S.d
    drive_fn(C)
    C.respond_to_server()
    if abs(S["trackPos"]) > 1.0:
        off_steps += 1
    max_damage = max(max_damage, S.get("damage", 0.0))
    cur_lap = S.get("curLapTime", cur_lap)
    if S.get("lastLapTime", 0) > 0:
        last_lap = S["lastLapTime"]
    dist_raced = S.get("distRaced", dist_raced)
    top_speed = max(top_speed, S["speedX"])
    if trace_w and steps % 5 == 0:
        R = C.R.d
        trace_w.writerow([steps, round(cur_lap, 2), round(S["distFromStart"], 1), round(dist_raced, 1),
                          round(S["speedX"], 1), round(S["trackPos"], 3), round(S["angle"], 3), round(S["rpm"]),
                          round(R["steer"], 3), round(R["accel"], 3), round(R["brake"], 3), R["gear"], S["damage"]])
wall_s = time.time() - wall0
if trace_f:
    trace_f.close()

# ---------- wait for TORCS to write results ----------
if status != "finished":
    torcs.kill()
try:
    torcs.wait(timeout=30)
except subprocess.TimeoutExpired:
    torcs.kill()
log_f.close()

# TORCS prints "Sim Time: 84.79 [s], Leader Laps: 1, ..." when the text-mode race ends.
# (Its results XML is not written when -r gets an absolute path, so we read the console log.)
with open(log_path, encoding="utf-8", errors="replace") as f:
    m = re.search(r"Sim Time:\s*([\d.]+).*?Leader Laps:\s*(\d+)", f.read())
race_time, laps = (float(m.group(1)), int(m.group(2))) if m else ("", "")
if status == "finished" and laps != 1:
    status = "incomplete"

row = {
    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "driver": args.driver,
    "status": status,
    "lap_time_s": round(last_lap, 3) if last_lap else "",  # TORCS lastLapTime: green light -> finish line
    "race_time_s": race_time,                               # TORCS console "Sim Time"
    "laps": laps,
    "damage": max_damage,                                   # TORCS damage sensor (0 = clean)
    "off_track_s": round(off_steps * STEP_DT, 2),
    "top_speed_kmh": round(top_speed, 1),
    "dist_raced_m": round(dist_raced, 1),
    "sim_steps": steps,
    "wall_s": round(wall_s, 1),
    "params": json.dumps(params, sort_keys=True),
    "tag": args.tag,
}
print("\n=== RESULT ===")
for k, v in row.items():
    print(f"{k:>18}: {v}")

new = not os.path.exists(args.out)
with open(args.out, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(row))
    if new:
        w.writeheader()
    w.writerow(row)
sys.exit(0 if status == "finished" else 1)
