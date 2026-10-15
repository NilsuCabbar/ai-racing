"""my_driver.py parametrelerini CMA-ES ile ayarlar (sadece numpy). Headless calisir, TORCS menusu gerekmez.

Her aday baseline/run_lap.py ile deterministik (-t 1000000) bir tur kosar:
  - tur bitmedi veya hasar > 0  -> ELENIR (puan = 1000 - gidilen_mesafe/10, arama yonunu kaybetmesin diye;
                                   tur ilk hasarda kesilir: --stop-on-damage)
  - temiz tur                    -> puan = tur suresi
Saglamlik dogrulamasi: her nesilde (1) kabul edilmis en iyiden hizli temiz adaylar ve (2) neslin en hizli temiz
adayi --robust-n kez --robust-jitter ile kosulur. --max-robust-crashes'tan fazla kaza varsa aday ELENIR
(puan = 900 + tur suresi/100, CMA-ES bu bolgeden uzaklassin diye) ve kabul edilmez.

Sonucta ayri ayri raporlanir:
  (a) en hizli temiz aday       (deterministik tur, saglamliktan bagimsiz)
  (b) jitter altinda en saglam  (dogrulanan adaylar icinde en az kaza, esitlikte daha hizli)
  ve kabul edilen en iyi        (dogrulamayi gecen en hizli)

Kullanim (repo kokunden):
    ..\\torcs-env\\Scripts\\python cmaes_search.py --gens 3 --popsize 8          # kisa test
    ..\\torcs-env\\Scripts\\python cmaes_search.py --gens 40 --out results\\cmaes_e4.json
    ... --fix "{\\"shift_hold\\": 0}"   (sabit tutulacak parametreler)

Kayitlar: --log (her aday ve her dogrulama), baseline/runs.csv ve baseline/robust.csv (run_lap.py).
--out: kabul edilen en iyi ("params") + fastest_clean + most_robust; ayrica <out>_fastest.json ve <out>_robust.json
(run_lap.py --params-file ile dogrudan kosulabilir).
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_LAP = os.path.join(HERE, "baseline", "run_lap.py")

# (alt, ust) sinirlar; search.py'deki SPACE + vites parametreleri
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
    "shift_hold": (0.0, 0.5),
    "gear_hyst": (0.0, 5000.0),
    "corner_steer": (0.1, 1.0),
    "corner_down_rpm": (3000.0, 12000.0),
}


def run_lap(params, extra, tag):
    cmd = [sys.executable, "-W", "ignore", RUN_LAP, "--json", "--params-file", "",
           "--params", json.dumps(params), "--tag", tag] + extra
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE).stdout
    lines = [ln for ln in out.splitlines() if ln.startswith("JSON ")]
    return json.loads(lines[-1][5:]) if lines else {"status": "error"}


def write_params(path, entry):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, default=3)
    ap.add_argument("--popsize", type=int, default=0, help="0 = CMA-ES default 4 + 3 ln(n)")
    ap.add_argument("--sigma", type=float, default=0.05,
                    help="initial step size, as a fraction of each range (0.15 crashed most candidates)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", default=os.path.join(HERE, "best_params.json"))
    ap.add_argument("--fix", default="{}", help="JSON of parameters to keep fixed")
    ap.add_argument("--robust-n", type=int, default=5, help="robust laps per validated candidate (0 = no validation)")
    ap.add_argument("--robust-jitter", type=float, default=0.001, help="--jitter for the robust laps")
    ap.add_argument("--max-robust-crashes", type=int, default=1, help="a candidate passes with at most this many crashes")
    ap.add_argument("--out", default=os.path.join(HERE, "cmaes_best.json"))
    ap.add_argument("--log", default=None, help="default: <out without .json>_log.csv")
    ap.add_argument("--prefix", default="cma")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    out_base = os.path.splitext(args.out)[0]
    log_path = args.log or out_base + "_log.csv"

    with open(args.start, encoding="utf-8") as f:
        start = json.load(f).get("params", {})
    fix = json.loads(args.fix)
    keys = [k for k in SPACE if k not in fix]
    lo = np.array([SPACE[k][0] for k in keys])
    hi = np.array([SPACE[k][1] for k in keys])

    def to_params(x):
        p = dict(start)
        p.update(fix)
        p.update({k: round(float(v), 4) for k, v in zip(keys, lo + np.clip(x, 0, 1) * (hi - lo))})
        return p

    # ---- CMA-ES state (Hansen's standard settings), search space normalised to [0, 1]^n ----
    n = len(keys)
    lam = args.popsize or 4 + int(3 * math.log(n))
    mu = lam // 2
    w = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    w /= w.sum()
    mueff = 1.0 / np.sum(w ** 2)
    cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
    cs = (mueff + 2) / (n + mueff + 5)
    c1 = 2 / ((n + 1.3) ** 2 + mueff)
    cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
    damps = 1 + 2 * max(0.0, math.sqrt((mueff - 1) / (n + 1)) - 1) + cs
    chi_n = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
    m = np.clip((np.array([float(start.get(k, (SPACE[k][0] + SPACE[k][1]) / 2)) for k in keys]) - lo) / (hi - lo), 0, 1)
    sigma = args.sigma
    C = np.eye(n)
    pc = np.zeros(n)
    ps = np.zeros(n)

    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    new_log = not os.path.exists(log_path)
    log_f = open(log_path, "a", newline="", encoding="utf-8")
    log_w = csv.writer(log_f)
    if new_log:
        log_w.writerow(["time", "tag", "gen", "kind", "score", "verdict", "lap_time_s", "damage", "dist_raced_m",
                        "robust_crashes", "robust_n", "robust_mean_s", "params"])

    fastest = None    # (a) {"lap", "params", "tag"}
    robust = None     # (b) {"crashes", "n", "mean", "lap", "params", "tag"}
    accepted = None   # fastest candidate that passed validation
    t0 = time.time()
    evals = validations = 0
    print(f"CMA-ES: n={n} params, popsize={lam}, gens={args.gens}, sigma={sigma}; validation: {args.robust_n} laps "
          f"with --jitter {args.robust_jitter}, pass if crashes <= {args.max_robust_crashes}", flush=True)

    def det_lap(params, tag, gen):
        nonlocal fastest, evals
        r = run_lap(params, ["--stop-on-damage"], tag)
        evals += 1
        if r.get("status") != "finished" or float(r.get("damage") or 0) > 0:
            score, verdict = 1000.0 - float(r.get("dist_raced_m") or 0) / 10.0, "reject:crash"
        elif not r.get("lap_time_s"):
            score, verdict = 1000.0, "reject:no-lap-time"
        else:
            score, verdict = float(r["lap_time_s"]), "clean"
            if fastest is None or score < fastest["lap"]:
                fastest = {"lap": score, "params": params, "tag": tag}
        log_w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), tag, gen, "det", round(score, 3), verdict,
                        r.get("lap_time_s"), r.get("damage"), r.get("dist_raced_m"), "", "", "",
                        json.dumps(params, sort_keys=True)])
        log_f.flush()
        return score, verdict, r

    def validate(params, lap, tag, gen):
        """Returns True if the candidate passes. Updates (b) most robust and the accepted best."""
        nonlocal robust, accepted, validations
        rr = run_lap(params, ["--robust", str(args.robust_n), "--jitter", str(args.robust_jitter),
                              "--stop-on-damage"], tag + "_robust")
        validations += 1
        crashes = int(rr.get("crashes", args.robust_n))
        mean = rr.get("mean_lap_s") or None
        ok = crashes <= args.max_robust_crashes
        if robust is None or (crashes, lap) < (robust["crashes"], robust["lap"]):
            robust = {"crashes": crashes, "n": args.robust_n, "mean": mean, "lap": lap, "params": params, "tag": tag}
        if ok and (accepted is None or lap < accepted["lap"]):
            accepted = {"lap": lap, "crashes": crashes, "n": args.robust_n, "mean": mean, "params": params, "tag": tag}
        log_w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), tag, gen, "robust", "", "pass" if ok else "fail",
                        lap, "", "", crashes, args.robust_n, mean or "", json.dumps(params, sort_keys=True)])
        log_f.flush()
        return ok, crashes

    def save():
        summary = {"settings": {"gens": args.gens, "popsize": lam, "sigma0": args.sigma, "seed": args.seed,
                                "robust_n": args.robust_n, "robust_jitter": args.robust_jitter,
                                "max_robust_crashes": args.max_robust_crashes, "fix": fix,
                                "evals": evals, "validations": validations},
                   "accepted": accepted, "fastest_clean": fastest, "most_robust": robust,
                   "params": (accepted or {}).get("params")}
        write_params(args.out, summary)
        if fastest:
            write_params(out_base + "_fastest.json", {"score": fastest["lap"], "params": fastest["params"]})
        if robust:
            write_params(out_base + "_robust.json", {"score": robust["lap"], "robust": f"{robust['crashes']}/{robust['n']}",
                                                     "params": robust["params"]})

    # start point first, so the search has a reference
    p0 = to_params(m)
    s0, v0, r0 = det_lap(p0, f"{args.prefix}_start", 0)
    print(f"start: lap={r0.get('lap_time_s')} damage={r0.get('damage')} {v0}", flush=True)
    if v0 == "clean" and args.robust_n:
        ok, cr = validate(p0, s0, f"{args.prefix}_start", 0)
        print(f"start validation: {cr}/{args.robust_n} crashes -> {'pass' if ok else 'fail'}", flush=True)
    save()

    for gen in range(1, args.gens + 1):
        evals_c, B = np.linalg.eigh(C)
        D = np.sqrt(np.maximum(evals_c, 1e-20))
        inv_sqrt_C = B @ np.diag(1 / D) @ B.T
        xs, ys, scores, verdicts = [], [], [], []
        for i in range(lam):
            x = np.clip(m + sigma * (B @ (D * rng.standard_normal(n))), 0, 1)
            s, v, r = det_lap(to_params(x), f"{args.prefix}_g{gen:03d}_{i:02d}", gen)
            xs.append(x)
            ys.append((x - m) / sigma)
            scores.append(s)
            verdicts.append(v)

        # validation: candidates faster than the accepted best, plus this generation's fastest clean one
        clean = sorted((scores[i], i) for i in range(lam) if verdicts[i] == "clean")
        to_check = [i for s, i in clean if accepted is None or s < accepted["lap"]][:3]
        if clean and clean[0][1] not in to_check:
            to_check.insert(0, clean[0][1])
        notes = []
        if args.robust_n:
            for i in to_check:
                ok, cr = validate(to_params(xs[i]), scores[i], f"{args.prefix}_g{gen:03d}_{i:02d}", gen)
                notes.append(f"#{i:02d} {scores[i]:.3f}s {cr}/{args.robust_n}{'' if ok else ' FAIL'}")
                if not ok:
                    scores[i] = 900.0 + scores[i] / 100.0

        order = np.argsort(scores)
        y_sel = np.array([ys[i] for i in order[:mu]])
        y_w = w @ y_sel
        m = np.clip(m + sigma * y_w, 0, 1)
        ps = (1 - cs) * ps + math.sqrt(cs * (2 - cs) * mueff) * (inv_sqrt_C @ y_w)
        hsig = np.linalg.norm(ps) / math.sqrt(1 - (1 - cs) ** (2 * gen)) / chi_n < 1.4 + 2 / (n + 1)
        pc = (1 - cc) * pc + hsig * math.sqrt(cc * (2 - cc) * mueff) * y_w
        C = ((1 - c1 - cmu) * C + c1 * (np.outer(pc, pc) + (1 - hsig) * cc * (2 - cc) * C)
             + cmu * (y_sel.T * w) @ y_sel)
        sigma *= math.exp((cs / damps) * (np.linalg.norm(ps) / chi_n - 1))
        save()
        n_clean = sum(v == "clean" for v in verdicts)
        print(f"gen {gen:2d}: clean {n_clean}/{lam}  gen-best={clean[0][0] if clean else '-'}  "
              f"validated [{'; '.join(notes)}]  (a)={fastest and fastest['lap']}  "
              f"(b)={robust and str(robust['crashes']) + '/' + str(robust['n']) + ' @ ' + str(robust['lap'])}  "
              f"accepted={accepted and accepted['lap']}  sigma={sigma:.3f}  {time.time() - t0:.0f}s", flush=True)

    log_f.close()
    print("\n=== RESULT ===")
    print("(a) fastest clean :", fastest and f"{fastest['lap']} s ({fastest['tag']})")
    print("(b) most robust   :", robust and f"{robust['crashes']}/{robust['n']} crashes, det lap {robust['lap']} s, "
                                            f"jitter mean {robust['mean']} ({robust['tag']})")
    print("accepted best     :", accepted and f"{accepted['lap']} s, {accepted['crashes']}/{accepted['n']} crashes "
                                              f"({accepted['tag']})")
    print("saved:", args.out)


if __name__ == "__main__":
    main()
