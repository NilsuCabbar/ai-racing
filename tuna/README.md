# tuna/: from 84.78 s to 80.31 s on Corkscrew

This folder is our working copy of the driver. The goal was simple: a faster single lap on Corkscrew from a standing start, with zero damage and without ever leaving the track. We set ourselves two extra rules from the start:

1. The driver may only use the live sensor values that TORCS sends every tick. No lap distance lookups, no track maps, no hard-coded corner positions. It should be able to drive any track.
2. We do not touch the car setup or the kit files (`torcs_jm_par.py`, the TORCS install). Only `tuna/` changes.

## Results

| | Corkscrew lap | Clean laps out of 20 with ±3% parameter noise | E-Track 2 lap (never tuned there) |
|---|---|---|---|
| Root driver, `best_params.json` | 84.78 s | 12 / 20 | 79.14 s |
| After the first search | 81.04 s | 15 / 20 | 76.86 s |
| **Final (`params.json`)** | **80.31 s** | **19 / 20** | **75.73 s** |

All laps are clean (damage 0, never off track). The simulation is deterministic, so the same code and parameters always give the same time on this machine.

The root README mentions 83.63 s for the same driver. On our machine, with the TORCS package from the IBM starter kit, the same code and parameters give 84.78 s, so 84.78 s is our baseline.

## How to run

```
py tuna/run_lap.py                     # one headless lap on Corkscrew, about 12 s
py tuna/run_lap.py --segments          # plus a table per 100 m of track
py tuna/run_lap.py --trace             # writes tuna/trace.csv with per-step telemetry
py tuna/run_lap.py --track e-track-2   # another track
py tuna/run_lap.py --gui               # open TORCS yourself, then Race > Quick Race > New Race
py tuna/tune.py --trials 200 --robust 3 --noise 0.02   # parameter search
```

`run_lap.py` starts TORCS with `wtorcs.exe -r config\raceman\quickrace.xml`, so there are no menus to click and no rendering. It drives one lap with `my_driver.py` and `params.json`, then appends the result to `results.csv`. It refuses to start if another TORCS is already listening on UDP port 3001, because the client would connect to the wrong race.

## What we did, step by step

### 1. A fast, repeatable test

The first thing we needed was a way to test a change in seconds instead of clicking through the TORCS menus. Running TORCS with `-r` and a race file does exactly that. With the quick race set to Corkscrew, one lap takes about 12 seconds of wall time. That made everything below possible.

### 2. Looking at the telemetry

We logged every tick of the baseline lap and summed it up:

* 23.7 s of the 84.78 s lap was spent braking, 25.7 s on partial throttle and only 32.5 s at full throttle.
* The two slowest corners (around 2400 m and 3200 m) dropped to about 47 km/h, which was exactly the `min_speed` floor. The steering was nearly at full lock there.
* Braking was soft and long: `brake = (speed - target) * 0.02`, so 10 km/h over target only gave 0.2 brake.
* Throttle was proportional: `accel = (target - speed) * 0.05 + 0.1`, so the car crept out of corners.
* The target speed only knew how far it could see straight ahead. It had no idea how sharp the corner was.

We also learned early that the tuned parameters sat on a knife edge. Changing only `brake_gain` from 0.02 to 0.03, or only `accel_gain` to 1.0, put the car into the wall. Under hard braking the front wheels lock and the car stops turning. So any new feature had to be tuned together with everything else.

### 3. Longest beam tie-break (84.78 s to 84.29 s)

The driver blends its steering towards the longest of the 19 range sensors. When several beams return the same distance (all 200 m on a straight), Python's `max` picked the first one, which is the beam at 45 degrees to the left. We now pick the tied beam closest to straight ahead. That alone saved 0.49 s.

### 4. New driving features

All of these are parameters in `DEFAULTS`, and every one can be switched off with 0.

