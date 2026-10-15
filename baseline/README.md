# Headless baseline – Corkscrew, 1 lap, standing start

Runs one lap with no TORCS menus or graphics and measures the lap time and damage.
The driver code (`my_driver.py`, `torcs_jm_par.py`) is imported as-is.
Expected layout: `working_space\RaceYourCode` (this repo), `working_space\torch\torcs` (organizers' TORCS),
`working_space\torcs-env` (venv; only numpy, the runner itself needs only the standard library).

```
cd C:\Users\Shadow\Downloads\IBM\working_space\RaceYourCode
..\torcs-env\Scripts\python baseline\run_lap.py                    # my_driver + best_params.json
..\torcs-env\Scripts\python baseline\run_lap.py --driver jm        # IBM sample driver
..\torcs-env\Scripts\python baseline\run_lap.py --params "{\"decel\": 18}" --trace --tag test
```

What it does:

1. Starts `torch\torcs\wtorcs.exe -r baseline\corkscrew_1lap.xml -t 1000000` (text mode, no window).
   `corkscrew_1lap.xml` is the organizers' `quickrace.xml` with the track set to corkscrew, 1 lap,
   only `scr_server` (car1-ow1), and the same start grid (initial speed 0).
2. Connects the client from `RaceYourCode/torcs_jm_par.py` on UDP 3001 and drives with `my_driver.drive`
   (or `torcs_jm_par.drive_modular` for `--driver jm`).
3. When TORCS ends the race it reads `lastLapTime` and `damage` from the sensors and `Sim Time` /
   `Leader Laps` from the TORCS console (`baseline\wtorcs_last.log`).
4. Appends a row to `baseline\runs.csv`. `--trace` writes `baseline\trace.csv` (every 5 control steps).

A lap takes about 2 s of real time.

## Why `-t 1000000`

`-t` is how long `scr_server` waits for the client's answer each step, in microseconds. The TORCS default is 10 000 (10 ms).
In headless mode the simulation runs as fast as it can. When Windows delays the Python process by more than 10 ms,
the server keeps using the previous command, and the run is no longer reproducible. With the default timeout,
3 of 6 runs with the same parameters crashed at the Corkscrew (~2 490 m). With 1 s, every run gives the same result.
Pass `--udp-timeout-us 0` to use the TORCS default again, for example to test robustness.

## Baseline (2026-10-15)

| Driver | Result | Lap time | Damage | Off track |
|---|---|---|---|---|
| `my_driver.py` + `best_params.json` | finished | **84.788 s** | 0 | 0 s |
| IBM sample (`--driver jm`) | crashed at ~2.47 km | – | 252 | – |

The lap time is measured from the green light to the finish line, starting 10 m behind the line from a standstill.
The repo README reports 83.63 s for the same parameters. That figure came from a GUI multi-lap race and a different way of
measuring the time in `lap_runner.py`, so use 84.788 s as the baseline for this setup.
