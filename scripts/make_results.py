"""Produce docs/figures/* and a results JSON from an event file (synthetic or real).

    python scripts/make_results.py --synthetic --hours 400 --out docs/figures
    python scripts/make_results.py --run data/run1.jsonl --out docs/figures
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "sim")]

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mc  # noqa: E402
import synth  # noqa: E402
from muon import alignment, classify, depletion, tracks  # noqa: E402
from muon import coincidence as co
from muon.events import from_records, load_jsonl  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--hours", type=float, default=400)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="docs/figures")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    devs = synth.default_devices()
    devs[1].offset_mm, devs[1].rot_rad = (0.12, -0.08), 0.015      # known misalignment to recover (synthetic only)
    if a.synthetic:
        ev = from_records(synth.generate(devs, a.hours, a.seed).records)
    else:
        ev = load_jsonl(a.run)
    A, B, C = (ev.device_events(n) for n in ("top", "middle", "bottom"))
    res: dict = {"source": "synthetic" if a.synthetic else a.run, "n_events": len(ev)}

    # 1. lag scan + significance
    scan = co.lag_scan(A, B, 200_000_000, 60_000_000_000)
    res["lag_top_middle"] = {k: scan[k] for k in ("n_zero", "bg_mean", "excess", "significance")}
    fig, ax = plt.subplots(); ax.plot(scan["lags_ns"] / 1e9, scan["counts"], ".-")
    ax.set(xlabel="lag [s]", ylabel="coincidences", title=f"Lag scan top-middle, {scan['significance']:.1f} sigma")
    fig.savefig(out / "lag_scan.png", dpi=120); plt.close(fig)

    # 2. accidental rate vs window
    ws, bgs = [], []
    for m in (0, 5, 10, 20, 40):
        s = co.lag_scan(A, B, 200_000_000, 30_000_000_000, margin_ns=int(m * 1e6))
        ws.append(150 + 150 + 2 * m); bgs.append(s["bg_mean"])
    res["accidental_vs_window"] = dict(window_ms=ws, bg_counts=bgs)
    fig, ax = plt.subplots(); ax.plot(ws, bgs, "o-"); ax.set(xlabel="window T1+T2+2*margin [ms]", ylabel="mean accidental pairs per lag")
    fig.savefig(out / "accidental_vs_window.png", dpi=120); plt.close(fig)

    # 3. triples -> reconstruction, alignment, zenith, H
    tri_all = co.match_triples(A, B, C)
    tri = classify.track_triples(tri_all, A, B, C)
    res["n_triples_raw"] = int(len(tri_all))
    res["n_triples"] = int(len(tri))
    if len(tri) >= 10:
        hits = np.array([[A.cols["x_px"][i], A.cols["y_px"][i], B.cols["x_px"][j], B.cols["y_px"][j],
                          C.cols["x_px"][k], C.cols["y_px"][k]] for i, j, k in tri])
        poses = {d.name: tracks.SensorPose(d.sensor.z_mm, 0, 0, 0, d.pitch_um, *d.size_px) for d in devs}
        new_mid, info = alignment.align_middle(poses["top"], poses["middle"], poses["bottom"], hits)
        res["alignment"] = {k: (float(v) if np.isscalar(v) else np.asarray(v).tolist()) for k, v in info.items()}
        poses["middle"] = new_mid
        zen, lens = [], []
        for (i, j, k), h in zip(tri, hits):
            r = tracks.reconstruct(poses, dict(top=h[0:2], middle=h[2:4], bottom=h[4:6]))
            zen.append(r["zenith"]); lens.append(A.cols["length_px"][i])
        zen = np.array(zen)
        # MC acceptance expectation + fit of exponent k in I ~ cos^k
        th_mc = mc.accepted_zenith([d.sensor for d in devs], 3_000_000)
        edges = np.linspace(0, 0.6, 7)
        obs, _ = np.histogram(zen, edges)
        best = None
        for k in np.arange(0.0, 6.01, 0.25):
            w = np.cos(th_mc) ** (k - 2)
            exp, _ = np.histogram(th_mc, edges, weights=w)
            exp = exp / exp.sum() * obs.sum()
            m = exp > 0
            chi2 = float(np.sum((obs[m] - exp[m]) ** 2 / exp[m]))
            if best is None or chi2 < best[1]:
                best = (float(k), chi2, int(m.sum()))
            if abs(k - 2) < 1e-9:
                chi2_cos2 = (chi2, int(m.sum()))
        res["zenith"] = dict(n=int(len(zen)), best_k=best[0], chi2_best=best[1], chi2_cos2=chi2_cos2[0], ndof=chi2_cos2[1])
        w2 = np.cos(th_mc) ** 0
        exp2, _ = np.histogram(th_mc, edges, weights=w2); exp2 = exp2 / exp2.sum() * obs.sum()
        c = 0.5 * (edges[1:] + edges[:-1])
        fig, ax = plt.subplots(); ax.errorbar(np.degrees(c), obs, np.sqrt(np.maximum(obs, 1)), fmt="ko", label="data")
        ax.step(np.degrees(c), exp2, where="mid", label="MC cos^2 x acceptance"); ax.set(xlabel="zenith [deg]", ylabel="triples"); ax.legend()
        fig.savefig(out / "zenith.png", dpi=120); plt.close(fig)
        cal = depletion.H_from_angles(np.array(lens), zen)
        res["H_from_coincidence_px"] = cal

    # 4. H from all track-like single-phone candidates (DECO MLE), each device
    res["H_mle_px"] = {}
    fig, ax = plt.subplots()
    for d in devs:
        e = ev.device_events(d.name)
        pred = classify.classify(e)
        L = e.cols["length_px"][pred == "track"]
        f = depletion.fit_H(L, l0=1.0, lmin=3.0)
        res["H_mle_px"][d.name] = f
        ax.hist(L, bins=40, range=(0, 60), histtype="step", label=f"{d.name} H={f['H']:.1f}+-{f['err']:.1f}px")
    ax.set(xlabel="track length [px]", ylabel="candidates"); ax.legend(); ax.set_yscale("log")
    fig.savefig(out / "track_length.png", dpi=120); plt.close(fig)

    # 5. classifier confusion (synthetic only: needs truth)
    if ev.truth is not None:
        cm = classify.confusion_matrix(ev.truth, classify.classify(ev))
        res["confusion_dot_worm_track"] = cm.tolist()

    (out / "results.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()
