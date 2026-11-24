"""Optional Phase 7: roof vs basement flux comparison (shielding attenuation).

    python scripts/flux_compare.py --roof data/roof.jsonl --basement data/basement.jsonl --concrete-cm 40

Uses triple (or double) coincidence rate per hour with Poisson errors. Livetime = time span of the run.
The mass-thickness estimate is a rough illustration (mean muon energy loss ~2 MeV cm2/g, concrete 2.4 g/cm3 and a
steep ~E^-2.7 spectrum make the attenuation per metre small, a few percent per 10 cm); the measured ratio is the result.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server")]

from muon import classify, coincidence as co  # noqa: E402
from muon.events import load_jsonl  # noqa: E402


def rate(path: str, mode: str = "triple") -> tuple[int, float]:
    ev = load_jsonl(path)
    a, b, c = (ev.device_events(n) for n in ("top", "middle", "bottom"))
    hours = (ev.utc_ns.max() - ev.utc_ns.min()) / 3.6e12
    if mode == "triple":
        n = len(classify.track_triples(co.match_triples(a, b, c), a, b, c))
    else:
        s = co.lag_scan(a, b, 200_000_000, 30_000_000_000)
        n = int(round(s["excess"]))
    return n, hours


def compare(n1: int, h1: float, n2: int, h2: float) -> dict:
    r1, r2 = n1 / h1, n2 / h2
    e1, e2 = np.sqrt(max(n1, 1)) / h1, np.sqrt(max(n2, 1)) / h2
    ratio = r2 / r1 if r1 > 0 else float("nan")
    err = ratio * np.sqrt((e1 / r1) ** 2 + (e2 / r2) ** 2) if r1 > 0 and r2 > 0 else float("nan")
    return dict(roof_per_h=r1, roof_err=e1, basement_per_h=r2, basement_err=e2, ratio=ratio, ratio_err=float(err),
                significance_of_deficit=float((r1 - r2) / np.hypot(e1, e2)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roof", required=True)
    ap.add_argument("--basement", required=True)
    ap.add_argument("--mode", choices=["triple", "double"], default="triple")
    ap.add_argument("--concrete-cm", type=float, default=None)
    a = ap.parse_args()
    (n1, h1), (n2, h2) = rate(a.roof, a.mode), rate(a.basement, a.mode)
    r = compare(n1, h1, n2, h2)
    print(f"roof {n1} in {h1:.1f} h; basement {n2} in {h2:.1f} h")
    for k, v in r.items():
        print(f"  {k}: {v:.4g}")
    if a.concrete_cm:
        print(f"  shielding: {a.concrete_cm:.0f} cm concrete = {a.concrete_cm * 2.4:.0f} g/cm2")


if __name__ == "__main__":
    main()
