# AI Racing – TORCS Corkscrew driver (IBM AI Racing League)

**Best lap: 76.598 s** – E17b, commit `46fb967`, driver in `mapped/`.
Corkscrew, 1 lap, standing start, `car1-ow1` via `scr_server`; damage 0, off track 0 s, the 3-lap race is clean, and
20 of 20 variants with every parameter changed by ±1 % are clean.

Only the Python driver code changes; the car, the track and the organizers' TORCS stay untouched.

| Step | Driver | Lap (s) |
|---|---|---|
| Original team driver (`my_driver.py` + `best_params.json`) | sensors only | 84.788 |
| Tuna's driver (`tuna/`) | sensors only | 80.332 |
| E9: Tuna's driver, parameters tuned with CMA-ES (`fast/`) | sensors only | 79.556 |
| **E17b: track map + racing line + speed profile with elevation (`mapped/`)** | **track map** | **76.598** |

All times are measured the same way: headless TORCS, `baseline/run_lap.py`, TORCS's own `lastLapTime` from the green
light. The simulation is deterministic, so the same code and parameters always give the same time.
Full history: [PROGRESS.md](PROGRESS.md) (one row per accepted or rejected change),
details of every experiment: [EXPERIMENTS.md](EXPERIMENTS.md).

> **Track map rule.** `mapped/` reads the track file (`tracks/road/corkscrew/corkscrew.xml`). The organizers have said
> this is allowed; the team is still confirming it. If it turns out not to be allowed, use **`fast/`** (E9, 79.556 s),
> which uses only the live sensors.

## Layout

```
working_space\
  RaceYourCode\     this repo
  torch\torcs\      the organizers' TORCS (wtorcs.exe), not modified
  torcs-env\        Python venv (numpy; the drivers themselves need only the standard library)
```

| Folder / file | What it is |
|---|---|
| `mapped/` | **main driver**: follows a precomputed racing line and speed table (`my_driver.py`, `params.json`, `table.csv`) and the tools that build the table |
| `fast/` | **fallback**, sensors only: Tuna's driver with CMA-ES-tuned parameters (E9) |
| `tuna/` | Tuna's original driver and tools (80.332 s); not changed |
| `baseline/` | lap runner (`run_lap.py`), robustness test (`perturb_test.py`), race files |
| `my_driver.py`, `best_params.json`, `lap_runner.py`, `search.py` | the original team driver and its tools |
| `torcs_jm_par.py` | SCR client from the IBM starter kit (not our work); every runner uses its `Client` |
| `results/` | logs, traces and test outputs referenced from EXPERIMENTS.md |

## Running

From `RaceYourCode` (Windows, PowerShell or cmd). Each command starts TORCS without a window, drives one lap and
prints the lap time, damage and off-track time (one lap takes about 2 s). Run one TORCS at a time: they all use UDP port 3001.

Main driver, track map (76.598 s):

```bash
..\torcs-env\Scripts\python baseline\run_lap.py --code-dir mapped --params-file mapped\params.json
```

Fallback, sensors only (79.556 s):

```bash
..\torcs-env\Scripts\python baseline\run_lap.py --code-dir fast --params-file fast\params.json
```

Useful options of `baseline/run_lap.py`: `--race-xml baseline\corkscrew_3lap.xml --max-sim-s 400` (3-lap race),
`--trace --trace-every 1 --trace-beams --trace-file FILE` (telemetry), `--params "{\"look_t\": 0.2}"` (override),
`--attach` (drive a race that waits in the TORCS window: Race → Quick Race → New Race, real time).

Acceptance gate for the map driver (1 lap, 3 laps, 20 × ±1 %; about 2 minutes):

```bash
..\torcs-env\Scripts\python mapped\gate.py --tag check
```

Rebuild the map driver's table (gives exactly the committed `mapped/table.csv`):

```bash
..\torcs-env\Scripts\python mapped\build_table.py --tp 0.75 --mu 2.596 --grip 0.90 --crest
```

## How the map driver works

1. **Track geometry** (`mapped/track.py`): the centreline is rebuilt from the 66 segments of `corkscrew.xml`. Turns with
   an end radius are split the way TORCS does it, which gives the exact lap length (3608.45 m). Checked against a real
   lap: the 19 range sensors, cast on the map, match within 2.5 cm (median).
2. **Racing line** (`mapped/line.py`): K1999-style curvature smoothing. Each point moves sideways until its curvature
   is the mean of its neighbours', within |trackPos| ≤ 0.75.
3. **Speed profile**: point-mass model, cornering grip mu·g, braking 3 g scaled by the same grip factor, and acceleration
   measured on a real lap, with a friction circle; mu is calibrated on a real lap (2.596).
4. **Elevation and crests**: the height profile is a spline from the segments' grades and end slopes. Over crests the
   load drops to g − v²·κ, which lowers grip, braking and traction there. This is what makes the Corkscrew safe.
5. **Driving** (`mapped/my_driver.py`): position on the map from distFromStart, trackPos and angle. Steering is a
   curvature feedforward plus a short pure-pursuit correction. Throttle and brake follow the table speed, with a speed
   cap from the front sensors and an edge guard. Traction control and gear shifting come from the sensor driver
   (its ABS is there but switched off).
6. **Acceptance gate** (`mapped/gate.py`): a change counts only if the 1-lap run has 0 damage and 0 s off track, the
   3-lap race is clean, and at least 19 of 20 ±1 % variants are clean.

The sensor-only fallback (`fast/`) brakes for a corner speed estimated from the longest range-sensor beam, uses
full throttle below the target, and aims at the longest beam. Tuna's README in `tuna/` explains it.

## IBM Granite and IBM SkillsBuild

_To be filled in by the team: how IBM Granite was used in this project and the SkillsBuild credentials completed._

---

## Kısa Türkçe özet

- En iyi tur **76,598 sn** (E17b, `mapped/`): pist haritası, yarış çizgisi, yükseklikli hız profili. Hasar 0, pist
  dışı 0, 3 tur temiz, ±%1'de 20/20.
- Pist haritası yasak çıkarsa yedek: `fast/` (E9, sadece sensör), **79,556 sn**.
- Çalıştırma: `..\torcs-env\Scripts\python baseline\run_lap.py --code-dir mapped --params-file mapped\params.json`
  (yedek için `mapped` yerine `fast`).
- İlerleme tablosu: [PROGRESS.md](PROGRESS.md), ayrıntılar: [EXPERIMENTS.md](EXPERIMENTS.md).
