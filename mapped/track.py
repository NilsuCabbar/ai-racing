"""Track geometry from a TORCS track XML (our own implementation, standard library + numpy).

Rebuilds the 2D centreline of the main track from its segments, the way TORCS lays them out:
  - "str": straight of length lg
  - "lft" / "rgt": arc of `arc` degrees with `radius`; with an `end radius` the turn is split into
    steps = int(arc * (radius + end radius) / 2 / profil steps length) + 1 sub-arcs of equal length whose
    radius goes linearly from `radius` to `end radius`; the length is scaled so the steps turn exactly `arc`
    (a harmonic-mean radius). This reproduces TORCS's lap length, 3608.45 m (trace: 3608.3-3608.4 m).
Distances along the track are 2D lengths, like TORCS's distFromStart; the start line is the start of the
first segment. Left is +, like trackPos (+1 = left edge).

Elevation: each segment rises by grade x length; between its ends the height is a cubic (Hermite) curve whose end
slopes are the previous segment's and this segment's `profil end tangent`. This spline profile explains the car's
measured ride height better than a linear one (E17: R^2 0.92 vs 0.88-0.90). crest[i] = -z'' (1/m, + on a crest),
smoothed over 5 m; the closure error (0.77 m) is spread linearly over the lap.

    py mapped/track.py            # summary of the Corkscrew
"""
import math
import os
import re
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TRACK_XML = os.path.join(os.path.dirname(os.path.dirname(HERE)), "torch", "torcs", "tracks", "road", "corkscrew",
                         "corkscrew.xml")


def _attnums(sec):
    return {a.get("name"): float(a.get("val")) for a in sec.findall("attnum")}


