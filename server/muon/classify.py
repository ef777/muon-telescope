"""Rule-based cluster classification: dot (gamma-like), worm (beta-like), track (muon candidate).

A 'track' label from one phone alone is only a muon *candidate*. Coincidence-confirmed tracks are the
labels used for evaluation / training (see label_from_coincidence).
"""
from __future__ import annotations

import numpy as np

from .events import Events

DEFAULT_RULES = {"dot_max_length": 2.5, "dot_max_npix": 4, "worm_min_width": 2.3}
CLASSES = ["dot", "worm", "track"]


def classify(ev: Events, rules: dict | None = None) -> np.ndarray:
    r = {**DEFAULT_RULES, **(rules or {})}
    L, w, n = ev.cols["length_px"], ev.cols["width_px"], ev.cols["n_pix"]
    out = np.full(len(ev), "track", dtype="<U5")
    out[w >= r["worm_min_width"]] = "worm"
    out[(L < r["dot_max_length"]) & (n <= r["dot_max_npix"]) & (w < r["worm_min_width"])] = "dot"
    return out


def confusion_matrix(truth: np.ndarray, pred: np.ndarray, labels=CLASSES) -> np.ndarray:
    """Rows = truth ('muon' is mapped to 'track'), columns = prediction."""
    t = np.where(truth == "muon", "track", truth)
    m = np.zeros((len(labels), len(labels)), int)
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            m[i, j] = int(np.sum((t == a) & (pred == b)))
    return m


def muon_fraction_in_coincident(pred: np.ndarray, coincident_idx: np.ndarray) -> float:
    """Fraction of coincidence-confirmed events that the classifier calls 'track'."""
    if len(coincident_idx) == 0:
        return float("nan")
    return float(np.mean(pred[coincident_idx] == "track"))
