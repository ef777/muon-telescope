"""Coincidence matching by exposure-interval overlap, lag scan for accidentals, Li&Ma significance."""
from __future__ import annotations

import argparse

import numpy as np
from scipy import stats

from .events import Events


def match_pairs(a: Events, b: Events, margin_ns: int = 5_000_000, shift_ns: int = 0) -> np.ndarray:
    """Index pairs (ia, ib) whose exposure intervals overlap within margin; b is shifted by shift_ns."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((0, 2), np.int64)
    order = np.argsort(b.start)
    bs, be = b.start[order] + shift_ns, b.end[order] + shift_ns
    maxdur = int((be - bs).max())
    lo = np.searchsorted(bs, a.start - margin_ns - maxdur, side="left")
    hi = np.searchsorted(bs, a.end + margin_ns, side="right")
    pairs = []
    for i in range(len(a)):
        for j in range(lo[i], hi[i]):
            if be[j] + margin_ns >= a.start[i] and bs[j] - margin_ns <= a.end[i]:
                pairs.append((i, order[j]))
    return np.array(pairs, np.int64).reshape(-1, 2)


def match_triples(a: Events, b: Events, c: Events, margin_ns: int = 5_000_000) -> np.ndarray:
    """(ia, ib, ic) where a~b, a~c and b~c all overlap."""
    ab, ac = match_pairs(a, b, margin_ns), match_pairs(a, c, margin_ns)
    bc = {(int(i), int(j)) for i, j in match_pairs(b, c, margin_ns)}
    c_of_a: dict[int, list[int]] = {}
    for i, k in ac:
        c_of_a.setdefault(int(i), []).append(int(k))
    out = [(int(i), int(j), k) for i, j in ab for k in c_of_a.get(int(i), []) if (int(j), k) in bc]
    return np.array(out, np.int64).reshape(-1, 3)


def li_ma(n_on: float, n_off: float, alpha: float) -> float:
    """Li & Ma (1983) eq. 17 signed significance. alpha = on-time / off-time."""
    if n_on == 0 or n_off == 0:
        return 0.0
    t1 = n_on * np.log((1 + alpha) / alpha * n_on / (n_on + n_off))
    t2 = n_off * np.log((1 + alpha) * n_off / (n_on + n_off))
    s = float(np.sqrt(2 * max(t1 + t2, 0.0)))
    return s if n_on >= alpha * n_off else -s


def lag_scan(a: Events, b: Events, step_ns: int, max_lag_ns: int = 60_000_000_000, margin_ns: int = 5_000_000,
             exclude_steps: int = 2) -> dict:
    """Coincidence count vs time shift of b. Zero-lag excess over the mean of |lag| >= exclude_steps."""
    ks = np.arange(-(max_lag_ns // step_ns), max_lag_ns // step_ns + 1)
    counts = np.array([len(match_pairs(a, b, margin_ns, int(k) * step_ns)) for k in ks])
    zero = int(counts[ks == 0][0])
    bg_mask = np.abs(ks) >= exclude_steps
    n_off = int(counts[bg_mask].sum())
    alpha = 1.0 / bg_mask.sum()
    bg = n_off * alpha
    return dict(lags_ns=ks * step_ns, counts=counts, n_zero=zero, bg_mean=float(bg), excess=float(zero - bg),
                significance=li_ma(float(zero), float(n_off), alpha),
                p_poisson=float(stats.poisson.sf(zero - 1, max(bg, 1e-12))))


def accidental_rate(r1_hz: float, r2_hz: float, t1_s: float, t2_s: float) -> float:
    """R_acc ~ R1 R2 (T1 + T2), in Hz."""
    return r1_hz * r2_hz * (t1_s + t2_s)


def main() -> None:
    from .events import load_jsonl
    ap = argparse.ArgumentParser(description="Pairwise coincidence + lag scan on a JSONL event file")
    ap.add_argument("--run", required=True, help="JSONL events file")
    ap.add_argument("--a", default="top")
    ap.add_argument("--b", default="middle")
    ap.add_argument("--step-ms", type=float, default=200.0)
    ap.add_argument("--max-lag-s", type=float, default=60.0)
    ns = ap.parse_args()
    ev = load_jsonl(ns.run)
    r = lag_scan(ev.device_events(ns.a), ev.device_events(ns.b), int(ns.step_ms * 1e6), int(ns.max_lag_s * 1e9))
    print(f"zero-lag={r['n_zero']} bg={r['bg_mean']:.2f} excess={r['excess']:.1f} sigma={r['significance']:.1f}")


if __name__ == "__main__":
    main()
