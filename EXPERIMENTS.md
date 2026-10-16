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
| 2026-10-15 | E7 new best_params (B) | E5 with `min_speed` 47 and `margin` 11. E5 values kept in `best_params_e5.json` | **82.690** | 0 | – | – | – | – |

Notes on E7: a sensitivity test, `baseline/perturb_test.py`. 20 variants per candidate, every parameter scaled by a
random factor in [0.99, 1.01] (seed 7, the same factors for both), each in the deterministic 3-lap race
(`baseline/corkscrew_3lap.xml`, which equals the real-time GUI per E6). Clean = all 3 laps done, damage 0, off-track 0.
Full output: `results/e7_perturb_A.txt`, `results/e7_perturb_B.txt`.

| Candidate | Nominal lap 1 / laps 2–3 | Clean variants | Damaged / off track | Lap 1 mean / worst / best |
|---|---|---|---|---|
| A: `min_speed` 47 | 82.388 / 79.214 / 79.126, clean | **10/20** | 9 (damage 7–32) / 4 (0.22–0.8 s) | 82.476 / 82.926 / 82.164 |
| B: `min_speed` 47 + `margin` 11 | 82.690 / 79.564 / 79.458, clean | **20/20** | 0 / 0 | 82.868 / 83.382 / 82.466 |

B is clearly more robust, so it becomes `best_params.json`. Its 1-lap race gives 82.690 s with damage 0 and 0 s off
track. That costs 0.534 s against E5 (82.156 s, 0.34 s off track) and is still 2.098 s faster than E1 (84.788 s).
Even A, which looked clean, fails in half of its ±1% neighbourhood, so a single clean run is not enough evidence.
This perturbation check is a good acceptance gate for future searches.

| 2026-10-16 | E8 Tuna's driver (`main`, `tuna/`) | `tuna/my_driver.py` + `tuna/params.json`, measured with `baseline/run_lap.py --code-dir tuna` | **80.332** | 0 | – | – | – | – |

Notes on E8: branch `v3-tuna` = `origin/main` (1e738cb) + the `baseline/` tools and this log from `v2-robust`. No driver code
or parameter was changed. Two tool changes, so the tools can drive a driver in a subfolder: `run_lap.py` also puts the repo
root on `sys.path` (for `torcs_jm_par.py`), and `perturb_test.py` gets `--code-dir`, `--fixed` (keys left unperturbed) and
accepts a flat params file like `tuna/params.json`.

- **1 lap, standing start:** 80.332 s, damage 0, off track 0 s, top speed 258.9 km/h. Tuna's README says 80.31 s. That is the
  same lap measured differently: `tuna/run_lap.py` takes `curLapTime` on the last step before the line and rounds it,
  and runs TORCS without `-t`. Our runner takes TORCS's `lastLapTime`. The E7 driver, re-run in the same session: 82.690 s.
- **3 laps** (`corkscrew_3lap.xml`): 80.332 / 77.082 / 76.850 s, damage 0, off track 0 s (E7: 82.690 / 79.564 / 79.458).
- **±1 % perturbation, 20 variants** (seed 7, as in E7; `results/e8_perturb_tuna_1pct.txt`): **20/20 clean**, no damage,
  no off-track. Lap 1 mean / worst / best 80.335 / 80.516 / 80.088 s (E7 B: 82.868 / 83.382 / 82.466). The lap-1 spread is
  0.43 s against 0.92 s for E7. Not perturbed: `steer_lock` (car constant), `max_gear` (integer: 6.06 would allow gear 7,
  which the kit client turns into neutral), `aim_sign` (a sign). Tuna's own search does not change these either.
- **±3 %, 20 variants** (same seed, `results/e8_perturb_tuna_3pct.txt`): **19/20 clean**. One variant (v11) left the track for 2.3 s in total over
  the 3 laps, without damage. Lap 1 mean / worst / best 80.309 / 80.972 / 79.812 s. This matches Tuna's 19/20 at ±3 %.
  The first 5 variants match an earlier, aborted run of the same test exactly, so the runs are reproducible.
  One variant (v10) is 0.52 s faster than nominal and clean, so there is still some time to find near these parameters (one run only).

Where the 2.36 s come from (1-lap traces, time gained over E7 per 300 m of distance raced):
the Corkscrew (2 400–2 700 m) 0.60 s, the last hairpin (3 000–3 300 m) 0.67 s, the first left-hander pair (300–600 m)
0.39 s, and about 0.1 s in each other section (more full throttle).

| | E7 (`v2-robust`) | E8 (Tuna) |
|---|---|---|
| Corner speed | fixed floor `min_speed` 47 km/h in `v = sqrt(v_floor² + 2·decel·free)` | floor from the sensors: `v = sqrt(mu·g·R)`, `R = min(D / (2 sin a), D² / chord_k)` from the longest beam; `mu` 0.45 g, `chord_k` 40 m |
| Min speed, Corkscrew / last hairpin | 44.4 / 43.8 km/h | **60.7 / 58.8 km/h** |
| Braking | `brake_gain` 0.070, `decel` 23.4, `margin` 11; peaks at 1.0 in both slow corners | `brake_gain` 0.023, `decel` 17.2 (earlier, softer), `margin` 8.5; peak 0.53; trail braking 0.026 (tiny); slide guard on (`speedY` > 5.7 km/h) |
| Throttle | proportional, `accel_gain` | full throttle below `target − 12.3 km/h`. Full / partial throttle 41.8 / 17.6 s (E7: 37.5 / 24.9 s) |
| Steering | `aim_w` 0.67 towards the longest beam; on ties `max()` takes the leftmost beam | `aim_w` 0.81; on ties the beam closest to straight ahead |
| trackPos target | 0 (centre), `center_k` 0.20 | `line_out` 0.088 outside before a corner, `line_in` 0 (off), `center_k` 0.25 |
| Gears | `shift_gear()` with road rpm, `shift_hold` 0.033 s | plain rpm thresholds, max gear 6 |

