"""Time synchronisation: NTP-style LAN offset/drift, GNSS elapsed->UTC map, tap-impulse cross-check."""
from __future__ import annotations

import numpy as np


def ntp_sample(t1: int, t2: int, t3: int, t4: int) -> tuple[float, float]:
    """Client sends t1, server receives t2, replies t3, client receives t4. Returns (offset_ns, rtt_ns).

    offset = server clock - client clock.
    """
    return ((t2 - t1) + (t3 - t4)) / 2.0, float((t4 - t1) - (t3 - t2))


def estimate_offset_drift(samples: list[tuple[int, int, int, int]], keep_frac: float = 0.2) -> dict:
    """Keep the lowest-RTT fraction, fit offset(t) = o0 + drift * (t - t_ref). Returns offset at t_ref, drift (ppm)."""
    arr = np.array([(*ntp_sample(*s), s[0]) for s in samples], float)   # offset, rtt, t1
    k = max(3, int(len(arr) * keep_frac))
    best = arr[np.argsort(arr[:, 1])[:k]]
    t_ref = float(best[:, 2].mean())
    x = best[:, 2] - t_ref
    A = np.vstack([np.ones_like(x), x]).T
    (o0, drift), *_ = np.linalg.lstsq(A, best[:, 0], rcond=None)
    resid = best[:, 0] - A @ np.array([o0, drift])
    return dict(offset_ns=float(o0), drift_ppm=float(drift * 1e6), t_ref_ns=t_ref,
                sigma_ns=float(resid.std(ddof=2)) if k > 2 else float("nan"), min_rtt_ns=float(best[:, 1].min()))


def apply_offset(t_client_ns: np.ndarray, est: dict) -> np.ndarray:
    return t_client_ns + est["offset_ns"] + est["drift_ppm"] * 1e-6 * (t_client_ns - est["t_ref_ns"])


def elapsed_to_utc_offset(pairs: list[tuple[int, int]]) -> dict:
    """pairs = (elapsedRealtimeNanos, utc_ns) from GNSS fixes. Median offset utc = elapsed + off; spread = uncertainty."""
    d = np.array([u - e for e, u in pairs], float)
    med = float(np.median(d))
    return dict(offset_ns=med, uncertainty_ns=float(1.4826 * np.median(np.abs(d - med))), n=len(d))


def tap_offset(times_a_ns: np.ndarray, times_b_ns: np.ndarray, max_pair_ns: float = 200e6) -> dict:
    """Offset (b - a) from common impulse events (taps) seen on both phones' accelerometers."""
    a, b = np.sort(times_a_ns).astype(float), np.sort(times_b_ns).astype(float)
    diffs = []
    for t in a:
        j = np.argmin(np.abs(b - t))
        if abs(b[j] - t) < max_pair_ns:
            diffs.append(b[j] - t)
    d = np.array(diffs)
    if len(d) == 0:
        return dict(offset_ns=np.nan, scatter_ns=np.nan, n=0)
    return dict(offset_ns=float(np.median(d)), scatter_ns=float(d.std()), n=len(d))
