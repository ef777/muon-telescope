"""Phase 1 acceptance helpers: hourly event rate stability and duty cycle from frame indices."""
from __future__ import annotations

import numpy as np

from .events import Events


def hourly_rates(ev: Events, device: str) -> dict:
    e = ev.device_events(device)
    if len(e) < 2:
        return dict(hours=np.array([]), rate=np.array([]), stable=False, max_dev=float("nan"))
    t = (e.utc_ns - e.utc_ns.min()) / 3.6e12
    n_h = int(np.floor(t.max()))
    counts = np.array([np.sum((t >= h) & (t < h + 1)) for h in range(n_h)], float)
    if len(counts) == 0:
        return dict(hours=np.array([]), rate=np.array([]), stable=False, max_dev=float("nan"))
    mean = counts.mean()
    dev = np.abs(counts - mean) / mean if mean > 0 else np.full_like(counts, np.inf)
    # Poisson noise alone gives ~1/sqrt(mean) relative scatter; stable if every hour is within 20 % OR within 3 sigma
    tol = np.maximum(0.20, 3 / np.sqrt(max(mean, 1)))
    return dict(hours=np.arange(n_h), rate=counts, mean=float(mean), max_dev=float(dev.max()), tol=float(tol), stable=bool(np.all(dev <= tol)))


def duty_cycle(ev: Events, device: str) -> float:
    """Fraction of frame indices that were processed, from the highest frame index (gaps = pauses/overheating)."""
    e = ev.device_events(device)
    if len(e) == 0:
        return float("nan")
    return float(len(np.unique(e.frame_idx)) / (e.frame_idx.max() - e.frame_idx.min() + 1))