**Does Tuna drive "outside in, cut to the inside"? No.** The racing-line code exists, but the search left `line_in` at 0
and `line_out` at 0.088. That offset goes through `center_k` and then only into the 19 % of the steering that is not
aimed at the longest beam: 0.088 × 0.25 × 0.19 / 0.785 ≈ 0.005 of full lock. The line comes from aiming at the farthest
visible point, as in E7. In the trace (trackPos relative to the corner, + = outside, 1 = edge) both drivers enter the
fast corners already on the inside half and stay there (Tuna: brake start −0.30…−0.69, minimum speed −0.21…−0.71, then
drifting out). In the two slow corners it is the reverse of outside-in: inside at the brake point, then the car is pushed
wide (Tuna Corkscrew +0.57 at minimum speed; last hairpin −0.35 → +0.29 → +0.76 at the exit; E7 the same, +0.21 / +0.12
→ +0.76). The time comes from corner speed, the tie-break and the throttle band, not from the line. A real outside-in line is still untried and may be the largest gap left
(the built-in robot `inferno` does ~74.65 s, Tuna's README).

| 2026-10-16 | E9 CMA-ES on Tuna's driver | `fast/` (copy of `tuna/`), `fast/cmaes_fast.py`, 40 generations from `tuna/params.json`; `fast/params.json` = `e9_g040_05` | **79.556** | 0 | – | – | – | – |

Notes on E9: `fast/my_driver.py` is an unchanged copy of `tuna/my_driver.py` (only the docstring says so); `tuna/` is untouched.
Only the parameters changed. Search (`fast/cmaes_fast.py`, numpy CMA-ES, as in E4 but on Tuna's driver):

- 22 parameters, bounds in `SPACE`; features that Tuna's search switched off (`abs_slip`, `rise_rate`, `edge_pos`,
  `line_in`) stay off. Population 13, 40 generations, 521 one-lap runs and 76 screens in 50 min (one TORCS at a time).
- Step size: σ = 0.05 of each range (E4's value) crashed 4/4 candidates in the Corkscrew. σ = 0.02 / 0.01 gave 8/10 and
  9/10 clean laps, so the run used σ = 0.015 (it ended at 0.011). Over the run: 377 clean, 119 off track, 25 crashes.
- Score = deterministic 1-lap time; off track = lap + 100 + 10 × seconds; crash = 1000 − distance / 10.
- Robustness screen: per generation, the 2 fastest clean candidates within 0.3 s of the best screened lap ran the 3-lap
  race nominally and with 4 fixed ±1 % perturbations; one unclean race failed the candidate (score 900 + lap / 100).
  37 of 76 screens failed. The fastest clean lap found, 79.404 s (`e9_g036_01`), went 0.66 s off track in the nominal
  3-lap race, and most candidates under 79.7 s failed the screen: the fast region is narrow.
- Full gate (`baseline/perturb_test.py`, ±1 %, 20 variants, seed 7, `--fixed steer_lock,max_gear,aim_sign`):

| Candidate | 1 lap | 3 laps | ±1 % clean | Lap 1 mean / worst / best | Result |
|---|---|---|---|---|---|
| `e9_g040_05` | **79.556** | 79.556 / 76.242 / 76.036 | **20/20** | 79.796 / 80.064 / 79.524 | accepted |
| `e9_g036_07` | 79.692 | 79.692 / 76.384 / 76.220 | 18/20 (2 off track) | 79.854 / 80.464 / 79.604 | rejected |
| `e9_g025_02` | 79.710 | 79.710 / 76.412 / 76.232 | 20/20 | 79.848 / 80.000 / 79.710 | passes, slower |

Accepted: `e9_g040_05`, 79.556 s, damage 0, off track 0 s (re-run alone: same), 0.776 s faster than E8.
Note the ±1 % lap-1 mean is 79.796 s: 0.24 s above the nominal lap, against 0.003 s for E8. The nominal set sits on the
fast side of its neighbourhood.

Largest parameter changes against Tuna: `full_band` −18 % (12.3 → 10.1), `slide_thresh` −16 %, `line_dist` −15 %,
`mix` +15 %, `steer_slow` +14 %, `center_k` +12 %, `brake_gain` −11 %, `mu` +8.5 % (0.451 → 0.490), `brake_steer`
0.026 → 0.017. Where the 0.71 s (trace distance) come from: the start and first left-hander pair (0–600 m) 0.38 s, then
0.04–0.13 s in most sections; the last hairpin (3 000–3 300 m) loses 0.12 s. The minimum speed in the two slow corners is
lower than in E8 (Corkscrew 53.9 vs 60.7 km/h, last hairpin 48.4 vs 58.8 km/h), so the gain comes from the faster
corners and the straights, not from the slow corners. Files: `results/e9_cmaes.json` (top 10 screened sets),
`results/e9_cmaes_log.csv` (every run), `results/e9_cmaes_console.txt`, `results/e9_perturb_*.txt`.
