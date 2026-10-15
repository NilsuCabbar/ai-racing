"""Rule-based driver: computes a target speed from the track sensors and brakes when needed.

Standard library only. Used by tuna/run_lap.py.
Sensors (from the Client in torcs_jm_par.py): angle, trackPos, speedX, track[19], rpm, wheelSpinVel.
track[] beams: -45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45 (degrees), index 9 = straight ahead.
Negative beam angles point to the left of the car.

Only live sensor values are used, so the driver works on any track (no positions or track maps).
"""
import math

DEFAULTS = {
    "max_speed": 200.0,     # km/h, upper limit on straights
    "min_speed": 45.0,      # km/h, lower limit inside corners
    "decel": 9.0,           # m/s^2, assumed braking deceleration (smaller = brakes earlier)
    "margin": 15.0,         # m, this much of the free distance ahead is treated as unusable
    "steer_lock": 0.785398, # rad
    "center_k": 0.5,        # pull towards the target line (trackPos gain)
    "brake_gain": 0.04,     # brake per km/h above target
    "accel_gain": 0.05,     # throttle per km/h below target
    "max_gear": 6,          # the car has 7 gears, but the kit client (torcs_jm_par.py) turns gear 7 into neutral
    "up_rpm": 7500.0,
    "down_rpm": 3500.0,
    "tc_thresh": 4.0,       # cut throttle if rear-front wheel spin difference (rad/s) exceeds this
    "tc_cut": 0.2,          # amount of throttle to cut
    "aim_w": 0.0,           # 0..1, blend steering towards the longest beam
    "aim_sign": -1.0,       # sign of the beam angle (+1 / -1), not searched
    "mix": 0.0,             # 0..1, share of the longest-beam distance instead of the front distance in the target speed
    "smooth": 0.0,          # 0..0.9, steering low-pass filter (higher = smoother)
    "steer_slow": 0.3,      # target speed is reduced by this share at full steering
    # ABS: release the brake when the front wheels turn slower than the car moves
    "abs_slip": 0.0,        # slip ratio where ABS starts (0 = ABS off)
    "abs_range": 0.1,       # slip above abs_slip that releases the brake completely
    # throttle: full throttle below target - full_band, proportional inside the band
    "full_band": 0.0,       # km/h (0 = old proportional throttle)
    # corner speed from sensor geometry (replaces the constant min_speed floor)
    "mu": 0.0,              # assumed lateral grip in g (0 = off)
    "chord_k": 50.0,        # m, sight-distance cap on the corner radius: R <= D_max^2 / chord_k
    # trail braking: less brake while steering, so the front wheels keep grip
    "brake_steer": 0.0,     # brake is scaled by (1 - brake_steer * |steer|)
    # safety nets that allow a more aggressive corner speed
    "rise_rate": 0.0,       # km/h per s, max rise of the target speed (0 = off)
    "slide_k": 0.0,         # target reduction per km/h of sideways speed above slide_thresh (0 = off)
    "slide_thresh": 5.0,    # km/h of sideways speed (speedY) that is still fine
    "edge_pos": 0.0,        # |trackPos| above which throttle is cut while moving outwards (0 = off)
    # racing line: outside before a corner, inside at the apex
    "line_out": 0.0,        # trackPos offset towards the outside before a corner (0 = off)
    "line_in": 0.0,         # trackPos offset towards the inside in the corner
    "line_dist": 80.0,      # m, front distance below which the car aims for the inside
    "line_min_deg": 4.0,    # longest-beam angle (deg) that counts as a corner ahead
}

BEAMS_DEG = [-45, -19, -12, -7, -4, -2.5, -1.7, -1, -0.5, 0, 0.5, 1, 1.7, 2.5, 4, 7, 12, 19, 45]
FRONT_WHEEL_R = 0.3024  # m, 12 in rim + 150 mm tyre wall (car1-ow1)
REAR_WHEEL_R = 0.3151   # m, 13 in rim + 150 mm tyre wall
G = 9.81
STEP_DT = 0.02  # s, TORCS calls the driver 50 times per second

_state = {"gear": 1, "steer": 0.0, "target": None, "pos": None}


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _longest_beam(track):
    """Index of the longest beam; ties (all 200 m) resolve to the one closest to straight ahead."""
    best = max(track)
    cands = [i for i, d in enumerate(track) if d >= best - 0.5]
    return min(cands, key=lambda i: abs(i - 9))


