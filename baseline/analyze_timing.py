"""Summarise a run_lap.py --timing-log CSV: how often the client answered late and how much command lag built up.

    ..\\torcs-env\\Scripts\\python baseline\\analyze_timing.py baseline\\timing_gui.csv

- late answers: client response > 10 ms (TORCS default UDP timeout). Their rate per step is directly comparable
  with --jitter P (P = probability per step of a 15 ms late answer).
- gear echo: steps from sending a new gear until the gear sensor shows it. 1 = in sync; every extra step is one
  step (20 ms) of accumulated command lag. This also works in the real-time GUI, where next_was_waiting cannot.
"""
import csv
import statistics as st
import sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
race = [r for r in rows if float(r["curLapTime"]) > 0 or int(r["laps_done"]) > 0]  # after the green light
resp = [float(r["resp_ms"]) for r in race]
late = [r for r in race if float(r["resp_ms"]) > 10.0]
gaps = [float(r["wait_ms"]) for r in race]
echo = [(int(r["step"]), int(r["laps_done"]), int(r["gear_echo_steps"])) for r in race if r["gear_echo_steps"]]

print(f"steps after start : {len(race)}  (laps completed: {race[-1]['laps_done'] if race else 0})")
print(f"response ms       : median {st.median(resp):.3f}  p99 {sorted(resp)[int(0.99 * (len(resp) - 1))]:.3f}  "
      f"max {max(resp):.3f}")
print(f"wait for state ms : median {st.median(gaps):.3f}  (real-time GUI ~20 ms, headless ~0)")
print(f"late answers >10ms: {len(late)}  rate per step {len(late) / len(race):.5f}  "
      f"(compare: --jitter 0.001 / 0.003)  per lap ~{len(late) / max(1, len(race)) * 4100:.1f}")
if late:
    print("  at steps        :", [int(r["step"]) for r in late][:30])
print(f"next already queued: {sum(int(r['next_was_waiting']) for r in race)} steps (only meaningful headless)")
if echo:
    lags = [e - 1 for _, _, e in echo]
    print(f"gear echo         : n={len(echo)}  lag steps min {min(lags)} median {st.median(lags)} max {max(lags)} "
          f"last {lags[-1]}  -> final command lag ~{lags[-1] * 20} ms")
    for lap in sorted({lp for _, lp, _ in echo}):
        lap_lags = [e - 1 for _, lp, e in echo if lp == lap]
        print(f"  lap {lap + 1}: lag steps {lap_lags}")