* **Corner speed from the sensors** (`mu`, `chord_k`). A circle that starts along our heading and passes through the end of the longest beam (distance D, angle a) has radius `R = D / (2 sin a)`. That gives a corner speed `v = sqrt(mu * g * R)`, which replaces the fixed `min_speed` floor in the braking formula. The first version crashed in S-bends: there the longest beam can be short but almost straight ahead, so R looked huge. The fix was a sight-distance cap. A road that bends with radius R only lets you see a chord of about `sqrt(chord_k * R)`, so `R <= D^2 / chord_k`.
* **Full-throttle band** (`full_band`). Below `target - full_band` the car uses full throttle. Inside the band the throttle is proportional. This removed most of the partial-throttle time on corner exits.
* **Trail braking** (`brake_steer`). The brake is scaled down by `1 - brake_steer * |steer|`, so the front tyres keep some grip for turning.
* **Slide guard** (`slide_k`, `slide_thresh`). If the car slides sideways (`speedY` above the threshold) the target speed drops a little.
* **Racing line** (`line_out`, `line_in`, `line_dist`). Before a corner the car aims slightly to the outside, and it can aim inside near the apex.
* **ABS** (`abs_slip`, `abs_range`), **target rise limit** (`rise_rate`) and **edge guard** (`edge_pos`). We built and tested these, but the search turned all three off. ABS did not help because a locked wheel in TORCS still slows the car well, and releasing the brake only made the car arrive too fast.

### 5. Parameter search (84.29 s to 81.04 s)

`tune.py` is a simple evolution strategy. It changes 1 to 4 parameters of the best set, runs a lap and keeps the change if the score improves. When nothing improves for 25 trials, the step size shrinks. A lap that is not clean always scores worse than any clean lap. Missing keys start from the driver defaults, so a new feature starts switched off and the search can turn it on.

400 trials brought the lap to 81.04 s.

### 6. Checking robustness

A deterministic lap time can hide a fragile setup. We had already seen that the same code gives 84.78 s on our machine and 83.63 s on another. To test this, we ran the lap 20 times, each time with every parameter multiplied by a random factor between 0.97 and 1.03. The 81.04 s set stayed clean in 15 or 16 of the 20 runs, depending on the random draws. The original parameters managed only 12.

Our first robust search penalised every unclean lap with 5 s. That was too strict. It switched the corner speed feature off and settled at about 84 s, so we stopped it.

### 7. A reference from a built-in robot

TORCS ships with robots that drive the same car, `car1-ow1`. We ran `inferno` on Corkscrew with the same setup. It did a standing-start lap of about 74.65 s and a flying lap of 71.10 s, with no damage. Robots like this read the full track geometry, so they are not allowed for us, but they show how much the car can do. Most of the gap is in corner speed and braking points, not top speed.

While looking at top speed we noticed that the car has 7 gears but our driver only used 6. Gear 7 does not help: the kit client in `torcs_jm_par.py` only accepts gears -1 to 6 and turns anything else into neutral. So `max_gear` stays at 6.

### 8. Final search (81.04 s to 80.31 s)

The last search scored each candidate as the mean of four laps: the normal lap plus three copies with ±2% parameter noise. An unclean lap counted as its time plus 5 s. The perturbation sets are fixed, so every candidate faces the same small errors and the comparison is fair. Candidates whose normal lap was more than 1.5 s behind were rejected without the extra laps, which saved a lot of time.

After 200 trials the normal lap was 80.31 s. On 20 new random perturbations it stayed clean 19 times, with a mean of 80.44 s and a worst lap of 80.90 s. On E-Track 2, where we never tuned anything, it ran a clean 75.73 s.

In the final set the corner speed estimate, the full-throttle band, the slide guard, light trail braking and a small outside line before corners are switched on. ABS, the rise limit and the edge guard are off.

## Files

| File | What it is |
|---|---|
| `my_driver.py` | the driver |
| `params.json` | the final parameters (80.31 s) |
| `run_lap.py` | headless one-lap test runner |
| `tune.py` | parameter search, with optional robustness scoring |
| `results.csv` | every saved test lap, with its parameters |

## Ideas for later

* A real racing line built from the sensor geometry. The search kept the current one very small, and this is probably where most of the remaining gap to the robots is.
* A better corner radius estimate that uses more than one beam, for example a circle fit through the edge points.
* Checking more tracks, so the parameters do not slowly overfit to Corkscrew.
