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

| 2026-10-16 | E10 track map, step 1: geometry | `mapped/track.py` rebuilds the Corkscrew centreline from `torch/torcs/tracks/road/corkscrew/corkscrew.xml`; no driving change | – | – | – | – | – | – |

Notes on E10: the organizers' rules on track maps are still being confirmed (user, 2026-10-16); E9 (79.556 s, sensors
only) stays the fallback. `mapped/` starts as a copy of `fast/` (driver and `params.json` unchanged so far). Our own code,
no other team's code or data.

- The main track has 66 segments (37 straight, 29 turns, 20 of them with an `end radius`), width 12 m everywhere, so
  trackPos ±1 = ±6 m. Tightest radius 11.5 m (`s35-2`, the Corkscrew).
- Straights and constant arcs are exact. Turns with an `end radius` were the only problem: taking the length as
  arc × (r0 + r1) / 2 gives 3649.86 m and leaves the track open by 29 m. The rule that fits: split the turn into
  int(arc × (r0 + r1) / 2 / step length) + 1 steps of equal length (step length = the segment's
  `profil steps length`, else the track's 8 m), radii linear from r0 to r1, and scale the length so the steps turn
  exactly `arc`. That gives **3608.45 m**, and the end of the lap closes on the start within 0.01 m and 360.000°.
  TORCS's own lap: distFromStart wraps at 3608.3 → 0.1 (trace, 0.1 m rounding).
- Check against a real lap (`results/e10_trace_e9_beams.csv`, the E9 driver, every step with the 19 beams;
  `baseline/run_lap.py` got `--trace-file`, `--trace-every`, `--trace-beams`). Each trace row is placed on the map at
  distFromStart / trackPos / angle and the beams are cast against the map's edges (`mapped/verify_geometry.py`,
  `results/e10_verify_geometry.txt`, 776 rows):
  - median |error| over all beams that hit an edge: **0.025 m**; the ±45° beams (edge 4–9 m away): median 0.003 m,
    99th percentile 0.025 m, max 0.27 m; the long straight-ahead beams: median 0.04 m, 95th percentile ≤ 0.72 m
    (at 100–200 m range, 0.001 rad of rounded `angle` is already 0.1–0.2 m).
  - every 300 m section has a median under 0.07 m, so no segment is misplaced.
  - shifting distFromStart by ±0.5 / ±1 / ±2 m raises the median error to 0.13 / 0.23 / 0.39 m: the start line is the
    start of `s1`, and the map lines up with distFromStart to well under 0.5 m.
- Beam convention confirmed: angle = track heading − car heading, negative beam angles point left, beams measure to
  the main-track edge (±6 m), not to the borders or curbs.

| 2026-10-16 | E11 track map, step 2: racing line | `mapped/line.py`: K1999-style line for edge limits 0.6 / 0.75 / 0.9 and a point-mass lap estimate; not driven | (model) 74.42 for 0.75 | – | – | – | – | – |

Notes on E11: nothing is driven yet; these are model numbers. Script: `mapped/step2_report.py`, full output
`results/e11_step2_report.txt`, drawings `results/e11_lines.svg`, `e11_lines_corkscrew.svg`, `e11_lines_hairpin.svg`.

- **Line**: the centreline shifted along its normal by l(s), |l| <= limit × 6 m. Each point is moved along its normal
  until its curvature equals the mean of its two neighbours' (even/odd Jacobi steps, coarse to fine: every 32nd point
  down to every point, 1 m spacing). On free points the remaining mismatch is below 1e-4 1/m. The limit is
  a parameter (`racing_line(t, tp_max)`). The car's centre stays on the line, so with limit 0.9 the outer wheels can be
  on the curbs, which is allowed; |trackPos| never exceeds the limit (table below).
