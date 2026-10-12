"""Corkscrew'de torcs_jm_par.py surucusunu calistirir ve tur sonucunu runs.csv'ye yazar.

Kullanim (TORCS'ta Race -> Quick Race -> New Race ile yaris bekleme modundayken):
    py lap_runner.py
    py lap_runner.py --params "{\"target_speed\": 120}"

Parametre anahtarlari torcs_jm_par.py'deki degiskenlerle ayni:
    target_speed, steer_gain, centering_gain, brake_threshold, gear_thresholds, traction_control
"""
import argparse
import csv
import json
import os
import sys
import random
import time

ap = argparse.ArgumentParser()
ap.add_argument("--params", default="{}", help="JSON; verilmeyen anahtarlar varsayilan kalir")
ap.add_argument("--driver", choices=["jm", "mine", "ai"], default="jm", help="jm=torcs_jm_par, mine=my_driver, ai=ai_driver (driver.pt)")
ap.add_argument("--params-file", default="", help="parametreleri JSON dosyasindan oku (orn. best_params.json)")
ap.add_argument("--port", type=int, default=3001)
ap.add_argument("--max-seconds", type=float, default=300.0, help="sim suresi siniri")
ap.add_argument("--trace", action="store_true", help="her 10 adimda trace.csv yaz")
ap.add_argument("--log", action="store_true", help="temiz turu drive_log.csv'ye ekle (sensor -> ogretmen komutu)")
ap.add_argument("--noise", type=float, default=0.0, help="gonderilen direksiyona eklenen gauss sapma (kayita temiz komut yazilir)")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--tag", default="", help="runs.csv'ye yazilacak not")
args = ap.parse_args()

# torcs_jm_par kendi komut satiri ayrisimini yapiyor; ona bizim argumanlarimizi gostermeyelim.
sys.argv = [sys.argv[0], "-p", str(args.port)]
import torcs_jm_par as drv  # noqa: E402

p = json.loads(args.params)
if args.params_file:
    with open(args.params_file, encoding="utf-8") as f:
        loaded = json.load(f)
    p = loaded.get("params", loaded)
if "target_speed" in p: drv.TARGET_SPEED = int(p["target_speed"])
if "steer_gain" in p: drv.STEER_GAIN = float(p["steer_gain"])
if "centering_gain" in p: drv.CENTERING_GAIN = float(p["centering_gain"])
if "brake_threshold" in p: drv.BRAKE_THRESHOLD = float(p["brake_threshold"])
if "gear_thresholds" in p: drv.GEAR_SPEEDS = [int(x) for x in p["gear_thresholds"]]
if "traction_control" in p: drv.ENABLE_TRACTION_CONTROL = bool(p["traction_control"])

STEP_DT = 0.02  # TORCS 50 adim/sn
OFF_TRACK = 1.0  # |trackPos| > 1 => pist disi
STUCK_SECONDS = 6.0

if args.driver == "mine":
    import my_driver
    def drive_fn(c):
        my_driver.drive(c, p)
elif args.driver == "ai":
    import ai_driver
    def drive_fn(c):
        ai_driver.drive(c, p)
else:
    drive_fn = drv.drive_modular

C = drv.Client(p=args.port)
max_steps = int(args.max_seconds / STEP_DT)

result = "timeout"
steps = 0
off_steps = 0
max_damage = 0.0
stuck_steps = 0
lap_time = ""
last_cur = 0.0
prev_dist = None

random.seed(args.seed)
log_rows = []
trace_f = open("trace.csv", "w", newline="", encoding="utf-8") if args.trace else None
trace_w = csv.writer(trace_f) if trace_f else None
if trace_w:
    trace_w.writerow(["step", "distFromStart", "speedX", "trackPos", "angle", "steer", "accel", "brake", "gear", "damage"])

for steps in range(1, max_steps + 1):
    C.get_servers_input()
    if C.so is None:  # sunucu yarisi bitirdi (1 tur) ya da kapatti
        result = "finished"
        break
    S = C.S.d
    if prev_dist is not None and steps > 500 and prev_dist - S["distFromStart"] > 1500:
        result = "finished"  # start cizgisini gecti (distFromStart basa sardi)
        lap_time = round(last_cur, 2)
        C.R.d["meta"] = 1  # yarisi yeniden baslat
        C.respond_to_server()
        C.shutdown()
        break
    prev_dist = S["distFromStart"]
    drive_fn(C)
    if args.log:
        R0 = C.R.d
        log_rows.append([S["speedX"], S["angle"], S["trackPos"]] + list(S["track"]) + [R0["steer"], R0["accel"], R0["brake"]])
    if args.noise:
        C.R.d["steer"] += random.gauss(0, args.noise)
    C.respond_to_server()
    if trace_w and steps % 10 == 0:
        R = C.R.d
        trace_w.writerow([steps, round(S["distFromStart"], 1), round(S["speedX"], 1), round(S["trackPos"], 2),
                          round(S["angle"], 2), round(R["steer"], 2), round(R["accel"], 2), R["brake"], R["gear"], S["damage"]])

    if abs(S["trackPos"]) > OFF_TRACK:
        off_steps += 1
    max_damage = max(max_damage, S.get("damage", 0))
    last_cur = S.get("curLapTime", last_cur)
    if S.get("lastLapTime", 0) > 0:
        lap_time = S["lastLapTime"]
    # takilma: 1 sn'den sonra neredeyse duruyor
    if steps * STEP_DT > 3 and abs(S["speedX"]) < 2:
        stuck_steps += 1
    else:
        stuck_steps = 0
    if stuck_steps * STEP_DT > STUCK_SECONDS:
        result = "stuck"
        break

if trace_f:
    trace_f.close()
dist = C.S.d.get("distRaced", 0)
if lap_time == "" and result == "finished":
    lap_time = round(last_cur, 2)  # sunucu son paketi gondermeden kapatiyor: son curLapTime yaklasik tur suresi
if result in ("stuck", "timeout"):
    C.R.d["meta"] = 1  # yarisi yeniden baslat
    C.respond_to_server()
    C.shutdown()

if args.log:
    clean = result == "finished" and off_steps * STEP_DT <= 1.0 and max_damage <= 30
    if clean:
        new_log = not os.path.exists("drive_log.csv")
        with open("drive_log.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_log:
                w.writerow(["speedX", "angle", "trackPos"] + [f"track{i}" for i in range(19)] + ["steer", "accel", "brake"])
            w.writerows(log_rows)
    print(f"drive_log: {'EKLENDI' if clean else 'ATILDI (temiz degil)'} ({len(log_rows)} satir)")

row = {
    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "result": result,
    "lap_time_s": lap_time,
    "sim_seconds": round(steps * STEP_DT, 1),
    "dist_raced_m": round(dist, 1),
    "off_track_s": round(off_steps * STEP_DT, 1),
    "max_damage": max_damage,
    "driver": args.driver,
    "params": json.dumps(p),
    "tag": args.tag,
}
print("\n=== SONUC ===")
for k, v in row.items():
    print(f"{k}: {v}")

new = not os.path.exists("runs.csv")
with open("runs.csv", "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(row))
    if new:
        w.writeheader()
    w.writerow(row)
