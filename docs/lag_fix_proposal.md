# Proposal: stop command lag from building up after a late answer

Status: **proposal only, not implemented.** We are waiting for the organizers to approve it.

## Problem

After one late answer from the Python client, every later command reaches the car one step (20 ms) late, for the rest
of the race. Each further late answer adds another step. The driver then steers and brakes on old data. On Corkscrew
this ends in a spin, usually at the Corkscrew corner (2.44–2.53 km) or in the last corners (~3.3 km).

Measured headless with the TORCS default UDP timeout. `--jitter P` makes the client answer 15 ms late with probability P
per step. See `EXPERIMENTS.md`, E1 and E4.

| Driver | No late answers | ~4 late answers per lap (P=0.001) | ~12 per lap (P=0.003) |
|---|---|---|---|
| old best_params | 0/10 crashes | 7/10 crashes | 10/10 crashes |
| current best_params | 0/10 | 4/10 | – |

The lag can be seen directly: the gear sensor shows a new gear 1 step after we send it when in sync. With
P=0.003 this grew to 5 steps (100 ms) by the end of the lap.

## Mechanism

1. `scr_server` sends state S(k) and waits up to 10 ms (default `-t`) for the client's answer.
2. If the answer is late, the server reuses the previous command for this step and moves on. It sends S(k+1).
3. The late answer A(k) arrives and stays in the server's UDP queue. When the server waits for the answer to S(k+1),
   it finds A(k) immediately and uses it.
4. The client answers S(k+1) with A(k+1), which waits in the queue for S(k+2), and so on. The server stays one answer
   behind, and nothing ever empties the extra answer from the queue.

## Proposed fix (client side, no server change)

After a late answer, **skip the answer to the next state once**. The server then uses the queued A(k) for S(k+1),
finds the queue empty at S(k+2), waits for a fresh answer, and is back in sync. That one step uses the older command,
which happens anyway.

```python
late = False
for step in range(C.maxSteps, 0, -1):
    C.get_servers_input()              # unchanged (REQUIRED block)
    t = time.perf_counter()
    drive(C)
    if late:                           # our previous answer was used for this state already
        late = False
        continue                       # skip one answer -> server queue is empty again
    C.respond_to_server()              # unchanged
    late = time.perf_counter() - t > 0.008   # 8 ms: margin below the 10 ms timeout
```

Limits:
- This detects lateness caused by our own code (`drive()` plus sending). If Windows delivers the state to Python late,
  the client cannot see that. The GUI measurement (`baseline/analyze_timing.py`) shows which cause happens in practice.
- An answer more than 2 steps late (> 30 ms) would need more than one skip. It could skip `round(delay / 20 ms)` answers.

## Lines it touches

- `torcs_jm_par.py` lines 562–569, the `if __name__ == "__main__":` main loop. This is **not** inside a
  "REQUIRED – DO NOT CHANGE" block, but it is the loop the race may run. The alternative is the same change in our
  own loop in `baseline/run_lap.py` (around line 234, `C.respond_to_server()`), if our runner is what races.
- **Not touched:** `get_servers_input` (lines 244–277, REQUIRED FOR RACE MODE), `respond_to_server` (279–287), the
  port handling (213–216, 563–564), or the server and TORCS files.

## Questions for the organizers

1. Which loop drives the car in the official race: `torcs_jm_par.py`'s main loop, our own script, or yours?
   (Note: that main loop currently calls the IBM sample `drive_modular`, not our `my_driver.drive`.)
2. Is it allowed to skip sending an answer for one step, as above?
3. Does the official race run in the real-time GUI or text mode, and with which `-t` (UDP timeout)?

## How to verify after implementing

Run each with and without the fix:

- `baseline/run_lap.py --robust 10 --jitter 0.001` and `--jitter 0.003`: the crash rate should drop.
- `--timing-log` and `analyze_timing.py`: the gear echo lag should return to 0 after each late answer instead of
  growing.
- `baseline/run_lap.py` with the default deterministic `-t 1000000`: the lap time must not change (82.156 s), since
  no answer is late there.
