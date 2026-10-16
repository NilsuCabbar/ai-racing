"""Map driver: follows a precomputed racing line and speed profile (mapped/table.csv) by distFromStart.

Standard library only. The table comes from mapped/build_table.py (track XML -> centreline -> racing line ->
point-mass speeds). Per control step:
  - steering (ctrl 0): pure pursuit. The car is placed on the map from distFromStart, trackPos and angle; it steers
    towards the line point `look_t` seconds ahead (at least `look_min` m) with wheel angle atan(2 L sin(alpha) / d).
  - steering (ctrl 1): feedforward from the line's curvature `ff_lead` seconds ahead, atan(L * k) * ff_gain, plus a
    pure-pursuit correction that only acts on the deviation: alpha minus the angle the target point would have if the
    car were on the line (k * d / 2), so the curvature is not counted twice.
  - speed: target = scale * table speed `lead_t` seconds ahead; full throttle below target - full_band,
    proportional inside the band, brake (speed - target) * brake_gain above it.
  - safety from the live sensors: a speed cap from the free distance straight ahead (safe_decel, safe_margin,
    safe_floor), and no throttle near the edge while moving outwards (edge_pos).
  - ABS, traction control and rpm gear shifting as in fast/my_driver.py (Tuna's driver).
Sensors: angle (track heading - car heading), trackPos (+1 left edge), speedX, track[19], rpm, wheelSpinVel.
"""
import bisect
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "table.csv")

DEFAULTS = {
    "scale": 1.0,           # share of the table speed (the grip scale is in the table, see build_table.py)
    "look_t": 0.35,         # s, pure-pursuit look-ahead time
    "look_min": 6.0,        # m, shortest look-ahead
    "steer_gain": 1.0,      # multiplies the pure-pursuit wheel angle (ctrl 0) / the correction (ctrl 1)
    "ctrl": 0,              # 0 = pure pursuit, 1 = curvature feedforward + pure-pursuit correction
    "ff_gain": 1.0,         # ctrl 1: share of the feedforward wheel angle
    "ff_lead": 0.1,         # s, ctrl 1: the curvature is read this far ahead (steering lag)
    "lead_t": 0.15,         # s, the target speed is read this far ahead
    "full_band": 8.0,       # km/h
    "brake_gain": 0.08,     # brake per km/h above target
    "safe_decel": 35.0,     # m/s^2, sensor speed cap (high = only catches real surprises)
    "safe_margin": 4.0,     # m
    "safe_floor": 60.0,     # km/h, the sensor cap never goes below this
    "edge_pos": 0.97,       # |trackPos| above which throttle is cut while moving outwards (0 = off)
    "max_gear": 6,          # the kit client turns gear 7 into neutral
    "up_rpm": 17095.3119,
    "down_rpm": 10421.859,
    "tc_thresh": 13.7772,   # cut throttle if rear-front wheel spin difference (rad/s) exceeds this
    "tc_cut": 0.6574,
    "abs_slip": 0.0,        # 0 = ABS off (as in E9)
    "abs_range": 0.1,
}

WHEELBASE = 2.95             # m, car1-ow1 front axle 1.6 m, rear axle -1.35 m
STEER_LOCK = math.radians(21.0)  # car1-ow1 steer lock; steer = 1 means this wheel angle
FRONT_WHEEL_R = 0.3024
STEP_DT = 0.02

_state = {"gear": 1, "pos": None}


def _load(path=TABLE):
    with open(path, encoding="utf-8") as f:
        head = f.readline()
        meta = dict(kv.split("=") for kv in head.strip("# \n").split())
        rows = list(csv.DictReader(f))
    cols = {k: [float(r[k]) for r in rows] for k in rows[0]}
    return float(meta["length"]), float(meta["ds"]), cols


LENGTH, DS, T = _load()
N = len(T["s"])


def _interp(col, s):
    s %= LENGTH
    x = s / DS
    i = int(x)
    f = x - i
    a = T[col][i % N]
    b = T[col][(i + 1) % N]
    return a + f * (b - a)


