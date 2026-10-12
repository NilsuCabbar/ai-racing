"""my_driver.py parametrelerini rastgele arama + yerel iyilestirme ile ayarlar.

Kullanim (TORCS'ta yaris bekleme modundayken):
    py search.py --n 30

Her deneme lap_runner.py'yi alt surec olarak dusuk oncelikle calistirir ve runs.csv'ye yazar.
En iyi parametreler best_params.json'a kaydedilir. Ctrl+C ile durdurulabilir; kayitlar korunur.
Puan = tur suresi + cezalar (dusuk iyi). Bitirilemeyen tur buyuk ceza alir.
"""
import argparse
import csv
import json
import random
import subprocess
import sys

# (alt, ust) sinirlar
SPACE = {
    "max_speed": (120.0, 400.0),
    "min_speed": (30.0, 130.0),
    "decel": (5.0, 40.0),
    "margin": (0.0, 40.0),
    "center_k": (0.2, 2.0),
    "brake_gain": (0.02, 0.5),
    "aim_w": (0.0, 1.0),
    "mix": (0.0, 1.0),
    "smooth": (0.0, 0.95),
    "up_rpm": (7000.0, 18500.0),
    "down_rpm": (3000.0, 15000.0),
    "tc_thresh": (1.0, 20.0),
    "tc_cut": (0.05, 0.6),
}
START = {"max_speed": 200.0, "min_speed": 45.0, "decel": 9.0, "margin": 15.0,
         "center_k": 0.5, "brake_gain": 0.04,
         "aim_w": 0.3, "mix": 0.0, "smooth": 0.0,
         "up_rpm": 7500.0, "down_rpm": 3500.0, "tc_thresh": 4.0, "tc_cut": 0.2}  # my_driver.py varsayilanlari
BELOW_NORMAL = 0x00004000  # Windows: dusuk oncelik


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def evaluate(params, tag):
    cmd = [sys.executable, "lap_runner.py", "--driver", "mine", "--max-seconds", "200",
           "--params", json.dumps(params), "--tag", tag]
    try:
        subprocess.run(cmd, creationflags=BELOW_NORMAL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=420)
    except subprocess.TimeoutExpired:
        return None, {}
    with open("runs.csv", newline="", encoding="utf-8") as f:
        last = list(csv.DictReader(f))[-1]
    if last["tag"] != tag:
        return None, last  # kayit dusmedi (baglanti yok?)
    if last["result"] != "finished" or not last["lap_time_s"]:
        # bitiremedi: ne kadar yol gittiyse o kadar az ceza
        return 1000.0 - float(last["dist_raced_m"]) / 4.0, last
    score = float(last["lap_time_s"]) + 3.0 * float(last["off_track_s"]) + 0.05 * float(last["max_damage"])
    return score, last


FIX = {}


def sample_random():
    return {k: (FIX[k] if k in FIX else round(random.uniform(*v), 3)) for k, v in SPACE.items()}


def perturb(best, sigma):
    out = {}
    for k, (lo, hi) in SPACE.items():
        if k in FIX:
            out[k] = FIX[k]
            continue
        out[k] = round(clip(best[k] + random.gauss(0, sigma * (hi - lo)), lo, hi), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="toplam deneme sayisi")
    ap.add_argument("--random-frac", type=float, default=0.3, help="denemelerin bu kadari rastgele, kalani en iyiye yakin")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--fix", default="{}", help="sabit tutulacak parametreler (JSON), orn. {\"up_rpm\": 15000}")
    ap.add_argument("--out", default="best_params.json", help="en iyiyi yazacagi dosya")
    ap.add_argument("--fresh", action="store_true", help="best_params.json yerine START ile basla")
    ap.add_argument("--prefix", default="search", help="runs.csv etiket oneki")
    args = ap.parse_args()
    random.seed(args.seed)

    FIX.update(json.loads(args.fix))
    start = dict(START)
    try:  # onceki en iyiden basla
        start.update(json.load(open("best_params.json"))["params"])
    except (OSError, KeyError, ValueError):
        pass
    start.update(FIX)
    best, best_score = dict(start), None
    n_random = int(args.n * args.random_frac)
    for i in range(args.n):
        if i == 0:
            cand = dict(start)  # once referans
        elif best_score is None or best_score >= 900:
            cand = perturb(best, sigma=0.15)  # henuz bitiren yok: en iyiden genis sapma
        elif i <= n_random:
            cand = sample_random()
        else:
            cand = perturb(best, sigma=0.08)
        score, row = evaluate(cand, f"{args.prefix}{i:03d}")
        if score is None:
            print("Kayit dusmedi, TORCS yarisi bekleme modunda mi? Durduruluyor.")
            break
        flag = ""
        if best_score is None or score < best_score:
            best, best_score, flag = cand, score, "  <-- YENI EN IYI"
            json.dump({"score": best_score, "params": best}, open(args.out, "w"), indent=2)
        print(f"[{i + 1}/{args.n}] puan={score:.2f} sonuc={row['result']} tur={row['lap_time_s']} "
              f"pist_disi={row['off_track_s']} hasar={row['max_damage']}{flag}", flush=True)
    print("\nEN IYI:", best_score, json.dumps(best))


if __name__ == "__main__":
    main()