def load_segments(path=TRACK_XML):
    """Main-track segments as dicts: name, type, lg / arc (rad), radius, end_radius, step_len; and the track width."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"<!DOCTYPE.*?\]>", "", text, flags=re.S)  # external entities (surfaces) are not needed
    text = re.sub(r"&[\w-]+;", "", text)
    root = ET.fromstring(text)
    main = root.find("section[@name='Main Track']")
    g = _attnums(main)
    width = g["width"]
    step_len = g.get("profil steps length", 0.0)
    segs = []
    for sec in main.find("section[@name='Track Segments']").findall("section"):
        a = _attnums(sec)
        typ = sec.find("attstr[@name='type']").get("val")
        seg = {"name": sec.get("name"), "type": typ, "step_len": a.get("profil steps length", step_len),
               "grade": a.get("grade", 0.0) / 100.0, "end_tangent": a.get("profil end tangent", 0.0) / 100.0}
        if typ == "str":
            seg["lg"] = a["lg"]
        else:
            seg["arc"] = math.radians(a["arc"])
            seg["radius"] = a["radius"]
            seg["end_radius"] = a.get("end radius", a["radius"])
            seg["lg"] = seg["arc"] * (seg["radius"] + seg["end_radius"]) / 2.0
        segs.append(seg)
    return segs, width


def pieces(segs):
    """Constant-curvature pieces (length, signed curvature, segment name) in track order."""
    out = []
    for s in segs:
        if s["type"] == "str":
            out.append((s["lg"], 0.0, s["name"]))
            continue
        sign = 1.0 if s["type"] == "lft" else -1.0
        r0, r1 = s["radius"], s["end_radius"]
        if r0 == r1:
            out.append((s["arc"] * r0, sign / r0, s["name"]))
            continue
        nom = s["arc"] * (r0 + r1) / 2.0
        steps = int(nom / s["step_len"]) + 1 if s["step_len"] > 0 else 1
        radii = [r0 + (r1 - r0) * (i / (steps - 1) if steps > 1 else 0.0) for i in range(steps)]
        # equal-length steps; the length is scaled so that the steps turn exactly `arc`
        step = s["arc"] / sum(1.0 / r for r in radii)
        for r in radii:
            out.append((step, sign / r, s["name"]))
    return out


def fix_lengths(segs):
    """Replace the nominal length of varying-radius turns by the stepped length used in pieces()."""
    for s in segs:
        if s["type"] != "str":
            s["lg"] = sum(p[0] for p in pieces([s]))
    return segs


class Track:
    """Centreline sampled every `ds` metres: s, x, y, yaw, curvature k (left +), and the half width."""

    def __init__(self, path=TRACK_XML, ds=1.0):
        self.segs, self.width = load_segments(path)
        fix_lengths(self.segs)
        self.half = self.width / 2.0
        pcs = pieces(self.segs)
        self.length = sum(p[0] for p in pcs)
        n = int(math.ceil(self.length / ds))
        self.ds = self.length / n
        s = np.arange(n) * self.ds
        # piecewise-constant curvature, integrated exactly per sample step
        ends = np.cumsum([p[0] for p in pcs])
        idx = np.minimum(np.searchsorted(ends, s, side="right"), len(pcs) - 1)
        k = np.array([pcs[i][1] for i in idx])
        names = [pcs[i][2] for i in idx]
        x, y, yaw = np.zeros(n + 1), np.zeros(n + 1), np.zeros(n + 1)
        for i in range(n):
            # exact arc integration over [s_i, s_i + ds], splitting at piece boundaries
            a, b, th, px, py = s[i], s[i] + self.ds, yaw[i], x[i], y[i]
            j = idx[i]
            while a < b - 1e-9:
                end = min(b, ends[j]) if j < len(pcs) else b
                L, kk = end - a, pcs[min(j, len(pcs) - 1)][1]
                if abs(kk) < 1e-12:
                    px, py = px + L * math.cos(th), py + L * math.sin(th)
                else:
                    th1 = th + kk * L
                    px += (math.sin(th1) - math.sin(th)) / kk
                    py -= (math.cos(th1) - math.cos(th)) / kk
                    th = th1
                a = end
                j += 1
            x[i + 1], y[i + 1], yaw[i + 1] = px, py, th
        self.s, self.k, self.names = s, k, names
        self.x, self.y, self.yaw = x[:n], y[:n], yaw[:n]
        self.closure = (x[n] - x[0], y[n] - y[0], math.degrees(yaw[n] - yaw[0]))
        self.z, self.crest = self._elevation()

    def _elevation(self):
        z = np.zeros(len(self.s))
        z0, t_in, start = 0.0, self.segs[-1]["end_tangent"], 0.0
        for sg in self.segs:
            L = sg["lg"]
            m = (self.s >= start) & (self.s < start + L)
            u = (self.s[m] - start) / L
            z1 = z0 + sg["grade"] * L
            z[m] = ((2 * u ** 3 - 3 * u ** 2 + 1) * z0 + (u ** 3 - 2 * u ** 2 + u) * L * t_in
                    + (-2 * u ** 3 + 3 * u ** 2) * z1 + (u ** 3 - u ** 2) * L * sg["end_tangent"])
            z0, t_in, start = z1, sg["end_tangent"], start + L
        z -= z0 * self.s / self.length              # spread the closure error
        zs = sum(np.roll(z, j) for j in range(-2, 3)) / 5.0
        d2 = (np.roll(zs, -1) - 2 * zs + np.roll(zs, 1)) / self.ds ** 2
        return z, -d2

    def idx(self, s):
        return np.asarray(np.round(np.mod(s, self.length) / self.ds), dtype=int) % len(self.s)

    def pose(self, s, offset=0.0):
        """Point at distance s, `offset` metres to the left of the centreline, and the track heading."""
        s = np.mod(s, self.length)
        i0 = np.floor(s / self.ds).astype(int) % len(self.s)
        f = s / self.ds - np.floor(s / self.ds)
        i1 = (i0 + 1) % len(self.s)
        yaw = np.where(i1 == 0, self.yaw[i0], self.yaw[i0] + f * (self.yaw[i1] - self.yaw[i0]))
        x = self.x[i0] + f * np.where(i1 == 0, self.ds * np.cos(self.yaw[i0]), self.x[i1] - self.x[i0])
        y = self.y[i0] + f * np.where(i1 == 0, self.ds * np.sin(self.yaw[i0]), self.y[i1] - self.y[i0])
        return x - offset * np.sin(yaw), y + offset * np.cos(yaw), yaw


if __name__ == "__main__":
    t = Track()
    segs = t.segs
    print(f"segments: {len(segs)} ({sum(s['type'] == 'str' for s in segs)} straight, "
          f"{sum(s['type'] != 'str' for s in segs)} turns, "
          f"{sum(s['type'] != 'str' and s['radius'] != s['end_radius'] for s in segs)} with end radius)")
    print(f"width {t.width} m, length {t.length:.2f} m")
    dx, dy, dyaw = t.closure
    print(f"closure: end - start = ({dx:.2f}, {dy:.2f}) m, heading {dyaw:.3f} deg (360 = one full turn)")
    tight = sorted({(round(1 / abs(k), 1), n) for k, n in zip(t.k, t.names) if k})[:6]
    print("tightest radii:", ", ".join(f"{r} m ({n})" for r, n in tight))
