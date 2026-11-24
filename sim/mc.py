"""Phase 3 Monte Carlo: expected single/double/triple muon rates for a 3-sensor stack.

Muons are sampled on the top sensor plane (horizontal-surface flux, so the rate
through area A is flux*A), direction cos(theta) = (1-u)^(1/4), phi uniform.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np

FLUX_PER_CM2_MIN = 1.0  # sea level, horizontal surface


@dataclass
class Sensor:
    w_mm: float
    h_mm: float
    z_mm: float
    eff: float = 0.7


def default_stack(gap_mm: float = 9.0, eff: float = 0.7) -> list[Sensor]:
    return [Sensor(7.6, 5.7, 0.0, eff), Sensor(6.4, 4.8, -gap_mm, eff), Sensor(6.4, 4.8, -2 * gap_mm, eff)]


def sample_muons(n: int, top: Sensor, rng: np.random.Generator):
    x = rng.uniform(-top.w_mm / 2, top.w_mm / 2, n)
    y = rng.uniform(-top.h_mm / 2, top.h_mm / 2, n)
    cos_t = (1.0 - rng.uniform(size=n)) ** 0.25
    sin_t = np.sqrt(1 - cos_t**2)
    phi = rng.uniform(0, 2 * np.pi, n)
    return x, y, np.arccos(cos_t), phi, sin_t, cos_t


def geometric_hits(n: int, sensors: list[Sensor], rng: np.random.Generator) -> np.ndarray:
    """Boolean (n, len(sensors)) array: track crosses sensor active area (efficiency not applied)."""
    x, y, _, phi, sin_t, cos_t = sample_muons(n, sensors[0], rng)
    hits = np.zeros((n, len(sensors)), bool)
    for i, s in enumerate(sensors):
        d = (sensors[0].z_mm - s.z_mm)  # downward distance
        xs = x + d * (sin_t / cos_t) * np.cos(phi)
        ys = y + d * (sin_t / cos_t) * np.sin(phi)
        hits[:, i] = (np.abs(xs) <= s.w_mm / 2) & (np.abs(ys) <= s.h_mm / 2)
    return hits


def expected_rates(sensors: list[Sensor], duty: float = 0.9, n: int = 2_000_000, seed: int = 1) -> dict:
    rng = np.random.default_rng(seed)
    hits = geometric_hits(n, sensors, rng)
    eff = np.array([s.eff for s in sensors])
    top = sensors[0]
    thru_per_h = FLUX_PER_CM2_MIN * (top.w_mm * top.h_mm / 100.0) * 60.0 * duty
    p_single_top = eff[0] * hits[:, 0].mean()
    p_double = (hits[:, 0] & hits[:, 1]).astype(float) * eff[0] * eff[1]
    p_triple = hits.all(axis=1).astype(float) * eff.prod()
    p_hit_mid = hits[:, 1].mean()
    p_hit_all = hits.all(axis=1).mean()
    se = lambda a: a.std() / np.sqrt(len(a))  # noqa: E731
    return {
        "through_top_per_h": thru_per_h,
        "single_top_per_h": thru_per_h * p_single_top,
        "P(geom hit mid | top)": p_hit_mid,
        "P(geom hit all | top)": p_hit_all,
        "double_per_h": thru_per_h * p_double.mean(),
        "double_per_h_err": thru_per_h * se(p_double),
        "triple_per_h": thru_per_h * p_triple.mean(),
        "triple_per_h_err": thru_per_h * se(p_triple),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Expected muon rates for a 3-sensor phone stack")
    ap.add_argument("--gap-mm", type=float, default=9.0)
    ap.add_argument("--eff", type=float, default=0.7)
    ap.add_argument("--duty", type=float, default=0.9)
    ap.add_argument("-n", type=int, default=2_000_000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    r = expected_rates(default_stack(a.gap_mm, a.eff), a.duty, a.n, a.seed)
    for k, v in r.items():
        print(f"{k:28s} {v:.4g}")


if __name__ == "__main__":
    main()
