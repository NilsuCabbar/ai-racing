"""Step 2 report: racing lines for several edge limits, lap estimates, comparison with the line E9 drives.

Nothing here drives the car. Outputs:
  mapped/line_tp060.csv, line_tp075.csv, line_tp090.csv   (distFromStart -> trackPos, curvature, model speed)
  results/e11_step2_report.txt, results/e11_lines.svg

    py mapped/step2_report.py
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import line as L  # noqa: E402
from track import Track  # noqa: E402

E9_TRACE = os.path.join(REPO, "results", "e10_trace_e9_beams.csv")
E9_LAP = 79.556
BRAKE_G = 3.0
LIMITS = [0.6, 0.75, 0.9]
out_lines = []


def say(s=""):
    print(s)
    out_lines.append(s)


def e9_data(t):
    R = list(csv.DictReader(open(E9_TRACE)))
    s = np.array([float(r["distFromStart"]) for r in R])
    p = np.array([float(r["trackPos"]) for r in R])
    v = np.array([float(r["speedX"]) for r in R])
    lap_t = np.array([float(r["curLapTime"]) for r in R])
    o = np.argsort(s)
    l = np.interp(t.s, s[o], p[o] * t.half, period=t.length)
    l_smooth = sum(np.roll(l, j) for j in range(-8, 9)) / 17.0  # trackPos has 3 decimals: smooth before curvature
    vv = np.interp(t.s, s[o], v[o], period=t.length)
    # time at which E9 passed each sample (first lap, after the start line)
    started = np.where((s < 3000) & (lap_t > 0))[0]
    tt = np.interp(t.s, s[started], lap_t[started])
    return l, l_smooth, vv, tt


def corners(t, thresh=1 / 250.0, merge=40.0):
    """Corners = runs of centreline curvature above thresh (merged when closer than `merge` m)."""
    on = np.abs(t.k) > thresh
    runs, i, n = [], 0, len(on)
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1] and np.sign(t.k[j + 1]) == np.sign(t.k[i]):  # split at L/R changes
                j += 1
            runs.append([i, j])
            i = j + 1
        else:
            i += 1
    merged = []
    for a, b in runs:
        if merged and (t.s[a] - t.s[merged[-1][1]]) < merge and np.sign(t.k[a]) == np.sign(t.k[merged[-1][1]]):
            merged[-1][1] = b
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        ang = np.degrees(np.sum(t.k[a:b + 1]) * t.ds)
        if abs(ang) < 15:
            continue
        rmin = 1 / np.abs(t.k[a:b + 1]).max()
        out.append({"a": a, "b": b, "turn": "L" if ang > 0 else "R", "deg": abs(ang), "rmin": rmin,
                    "segs": sorted(set(t.names[a:b + 1]), key=t.names[a:b + 1].index)})
    return out


def svg(t, lines, e9, path_svg, box=None, title=""):
    """Track edges, E9's line and the racing lines; box = (s_from, s_to) for a zoom."""
    nx, ny = -np.sin(t.yaw), np.cos(t.yaw)
    sel = np.arange(len(t.s)) if box is None else np.where((t.s >= box[0]) & (t.s <= box[1]))[0]
    X = [t.x[sel] + nx[sel] * t.half, t.x[sel] - nx[sel] * t.half]
    Y = [t.y[sel] + ny[sel] * t.half, t.y[sel] - ny[sel] * t.half]
    xmin, xmax = min(a.min() for a in X) - 5, max(a.max() for a in X) + 5
    ymin, ymax = min(a.min() for a in Y) - 5, max(a.max() for a in Y) + 5
    W = 900
    sc = W / max(xmax - xmin, ymax - ymin)
    H = (ymax - ymin) * sc

    def pl(xs, ys, color, wdt, dash=""):
        pts = " ".join(f"{(a - xmin) * sc:.1f},{(ymax - b) * sc:.1f}" for a, b in zip(xs, ys))
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{wdt}"{d}/>'

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H + 40:.0f}" width="{W}" height="{H + 40:.0f}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             f'<text x="10" y="{H + 25:.0f}" font-family="sans-serif" font-size="14" fill="#333">{title}</text>']
    parts += [pl(X[0], Y[0], "#999", 1.5), pl(X[1], Y[1], "#999", 1.5)]
    colors = {"E9": "#d62728", 0.6: "#2ca02c", 0.75: "#1f77b4", 0.9: "#9467bd"}
    for key, l in [("E9", e9)] + list(lines.items()):
        parts.append(pl(t.x[sel] + nx[sel] * l[sel], t.y[sel] + ny[sel] * l[sel], colors[key],
                        2.6 if key == "E9" else 2.0, "6,3" if key == "E9" else ""))
    # distance marks every 100 m
    for s0 in range(0, int(t.length), 100):
        i = int(s0 / t.ds)
        if i in set(sel.tolist()):
            px, py = (t.x[i] - xmin) * sc, (ymax - t.y[i]) * sc
            parts.append(f'<text x="{px:.0f}" y="{py:.0f}" font-family="sans-serif" font-size="10" fill="#666">{s0}</text>')
    legend = [("E9 (driven)", colors["E9"])] + [(f"line |trackPos| ≤ {k}", colors[k]) for k in lines]
    for j, (name, c) in enumerate(legend):
        parts.append(f'<rect x="10" y="{10 + 18 * j}" width="14" height="4" fill="{c}"/>'
                     f'<text x="30" y="{16 + 18 * j}" font-family="sans-serif" font-size="12" fill="#333">{name}</text>')
    parts.append("</svg>")
    with open(path_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def main():
    t = Track()
    e9_l, e9_ls, e9_v, e9_t = e9_data(t)
    _, _, ds9, k9 = L.path(t, e9_ls)

    # --- calibrate mu so that the model reproduces E9's real lap on E9's own line ---
    lo, hi = 1.0, 4.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if L.standing_lap(t, k9, ds9, mu=mid, brake_g=BRAKE_G)[0] > E9_LAP:
            lo = mid
        else:
            hi = mid
    mu = round((lo + hi) / 2, 3)
    say("STEP 2: racing line (K1999-style curvature smoothing) and point-mass lap estimate. Not driven yet.")
    say(f"Track {t.length:.2f} m, half width {t.half} m. Model: lateral grip mu*g, braking {BRAKE_G} g, "
        "full-throttle table from the E9 lap, friction circle.")
    say(f"Calibration: mu = {mu} makes the model give E9's real lap ({E9_LAP} s) on E9's own line "
        "(E9's lateral g measured on the map: ~1.8 g at 50 km/h, 2.0-2.4 g at 60-160 km/h).")
    say()

    lines, rows = {}, []
    for tp in LIMITS:
        l = L.racing_line(t, tp)
        lines[tp] = l
        x, y, ds, k = L.path(t, l)
        lap, v, order = L.standing_lap(t, k, ds, mu=mu, brake_g=BRAKE_G)
        v_idx = np.zeros(len(t.s))
        v_idx[order[:-1]] = v[:-1]
        L.save_table(os.path.join(HERE, f"line_tp{int(tp * 100):03d}.csv"), t, l, k, v_idx)
        sens = [L.standing_lap(t, k, ds, mu=mu * f, brake_g=BRAKE_G)[0] for f in (0.9, 1.1)]
        rows.append((tp, np.abs(l).max() / t.half, ds.sum(), 1 / np.abs(k).max(), lap, sens, v_idx))
    say("| limit |trackPos| | max |trackPos| on line | path length (m) | tightest radius (m) | est. lap (s) | vs E9 (s) | mu -10% / +10% (s) |")
    say("|---|---|---|---|---|---|---|")
    for tp, mx, plen, rmin, lap, sens, _ in rows:
        say(f"| {tp} | {mx:.3f} | {plen:.1f} | {rmin:.1f} | {lap:.2f} | {lap - E9_LAP:+.2f} | {sens[0]:.2f} / {sens[1]:.2f} |")
    _, _, dsc, kc = L.path(t, np.zeros(len(t.s)))
    lap_c = L.standing_lap(t, kc, dsc, mu=mu, brake_g=BRAKE_G)[0]
    say(f"| centreline (0) | 0 | {dsc.sum():.1f} | {t.half and 1 / np.abs(t.k).max():.1f} | {lap_c:.2f} | {lap_c - E9_LAP:+.2f} | |")
    say(f"| E9 driven line | {np.abs(e9_l).max() / t.half:.3f} | {ds9.sum():.1f} | {1 / np.abs(k9).max():.1f} | {E9_LAP} (real) | 0 | |")
    say()

    # --- per corner: E9's line vs the 0.75 line ---
    ref = 0.75
    l = lines[ref]
    _, _, dsr, kr = L.path(t, l)
    lap_r, v_r, order_r = L.standing_lap(t, kr, dsr, mu=mu, brake_g=BRAKE_G)
    lap_9, v_9, order_9 = L.standing_lap(t, k9, ds9, mu=mu, brake_g=BRAKE_G)

    def times(v, ds, order):
        dt = 2.0 * ds[order[:-1]] / np.maximum(v[:-1] + v[1:], 1e-6)
        tcum = np.concatenate([[0], np.cumsum(dt)])
        out = np.zeros(len(t.s))
        # unrolled sequence starts 10 m before the line; keep the pass after the line
        nstart = int(round(L.GRID_BEHIND / t.ds))
        out[np.array(order[nstart:-1])] = tcum[nstart:-1] - tcum[nstart]
        return out

    T_r, T_9 = times(v_r, dsr, order_r), times(v_9, ds9, order_9)
    vr_idx = np.zeros(len(t.s))
    vr_idx[order_r[:-1]] = v_r[:-1]
    say(f"Corners: E9's driven line vs the |trackPos|<={ref} line. trackPos: + = left. 'out/in' is relative to the corner.")
    say("Model time = point-mass model on each line with the same mu; 'E9 real' = E9's real time through the same stretch.")
    say("| # | from-to (m) | turn | angle | min centre radius | E9 trackPos entry/apex/exit | line entry/apex/exit | "
        "min path radius E9 / line (m) | min speed E9 real / line model (km/h) | stretch (m) | model time E9 line / racing line (s) | gain (s) |")
    say("|---|---|---|---|---|---|---|---|---|---|---|---|")
    cs = corners(t)
    total_gain = 0.0
    for j, c in enumerate(cs):
        a, b = c["a"], c["b"]
        # stretch = braking zone and exit: up to 60 m around the corner, split halfway to the neighbouring corners
        prev_b = cs[j - 1]["b"] if j > 0 else -10 ** 9
        next_a = cs[j + 1]["a"] if j + 1 < len(cs) else 10 ** 9
        a0 = max(0, a - 60, (prev_b + a) // 2)
        b0 = min(len(t.s) - 1, b + 60, (b + next_a) // 2)
        sign = 1 if c["turn"] == "L" else -1
        apex = a + int(np.argmax(np.abs(t.k[a:b + 1])))

        def rel(lv, i):  # + = outside of the corner
            return -sign * lv[i] / t.half

        def ent_apx_ext(lv):
            return f"{rel(lv, a):+.2f}/{rel(lv, apex):+.2f}/{rel(lv, b):+.2f}"

        r9 = 1 / np.abs(k9[a:b + 1]).max()
        rr = 1 / np.abs(kr[a:b + 1]).max()
        dt9 = T_9[b0] - T_9[a0]
        dtr = T_r[b0] - T_r[a0]
        gain = dt9 - dtr
        total_gain += gain
        say(f"| {j + 1} | {t.s[a]:.0f}-{t.s[b]:.0f} | {c['turn']} | {c['deg']:.0f} deg | {c['rmin']:.1f} | "
            f"{ent_apx_ext(e9_l)} | {ent_apx_ext(l)} | {r9:.0f} / {rr:.0f} | "
            f"{e9_v[a:b + 1].min():.0f} / {vr_idx[a:b + 1].min() * 3.6:.0f} | {t.s[a0]:.0f}-{t.s[b0]:.0f} | "
            f"{dt9:.2f} / {dtr:.2f} | {gain:+.2f} |")
    say(f"Sum over corner stretches (no overlap): {total_gain:+.2f} s, the rest is on the straights; whole lap model: E9 line {lap_9:.2f} s, "
        f"racing line {lap_r:.2f} s ({lap_r - lap_9:+.2f} s).")
    say()
    say("Line tables: mapped/line_tp060.csv, mapped/line_tp075.csv, mapped/line_tp090.csv "
        "(distFromStart, trackPos, offset_m, curvature, radius_m, v_kmh = model speed).")
    with open(os.path.join(REPO, "results", "e11_step2_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    svg(t, lines, e9_l, os.path.join(REPO, "results", "e11_lines.svg"), title="Corkscrew: E9 line (dashed) and racing lines")
    svg(t, lines, e9_l, os.path.join(REPO, "results", "e11_lines_corkscrew.svg"), box=(2300, 2650),
        title="Zoom 2300-2650 m (the Corkscrew)")
    svg(t, lines, e9_l, os.path.join(REPO, "results", "e11_lines_hairpin.svg"), box=(3150, 3400),
        title="Zoom 3150-3400 m (last hairpin)")


if __name__ == "__main__":
    main()
