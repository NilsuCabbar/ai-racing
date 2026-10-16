"""Analyses a map-driver lap (baseline/run_lap.py --trace --trace-every 1 --trace-beams) against mapped/table.csv.

Prints: line-following error, max |trackPos|, speed vs target, and per corner the real time against the model
time (point-mass model of mapped/line.py on the same line, with grip and braking scaled by scale^2, which is what
following scale x the table speed means in corners and braking zones), the real lateral g and sideways slip.

    py mapped/analyze_run.py mapped/trace_last.csv --scale 0.85 [--ref results/e10_trace_e9_beams.csv]
"""
import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import line as L  # noqa: E402
from step2_report import corners  # noqa: E402
from track import Track  # noqa: E402


def load_trace(path, t):
    R = list(csv.DictReader(open(path)))
    f = lambda k: np.array([float(r[k]) for r in R])  # noqa: E731
    d = {k: f(k) for k in ("distFromStart", "trackPos", "speedX", "speedY", "curLapTime", "steer", "accel",
                          "brake", "angle", "distRaced")}
    lap1 = (d["curLapTime"] > 0) & (d["distRaced"] > 9) & (d["distRaced"] < t.length + 10)
    return d, lap1


def times_at(t, d, lap1):
    s, tt = d["distFromStart"][lap1], d["curLapTime"][lap1]
    o = np.argsort(s)
    return np.interp(t.s, s[o], tt[o])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--scale", type=float, default=0.85)
    ap.add_argument("--mu", type=float, default=2.70)
    ap.add_argument("--brake-g", type=float, default=3.0)
    ap.add_argument("--crest", action="store_true", help="model with the crest load model (E17)")
    ap.add_argument("--ref", default=None, help="another trace to compare times with (e.g. the E9 lap)")
    a = ap.parse_args()
    t = Track()
    tab = list(csv.DictReader(open(os.path.join(HERE, "table.csv")).readlines()[1:]))
    off = np.array([float(r["offset"]) for r in tab])
    vt = np.array([float(r["v"]) for r in tab]) * 3.6
    kl = np.array([float(r["k"]) for r in tab])

    d, lap1 = load_trace(a.trace, t)
    s = d["distFromStart"]
    idx = np.round((s % t.length) / t.ds).astype(int) % len(t.s)
    err = d["trackPos"] * t.half - off[idx]
    m = lap1
    print(f"lap rows {m.sum()}; max |trackPos| {np.abs(d['trackPos'][m]).max():.3f} at "
          f"{s[m][np.argmax(np.abs(d['trackPos'][m]))]:.0f} m")
    print(f"line error (m): median |e| {np.median(np.abs(err[m])):.2f}, 95th {np.percentile(np.abs(err[m]), 95):.2f}, "
          f"max {np.abs(err[m]).max():.2f} at {s[m][np.argmax(np.abs(err[m]))]:.0f} m")
    tgt = a.scale * vt[idx]
    dv = d["speedX"] - tgt
    print(f"speed - target (km/h): median {np.median(dv[m]):+.1f}, 5th {np.percentile(dv[m], 5):+.1f}, "
          f"95th {np.percentile(dv[m], 95):+.1f}")
    print(f"time braking {np.sum(d['brake'][m] > 0.02) * 0.02:.1f} s, full throttle {np.sum(d['accel'][m] > 0.99) * 0.02:.1f} s")

    # model on the same line with grip and braking scaled by scale^2 (cornering and braking at scale x speed)
    _, _, ds, k = L.path(t, off)
    sc2 = a.scale ** 2
    kc = t.crest if a.crest else None
    n = len(k)
    i_grid = int(round((t.length - L.GRID_BEHIND) / t.ds)) % n
    order = [(i_grid + j) % n for j in range(n + int(round(L.GRID_BEHIND / t.ds)) + 1)]

    def model(mu, bg):
        vv = L.speed_profile(k[order], ds[order], mu=mu, brake_g=bg, crest=None if kc is None else kc[order])
        return float(np.sum(2.0 * ds[order][:-1] / np.maximum(vv[:-1] + vv[1:], 1e-6))), vv

    lap_m, v_m = model(a.mu * sc2, a.brake_g * sc2)
    lap_full = model(a.mu, a.brake_g)[0]
    dt = 2.0 * ds[order[:-1]] / np.maximum(v_m[:-1] + v_m[1:], 1e-6)
    tc = np.concatenate([[0], np.cumsum(dt)])
    nst = int(round(L.GRID_BEHIND / t.ds))
    Tm = np.zeros(len(t.s))
    Tm[np.array(order[nst:-1])] = tc[nst:-1] - tc[nst]
    Tr = times_at(t, d, lap1)
    print(f"model lap at this scale (grip x{sc2:.3f}): {lap_m:.2f} s; at full table speed {lap_full:.2f} s")

    ref_T = None
    if a.ref:
        dr, l1r = load_trace(a.ref, t)
        ref_T = times_at(t, dr, l1r)

    # lateral g of the real lap on the map (its own path, trackPos smoothed over +-8 m)
    so = np.argsort(s[m])
    lp = np.interp(t.s, s[m][so], d["trackPos"][m][so] * t.half, period=t.length)
    lp = sum(np.roll(lp, j) for j in range(-8, 9)) / 17.0
    _, _, _, kr = L.path(t, lp)
    vr = np.interp(t.s, s[m][so], d["speedX"][m][so], period=t.length)
    vy = np.interp(t.s, s[m][so], np.abs(d["speedY"][m][so]), period=t.length)
    glat = (vr / 3.6) ** 2 * np.abs(kr) / 9.81

    cs = corners(t)
    print("\n| # | corner (m) | stretch (m) | min speed real / target (km/h) | real lat g (max) | max slip (km/h) | "
          "time real / model (s) | real - model | " + ("ref (E9) time / real - ref |" if ref_T is not None else ""))
    print("|---|---|---|---|---|---|---|---|" + ("---|" if ref_T is not None else ""))
    for j, c in enumerate(cs):
        a_, b_ = c["a"], c["b"]
        prev_b = cs[j - 1]["b"] if j > 0 else -10 ** 9
        next_a = cs[j + 1]["a"] if j + 1 < len(cs) else 10 ** 9
        a0 = max(0, a_ - 60, (prev_b + a_) // 2)
        b0 = min(len(t.s) - 1, b_ + 60, (b_ + next_a) // 2)
        tr, tm = Tr[b0] - Tr[a0], Tm[b0] - Tm[a0]
        line = (f"| {j + 1} | {t.s[a_]:.0f}-{t.s[b_]:.0f} {c['turn']} | {t.s[a0]:.0f}-{t.s[b0]:.0f} | "
                f"{vr[a_:b_ + 1].min():.0f} / {a.scale * vt[a_:b_ + 1].min():.0f} | {glat[a_:b_ + 1].max():.2f} | "
                f"{vy[a_:b_ + 1].max():.1f} | {tr:.2f} / {tm:.2f} | {tr - tm:+.2f} |")
        if ref_T is not None:
            trf = ref_T[b0] - ref_T[a0]
            line += f" {trf:.2f} / {tr - trf:+.2f} |"
        print(line)


if __name__ == "__main__":
    main()