def _yaw(s):
    s %= LENGTH
    x = s / DS
    i = int(x)
    a = T["yaw"][i % N]
    b = T["yaw"][(i + 1) % N]
    while b - a > math.pi:
        b -= 2 * math.pi
    while b - a < -math.pi:
        b += 2 * math.pi
    return a + (x - i) * (b - a)


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def drive(c, p=None):
    prm = dict(DEFAULTS)
    if p:
        prm.update(p)
    S, R = c.S.d, c.R.d
    speed = S["speedX"]                 # km/h
    v = max(speed / 3.6, 0.0)           # m/s
    s = S["distFromStart"]
    pos = S["trackPos"]
    track = S["track"]

    # --- where the car is on the map ---
    yaw_t = _yaw(s)
    off = pos * 6.0                      # half width 6 m
    cx = _interp("cx", s) - off * math.sin(yaw_t)
    cy = _interp("cy", s) + off * math.cos(yaw_t)
    car_yaw = yaw_t - S["angle"]

    # --- steering: pure pursuit towards the line point ahead ---
    look = max(prm["look_min"], v * prm["look_t"])
    tx, ty = _interp("lx", s + look), _interp("ly", s + look)
    dx, dy = tx - cx, ty - cy
    alpha = math.atan2(dy, dx) - car_yaw
    alpha = (alpha + math.pi) % (2 * math.pi) - math.pi
    dist = max(1.0, math.hypot(dx, dy))
    if prm["ctrl"] >= 0.5:
        k_mid = _interp("k", s + 0.5 * look)            # the line's curvature between here and the target point
        corr = alpha - math.asin(_clip(k_mid * dist / 2.0, -1.0, 1.0))
        k_ff = _interp("k", s + v * prm["ff_lead"])
        wheel = (prm["ff_gain"] * math.atan(WHEELBASE * k_ff)
                 + prm["steer_gain"] * math.atan(2.0 * WHEELBASE * math.sin(corr) / dist))
    else:
        wheel = math.atan(2.0 * WHEELBASE * math.sin(alpha) / dist) * prm["steer_gain"]
    R["steer"] = _clip(wheel / STEER_LOCK, -1.0, 1.0)

    # --- target speed from the table, with a sensor safety cap ---
    target = prm["scale"] * _interp("v", s + v * prm["lead_t"]) * 3.6
    front = max(track[8], track[9], track[10])
    if front > 0:
        cap = math.sqrt((prm["safe_floor"] / 3.6) ** 2 + 2.0 * prm["safe_decel"] * max(0.0, front - prm["safe_margin"]))
        target = min(target, cap * 3.6)

    # edge guard: near the edge and still moving outwards -> no throttle
    outward = _state["pos"] is not None and abs(pos) > abs(_state["pos"])
    _state["pos"] = pos
    edge = prm["edge_pos"] > 0 and abs(pos) > prm["edge_pos"] and outward

    # --- throttle / brake ---
    if speed > target:
        brake = _clip((speed - target) * prm["brake_gain"], 0.0, 1.0)
        if prm["abs_slip"] > 0 and speed > 10:
            w = S["wheelSpinVel"]
            wheel_v = (w[0] + w[1]) / 2.0 * FRONT_WHEEL_R * 3.6
            slip = (speed - wheel_v) / speed
            if slip > prm["abs_slip"]:
                brake *= _clip(1.0 - (slip - prm["abs_slip"]) / prm["abs_range"], 0.0, 1.0)
        R["brake"] = brake
        R["accel"] = 0.0
    else:
        R["brake"] = 0.0
        R["accel"] = _clip((target - speed) / prm["full_band"], 0.0, 1.0) if prm["full_band"] > 0 else 1.0
        if edge:
            R["accel"] = 0.0

    # --- traction control ---
    w = S["wheelSpinVel"]
    if (w[2] + w[3]) - (w[0] + w[1]) > prm["tc_thresh"]:
        R["accel"] = max(0.0, R["accel"] - prm["tc_cut"])

    # --- gears (rpm based) ---
    g = _state["gear"]
    if speed < 1:
        g = 1
    elif S["rpm"] > prm["up_rpm"] and g < prm["max_gear"]:
        g += 1
    elif S["rpm"] < prm["down_rpm"] and g > 1:
        g -= 1
    _state["gear"] = g
    R["gear"] = g