- **Speed model** (also step 3's tool; used here only for the lap estimates): v <= sqrt(mu g / |k|); forward pass with a
  full-throttle table measured on the E9 lap (12 m/s² up to 170 km/h, 9 at 190, 4 at 250); backward pass with
  3.0 g braking (E9 brakes at 2.4–2.5 g with only 0.4–0.5 brake); friction circle; standing start 10 m before the line.
- **Calibration**: on the map, E9's own line (trackPos smoothed ±8 m) shows 1.8 g at 50 km/h and 2.0–2.4 g (p90) at
  60–160 km/h, with sideways slip, so the car is near its grip there (downforce). A first estimate of 1.2–1.3 g was wrong:
  its curvature formula was half too small. mu is set so that the model gives E9's real 79.556 s on E9's own line:
  **mu = 2.70**, above the measured 2.0–2.4 g, because the model has no downforce growth with speed and E9's line is
  noisy. So the absolute lap estimates are rough (±10 % mu ≈ ±2.5 s); the comparison of lines inside the same model
  is the useful part.

| limit \|trackPos\| | max \|trackPos\| on line | path length (m) | tightest radius (m) | est. lap (s) | vs E9 (s) | mu -10% / +10% (s) |
|---|---|---|---|---|---|---|
| 0.6 | 0.600 | 3572.7 | 22.4 | 75.39 | -4.16 | 77.91 / 73.24 |
| 0.75 | 0.750 | 3565.2 | 24.4 | 74.42 | -5.13 | 76.99 / 72.24 |
| 0.9 | 0.900 | 3557.8 | 26.5 | 73.60 | -5.95 | 76.22 / 71.34 |
| centreline (0) | 0 | 3608.4 | 11.5 | 80.16 | +0.60 | |
| E9 driven line | 0.928 | 3573.5 | 13.7 | 79.556 (real) | 0 | |

The racing line is shorter (3565 m vs 3573 m for E9 and 3608 m for the centreline) and its tightest radius is about twice
E9's (24 m vs 14 m). Each extra 0.15 of trackPos is worth about 0.9 s in the model. The 0.75 estimate (74.4 s) is close to
the built-in robot `inferno` (about 74.65 s from a standing start, Tuna's README); `inferno` reads the track itself.

Per corner, E9's line vs the 0.75 line (trackPos relative to the corner: + = outside; corner stretches split halfway
between corners, no overlap; model times use the same mu on both lines):

| # | from-to (m) | turn | angle | min centre radius | E9 trackPos entry/apex/exit | line entry/apex/exit | min path radius E9 / line (m) | min speed E9 real / line model (km/h) | stretch (m) | model time E9 line / racing line (s) | gain (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 | L | 25 deg | 86.5 | -0.77/-0.77/-0.50 | -0.51/-0.51/-0.53 | 91 / 345 | 176 / 225 | 125-281 | 2.80 / 2.45 | +0.35 |
| 2 | 407-540 | L | 197 deg | 24.0 | -0.80/-0.13/+0.15 | -0.08/-0.62/+0.28 | 25 / 35 | 83 / 109 | 347-564 | 6.31 / 6.21 | +0.10 |
| 3 | 589-638 | R | 17 deg | 105.7 | -0.71/-0.71/-0.69 | -0.75/-0.75/-0.06 | 187 / 243 | 178 / 182 | 564-685 | 2.19 / 2.29 | -0.09 |
| 4 | 733-806 | R | 94 deg | 44.2 | -0.80/-0.80/-0.06 | +0.02/+0.02/-0.06 | 35 / 53 | 98 / 135 | 685-866 | 4.60 / 4.28 | +0.32 |
| 5 | 995-1074 | R | 71 deg | 48.0 | -0.78/-0.33/-0.27 | +0.00/-0.33/-0.21 | 49 / 81 | 128 / 167 | 935-1134 | 4.40 / 3.86 | +0.54 |
| 6 | 1477-1612 | L | 116 deg | 48.0 | -0.77/-0.50/-0.20 | +0.14/-0.75/+0.36 | 45 / 56 | 116 / 138 | 1417-1672 | 5.65 / 5.68 | -0.03 |
| 7 | 1918-1949 | L | 55 deg | 33.6 | -0.80/-0.80/-0.09 | -0.42/-0.42/-0.35 | 31 / 87 | 110 / 173 | 1858-2009 | 3.84 / 2.94 | +0.90 |
| 8 | 2351-2378 | R | 17 deg | 62.5 | -0.76/-0.76/-0.40 | -0.50/-0.50/-0.75 | 130 / 249 | 208 / 167 | 2291-2405 | 1.82 / 2.19 | -0.37 |
| 9 | 2432-2469 | L | 103 deg | 11.5 | -0.81/+0.83/+0.87 | +0.10/-0.64/-0.55 | 14 / 26 | 54 / 95 | 2405-2476 | 3.00 / 2.51 | +0.50 |
| 10 | 2484-2597 | R | 102 deg | 14.4 | -0.86/-0.86/+0.38 | -0.56/-0.56/+0.50 | 15 / 37 | 70 / 113 | 2476-2597 | 3.84 / 3.05 | +0.79 |
| 11 | 2598-2784 | L | 121 deg | 48.0 | -0.41/-0.79/-0.26 | -0.52/-0.69/-0.14 | 58 / 70 | 137 / 155 | 2597-2844 | 5.25 / 5.06 | +0.20 |
| 12 | 2943-3020 | R | 81 deg | 52.8 | -0.79/-0.29/-0.23 | +0.03/-0.25/-0.09 | 47 / 69 | 119 / 154 | 2883-3080 | 4.46 / 4.15 | +0.31 |
| 13 | 3250-3286 | L | 116 deg | 18.3 | -0.81/-0.42/+0.83 | -0.14/-0.70/-0.14 | 14 / 24 | 48 / 91 | 3190-3346 | 5.32 / 4.90 | +0.42 |

Corner stretches sum to +3.91 s, the straights to the remaining 1.22 s. Where the line differs most:
- **The Corkscrew (2432–2597 m, #9–#10)**: E9 runs wide (+0.83/+0.87 outside in the left part, radius 14–15 m).
  The line straightens the S (radius 26 m and 37 m, min model speed 95 / 113 km/h vs 54 / 70 km/h real for E9): +1.29 s.
- **#7 (1918–1949 m)**: E9 stays on the inside (−0.80) all through (31 m); the line uses the whole corner (87 m): +0.90 s.
- **#5 and #4 (733–1074 m)**: E9 enters on the inside (−0.80/−0.78); the line enters near the middle: +0.86 s.
- **#13, last hairpin (3250–3286 m)**: E9 is pushed out to +0.83 at the exit; the line holds −0.70 at the apex: +0.42 s.
- **#8 (2351 m)** shows −0.37 s: the model starts braking there for the Corkscrew at 3 g, while E9 really carries 208 km/h
  and brakes later and harder. Braking points will need tuning once it drives.
- E9 drives with almost no "outside-in": its entry trackPos is on the inside in all 13 corners (−0.71…−0.86 in 12 of them).

Line tables (distFromStart → trackPos, offset, curvature, radius, model speed): `mapped/line_tp060.csv`,
`mapped/line_tp075.csv`, `mapped/line_tp090.csv`.

| 2026-10-16 | E12 track map, steps 3–4: first map drive | `mapped/my_driver.py` follows `mapped/table.csv` (0.75 line, mu 2.70, 3 g) at `scale` 0.85 | 88.374 | 0 | – | – | – | – |

Notes on E12: first lap with the map driver. Slower than E9 on purpose (85 % of the profile); the aim was a clean lap.
- **Table** (`mapped/build_table.py`): per metre the line offset, line point, centreline point and heading, line
  curvature and the flying-lap model speed (three laps unrolled from rest, the middle one kept, so there is no
  standing-start dip; the car just accelerates at the start).
- **Driver** (`mapped/my_driver.py`, all new; ABS, traction control and rpm gears copied from E9): the car is placed on
  the map from distFromStart / trackPos / angle. Steering is pure pursuit towards the line point
  max(6 m, 0.35 s × v) ahead, wheel angle atan(2 L sin α / d) with car1-ow1's wheelbase 2.95 m and steer lock 21°.
  Target speed = scale × table speed 0.15 s ahead; full throttle below target − 8 km/h, proportional above,
  brake 0.08 per km/h over target. Safety from the sensors: a speed cap from the free distance ahead
  (35 m/s², 4 m margin, floor 60 km/h) and no throttle at |trackPos| > 0.97 while moving outwards.
- **Result** (`baseline/run_lap.py`): 1 lap **88.374 s**, damage 0, off track 0 s; max |trackPos| 0.82 (at 2543 m,
  Corkscrew). 3 laps 88.374 / 85.198 / 85.192, clean. ±1 %, 20 variants: **20/20 clean**, lap 1 mean / worst / best
  88.352 / 88.998 / 87.816 (`results/e12_perturb_map085.txt`).
- **Line following**: median |error| 0.21 m, 95th percentile 0.72 m, max 1.08 m (1074 m, exit of #5).
  Speed − target: median −2.4 km/h, 5th percentile −25.6 km/h (start and corner exits).
- **Model vs real lap**: the model following exactly 0.85 × the table: 86.26 s; real 88.37 s, so 2.1 s are lost to
  following the target late (proportional throttle band, look-ahead). The model at full table speed: 74.39 s.
  Scaling the whole profile also caps the straights at 85 % (top speed 230.5 km/h vs 262 for E9; full throttle only
  5.0 s of the lap). For the next steps the scale should act on grip and braking (mu, brake_g) only, so that the
  straights stay at full throttle.

Per corner (`mapped/analyze_run.py`, `results/e12_analysis.txt`). Model = point mass on the same line with mu and
braking × 0.85² (what 85 % of the corner speed means); E9 = the E9 lap through the same stretch:

| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | time real / model (s) | real - model | ref (E9) time / real - ref |
|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 L | 125-281 | 222 / 243 | 2.69 | 2.7 | 2.57 / 2.47 | +0.10 | 2.84 / -0.27 |
| 2 | 407-540 L | 347-564 | 91 / 93 | 3.15 | 1.8 | 7.50 / 7.28 | +0.23 | 6.24 / +1.26 |
| 3 | 589-638 R | 564-685 | 153 / 155 | 1.11 | 1.4 | 2.75 / 2.68 | +0.07 | 2.24 / +0.51 |
| 4 | 733-806 R | 685-866 | 113 / 115 | 2.42 | 2.6 | 5.14 / 4.99 | +0.15 | 4.61 / +0.53 |
| 5 | 995-1074 R | 935-1134 | 140 / 142 | 2.96 | 2.9 | 4.66 / 4.53 | +0.13 | 4.30 / +0.36 |
| 6 | 1477-1612 L | 1417-1672 | 116 / 118 | 1.86 | 2.1 | 6.82 / 6.59 | +0.24 | 5.60 / +1.23 |
| 7 | 1918-1949 L | 1858-2009 | 144 / 147 | 3.61 | 2.1 | 3.60 / 3.44 | +0.16 | 3.58 / +0.02 |
| 8 | 2351-2378 R | 2291-2405 | 138 / 142 | 1.94 | 1.8 | 2.67 / 2.81 | -0.14 | 1.85 / +0.82 |
| 9 | 2432-2469 L | 2405-2476 | 79 / 81 | 3.86 | 1.3 | 3.00 / 2.94 | +0.07 | 3.04 / -0.03 |
| 10 | 2484-2597 R | 2476-2597 | 92 / 96 | 2.94 | 12.8 | 3.63 / 3.45 | +0.18 | 4.03 / -0.40 |
| 11 | 2598-2784 L | 2597-2844 | 130 / 132 | 2.31 | 2.5 | 6.06 / 5.90 | +0.16 | 5.38 / +0.67 |
| 12 | 2943-3020 R | 2883-3080 | 129 / 131 | 2.55 | 2.2 | 4.99 / 4.87 | +0.12 | 4.38 / +0.61 |
| 13 | 3250-3286 L | 3190-3346 | 76 / 78 | 2.75 | 1.9 | 5.89 / 5.68 | +0.21 | 5.59 / +0.30 |

Real is 0.07–0.24 s slower than the model in every corner except #8 (−0.14 s, where the model brakes early for the
Corkscrew). Against E9 the map lap is already faster in #1, #9 and #10 (the Corkscrew: −0.43 s), although it runs 15 %
below the profile; it loses mostly where the 0.85 cap holds it back on the following straight (#2, #6, #8).

**mu recalibration.** Measured on the line's curvature at the real speed, the car holds 1.81–1.90 g in all slow and
medium corners (#2, #4–#7, #9, #11–#13, 76–144 km/h) with only 0–3 km/h of sideways slip. The model asked for
0.85² × 2.70 = 1.95 g. So nothing was at the limit, and this lap cannot raise or lower the global mu; it shows
mu ≥ 1.9 everywhere and the model's corner speeds are followed within 3–4 %. One exception: **#10 (2484–2597 m, the
right-hand part of the Corkscrew)** slides 8.7–12.8 km/h at 1.79 g, so the grip there is lower (the car goes light over
the drop). mu stays 2.70 for now; the limit will come from raising the grip scale step by step. #10 will likely need a
local grip factor.

| 2026-10-16 | E13 map: grip scale instead of speed scale | table built with mu and braking × 0.85 (`build_table.py --grip 0.85`), driver `scale` 1.0: straights at full throttle | **82.598** | 0 | – | – | – | – |

Notes on E13: same driver and line as E12, only the meaning of the scale changes. `mapped/build_table.py --grip g`
multiplies mu (2.70) and the braking (3.0 g) by g; acceleration and top speed are not scaled. Corner speeds are
√0.85 = 92 % of the full model (E12: 85 %), straights are not capped. Model lap for this table: 78.90 s.
`mapped/gate.py` runs the acceptance gate (1 lap with a full trace, then `perturb_test.py`: 3-lap race + 20 × ±1 %;
not perturbed: `max_gear`, `ctrl`).

- 1 lap **82.598 s**, damage 0, off track 0 s (E12: 88.374 s); 3 laps clean; ±1 %: **20/20** clean, lap 1 mean / worst /
  best 82.570 / 83.026 / 82.250 (`results/e13_g085_gate.txt`). Full throttle 26.2 s of the lap (E12: 5.0 s).
- Max |trackPos| 0.922 at 3304 m (exit of the last hairpin), line error median 0.28 m, 95th 1.46 m, max 2.29 m (3293 m).
  Speed − target: median −5.8 km/h; the car follows the profile late.
- #10 (right-hand part of the Corkscrew) slides up to 25.5 km/h sideways; all other corners 2–8 km/h.
- Real vs model: every corner is 0.08–0.33 s slower than the model (sum 2.3 s); the rest of the 3.7 s gap is the start
  and the exits. Still 3.04 s slower than E9, mainly #2, #6 and #8 (+0.75…+0.77 s each): the model brakes early at
  0.85 × 3 g, while E9 brakes later.

| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | time real / model (s) | real - model | ref (E9) time / real - ref |
|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 L | 125-281 | 222 / 285 | 2.69 | 2.7 | 2.57 / 2.46 | +0.11 | 2.84 / -0.27 |
| 2 | 407-540 L | 347-564 | 99 / 101 | 3.48 | 5.3 | 7.02 / 6.72 | +0.30 | 6.24 / +0.77 |
| 3 | 589-638 R | 564-685 | 172 / 176 | 1.49 | 2.4 | 2.55 / 2.44 | +0.10 | 2.24 / +0.31 |
| 4 | 733-806 R | 685-866 | 123 / 125 | 3.09 | 5.7 | 4.76 / 4.62 | +0.14 | 4.61 / +0.16 |
| 5 | 995-1074 R | 935-1134 | 151 / 154 | 3.45 | 4.9 | 4.40 / 4.18 | +0.22 | 4.30 / +0.10 |
| 6 | 1477-1612 L | 1417-1672 | 125 / 128 | 2.18 | 3.9 | 6.36 / 6.11 | +0.24 | 5.60 / +0.76 |
| 7 | 1918-1949 L | 1858-2009 | 152 / 159 | 4.19 | 3.0 | 3.43 / 3.18 | +0.25 | 3.58 / -0.15 |
| 8 | 2351-2378 R | 2291-2405 | 147 / 152 | 1.89 | 2.0 | 2.60 / 2.50 | +0.09 | 1.85 / +0.75 |
| 9 | 2432-2469 L | 2405-2476 | 86 / 87 | 4.50 | 2.8 | 2.79 / 2.71 | +0.08 | 3.04 / -0.25 |
| 10 | 2484-2597 R | 2476-2597 | 97 / 104 | 3.09 | 25.5 | 3.37 / 3.24 | +0.13 | 4.03 / -0.66 |
| 11 | 2598-2784 L | 2597-2844 | 140 / 143 | 2.51 | 3.9 | 5.59 / 5.46 | +0.13 | 5.38 / +0.21 |
| 12 | 2943-3020 R | 2883-3080 | 140 / 142 | 2.99 | 3.4 | 4.72 / 4.50 | +0.22 | 4.38 / +0.34 |
| 13 | 3250-3286 L | 3190-3346 | 83 / 84 | 3.12 | 8.0 | 5.60 / 5.27 | +0.33 | 5.59 / +0.01 |

| 2026-10-16 | E14 map: curvature feedforward steering | `ctrl` 1: wheel = atan(L · k(s + 0.1 s · v)) + pure-pursuit correction on the deviation only; look-ahead 0.15 s | **82.024** | 0 | – | – | – | – |

Notes on E14: same table as E13 (0.75 line, grip 0.85). New steering mode in `mapped/my_driver.py` (`ctrl` 1; `ctrl` 0
keeps pure pursuit): feedforward wheel angle atan(wheelbase × line curvature `ff_lead` s ahead) × `ff_gain`, plus
pure pursuit towards the line point `look_t` s ahead with the line's own bend removed from the angle
(α − asin(k·d/2)), so the curvature is not counted twice. Screening, single laps (all clean):

| Steering | look_t 0.35 | 0.25 | 0.2 | 0.15 |
|---|---|---|---|---|
| pure pursuit (`ctrl` 0) | 82.598 (E13) | – | 82.220 | 82.172 |
| feedforward + correction (`ctrl` 1, ff_lead 0.1) | 82.502 | 82.324 | 82.082 | **82.024** |
| `ctrl` 1, other ff_lead | – | 82.124 (0.05) | 82.194 (0.0) | – |
| `ctrl` 1, look_t 0.5 | 83.752 | | | |

So the shorter look-ahead brings ~0.4 s and the feedforward another ~0.15 s.

- Gate (`results/e14_ff_gate.txt`): 1 lap **82.024 s**, damage 0, off track 0 s; 3 laps clean; ±1 %: **20/20**.
- Line following: median |error| **0.09 m** (E13 0.28), 95th 0.60 m (1.46), max 1.72 m at 3288 m (2.29);
  max |trackPos| **0.794** (0.922). The steering lag is mostly gone.
- The lap time hardly moved, because the remaining gap to the model (3.1 s) is speed following: speed − target median
  −5.4 km/h. The table accelerates exactly as fast as the car can (measured full-throttle table), so once the car falls
  behind it never catches up, and the 8 km/h proportional band opens the throttle late. Next: E15 on speed following.

| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | time real / model (s) | real - model | ref (E9) time / real - ref |
|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 L | 125-281 | 222 / 285 | 2.86 | 2.6 | 2.54 / 2.46 | +0.08 | 2.84 / -0.30 |
| 2 | 407-540 L | 347-564 | 98 / 101 | 3.57 | 4.9 | 6.94 / 6.72 | +0.22 | 6.24 / +0.70 |
| 3 | 589-638 R | 564-685 | 174 / 176 | 1.48 | 2.3 | 2.52 / 2.44 | +0.08 | 2.24 / +0.29 |
| 4 | 733-806 R | 685-866 | 123 / 125 | 2.86 | 6.6 | 4.72 / 4.62 | +0.10 | 4.61 / +0.11 |
| 5 | 995-1074 R | 935-1134 | 151 / 154 | 3.37 | 4.6 | 4.37 / 4.18 | +0.19 | 4.30 / +0.07 |
| 6 | 1477-1612 L | 1417-1672 | 125 / 128 | 2.19 | 3.9 | 6.29 / 6.11 | +0.18 | 5.60 / +0.70 |
| 7 | 1918-1949 L | 1858-2009 | 156 / 159 | 4.35 | 3.1 | 3.38 / 3.18 | +0.20 | 3.58 / -0.20 |
| 8 | 2351-2378 R | 2291-2405 | 147 / 152 | 1.88 | 2.8 | 2.60 / 2.50 | +0.09 | 1.85 / +0.75 |
| 9 | 2432-2469 L | 2405-2476 | 86 / 87 | 4.66 | 3.0 | 2.78 / 2.71 | +0.07 | 3.04 / -0.25 |
| 10 | 2484-2597 R | 2476-2597 | 98 / 104 | 3.67 | 21.3 | 3.37 / 3.24 | +0.12 | 4.03 / -0.67 |
| 11 | 2598-2784 L | 2597-2844 | 140 / 143 | 2.63 | 4.0 | 5.55 / 5.46 | +0.09 | 5.38 / +0.17 |
| 12 | 2943-3020 R | 2883-3080 | 140 / 142 | 3.07 | 3.6 | 4.66 / 4.50 | +0.16 | 4.38 / +0.28 |
| 13 | 3250-3286 L | 3190-3346 | 82 / 84 | 3.12 | 11.5 | 5.60 / 5.27 | +0.33 | 5.59 / +0.01 |

| 2026-10-16 | E15 map: speed following | `full_band` 8 → 1 km/h, `lead_t` 0.15 → 0 s (parameters only) | **80.674** | 0 | – | – | – | – |

Notes on E15: same table (0.75 line, grip 0.85) and E14 steering; only how the target speed is followed.
Single-lap screening (all from E14's 82.024 s):

| Change | Lap (s) | | Change | Lap (s) |
|---|---|---|---|---|
| `full_band` 3 | 81.546 | | `full_band` 1, `lead_t` 0.05 | 81.082 |
| `full_band` 1 | 81.322 | | `full_band` 1, `lead_t` 0 | **80.674** |
| `full_band` 0.5 | 81.116 | | `full_band` 1, `brake_gain` 0.04 | 80.944 |
| `lead_t` 0.3 / 0.5 | 82.584 / 83.678 | | `full_band` 1, `brake_gain` 0.2 | 81.892 |
| `full_band` 2, `lead_t` 0.3 (± `brake_gain` 0.15) | 82.160 | | `full_band` 1, `lead_t` 0.05, `brake_gain` 0.2 | 83.532, damage 12 |

Reading the target earlier only makes the car brake earlier (the table already contains the braking), and a narrow
band opens the throttle at once. A lower `brake_gain` is also faster, but only because the car then enters corners
above the target, which is the grip ladder's job; `brake_gain` stays 0.08 so the target is followed honestly.

- Gate (`results/e15_speed_gate.txt`): 1 lap **80.674 s**, damage 0, off track 0 s; 3 laps clean; ±1 %: **20/20**.
- Speed − target: median **−1.0 km/h** (E14 −5.4), 95th +5.8. Full throttle 29.8 s. Line error median 0.09 m, max 1.78 m;
  max |trackPos| 0.787.
- Real vs model per corner now +0.01…+0.13 s except #13 (+0.29); the model lap for this table is 78.89 s.
  Against E9: faster in #1, #5, #7, #9, #10, #13; still slower in #2, #6 and #8 (+0.54…+0.61 s), where the
  table's 0.85 × 3 g braking is earlier than E9's.

| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | time real / model (s) | real - model | ref (E9) time / real - ref |
|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 L | 125-281 | 222 / 285 | 2.94 | 2.7 | 2.52 / 2.46 | +0.06 | 2.84 / -0.32 |
| 2 | 407-540 L | 347-564 | 100 / 101 | 3.63 | 13.8 | 6.85 / 6.72 | +0.13 | 6.24 / +0.61 |
| 3 | 589-638 R | 564-685 | 172 / 176 | 1.40 | 2.5 | 2.52 / 2.44 | +0.07 | 2.24 / +0.28 |
| 4 | 733-806 R | 685-866 | 124 / 125 | 3.02 | 7.8 | 4.65 / 4.62 | +0.03 | 4.61 / +0.04 |
| 5 | 995-1074 R | 935-1134 | 154 / 154 | 3.54 | 5.0 | 4.24 / 4.18 | +0.06 | 4.30 / -0.06 |
| 6 | 1477-1612 L | 1417-1672 | 127 / 128 | 2.26 | 4.3 | 6.13 / 6.11 | +0.02 | 5.60 / +0.54 |
| 7 | 1918-1949 L | 1858-2009 | 158 / 159 | 4.47 | 3.3 | 3.31 / 3.18 | +0.13 | 3.58 / -0.27 |
| 8 | 2351-2378 R | 2291-2405 | 153 / 152 | 2.05 | 2.2 | 2.44 / 2.50 | -0.07 | 1.85 / +0.59 |
| 9 | 2432-2469 L | 2405-2476 | 87 / 87 | 4.60 | 2.8 | 2.76 / 2.71 | +0.05 | 3.04 / -0.28 |
| 10 | 2484-2597 R | 2476-2597 | 100 / 104 | 3.70 | 12.0 | 3.35 / 3.24 | +0.11 | 4.03 / -0.69 |
| 11 | 2598-2784 L | 2597-2844 | 142 / 143 | 2.62 | 4.2 | 5.47 / 5.46 | +0.01 | 5.38 / +0.09 |
| 12 | 2943-3020 R | 2883-3080 | 142 / 142 | 3.19 | 3.9 | 4.55 / 4.50 | +0.06 | 4.38 / +0.17 |
| 13 | 3250-3286 L | 3190-3346 | 84 / 84 | 3.16 | 11.3 | 5.57 / 5.27 | +0.29 | 5.59 / -0.02 |

| 2026-10-16 | E16 map: grip ladder | table grip 0.90 → 0.95 (E15 driver); stop at the first failed step | **80.060** (grip 0.90) | 0 | – | – | – | – |

Notes on E16: `build_table.py --grip g` for g = 0.90, 0.95, … with the E15 driver, each step through `mapped/gate.py`
(1 lap, 3 laps, 20 × ±1 %); the ladder stops at the first failure and keeps the last step that passed.

| Grip | Model lap | 1 lap | 3 laps | ±1 % | Result |
|---|---|---|---|---|---|
| 0.85 (E15) | 78.89 | 80.674 | 80.674 / … clean | 20/20 | passed |
| **0.90** | 77.26 | **80.060** | 80.060 / 76.594 / 76.442 clean | **20/20** (lap 1 mean / worst / best 80.212 / 80.492 / 79.996) | passed: **kept** |
| 0.95 | 75.75 | timeout: damage 1 at 2496 m, then off track at 3295 m (spun at the exit of #13, stuck) | – | – | failed |
| 0.95, #10 grip × 0.947 (= 0.90 there) | 75.81 | 95.088: the same damage 1 at 2496 m, 8.5 s off track from 3295 m | – | – | failed |

Why 0.95 fails (`results/e16_trace_g095_l10.csv` against `results/e16_trace_g090.csv`):
- **#9 → #10, the crest of the Corkscrew (2465–2500 m)**: the car changes from left to right lock while it goes light
  (z 0.29 → 0.44 m, then lands at 0.25–0.27 m). The steering sits at full lock (±1 = 21°), traction control keeps cutting
  the throttle (1.0 ↔ 0.34), sideways slip reaches 17–20 km/h, and the car is 6–15 km/h **below** the target. At 0.95
  it is pushed out to trackPos −0.91 (0.90: −0.71) and takes damage 1 when it lands. Because the car is below the
  target there, the local grip margin for #10 cannot help, and it did not (same speed, same damage).
- **#13, last hairpin exit (3295 m)**: the rear steps out under throttle with the steering still loaded and the car spins
  off the right edge. Also traction, not cornering grip.
So the limit at 0.95 is traction and the car's behaviour over the crest, not the corner speeds in the table.

Grip 0.90 lap (`results/e16_g090_analysis.txt`): max |trackPos| 0.797, line error median 0.10 m but max 3.32 m at
508 m (#2 exit, 12 km/h slip). Real is 2.8 s slower than its model (77.25 s): #2 +0.35, #10 +0.36 and #13 +0.38 s
are the traction-limited exits. Against E9 it is still +0.50 s: faster in the Corkscrew (#9, #10: −0.82 s), #1 (−0.32),
#7 (−0.33), slower in #2 (+0.64), #8 (+0.47), #6 (+0.41) and #3 (+0.36). #2/#6/#8 are braking zones: the table's
0.9 × 3 g braking point is earlier than E9's.

| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | time real / model (s) | real - model | ref (E9) time / real - ref |
|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 L | 125-281 | 222 / 285 | 2.94 | 2.7 | 2.52 / 2.46 | +0.07 | 2.84 / -0.32 |
| 2 | 407-540 L | 347-564 | 103 / 104 | 3.66 | 12.1 | 6.88 / 6.53 | +0.35 | 6.24 / +0.64 |
| 3 | 589-638 R | 564-685 | 161 / 178 | 1.26 | 2.2 | 2.60 / 2.38 | +0.21 | 2.24 / +0.36 |
| 4 | 733-806 R | 685-866 | 128 / 128 | 3.24 | 8.5 | 4.54 / 4.50 | +0.04 | 4.61 / -0.07 |
| 5 | 995-1074 R | 935-1134 | 158 / 159 | 3.87 | 5.7 | 4.15 / 4.06 | +0.09 | 4.30 / -0.15 |
| 6 | 1477-1612 L | 1417-1672 | 131 / 131 | 2.39 | 5.2 | 6.01 / 5.96 | +0.05 | 5.60 / +0.41 |
| 7 | 1918-1949 L | 1858-2009 | 160 / 164 | 4.73 | 3.8 | 3.25 / 3.09 | +0.16 | 3.58 / -0.33 |
| 8 | 2351-2378 R | 2291-2405 | 158 / 156 | 2.32 | 2.4 | 2.32 / 2.39 | -0.07 | 1.85 / +0.47 |
| 9 | 2432-2469 L | 2405-2476 | 90 / 90 | 4.54 | 5.3 | 2.72 / 2.64 | +0.08 | 3.04 / -0.32 |
| 10 | 2484-2597 R | 2476-2597 | 98 / 107 | 2.80 | 16.9 | 3.54 / 3.17 | +0.36 | 4.03 / -0.50 |
| 11 | 2598-2784 L | 2597-2844 | 146 / 147 | 2.82 | 5.1 | 5.33 / 5.31 | +0.02 | 5.38 / -0.05 |
| 12 | 2943-3020 R | 2883-3080 | 146 / 146 | 3.30 | 4.2 | 4.44 / 4.37 | +0.07 | 4.38 / +0.06 |
| 13 | 3250-3286 L | 3190-3346 | 86 / 87 | 3.14 | 12.8 | 5.52 / 5.14 | +0.38 | 5.59 / -0.07 |

| 2026-10-16 | E17a map: braking-pass fix | `line.py` backward pass evaluates the braking grip at the known speed; mu recalibrated to 2.393; grip 0.90 | DNF-like (damage 64) | 64 | – | – | – | – |
| 2026-10-16 | E17b map: crest model | elevation spline from the XML, grip/braking/traction × (1 − v²·crest/g); mu recalibrated to 2.596; grip 0.90 | **76.598** | 0 | – | – | – | – |

Notes on E17 (`mapped/track.py`, `mapped/line.py`, `mapped/build_table.py --crest`):

- **Elevation**: every segment has `grade` and `profil end tangent`. Height = cubic Hermite per segment from z0 to
  z0 + grade × length with end slopes = previous and own end tangent; closure error 0.77 m spread over the lap; total
  climb 54.9 m, range −2…46 m. Check against the car's ride height `z` on the E9 lap (`results/e10_trace_e9_beams.csv`):
  z_car = 0.295 − 0.9e-5·v² − 1.9e-3·v²·z'' explains **R² = 0.917** (spline) vs 0.88–0.90 (linear profile), so the
  spline profile is the one TORCS uses. Crests (−z'' as 1/m): 2376 m (0.0048, the braking zone before the Corkscrew),
  2434 m (0.0040, #9), **2471 m (0.0037, #9 → #10)**, 2230 m, 219 m. At 95 km/h on 2471 m the load drops ~25 %;
  at 160 km/h on 2376 m it drops to almost zero.
- **Model**: normal load factor = 1 − v²·crest/g (crests only, dips not credited). Corner limit
  v² ≤ mu·g / (|k| + mu·crest); braking and traction are multiplied by the load factor.
- **A bug found on the way**: the backward (braking) pass evaluated the friction circle at the not yet lowered speed of
  the point, i.e. close to the corner limit, which left almost no grip for braking. Every braking point in
  E11–E16 was therefore too early (the "table brakes earlier than E9" in #2/#6/#8). Fixed: the braking grip is now taken
  at the known speed of the next point. With the fix, mu calibrated on E9's own line as in E11 is **2.393** without
  crests (closer to the 2.0–2.4 g measured on E9) and **2.596** with the crest model.
- **E17a**, braking fix only (mu 2.393, grip 0.90): first damage at **2491 m**, off track from 2478 m (Corkscrew crest),
  damage 64; at grip 0.95 damage 111 and stuck. The later braking is not survivable over the crests without the crest
  model. Rejected.
- **E17b**, braking fix + crest model (mu 2.596, grip 0.90, model lap 74.36 s): gate (`results/e17b_g090_gate.txt`):
  1 lap **76.598 s**, damage 0, off track 0 s; 3 laps 76.598 / 73.086 / 73.060 clean; ±1 %: **20/20**, lap 1 mean / worst /
  best 76.704 / 77.190 / 76.532. **2.958 s faster than E9.** At grip 0.95 the Corkscrew is now fine; the lap fails
  only at the exit of #13 (off track at 3289 m, spin): that is E20's job.
- **#9–#10 model vs real** (2405–2597 m): real 2.39 / 3.38 s vs model 2.34 / 3.26 s (+0.04 / +0.12 s). Against E16 (grip
  0.90, no crest model): 5.76 s vs 6.22 s through the stretch, full-lock steps 10 vs 58, TC cuts 91 vs 120 steps,
  max slip 17.7 vs 18.3 km/h.
- Max |trackPos| 0.845 at 3298 m and the largest line error (3.25 m at 3286 m) are both at #13's exit (22.8 km/h slip,
  +0.45 s against the model). #3 is +0.24 s (exit of #2). Against E9 the lap is faster everywhere except #3 (+0.27) and
  #8 (+0.45).

| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | time real / model (s) | real - model | ref (E9) time / real - ref |
|---|---|---|---|---|---|---|---|---|
| 1 | 185-221 L | 125-281 | 191 / 192 | 2.69 | 2.3 | 2.70 / 2.68 | +0.02 | 2.84 / -0.14 |
| 2 | 407-540 L | 347-564 | 101 / 102 | 3.77 | 14.1 | 5.98 / 5.89 | +0.09 | 6.24 / -0.27 |
| 3 | 589-638 R | 564-685 | 172 / 177 | 1.40 | 2.5 | 2.51 / 2.26 | +0.24 | 2.24 / +0.27 |
| 4 | 733-806 R | 685-866 | 126 / 126 | 3.60 | 6.9 | 4.23 / 4.16 | +0.07 | 4.61 / -0.38 |
| 5 | 995-1074 R | 935-1134 | 154 / 155 | 3.66 | 5.1 | 3.91 / 3.85 | +0.07 | 4.30 / -0.39 |
| 6 | 1477-1612 L | 1417-1672 | 128 / 129 | 3.14 | 7.0 | 5.47 / 5.43 | +0.04 | 5.60 / -0.12 |
| 7 | 1918-1949 L | 1858-2009 | 157 / 159 | 4.78 | 6.2 | 3.08 / 2.95 | +0.12 | 3.58 / -0.50 |
| 8 | 2351-2378 R | 2291-2405 | 137 / 139 | 2.43 | 1.9 | 2.30 / 2.29 | +0.01 | 1.85 / +0.45 |
| 9 | 2432-2469 L | 2405-2476 | 88 / 88 | 4.28 | 12.2 | 2.39 / 2.34 | +0.04 | 3.04 / -0.65 |
| 10 | 2484-2597 R | 2476-2597 | 102 / 105 | 3.83 | 17.5 | 3.38 / 3.26 | +0.12 | 4.03 / -0.65 |
| 11 | 2598-2784 L | 2597-2844 | 140 / 140 | 4.78 | 7.7 | 5.23 / 5.22 | +0.02 | 5.38 / -0.15 |
| 12 | 2943-3020 R | 2883-3080 | 143 / 143 | 3.37 | 5.5 | 4.16 / 4.06 | +0.10 | 4.38 / -0.22 |
| 13 | 3250-3286 L | 3190-3346 | 84 / 85 | 3.42 | 22.8 | 4.97 / 4.53 | +0.45 | 5.59 / -0.62 |

| 2026-10-16 | E18 map: steering lock and local narrow line | check of the wheel angle the line needs; line limit 0.6 only on 2405–2597 m (`build_table.py --narrow`) | 76.868 | 0 | – | – | – | – |

Notes on E18: (1) the kinematic wheel angle the 0.75 line needs, atan(2.95 m × k), is at most **6.9°** (3269 m, #13)
and 6.4° in #9–#10, against a 21° lock. The line is drivable at any speed as far as steering geometry goes; full
lock only appears when the front slides and the controller asks for more. In E17b that is 10 steps in #9–#10 and 45 steps at
3266–3290 m (#13, slip up to 18 km/h). (2) The line was rebuilt with |trackPos| ≤ 0.6 on 2405–2597 m (blended over 30 m,
`line.local_limit`), same grip 0.90 and crest model: model lap 74.50 s (+0.14), real 1 lap **76.868 s** (+0.27 s
against E17b), clean. Through 2405–2597 m: 6.14 s vs 5.76 s, full lock 31 vs 10 steps, max slip 19.1 vs 17.7 km/h.
A tighter line there makes the crest worse. Rejected; the 0.75 line stays. The narrowing option stays in the code.

| 2026-10-16 | E19 map: traction control threshold | `tc_thresh` 13.8 → 16 (screened 8–25, off, `tc_cut` 0.3–0.9) on E17b | 76.574 | 0 | – | – | – | – |

Notes on E19 (E17b table, grip 0.90; single laps):

| `tc_thresh` (`tc_cut` 0.657) | 8 | 10 | 13.8 (E17b) | 16 | 18 | 20 | 25 | off (1000) |
|---|---|---|---|---|---|---|---|---|
| lap (s) | 76.820 | 76.838 | 76.598 | 76.574 | 76.572 | 76.688 | 76.966 | timeout, damage 110 |

`tc_cut` with `tc_thresh` 18: 0.3 → timeout/damage 60, 0.5 → timeout (off track), 0.8 → 76.676, 0.9 (13.8) → 76.888;
16 / 0.8 → 76.674. The traction control is needed (off = crash) and the current threshold is already within 0.03 s
of the best. Gate for `tc_thresh` 16 (`results/e19_tc16_gate.txt`): 76.574 s, 3 laps clean, ±1 % **19/20** (lap 1 mean
76.638). The partial-throttle steps in #9–#10 (157 vs 158) and #13 (82 vs 85) and the stretch times (5.76 / 4.93 s) are the
same as E17b, so the TC does not cut more at the crest than it should. Rejected: 0.024 s is noise against 20/20 → 19/20.

| 2026-10-16 | E20 map: exit guard at high steering | throttle ≤ max(0.2, 1 − 2·(\|steer\| − 0.6)); optional brake limit at full lock (`lock_brake`) | 76.872 (grip 0.90) / 76.906 (grip 0.95) | 0 | – | – | – | – |

Notes on E20 (`mapped/my_driver.py`: `exit_steer`, `exit_k`, `exit_min`, `lock_brake`; off by default).
What happens at #13 (`results/e17b_trace_g090.csv`, `mapped/trace_e17b_g095.csv`): the car enters the left hairpin
sideways (slip −20…−23 km/h, angle −0.49), the steering reaches full lock at 3266 m and stays there to 3290 m while the
throttle goes to 1.0 (TC cuts it to 0.34); the car runs ~2 m outside the line (trackPos +0.39 against +0.75). At grip
0.95 it is a little faster and, pointing at the right edge, the sensor speed cap brakes (0.2–0.69 at 3282–3287 m) **at full
lock**; the car spins and leaves the track at 3289 m. Single laps (E17b tables):

| Setting | grip 0.90 | grip 0.95 |
|---|---|---|
| none (E17b) | 76.598 | timeout, off track |
| `exit_steer` 0.6, `exit_k` 2 | 76.872 | **76.906, clean** |
| `exit_steer` 0.8 | 76.592 | timeout, damage 50 |
| `exit_steer` 0.7 | 76.714 | 78.030, 0.1 s off |
| `exit_steer` 0.6, `exit_k` 4 | 77.312 | 77.410 clean |
| `exit_steer` 0.6, `exit_k` 1 | 76.734 | 81.542, 2.3 s off |
| `exit_steer` 0.6, `exit_min` 0.5 | 76.784 | 77.546 clean |
| `exit_steer` 0.7, `exit_k` 1 | 76.516 | timeout, damage 23 |
| `exit_steer` 0.5, `exit_k` 1 | 76.768 | 77.576 clean |
| `lock_brake` 0.1 | 76.598 | 90.514, 9.9 s off |
| `exit_steer` 0.6 + `lock_brake` 0.1 | 76.872 | 76.906 clean |

The brake limit alone does not stop the spin; limiting the throttle on the exit does. `exit_steer` 0.6 / `exit_k` 2 is
the only setting that keeps grip 0.95 clean with margin; it costs 0.27 s at grip 0.90. On its own it is not an
improvement (rejected at 0.90); it is kept for the ladder in E21, whose result decides whether it stays.

| 2026-10-16 | E21 map: grip ladder with the exit guard | E17b crest tables, grip 0.90 → 0.95 → 1.00, with E20's guard (`exit_steer` 0.6, `exit_k` 2); stop at the first failure | 76.906 (grip 0.95, last passing step) | 0 | – | – | – | – |

Notes on E21 (`mapped/gate.py --params '{"exit_steer": 0.6, "exit_k": 2.0}'`, tables `build_table.py --mu 2.596 --crest
--grip g`):

| Grip | Model lap | 1 lap | 3 laps | ±1 % | Result |
|---|---|---|---|---|---|
| 0.90 | 74.36 | 76.872 | 76.872 / 73.174 / 73.126 clean | 20/20 (lap 1 mean 76.875) | passed |
| 0.95 | 73.23 | **76.906** | 76.906 / 73.294 / 73.220 clean | **20/20** (lap 1 mean 77.169) | passed: last step |
| 1.00 | 72.21 | 77.978, **0.6 s off track** at 3290–3300 m (#13 exit, 57 km/h) | – | – | failed |

The ladder keeps grip 0.95, but its lap (76.906 s) is 0.31 s slower than E17b (grip 0.90, no guard, 76.598 s), so the best
does not change. Section times (s) show why more grip does not pay:

| Grip | 0–600 | 600–1200 | 1200–1800 | 1800–2400 | 2400–3000 | 3000–3600 |
|---|---|---|---|---|---|---|
| 0.90 | 13.79 | 12.23 | 10.61 | 10.84 | 14.30 | 12.78 |
| 0.95 | 13.79 | 12.10 | 10.58 | 10.78 | 14.44 | 12.91 |
| 1.00 | 13.75 | 11.98 | 10.51 | 10.74 | 14.48 | 14.18 |

From 600 to 2400 m each 0.05 of grip is worth 0.1–0.25 s, as the model says. The Corkscrew (2400–3000 m) and #13
(3000–3600 m) get slower instead, and at 1.00 #13 leaves the track. These two places, not the rest of the lap, now set
the limit: the model's corner speed there is more than the car can use (crest + traction at the exits). A local grip
factor for these two stretches (`build_table.py --local`) would let the rest of the lap run at a higher grip. Not
tried yet; it needs your go-ahead, because the earlier rule allowed a local margin for #10 only.
