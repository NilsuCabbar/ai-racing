"""Acceptance gate for the map driver: 1 lap (with a full trace), then baseline/perturb_test.py (3-lap race, nominal +
20 variants at +-1 %). One TORCS at a time. Writes results/<tag>_gate.txt and prints one summary line.

Pass = 1 lap: finished, damage 0, off track 0 s; 3 laps clean; at least --need of the 20 variants clean.

    py mapped/gate.py --tag e13_g085 [--params "{\\"look_t\\": 0.3}"] [--skip-perturb]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = sys.executable
FIXED = "max_gear,ctrl"  # integers / switches are not perturbed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--params-file", default=os.path.join(HERE, "params.json"))
    ap.add_argument("--params", default="{}")
    ap.add_argument("--need", type=int, default=19)
    ap.add_argument("--skip-perturb", action="store_true", help="only the 1-lap run")
    a = ap.parse_args()
    out = []

    cmd = [PY, "-W", "ignore", os.path.join(REPO, "baseline", "run_lap.py"), "--json", "--code-dir", HERE,
           "--params-file", a.params_file, "--params", a.params, "--trace", "--trace-every", "1", "--trace-beams",
           "--trace-file", os.path.join(HERE, "trace_last.csv"), "--tag", a.tag]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    line = [ln for ln in r.splitlines() if ln.startswith("JSON ")]
    one = json.loads(line[-1][5:]) if line else {"status": "error"}
    lap1_ok = (one.get("status") == "finished" and float(one.get("damage") or 0) == 0
               and float(one.get("off_track_s") or 0) == 0)
    out.append(f"1 lap: {one.get('status')} lap {one.get('lap_time_s')} damage {one.get('damage')} "
               f"off {one.get('off_track_s')} top {one.get('top_speed_kmh')} -> {'ok' if lap1_ok else 'FAIL'}")
    shutil.copy(os.path.join(HERE, "trace_last.csv"), os.path.join(HERE, f"trace_{a.tag}.csv"))

    clean = nominal_ok = None
    if lap1_ok and not a.skip_perturb:
        with open(a.params_file, encoding="utf-8") as f:
            base = json.load(f)
        base = base.get("params", base)
        base.update(json.loads(a.params))
        tmp = os.path.join(HERE, f"_params_{a.tag}.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(base, f)
        cmd = [PY, "-W", "ignore", os.path.join(REPO, "baseline", "perturb_test.py"), "--code-dir", HERE,
               "--params-file", tmp, "--fixed", FIXED, "--n", "20", "--rel", "0.01", "--seed", "7", "--tag", a.tag]
        txt = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
        os.remove(tmp)
        out.append(txt.rstrip())
        m = re.search(r"^\s*clean: (\d+)", txt, re.M)
        clean = int(m.group(1)) if m else 0
        nominal_ok = "CLEAN" in (re.search(r"^nominal.*$", txt, re.M) or [""])[0] and "NOT CLEAN" not in \
            (re.search(r"^nominal.*$", txt, re.M) or [""])[0]
    passed = bool(lap1_ok and (a.skip_perturb or (nominal_ok and clean is not None and clean >= a.need)))
    summary = (f"GATE {a.tag}: lap {one.get('lap_time_s')} | 1-lap {'ok' if lap1_ok else 'FAIL'} | "
               f"3-lap {'-' if nominal_ok is None else ('ok' if nominal_ok else 'FAIL')} | "
               f"perturb {'-' if clean is None else f'{clean}/20'} | {'PASS' if passed else 'FAIL'}")
    out.append(summary)
    with open(os.path.join(REPO, "results", f"{a.tag}_gate.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
