# AI Racing – TORCS Corkscrew driver (IBM AI Racing League)

A Python driver for the TORCS `scr_server` car (600 kg open-wheel car, `car1-ow1`) on the **Corkscrew** track.
Only the Python AI code is changed; the car model is untouched. All laps start from a standing start.

**Best clean lap: 83.63 s** (no damage, never off track). Starting point was a driver that could not finish the lap.

| Step | Lap time |
|---|---|
| IBM sample driver (`torcs_jm_par.py`, default settings) | did not finish (crashed at ~2.5 km) |
| `my_driver.py` first version (look-ahead braking) | 147.15 s |
| + parameter search | 106.09 s |
| + aim at the longest track sensor, steering smoothing, mixed look-ahead | 85.74 s |
| + high-rpm gear shifting (engine peaks near 18 000 rpm) and re-tuned braking/traction | **83.63 s** |

The simulation is deterministic: the same parameters give the same lap time every run.

## How the driver works (`my_driver.py`)

Per tick it reads the TORCS sensors and sends `steer`, `accel`, `brake`, `gear`.

- **Steering:** classic angle/track-position controller, blended with the direction of the *longest* of the 19 track sensors (`aim_w`), then low-pass filtered (`smooth`).
- **Target speed:** the speed from which the car can still stop in the free distance ahead (`decel`, `margin`), floored by `min_speed`. `mix` blends the straight-ahead distance with the longest-sensor distance so the car accelerates earlier out of corners.
- **Throttle / brake:** proportional to (target − speed) with `accel_gain` / `brake_gain`.
- **Traction control:** cuts throttle when rear wheels spin faster than front wheels (`tc_thresh`, `tc_cut`).
- **Gears:** rpm based. The engine makes most power at 16–18 k rpm, so the car upshifts at `up_rpm` (16 500) and downshifts at `down_rpm` (10 000).

All tunable values are in `best_params.json`.

## Requirements

- Windows (tested on Windows 11) with TORCS + the SCR `scr_server` driver
- Python 3.8+ (tested on 3.13). Standard library only, no `pip install` needed for the driver.

## TORCS setup (once)

1. Start TORCS → **Race → Quick Race → Configure Race**.
2. Track: **Corkscrew** (category *road*).
3. Driver: **`scr_server`** (the driver the Python client controls).
4. Laps: set to a high number (e.g. 20). With 1 lap TORCS shuts the server down at the finish and the race has to be restarted by hand; with many laps the runner restarts the race itself after the first lap, which is what the parameter search needs.
5. (Optional, ~35× faster for searches) set `display mode` to `results only` in `config/raceman/quickrace.xml`. Remove it again if you want to watch the car.

## Run

1. In TORCS: **Race → Quick Race → New Race**. The screen stays blue/black and waits for a client (UDP port 3001).
2. In a terminal, in this folder:

```bash
py lap_runner.py --driver mine --params-file best_params.json
```

Expected output:

```
=== SONUC ===
result: finished
lap_time_s: 83.63
off_track_s: 0.0
max_damage: 0.0
```

Each run is appended to `runs.csv` (lap time, time off track, damage, parameters).

Useful options of `lap_runner.py`:

| Option | Meaning |
|---|---|
| `--driver mine` | our driver (`jm` = IBM sample driver) |
| `--params-file FILE` / `--params JSON` | parameter set |
| `--trace` | write `trace.csv` (position, speed, commands every 10 steps) |
| `--max-seconds N` | simulated-time limit (default 300) |
| `--tag TEXT` | note stored in `runs.csv` |

### Re-running the parameter search

```bash
py search.py --n 100 --seed 1 --prefix s_
```

Random search plus local refinement over the parameters listed in `SPACE` in `search.py`.
Score = lap time + 3 × seconds off track + 0.05 × damage (unfinished laps get a large penalty).
The best set is written to `best_params.json` (`--out FILE` to change). Use `--fix "{\"up_rpm\": 16500}"` to hold parameters constant.
Stop with Ctrl+C; results already written to `runs.csv` are kept.

## Files

| File | Purpose |
|---|---|
| `my_driver.py` | the driver |
| `lap_runner.py` | runs one lap with a parameter set and measures it |
| `search.py` | automatic parameter search |
| `best_params.json` | best parameters (83.63 s) |
| `torcs_jm_par.py` | SCR client / IBM sample driver from the competition starter kit (not our work); `lap_runner.py` uses its `Client` |

## IBM Granite and IBM SkillsBuild

_To be filled in by the team: how IBM Granite was used in this project and the SkillsBuild credentials completed._

---

## Kısa Türkçe özet

1. TORCS'ta Quick Race → pist **Corkscrew**, sürücü **scr_server**, tur sayısı **20**.
2. **Race → Quick Race → New Race** (mavi bekleme ekranı).
3. Bu klasörde terminalde: `py lap_runner.py --driver mine --params-file best_params.json`
4. Sonuç `runs.csv`'ye yazılır. En iyi temiz tur: **83,63 sn**.
