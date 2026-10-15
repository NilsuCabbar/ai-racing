# AI Racing – TORCS Corkscrew driver (IBM AI Racing League)

A Python driver for the TORCS `scr_server` car (`car1-ow1`, 600 kg open-wheel car) on **Corkscrew**.
Only the Python AI code is changed. The car model and the organizers' TORCS package are untouched.

**Current result: 1 lap, standing start, 82.690 s, damage 0, 0 s off track.**
It stays clean in 20 of 20 variants with every parameter changed by ±1% (3-lap race).

| Step | Lap 1 | Damage | Off track | Notes |
|---|---|---|---|---|
| Baseline (`best_params_baseline.json`) | 84.788 s | 0 | 0 s | crashes 7/10 laps under timing stress |
| E5: CMA-ES search (`best_params_e5.json`) | 82.156 s | 0 | 0.34 s | 6 damage in lap 3 of a 3-lap race |
| **E7: E5 + `min_speed` 47, `margin` 11 (`best_params.json`)** | **82.690 s** | **0** | **0 s** | **20/20 clean under ±1%** |

Details, every measurement and what did not work: [EXPERIMENTS.md](EXPERIMENTS.md).

All times come from headless TORCS (text mode). A lap there is identical to a lap in the real-time GUI, and the GUI showed
no command lag (E6). An earlier version of this README reported 83.63 s for the baseline parameters. That number
came from `lap_runner.py` in a multi-lap GUI race, which times the lap differently. The same parameters measure
84.788 s here.

## How the driver works (`my_driver.py`)

Each step it reads the TORCS sensors and sends `steer`, `accel`, `brake` and `gear`.

- **Steering:** angle/track-position controller, blended with the direction of the longest track sensor (`aim_w`) and smoothed (`smooth`).
- **Target speed:** the speed from which the car can still stop in the free distance ahead (`decel`, `margin`), at least `min_speed`.
- **Throttle/brake:** proportional to target − speed. Traction control cuts throttle on rear wheelspin (`tc_thresh`, `tc_cut`).
- **Gears (`shift_gear`):** shifts on the rpm computed from road speed, with a minimum hold time, downshift hysteresis and a mid-corner limit.

All tunable values are in `best_params.json`.

## Setup

Folder layout: `working_space\RaceYourCode` (this repo), `working_space\torch\torcs` (organizers' TORCS),
`working_space\torcs-env` (Python venv with numpy, needed only for `cmaes_search.py`). The driver and the runners use only the standard library.

Run the commands below from this folder.

## Run

**Headless lap** (starts TORCS itself, no menus, about 2 s per lap):

```
..\torcs-env\Scripts\python baseline\run_lap.py                     # 1 lap with best_params.json
..\torcs-env\Scripts\python baseline\run_lap.py --race-xml baseline\corkscrew_3lap.xml --max-sim-s 400
..\torcs-env\Scripts\python baseline\run_lap.py --robust 10 --jitter 0.001   # timing stress test
```

**GUI race** (real time, watch the car):

1. Start `torch\torcs\wtorcs.exe` → Race → Quick Race → Configure Race: Corkscrew, only `scr_server 1`, number of laps.
2. Race → Quick Race → New Race.
3. `..\torcs-env\Scripts\python baseline\run_lap.py --attach --timing-log baseline\timing_gui.csv`
4. Optional: `..\torcs-env\Scripts\python baseline\analyze_timing.py baseline\timing_gui.csv` (late answers, command lag)

**Robustness check** (20 variants with every parameter changed by ±1%, 3-lap race):

```
..\torcs-env\Scripts\python baseline\perturb_test.py --n 20
```

**Parameter search** (CMA-ES): `..\torcs-env\Scripts\python cmaes_search.py --gens 40 --out results\my_run.json`

Runner options and details: [baseline/README.md](baseline/README.md).

## Files

| File | Purpose |
|---|---|
| `my_driver.py` | the driver |
| `best_params.json` | current parameters (E7). `best_params_e5.json` and `best_params_baseline.json` hold the earlier ones |
| `baseline/run_lap.py` | headless or GUI lap runner: lap time, damage, off track, robust/jitter/timing modes |
| `baseline/perturb_test.py` | ±1% sensitivity test |
| `baseline/analyze_timing.py` | summary of a `--timing-log` |
| `cmaes_search.py` | CMA-ES parameter search |
| `EXPERIMENTS.md`, `results/` | experiment log and saved results |
| `docs/lag_fix_proposal.md` | proposed fix for command lag after a late answer (not implemented, waiting for organizer approval) |
| `lap_runner.py`, `search.py` | the first runner and random search (GUI, manual restart) |
| `torcs_jm_par.py` | SCR client and IBM sample driver from the starter kit (not our work, unchanged) |

## IBM Granite and IBM SkillsBuild

_To be filled in by the team: how IBM Granite was used in this project and the SkillsBuild credentials completed._

---

## Kısa Türkçe özet

- Sonuç: Corkscrew, 1 tur, duran kalkış, **82,690 sn**, hasar 0, pist dışı 0. Parametreler ±%1 oynatıldığında 20 varyantın 20'si temiz.
- Headless ölçüm: `..\torcs-env\Scripts\python baseline\run_lap.py`
- GUI'de izlemek için: TORCS'ta Quick Race'i Corkscrew ve `scr_server 1` ile ayarlayıp New Race'e bas, sonra komuta `--attach` ekle.
- Eski README'deki 83,63 sn başka bir ölçüm yönteminden geliyordu. Aynı parametreler burada 84,788 sn ölçülüyor.