def drive(c, p=None):
    prm = dict(DEFAULTS)
    if p:
        prm.update(p)
    S, R = c.S.d, c.R.d
    speed = S["speedX"]
    track = S["track"]
    imax = _longest_beam(track)
    dmax = track[imax]
    beam_deg = BEAMS_DEG[imax]
    front = max(track[8], track[9], track[10])  # three centre beams

    # --- racing line: which trackPos to aim for ---
    # trackPos is +1 at the left edge, -1 at the right edge; beam angles < 0 point left.
    line = 0.0
    if (prm["line_out"] or prm["line_in"]) and abs(beam_deg) >= prm["line_min_deg"] and dmax < 199.0:
        turn = 1.0 if beam_deg < 0 else -1.0  # +1 = left-hand corner ahead
        if front > prm["line_dist"]:
            line = -turn * prm["line_out"]  # outside before the corner
        else:
            line = turn * prm["line_in"]  # inside towards the apex
        line = _clip(line, -0.85, 0.85)

    # --- steering ---
    target_angle = S["angle"] - (S["trackPos"] - line) * prm["center_k"]
    steer = _clip(target_angle / prm["steer_lock"], -1.0, 1.0)
    if prm["aim_w"] > 0:
        aim = _clip(prm["aim_sign"] * math.radians(beam_deg) / prm["steer_lock"], -1.0, 1.0)
        steer = (1.0 - prm["aim_w"]) * steer + prm["aim_w"] * aim
    steer = prm["smooth"] * _state["steer"] + (1.0 - prm["smooth"]) * steer
    _state["steer"] = steer
    R["steer"] = _clip(steer, -1.0, 1.0)

    # --- corner speed: radius of the arc that starts along our heading and ends at the far point ---
    # A circle tangent to the heading through a point at distance D and angle a has R = D / (2 sin a).
    # A road that bends with radius R only lets you see a chord of about sqrt(chord_k * R) ahead,
    # so a short longest beam also caps the radius: R <= D^2 / chord_k.
    v_floor = prm["min_speed"]
    if prm["mu"] > 0:
        radius = dmax * dmax / prm["chord_k"]
        if abs(beam_deg) >= 1.0:
            radius = min(radius, dmax / (2.0 * math.sin(math.radians(abs(beam_deg)))))
        v_corner = math.sqrt(prm["mu"] * G * radius) * 3.6
        v_floor = _clip(v_corner, prm["min_speed"], prm["max_speed"])

    # --- target speed: the speed from which we can still slow to v_floor in the free distance ahead ---
    look = (1.0 - prm["mix"]) * front + prm["mix"] * dmax
    free = max(0.0, look - prm["margin"])
    v_allowed = math.sqrt((v_floor / 3.6) ** 2 + 2.0 * prm["decel"] * free) * 3.6
    target = _clip(v_allowed, prm["min_speed"], prm["max_speed"])
    # slow down a bit more when the steering is heavily loaded
    target *= 1.0 - prm["steer_slow"] * abs(R["steer"])
    # slide guard: the car is sliding sideways, so the corner is faster than its grip
    if prm["slide_k"] > 0:
        target *= _clip(1.0 - prm["slide_k"] * max(0.0, abs(S["speedY"]) - prm["slide_thresh"]), 0.3, 1.0)
    target = max(prm["min_speed"], target)
    # the target may drop at once but only rises at rise_rate (km/h per second), so a single
    # optimistic sensor reading cannot open the throttle fully
    if prm["rise_rate"] > 0 and _state["target"] is not None:
        target = min(target, _state["target"] + prm["rise_rate"] * STEP_DT)
    _state["target"] = target

    # edge guard: near the edge and still moving outwards -> no throttle
    pos = S["trackPos"]
    outward = _state["pos"] is not None and abs(pos) > abs(_state["pos"])
    _state["pos"] = pos
    edge = prm["edge_pos"] > 0 and abs(pos) > prm["edge_pos"] and outward

    # --- throttle / brake ---
    if speed > target:
        brake = _clip((speed - target) * prm["brake_gain"], 0.0, 1.0)
        brake *= _clip(1.0 - prm["brake_steer"] * abs(R["steer"]), 0.0, 1.0)
        if prm["abs_slip"] > 0 and speed > 10:
            w = S["wheelSpinVel"]
            wheel = (w[0] + w[1]) / 2.0 * FRONT_WHEEL_R * 3.6
            slip = (speed - wheel) / speed
            if slip > prm["abs_slip"]:
                brake *= _clip(1.0 - (slip - prm["abs_slip"]) / prm["abs_range"], 0.0, 1.0)
        R["brake"] = brake
        R["accel"] = 0.0
    else:
        R["brake"] = 0.0
        if prm["full_band"] > 0:
            R["accel"] = _clip((target - speed) / prm["full_band"], 0.1, 1.0)
        else:
            R["accel"] = _clip((target - speed) * prm["accel_gain"] + 0.1, 0.0, 1.0)
        if edge:
            R["accel"] = 0.0

    # --- traction control: cut throttle when the rear wheels spin faster than the front wheels ---
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
