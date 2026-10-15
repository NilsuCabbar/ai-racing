"""Bizim surucu: onu goren mesafeye gore hedef hiz hesaplar, gerekirse fren yapar.

Sadece standart kutuphane. lap_runner.py --driver mine ile kullanilir.
Sensorler (torcs_jm_par.py'deki Client'tan): angle, trackPos, speedX, track[19], rpm, wheelSpinVel.
track[] isinlari: -45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45 (derece), 9 = tam onu.
"""
import math

DEFAULTS = {
    "max_speed": 200.0,     # km/h, duzlukte ust sinir
    "min_speed": 45.0,      # km/h, viraj icinde alt sinir
    "decel": 9.0,           # m/s^2, formuldeki varsayilan fren gucu (kucukse erken frenler)
    "margin": 15.0,         # m, onumuzdeki boslugun bu kadari "kullanilmaz" sayilir
    "steer_lock": 0.785398, # rad
    "center_k": 0.5,        # pist ortasina cekme (trackPos katsayisi)
    "brake_gain": 0.04,     # (hiz - hedef) km/h basina fren
    "accel_gain": 0.05,     # (hedef - hiz) km/h basina gaz
    "up_rpm": 7500.0,
    "down_rpm": 3500.0,
    "tc_thresh": 4.0,       # arka-on tekerlek donus farki (rad/s) bunu gecerse gazi kes
    "tc_cut": 0.2,          # kesilecek gaz miktari
    "aim_w": 0.0,           # 0..1, direksiyonu en uzun isina dogru karistir
    "aim_sign": -1.0,       # isin acisi isaretinin yonu (+1 / -1), arama disi
    "mix": 0.0,             # 0..1, hedef hizda on mesafe yerine en uzun isin mesafesi payi
    "smooth": 0.0,          # 0..0.9, direksiyon alcak gecirgen filtre (yuksek = yumusak)
    # vites (shift_gear). shift_hold=0 -> eski davranis (olculen rpm, her tick vites)
    "shift_hold": 0.0,      # s, iki vites degisimi arasi en az sure
    "gear_hyst": 1500.0,    # rpm, dusurunce alt viteste en az up_rpm - gear_hyst kalmali (hemen geri takmasin)
    "corner_steer": 0.3,    # |steer| bunun ustundeyse viraj sayilir
    "corner_down_rpm": 7000.0,  # virajda ancak yol devri bunun altina inerse vites dusur
}

BEAMS_DEG = [-45, -19, -12, -7, -4, -2.5, -1.7, -1, -0.5, 0, 0.5, 1, 1.7, 2.5, 4, 7, 12, 19, 45]

# car1-ow1 vites oranlari (torcs/drivers/scr_server/0/default.xml) ve
# motor devri / (km/h * vites orani): kaymasiz surusten olculdu (baseline/trace.csv, 4.-6. vites ~40.5)
GEAR_RATIOS = [3.9, 2.9, 2.3, 1.87, 1.68, 1.54]
RPM_PER_KMH_RATIO = 40.5

_state = {"gear": 1, "steer": 0.0, "since_shift": 0}


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def drive(c, p=None):
    prm = dict(DEFAULTS)
    if p:
        prm.update(p)
    S, R = c.S.d, c.R.d
    speed = S["speedX"]
    track = S["track"]

    # --- direksiyon ---
    target_angle = S["angle"] - S["trackPos"] * prm["center_k"]
    steer = _clip(target_angle / prm["steer_lock"], -1.0, 1.0)
    imax = max(range(len(track)), key=lambda i: track[i])
    if prm["aim_w"] > 0:
        aim = _clip(prm["aim_sign"] * math.radians(BEAMS_DEG[imax]) / prm["steer_lock"], -1.0, 1.0)
        steer = (1.0 - prm["aim_w"]) * steer + prm["aim_w"] * aim
    steer = prm["smooth"] * _state["steer"] + (1.0 - prm["smooth"]) * steer
    _state["steer"] = steer
    R["steer"] = _clip(steer, -1.0, 1.0)

    # --- hedef hiz: onumuzdeki bosluktan "durabilecegim hiz" ---
    front = max(track[8], track[9], track[10])  # orta uc isin
    front = (1.0 - prm["mix"]) * front + prm["mix"] * track[imax]
    free = max(0.0, front - prm["margin"])
    v_allowed = math.sqrt((prm["min_speed"] / 3.6) ** 2 + 2.0 * prm["decel"] * free) * 3.6
    target = _clip(v_allowed, prm["min_speed"], prm["max_speed"])
    # direksiyon cok doluysa biraz daha yavasla
    target *= 1.0 - 0.3 * abs(R["steer"])
    target = max(prm["min_speed"], target)

    # --- gaz / fren ---
    if speed > target:
        R["brake"] = _clip((speed - target) * prm["brake_gain"], 0.0, 1.0)
        R["accel"] = 0.0
    else:
        R["brake"] = 0.0
        R["accel"] = _clip((target - speed) * prm["accel_gain"] + 0.1, 0.0, 1.0)

    # --- cekis kontrolu: arka tekerlek on tekerlekten cok donuyorsa gazi kes ---
    w = S["wheelSpinVel"]
    if (w[2] + w[3]) - (w[0] + w[1]) > prm["tc_thresh"]:
        R["accel"] = max(0.0, R["accel"] - prm["tc_cut"])

    R["gear"] = shift_gear(S, prm, R["steer"])


def shift_gear(S, prm, steer):
    """Vites secimi. Patinaj/havalanmada olculen rpm sicradigi icin karar hizdan hesaplanan
    "yol devri" ile verilir; en az shift_hold s bekler, inerken histerezis ve viraj siniri uygular."""
    g = _state["gear"]
    speed = S["speedX"]
    if prm["shift_hold"] <= 0:  # eski davranis: olculen rpm, her tick degisebilir
        if speed < 1:
            g = 1
        elif S["rpm"] > prm["up_rpm"] and g < 6:
            g += 1
        elif S["rpm"] < prm["down_rpm"] and g > 1:
            g -= 1
        _state["gear"] = g
        return g

    _state["since_shift"] += 1
    if speed < 1:
        _state["gear"] = 1
        return 1
    if _state["since_shift"] * 0.02 < prm["shift_hold"]:
        return g
    road_rpm = speed * RPM_PER_KMH_RATIO * GEAR_RATIOS[g - 1]
    new_g = g
    if road_rpm > prm["up_rpm"] and g < 6:
        new_g = g + 1
    elif road_rpm < prm["down_rpm"] and g > 1:
        lower_rpm = speed * RPM_PER_KMH_RATIO * GEAR_RATIOS[g - 2]
        cornering = abs(steer) > prm["corner_steer"]
        if lower_rpm < prm["up_rpm"] - prm["gear_hyst"] and (not cornering or road_rpm < prm["corner_down_rpm"]):
            new_g = g - 1
    if new_g != g:
        _state["gear"] = new_g
        _state["since_shift"] = 0
    return new_g
