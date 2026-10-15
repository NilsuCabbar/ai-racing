"""Rule-based driver: computes a target speed from the free distance ahead and brakes when needed.

Standard library only. Used by tuna/run_lap.py.
Sensors (from the Client in torcs_jm_par.py): angle, trackPos, speedX, track[19], rpm, wheelSpinVel.
track[] beams: -45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45 (degrees), index 9 = straight ahead.
"""
import math

DEFAULTS = {
    "max_speed": 200.0,     # km/h, upper limit on straights
    "min_speed": 45.0,      # km/h, lower limit inside corners
    "decel": 9.0,           # m/s^2, assumed braking deceleration (smaller = brakes earlier)
    "margin": 15.0,         # m, this much of the free distance ahead is treated as unusable
    "steer_lock": 0.785398, # rad
    "center_k": 0.5,        # pull towards the track centre (trackPos gain)
    "brake_gain": 0.04,     # brake per km/h above target
    "accel_gain": 0.05,     # throttle per km/h below target
    "up_rpm": 7500.0,
    "down_rpm": 3500.0,
    "tc_thresh": 4.0,       # cut throttle if rear-front wheel spin difference (rad/s) exceeds this
    "tc_cut": 0.2,          # amount of throttle to cut
    "aim_w": 0.0,           # 0..1, blend steering towards the longest beam
    "aim_sign": -1.0,       # sign of the beam angle (+1 / -1), not searched
    "mix": 0.0,             # 0..1, share of the longest-beam distance instead of the front distance in the target speed
    "smooth": 0.0,          # 0..0.9, steering low-pass filter (higher = smoother)
}

BEAMS_DEG = [-45, -19, -12, -7, -4, -2.5, -1.7, -1, -0.5, 0, 0.5, 1, 1.7, 2.5, 4, 7, 12, 19, 45]

_state = {"gear": 1, "steer": 0.0}


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def drive(c, p=None):
    prm = dict(DEFAULTS)
    if p:
        prm.update(p)
    S, R = c.S.d, c.R.d
    speed = S["speedX"]
    track = S["track"]

    # --- steering ---
    target_angle = S["angle"] - S["trackPos"] * prm["center_k"]
    steer = _clip(target_angle / prm["steer_lock"], -1.0, 1.0)
    imax = max(range(len(track)), key=lambda i: track[i])
    if prm["aim_w"] > 0:
        aim = _clip(prm["aim_sign"] * math.radians(BEAMS_DEG[imax]) / prm["steer_lock"], -1.0, 1.0)
        steer = (1.0 - prm["aim_w"]) * steer + prm["aim_w"] * aim
    steer = prm["smooth"] * _state["steer"] + (1.0 - prm["smooth"]) * steer
    _state["steer"] = steer
    R["steer"] = _clip(steer, -1.0, 1.0)

    # --- target speed: the speed from which we can still stop in the free distance ahead ---
    front = max(track[8], track[9], track[10])  # three centre beams
    front = (1.0 - prm["mix"]) * front + prm["mix"] * track[imax]
    free = max(0.0, front - prm["margin"])
    v_allowed = math.sqrt((prm["min_speed"] / 3.6) ** 2 + 2.0 * prm["decel"] * free) * 3.6
    target = _clip(v_allowed, prm["min_speed"], prm["max_speed"])
    # slow down a bit more when the steering is heavily loaded
    target *= 1.0 - 0.3 * abs(R["steer"])
    target = max(prm["min_speed"], target)

    # --- throttle / brake ---
    if speed > target:
        R["brake"] = _clip((speed - target) * prm["brake_gain"], 0.0, 1.0)
        R["accel"] = 0.0
    else:
        R["brake"] = 0.0
        R["accel"] = _clip((target - speed) * prm["accel_gain"] + 0.1, 0.0, 1.0)

    # --- traction control: cut throttle when the rear wheels spin faster than the front wheels ---
    w = S["wheelSpinVel"]
    if (w[2] + w[3]) - (w[0] + w[1]) > prm["tc_thresh"]:
        R["accel"] = max(0.0, R["accel"] - prm["tc_cut"])

    # --- gears (rpm based) ---
    g = _state["gear"]
    if speed < 1:
        g = 1
    elif S["rpm"] > prm["up_rpm"] and g < 6:
        g += 1
    elif S["rpm"] < prm["down_rpm"] and g > 1:
        g -= 1
    _state["gear"] = g
    R["gear"] = g
