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
| 2026-10-15 | E4 (a) fastest clean | CMA-ES 40 gens x 12, sigma 0.05, seed 4, validation 5 laps `--jitter 0.001`, pass if <= 1 crash. Candidate `e4_g022_04` (`results/cmaes_e4_fastest.json`) | **82.156** | 0 | 10 (0) / 10 (0.001) | 0/10 / 4/10 | 82.156 / 82.714 (mean, jitter) | 0 / 334 |
| 2026-10-15 | E4 (b) most robust = accepted | same search, best validated candidate `e4_g036_03` (`results/cmaes_e4_robust.json`); 0/5 in the search | **82.552** | 0 | 10 (0) / 10 (0.001) | 0/10 / 5/10 | 82.552 / 83.282 (mean, jitter) | 0 / 244 |
| 2026-10-15 | E4 baseline, same check | `best_params.json` (unchanged), same verification seeds | 84.788 | 0 | 10 (0) / 10 (0.001) | 0/10 / 7/10 | 84.788 / 84.927 (mean, jitter) | 0 / 282 |

Notes on E4: the verification rows use 10 new laps with `--seed 100`. The search itself used seeds 0–4.
- The search ran 481 laps and 57 validations in 33 min. All candidates are in `results/cmaes_e4_log.csv`.
- Both candidates are ~2.2–2.6 s faster than the baseline in the deterministic lap, with 0 damage.
- The robustness gain does not hold up. In the search, (a) failed its validation (2/5) and (b) passed (0/5).
  With fresh seeds, (a) crashed 4/10, (b) 5/10 and the baseline 7/10. These are not significantly different.
  (b)'s 0/5 was luck: with ~57 validations of candidates that crash about half the time, some 0/5 results are expected.
  So 5 validation laps cannot rank robustness. A useful gate needs about 20 laps, or the command lag has to be fixed.
- `best_params.json` is unchanged.
- A first E4 attempt stopped at generation 7. TORCS sometimes shuts down right at the line before the client sees
  `lastLapTime`. `run_lap.py` now falls back to TORCS's own "Sim Time" for a finished 1-lap race.
| 2026-10-15 | E5 new best_params | `best_params.json` = E4 (a) `e4_g022_04`. The old values are in `best_params_baseline.json` | **82.156** | 0 | 10 (0) / 10 (0.001) (E4 check) | 0/10 / 4/10 | 82.156 / 82.714 (mean, jitter) | 0 / 334 |

Notes on E5: 2.632 s faster than the E1 baseline, with 0 damage. Off-track time is 0.34 s (|trackPos| > 1 briefly; E1 had 0 s),
so check whether the rules penalise leaving the track. These parameters turn on the new gear logic (`shift_hold` 0.033 s).
| 2026-10-15 | E6 GUI, real time | E5 `best_params`, TORCS GUI Quick Race, 3 laps, default timeout, `run_lap.py --attach --timing-log` | lap 1 **82.156** (laps 2–3: 79.582 / 79.85) | 6 (lap 3) | – | – | – | – |

Notes on E6 (`results/e6_gui_timing.csv`, `results/e6_gui_trace.csv`):
- **No command lag in the real-time GUI.** Over 11,688 steps there were 0 answers over 10 ms. The median response was 0.18 ms
  (max 0.92 ms), and states arrived every ~20 ms (one 40 ms frame hitch). The gear echo was 1 step for all 141 shifts,
  so the lag was 0 the whole race. That is below the mildest jitter test (P=0.001 ≈ 4 late answers per lap), so the
  lag problem does not appear in these conditions.
- Lap 1 equals the headless deterministic lap exactly (82.156 s). A headless 3-lap race (`-t 1000000`) reproduces the
  GUI run step for step (same damage step, 1.06 s off track, laps 82.156 / 79.582 / 79.862). Headless = GUI here.
- Damage 6 is all in **lap 3**, at distFromStart **2490 m** (second, right-hand part of the Corkscrew). The car is at 80 km/h,
  braking, slid ~27° (angle −0.48 rad), trackPos −0.67, so it is inside the track and not touching a wall. It slides at this
  spot every lap (max |angle| 0.36 / 0.43 / 0.48); lap 3 arrived ~2 km/h faster with less braking.
- Off track: about 0.3 s per lap (1.06 s total), always at **3275–3278 m**, the exit of the last hairpin at ~48 km/h.
  The car runs 0.16 m past the right edge (trackPos −1.026; track 12 m wide), because the throttle opens (0.46) while
  steering is still ~0.8. Lap 1's 0.34 s is all here. Lap 1 has no damage.
- The runner printed `udp_timeout_us: 1000000` in attach mode. That is only its default argument; the GUI used TORCS's
  own default (10 ms). The third lap time is missing from `lap_times` because TORCS shut down first; its value is
  241.59 − 82.156 − 79.582 = 79.85 s (TORCS results screen).

Safety cost, parameters only (headless 3-lap race; lap 1 = the competition lap):

| Variant | Lap 1 (s) | Cost | Laps 2 / 3 | Damage | Off track | Corkscrew max angle |
|---|---|---|---|---|---|---|
| current (E5) | 82.156 | – | 79.582 / 79.862 | 6 | 0.3 / 0.3 / 0.4 s | 0.48 |
| `min_speed` 48.57 → 47 | 82.388 | +0.23 | 79.214 / 79.126 | 0 | 0 | 0.39 |
| `min_speed` 46.6 / 46.8 / 47.2 / 47.4 | 82.30 / 82.57 / 82.36 / 82.29 | +0.13…+0.41 | | 0 | 0 (47.4: 0.1 s lap 1) | ≤ 0.42 |
| `min_speed` 46 / 45 / 44 | 83.01 / 82.51 / 83.25 | | | **20 / 17 / 17** | 0 | 0.58 / 0.55 / 0.54 |
| `margin` 11 (10.5 / 11.5 / 12) | 82.578 (82.49 / 82.96 / 83.17) | +0.34…+1.02 | | 0 | 0 | ≤ 0.40 |
| `decel` 22.5 (22 / 23) | 82.670 (82.97 / 82.42) | +0.26…+0.82 | | 0 | 0 | ≤ 0.39 |
| `min_speed` 47 + `margin` 11 | 82.690 | +0.53 | 79.564 / 79.458 | 0 | 0 | 0.35 |
| `center_k` 0.4 | DNF | | | 60 | | |

The response is chaotic: `min_speed` 46 → 20 damage, 46.6–47.4 → clean. Under `--jitter 0.001` (10 laps, seed 200) none of
these is more robust (current 3/10, `min_speed` 47 8/10, +`margin` 11 7/10). That stress is the lag problem, and the
GUI shows it does not happen in practice.

