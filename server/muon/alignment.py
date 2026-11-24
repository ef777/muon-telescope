"""Track-based alignment: solve (dx, dy, rotation) of the middle sensor from triple residuals.

Top and bottom define the reference line (fixed); the middle sensor pose is adjusted so its hit lies on it.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy.optimize import least_squares

from .tracks import SensorPose


def _residual_vectors(top: SensorPose, mid: SensorPose, bot: SensorPose, hits: np.ndarray) -> np.ndarray:
    """hits: (N, 6) px = top_x, top_y, mid_x, mid_y, bot_x, bot_y. Returns (N, 2) xy miss distance at mid z."""
    pt, pm, pb = (s.to_stack(hits[:, 2 * i], hits[:, 2 * i + 1]) for i, s in enumerate((top, mid, bot)))
    f = (top.z_mm - mid.z_mm) / (top.z_mm - bot.z_mm)
    line_xy = pt[:, :2] + f * (pb[:, :2] - pt[:, :2])
    return pm[:, :2] - line_xy


def rms_residual(top, mid, bot, hits) -> float:
    r = _residual_vectors(top, mid, bot, hits)
    return float(np.sqrt(np.mean(np.sum(r**2, axis=1))))


def median_residual(top, mid, bot, hits) -> float:
    """Robust (outlier-insensitive) miss distance [mm]."""
    return float(np.median(np.linalg.norm(_residual_vectors(top, mid, bot, hits), axis=1)))


def align_middle(top: SensorPose, mid: SensorPose, bot: SensorPose, hits: np.ndarray, loss: str = "soft_l1",
                 f_scale: float = 0.1) -> tuple[SensorPose, dict]:
    """Returns (aligned middle pose, info with rms before/after and parameters)."""
    def fun(p):
        m = replace(mid, x_mm=mid.x_mm + p[0], y_mm=mid.y_mm + p[1], rot_rad=mid.rot_rad + p[2])
        return _residual_vectors(top, m, bot, hits).ravel()

    sol = least_squares(fun, np.zeros(3), loss=loss, f_scale=f_scale)
    new = replace(mid, x_mm=mid.x_mm + sol.x[0], y_mm=mid.y_mm + sol.x[1], rot_rad=mid.rot_rad + sol.x[2])
    # parameter errors from Jacobian (unit-weight scaling by residual variance)
    n, k = len(fun(np.zeros(3))), 3
    s2 = np.sum(sol.fun**2) / max(n - k, 1)
    try:
        cov = np.linalg.inv(sol.jac.T @ sol.jac) * s2
        err = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        err = np.full(3, np.nan)
    return new, dict(rms_before=rms_residual(top, mid, bot, hits), rms_after=rms_residual(top, new, bot, hits),
                     median_before=median_residual(top, mid, bot, hits), median_after=median_residual(top, new, bot, hits),
                     dx_mm=sol.x[0], dy_mm=sol.x[1], drot_rad=sol.x[2], errors=err, n_tracks=len(hits))
