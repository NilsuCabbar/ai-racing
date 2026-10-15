# Experiments log

Corkscrew, 1 lap, standing start, car1-ow1 (`scr_server`). All runs are headless (`baseline/run_lap.py`).

- **Det. lap**: one run with `-t 1000000`. scr_server waits for every command, so the result is reproducible.
- **Robust**: N runs (`--robust N`) with the TORCS default UDP timeout (10 ms). Late commands get skipped, as they can be in a real race.
  A crash is a run that does not finish or that ends with damage > 0.
- **Jitter P**: robust runs where each step, with probability P, the client answers 15 ms late (`--jitter P`).
  On an idle PC the default timeout is rarely missed, so this makes the stress repeatable. Each miss makes every
  later command one step (20 ms) late, because the late answer stays in the UDP queue. The lag adds up over the lap.

| Date | Experiment | What changed | Det. lap (s) | Det. damage | Robust N (jitter) | Crash rate | Robust mean / best (s) | Robust max damage |
|---|---|---|---|---|---|---|---|---|
| 2026-10-15 | E0 IBM sample | `torcs_jm_par.drive_modular`, default settings | DNF (crash ~2.47 km) | 252 | – | – | – | – |
| 2026-10-15 | E1 baseline | `my_driver.py` + `best_params.json` from `main` (README claims 83.63 s from GUI runs) | 84.788 | 0 | 6 (ad hoc) | 3/6 | 84.788 / 84.788 | 134 |
| 2026-10-15 | E1 baseline, realistic | same, `--robust 10` on an idle PC | 84.788 | 0 | 10 (0) | 0/10 | 84.788 / 84.788 | 0 |
| 2026-10-15 | E1 baseline, stress | same, `--robust 10 --jitter 0.001` (~4 late steps per lap) | 84.788 | 0 | 10 (0.001) | 7/10 | 89.888 / 84.788 | 847 |
| 2026-10-15 | E1 baseline, stress | same, `--robust 10 --jitter 0.003` | 84.788 | 0 | 10 (0.003) | 10/10 | – | 1169 |

Notes on E1: the ad hoc crashes (3/6) were the first runs after setup (cold start). Later, 10/10 were clean.
Most crashes happen at the Corkscrew (2.44–2.53 km) or in the last corners (~3.3 km).
| 2026-10-15 | E2 gear fix, hold 0.2 s | `shift_gear()`: road-speed rpm, min hold, downshift hysteresis, corner limit | 84.856 | 0 | 10 (0) / 10 (0.001) | 0/10 / 8/10 | 84.856 / 88.857 (mean, jitter) | 0 / 153 |
| 2026-10-15 | E2 gear fix, hold 0.3 s | same, `shift_hold` 0.3 | 86.418 | 0 | 10 (0) / 10 (0.001) | 0/10 / 8/10 | 86.418 / 90.704 (mean, jitter) | 0 / 537 |
| 2026-10-15 | E1 rerun for E2 | old shifting, same session | 84.788 | 0 | 10 (0) / 10 (0.001) | 0/10 / 7/10 | 84.788 / 84.809 (mean, jitter) | 0 / 177 |

Notes on E2: the clean deterministic lap has only 1 quick 1-2-1 reversal and 1 two-gear jump (3 to 1 under hard braking).
The 3-1-6 jumps seen before appear only once the delayed car is already sliding, so they are a symptom.
The fix does not lower the crash rate, and the other parameters were tuned for the old shifting.
`shift_gear()` stays in, but off (`shift_hold: 0` = old behaviour), and its parameters go to the CMA-ES search.
The real cause under jitter is the accumulated command lag: each late answer adds one 20 ms step for the rest of the lap.
| 2026-10-15 | E3 CMA-ES test A | `cmaes_search.py --gens 3 --popsize 8`, sigma 0.15, 17 params, start = best_params | 84.788 (start, no gain) | 0 | 5 (0), start only | 0/5 | – | 0 |
| 2026-10-15 | E3 CMA-ES test B | same, sigma 0.05, `--stop-on-damage` | 84.788 (start, no gain) | 0 | 5 (0), start only | 0/5 | – | 0 |

Notes on E3: these are short pipeline tests (25 evaluations each), not a real search. With sigma 0.15, 18 of 24 candidates
crashed. With sigma 0.05, 9 of 24 crashed (generation 3: 0 of 8), and generation bests went 86.52, 85.90, 85.43 s.
About 3.4 s per evaluation (84 s for 25). Small damages (1–6) are rejected too, as intended.

