"""Builds mapped/table.csv, the lookup table the map driver reads (one row per metre of track).

Columns: distFromStart, line offset (m, left +), line point x/y, centreline x/y/heading, line curvature, flying-lap
model speed (m/s). The speed is the point-mass profile of mapped/line.py for a lap at speed (three laps unrolled from
rest, the middle one kept), so the table has no standing-start dip; the car simply accelerates as hard as it can at
the start.

    py mapped/build_table.py --tp 0.75 --mu 2.70 --brake-g 3.0 --grip 0.85 [--local 2484:2597:0.9]

--grip scales the cornering grip (mu) and the braking (brake_g) together; acceleration and top speed are not scaled,
so the straights stay at full throttle. --local a:b:f multiplies the grip by f between distFromStart a and b only
(blended over 20 m on both sides), for a weak corner.
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


def flying_profile(t, k, ds, mu, brake_g, crest=None):
    n = len(k)
    order = [j % n for j in range(3 * n + 1)]
    mu = np.broadcast_to(np.asarray(mu, dtype=float), (n,))
    v = L.speed_profile(k[order], ds[order], mu=mu[order], brake_g=brake_g,
                        crest=None if crest is None else crest[order])
    out = np.zeros(n)
    out[np.array(order[n:2 * n])] = v[n:2 * n]
    return out


def grip_factor(t, local):
    """Per-sample grip factor from 'a:b:f' strings, blended linearly over 20 m outside [a, b]."""
    g = np.ones(len(t.s))
    for spec in local:
        a, b, f = (float(x) for x in spec.split(":"))
        d = np.maximum(a - t.s, t.s - b)            # distance outside [a, b] (<= 0 inside)
        w = np.clip(1.0 - d / 20.0, 0.0, 1.0)       # 1 inside, 0 beyond 20 m
        g = np.minimum(g, 1.0 - w * (1.0 - f))
    return g


def build(tp, mu, brake_g, out_path, grip=1.0, local=(), crest=False, narrow=()):
    t = Track()
    l = L.racing_line(t, tp, local=[tuple(float(x) for x in n.split(":")) for n in narrow])
    x, y, ds, k = L.path(t, l)
    gf = grip_factor(t, local)
    kc = t.crest if crest else None
    v = flying_profile(t, k, ds, mu * grip * gf, brake_g * grip, kc)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# tp_max={tp} mu={mu} brake_g={brake_g} grip={grip} local={','.join(local) or '-'} crest={int(crest)} narrow={','.join(narrow) or '-'} "
                    f"length={t.length:.4f} ds={t.ds:.6f}"])
        w.writerow(["s", "offset", "lx", "ly", "cx", "cy", "yaw", "k", "v"])
        for i in range(len(t.s)):
            w.writerow([round(t.s[i], 4), round(l[i], 4), round(x[i], 4), round(y[i], 4), round(t.x[i], 4),
                        round(t.y[i], 4), round(t.yaw[i], 6), round(k[i], 6), round(v[i], 3)])
    n = len(k)
    i_grid = int(round((t.length - L.GRID_BEHIND) / t.ds)) % n
    order = [(i_grid + j) % n for j in range(n + int(round(L.GRID_BEHIND / t.ds)) + 1)]
    vv = L.speed_profile(k[order], ds[order], mu=(mu * grip * gf)[order], brake_g=brake_g * grip,
                         crest=None if kc is None else kc[order])
    lap = float(np.sum(2.0 * ds[order][:-1] / np.maximum(vv[:-1] + vv[1:], 1e-6)))
    return lap, v


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tp", type=float, default=0.75)
    ap.add_argument("--mu", type=float, default=2.70)
    ap.add_argument("--brake-g", type=float, default=3.0)
    ap.add_argument("--grip", type=float, default=1.0, help="scales mu and brake_g, not acceleration")
    ap.add_argument("--local", action="append", default=[], metavar="A:B:F", help="extra grip factor F on [A, B] m")
    ap.add_argument("--crest", action="store_true", help="lower grip, braking and traction on crests (E17)")
    ap.add_argument("--narrow", action="append", default=[], metavar="A:B:TP",
                    help="narrower |trackPos| limit TP for the line on [A, B] m (E18)")
    ap.add_argument("--out", default=os.path.join(HERE, "table.csv"))
    a = ap.parse_args()
    lap, v = build(a.tp, a.mu, a.brake_g, a.out, a.grip, a.local, a.crest, a.narrow)
    print(f"table {a.out}: tp_max {a.tp}, mu {a.mu}, brake {a.brake_g} g, grip x{a.grip}, local {a.local}, "
          f"crest {a.crest}, narrow {a.narrow}; "
          f"model standing lap {lap:.2f} s; "
          f"speed {v.min() * 3.6:.0f}-{v.max() * 3.6:.0f} km/h")
