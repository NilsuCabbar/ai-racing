"""Checks the rebuilt centreline (mapped/track.py) against a real lap.

For every trace row (baseline/run_lap.py --trace-beams), the car is placed on the map at distFromStart, trackPos
and angle, and the 19 range-finder beams are cast against the two track edges. The predicted distances are compared
with what TORCS measured. A scan over a shift of distFromStart checks that the start line is where we think it is.

    py mapped/verify_geometry.py results/e10_trace_e9_beams.csv
"""
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from track import Track  # noqa: E402

BEAMS_DEG = np.array([-45, -19, -12, -7, -4, -2.5, -1.7, -1, -0.5, 0, 0.5, 1, 1.7, 2.5, 4, 7, 12, 19, 45])
MAX_RANGE = 200.0


def edges(t):
    nx, ny = -np.sin(t.yaw), np.cos(t.yaw)
    left = np.stack([t.x + t.half * nx, t.y + t.half * ny], 1)
    right = np.stack([t.x - t.half * nx, t.y - t.half * ny], 1)
    return left, right


def cast(px, py, dirs, segs_a, segs_b):
    """Distance along each ray (unit vectors dirs, shape (m, 2)) to the nearest of the segments a->b."""
    d = segs_b - segs_a                       # (k, 2)
    ox, oy = segs_a[:, 0] - px, segs_a[:, 1] - py
    rx, ry = dirs[:, 0:1], dirs[:, 1:2]       # (m, 1)
    den = rx * d[:, 1] - ry * d[:, 0]         # (m, k)
    with np.errstate(divide="ignore", invalid="ignore"):
        tr = (ox * d[:, 1] - oy * d[:, 0]) / den   # distance along the ray
        u = (ox * ry - oy * rx) / den              # position along the segment
    ok = (np.abs(den) > 1e-12) & (tr > 0) & (u >= 0) & (u <= 1)
    tr = np.where(ok, tr, np.inf)
    return np.minimum(tr.min(1), MAX_RANGE)


def predict(t, left, right, s, pos, ang):
    n = len(t.s)
    i0 = int(round((s % t.length) / t.ds))
    win = np.arange(i0 - 60, i0 + 260) % n          # edges from 60 m behind to 260 m ahead
    nxt = (win + 1) % n
    a = np.concatenate([left[win], right[win]])
    b = np.concatenate([left[nxt], right[nxt]])
    x, y, yaw = t.pose(np.array([s]), np.array([pos * t.half]))
    car_yaw = yaw[0] - ang                          # TORCS angle = track heading - car heading
    th = car_yaw - np.radians(BEAMS_DEG)            # negative beam angles point left
    return cast(x[0], y[0], np.stack([np.cos(th), np.sin(th)], 1), a, b)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "e10_trace_e9_beams.csv")
    every = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    t = Track()
    left, right = edges(t)
    rows = list(csv.DictReader(open(path)))
    rows = [r for r in rows[::every] if abs(float(r["trackPos"])) < 1.0]
    meas = np.array([[float(r[f"track{i}"]) for i in range(19)] for r in rows])
    S = np.array([float(r["distFromStart"]) for r in rows])
    P = np.array([float(r["trackPos"]) for r in rows])
    A = np.array([float(r["angle"]) for r in rows])

    def errors(shift):
        pred = np.array([predict(t, left, right, s + shift, p, a) for s, p, a in zip(S, P, A)])
        return pred, pred - meas

    print(f"track length {t.length:.2f} m; {len(rows)} trace rows")
    print("shift of distFromStart (m) -> median |error| over all beams < 200 m")
    for shift in [-4, -2, -1, -0.5, 0, 0.5, 1, 2, 4]:
        sub = slice(None, None, 4)
        pred = np.array([predict(t, left, right, s + shift, p, a) for s, p, a in zip(S[sub], P[sub], A[sub])])
        e = (pred - meas[sub])[meas[sub] < 199]
        print(f"  {shift:+5.1f}: {np.median(np.abs(e)):.3f} m")

    pred, err = errors(0.0)
    valid = meas < 199
    print("\nper beam (shift 0): median |error| / 95th percentile |error| (m), beams that hit an edge")
    for i, b in enumerate(BEAMS_DEG):
        e = np.abs(err[valid[:, i], i])
        print(f"  {b:+6.1f} deg: {np.median(e):6.3f} / {np.percentile(e, 95):6.3f}   n={len(e)}")
    print("\nby section: median |error| of the +-45/19/12 deg beams (near edges) and of all beams")
    near = [0, 1, 2, 16, 17, 18]
    for lo in range(0, 3609, 300):
        m = (S >= lo) & (S < lo + 300)
        if not m.any():
            continue
        en = np.abs(err[m][:, near][valid[m][:, near]])
        ea = np.abs(err[m][valid[m]])
        print(f"  {lo:5d}-{lo + 300:5d} m: near {np.median(en):.3f}  all {np.median(ea):.3f}  "
              f"(95th all {np.percentile(ea, 95):.2f})")
    # lateral check: left/right edge distance from the side beams vs the map
    e45 = np.abs(err[:, [0, 18]][valid[:, [0, 18]]])
    print(f"\n+-45 deg beams overall: median {np.median(e45):.3f} m, 99th {np.percentile(e45, 99):.3f} m, "
          f"max {e45.max():.3f} m")


if __name__ == "__main__":
    main()
