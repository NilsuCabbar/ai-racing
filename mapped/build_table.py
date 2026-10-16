"""Builds mapped/table.csv, the lookup table the map driver reads (one row per metre of track).

Columns: distFromStart, line offset (m, left +), line point x/y, centreline x/y/heading, line curvature, flying-lap
model speed (m/s). The speed is the point-mass profile of mapped/line.py for a lap at speed (three laps unrolled from
rest, the middle one kept), so the table has no standing-start dip; the car simply accelerates as hard as it can at
the start.

    py mapped/build_table.py --tp 0.75 --mu 2.70 --brake-g 3.0
"""
import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import line as L  # noqa: E402
from track import Track  # noqa: E402


def flying_profile(t, k, ds, mu, brake_g):
    n = len(k)
    order = [j % n for j in range(3 * n + 1)]
    v = L.speed_profile(k[order], ds[order], mu=mu, brake_g=brake_g)
    out = np.zeros(n)
    out[np.array(order[n:2 * n])] = v[n:2 * n]
    return out


def build(tp, mu, brake_g, out_path):
    t = Track()
    l = L.racing_line(t, tp)
    x, y, ds, k = L.path(t, l)
    v = flying_profile(t, k, ds, mu, brake_g)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# tp_max={tp} mu={mu} brake_g={brake_g} length={t.length:.4f} ds={t.ds:.6f}"])
        w.writerow(["s", "offset", "lx", "ly", "cx", "cy", "yaw", "k", "v"])
        for i in range(len(t.s)):
            w.writerow([round(t.s[i], 4), round(l[i], 4), round(x[i], 4), round(y[i], 4), round(t.x[i], 4),
                        round(t.y[i], 4), round(t.yaw[i], 6), round(k[i], 6), round(v[i], 3)])
    lap = L.standing_lap(t, k, ds, mu=mu, brake_g=brake_g)[0]
    return lap, v


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tp", type=float, default=0.75)
    ap.add_argument("--mu", type=float, default=2.70)
    ap.add_argument("--brake-g", type=float, default=3.0)
    ap.add_argument("--out", default=os.path.join(HERE, "table.csv"))
    a = ap.parse_args()
    lap, v = build(a.tp, a.mu, a.brake_g, a.out)
    print(f"table {a.out}: tp_max {a.tp}, mu {a.mu}, brake {a.brake_g} g; model standing lap {lap:.2f} s; "
          f"speed {v.min() * 3.6:.0f}-{v.max() * 3.6:.0f} km/h")
