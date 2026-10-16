"""Racing line and point-mass speed profile on the rebuilt track (our own implementation, numpy only).

Racing line (K1999-style curvature smoothing): the line is the centreline shifted by an offset l(s) along the
normal (left +, metres). Repeatedly, every point is moved along its normal so that its curvature becomes the mean
of its neighbours' curvatures, with |l| <= tp_max * half width. This makes the curvature change as evenly as the
edges allow, which spreads each corner over the widest possible arc. It runs coarse to fine (every 16th point,
then 8th, ... 1st) so that long-range shape converges fast.

Speed profile (point mass): v <= sqrt(mu * g / |k|) in corners; a forward pass limits acceleration with a full-
throttle table measured on the E9 lap (results/e10_trace_e9_beams.csv) and a backward pass limits braking to
brake_g * g. A standing-start lap starts 10 m before the line at v = 0 and ends at the line one lap later.

    py mapped/line.py                       # report for tp_max 0.6 / 0.75 / 0.9
"""
import csv
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from track import Track  # noqa: E402

G = 9.81
# full-throttle acceleration (m/s^2) vs speed (km/h), medians from the E9 lap (straight, accel = 1, no brake)
ACC_TABLE_KMH = [0, 100, 170, 185, 200, 220, 240, 260, 290, 320]
ACC_TABLE = [12.0, 11.5, 12.5, 9.5, 8.5, 7.0, 5.0, 4.0, 1.5, 0.0]
GRID_BEHIND = 10.0  # m, the car starts this far before the start line


def curvature(x, y):
    """Signed curvature (left +) of a closed polyline from each point and its two neighbours."""
    ax, ay = np.roll(x, 1), np.roll(y, 1)
    cx, cy = np.roll(x, -1), np.roll(y, -1)
    cross = (x - ax) * (cy - ay) - (y - ay) * (cx - ax)
    d1 = np.hypot(x - ax, y - ay)
    d2 = np.hypot(cx - x, cy - y)
    d3 = np.hypot(cx - ax, cy - ay)
    return 2.0 * cross / np.maximum(d1 * d2 * d3, 1e-12)


def _relax(cx, cy, nx, ny, l, lim, iters, relax=0.5):
    """Move each point along its normal towards the mean curvature of its neighbours (Jacobi, even/odd split)."""
    n = len(l)
    for it in range(iters):
        for parity in (0, 1):
            x, y = cx + nx * l, cy + ny * l
            k = curvature(x, y)
            target = 0.5 * (np.roll(k, 1) + np.roll(k, -1))
            # d(curvature)/d(offset) for the middle of three points: about -2 / (d1 * d2) (moving left bends right)
            d1 = np.hypot(x - np.roll(x, 1), y - np.roll(y, 1))
            d2 = np.hypot(np.roll(x, -1) - x, np.roll(y, -1) - y)
            deriv = -2.0 / np.maximum(d1 * d2, 1e-9)
            step = relax * (target - k) / deriv
            sel = (np.arange(n) % 2) == parity
            l = np.where(sel, np.clip(l + step, -lim, lim), l)
    return l


def racing_line(t, tp_max=0.75, iters=(400, 400, 400, 600, 800, 1200)):
    """Offset l (m, left +) per centreline sample with |l| <= tp_max * half width."""
    lim = tp_max * t.half
    nx_all, ny_all = -np.sin(t.yaw), np.cos(t.yaw)
    n = len(t.s)
    l_full = np.zeros(n)
    strides = [32, 16, 8, 4, 2, 1]
    for stride, it in zip(strides, iters):
        idx = np.arange(0, n, stride)
        l = l_full[idx]
        l = _relax(t.x[idx], t.y[idx], nx_all[idx], ny_all[idx], l, lim, it)
        # back to full resolution (periodic linear interpolation)
        l_full = np.interp(np.arange(n), np.append(idx, n), np.append(l, l[0]))
    return l_full


def path(t, l):
    nx, ny = -np.sin(t.yaw), np.cos(t.yaw)
    x, y = t.x + nx * l, t.y + ny * l
    ds = np.hypot(np.roll(x, -1) - x, np.roll(y, -1) - y)  # path length from point i to i+1
    k = curvature(x, y)
    # light smoothing of the 1 m curvature (5-point mean) so single-sample noise does not set speeds
    k = sum(np.roll(k, j) for j in range(-2, 3)) / 5.0
    return x, y, ds, k


def speed_profile(k, ds, mu=1.3, brake_g=2.0, v_top=320.0):
    """Point-mass speeds (m/s) along an open sequence of samples that starts at rest.
    k[i]: curvature at sample i, ds[i]: distance from sample i to i+1. Grip is a friction circle: what cornering
    uses is not available for accelerating or braking."""
    acc_v = np.array(ACC_TABLE_KMH) / 3.6
    acc_a = np.array(ACC_TABLE)
    v = np.minimum(np.sqrt(mu * G / np.maximum(np.abs(k), 1e-9)), v_top / 3.6)
    m = len(k)

    def left(i):  # share of grip left after cornering
        lat = v[i] ** 2 * abs(k[i]) / (mu * G)
        return math.sqrt(max(0.0, 1.0 - min(1.0, lat) ** 2))

    def forward():
        v[0] = 0.0
        for i in range(m - 1):
            acc = np.interp(v[i], acc_v, acc_a) * left(i)
            v[i + 1] = min(v[i + 1], math.sqrt(v[i] ** 2 + 2.0 * acc * ds[i]))

    forward()
    for i in range(m - 2, -1, -1):
        v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2.0 * brake_g * G * left(i) * ds[i]))
    forward()  # the backward pass can lower earlier points; accelerate again from there
    return v


def standing_lap(t, k, ds, **kw):
    """Lap time from the green light: from rest 10 m behind the line, to the line one lap later.
    Returns (seconds, speeds m/s, sample indices of the unrolled sequence)."""
    n = len(k)
    i_grid = int(round((t.length - GRID_BEHIND) / t.ds)) % n
    order = [(i_grid + j) % n for j in range(n + int(round(GRID_BEHIND / t.ds)) + 1)]
    kk, dd = k[order], ds[order]
    v = speed_profile(kk, dd, **kw)
    tsec = float(np.sum(2.0 * dd[:-1] / np.maximum(v[:-1] + v[1:], 1e-6)))
    return tsec, v, order


def save_table(path_csv, t, l, k, v_by_idx):
    with open(path_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["distFromStart", "trackPos", "offset_m", "curvature", "radius_m", "v_kmh"])
        for i in range(len(t.s)):
            r = 1.0 / abs(k[i]) if abs(k[i]) > 1e-6 else 1e6
            w.writerow([round(t.s[i], 2), round(l[i] / t.half, 4), round(l[i], 3), round(k[i], 6), round(r, 1),
                        round(v_by_idx[i] * 3.6, 1)])
