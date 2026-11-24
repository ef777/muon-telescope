"""Depletion-layer thickness H from track lengths (DECO method) and from coincidence-known angles.

dN/dL = 4 L H^4 / (L^2 + H^2)^3   (cos^2 theta muons, L = H tan theta; lengths in pixels).
Truncated at L >= lmin: survival S(lmin) = H^4 / (lmin^2 + H^2)^2.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar


def pdf(L, H):
    L = np.asarray(L, float)
    return 4 * L * H**4 / (L**2 + H**2) ** 3


def _nll(H: float, L: np.ndarray, lmin: float) -> float:
    ll = np.log(4 * L) + 4 * np.log(H) - 3 * np.log(L**2 + H**2)
    return float(-(ll.sum() - len(L) * (4 * np.log(H) - 2 * np.log(lmin**2 + H**2))))


def fit_H(lengths_px, l0: float = 0.0, lmin: float = 3.0, bounds=(1.0, 500.0)) -> dict:
    """MLE of H [px]. l0 = pixel footprint subtracted from measured lengths. Error from curvature of the NLL."""
    L = np.asarray(lengths_px, float) - l0
    L = L[L >= lmin]
    if len(L) < 10:
        return dict(H=np.nan, err=np.nan, n=len(L))
    r = minimize_scalar(_nll, bounds=bounds, args=(L, lmin), method="bounded")
    H = float(r.x)
    h = max(H * 1e-3, 1e-6)
    d2 = (_nll(H + h, L, lmin) - 2 * _nll(H, L, lmin) + _nll(H - h, L, lmin)) / h**2
    return dict(H=H, err=float(1 / np.sqrt(d2)) if d2 > 0 else np.nan, n=len(L))


def H_from_angles(lengths_px, zeniths_rad, **_) -> dict:
    """Calibration with coincidence-known zenith angles: linear fit L = H tan(theta) + l0.

    The free intercept l0 absorbs the pixel footprint of the cluster. Triple coincidences only accept small
    zenith angles (tan(theta) <~ 0.3 for a 6 mm sensor at 18 mm spacing), so the lever arm is short and the
    slope error is large unless many tracks are collected.
    """
    L = np.asarray(lengths_px, float)
    t = np.tan(np.asarray(zeniths_rad, float))
    if len(L) < 8:
        return dict(H=np.nan, err=np.nan, l0=np.nan, n=len(L))
    A = np.vstack([t, np.ones_like(t)]).T
    coef, *_ = np.linalg.lstsq(A, L, rcond=None)
    resid = L - A @ coef
    cov = np.linalg.inv(A.T @ A) * resid.var(ddof=2)
    return dict(H=float(coef[0]), err=float(np.sqrt(cov[0, 0])), l0=float(coef[1]), n=int(len(L)))
