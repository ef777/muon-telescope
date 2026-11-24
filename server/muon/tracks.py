"""Pixel -> mm -> stack coordinates, 3D line fits, zenith angles. Units: mm, rad."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SensorPose:
    z_mm: float
    x_mm: float = 0.0
    y_mm: float = 0.0
    rot_rad: float = 0.0
    pitch_um: float = 1.0
    w_px: float = 1.0
    h_px: float = 1.0

    def to_stack(self, x_px, y_px) -> np.ndarray:
        """Pixel coords -> (x, y, z) in the stack frame; rotation about sensor centre, then translation."""
        lx = (np.asarray(x_px, float) - self.w_px / 2) * self.pitch_um / 1000
        ly = (np.asarray(y_px, float) - self.h_px / 2) * self.pitch_um / 1000
        c, s = np.cos(self.rot_rad), np.sin(self.rot_rad)
        x = self.x_mm + c * lx - s * ly
        y = self.y_mm + s * lx + c * ly
        return np.stack([x, y, np.full_like(x, self.z_mm, dtype=float)], axis=-1)


def poses_from_config(cfg: dict, devices: dict[str, dict]) -> dict[str, SensorPose]:
    """cfg: parsed geometry.yaml['sensors']; devices: name -> {pitch_um, w_px, h_px}."""
    out = {}
    for name, s in cfg.items():
        d = devices[name]
        out[name] = SensorPose(s["z_mm"], s["x_mm"], s["y_mm"], s["rot_rad"], d["pitch_um"], d["w_px"], d["h_px"])
    return out


def fit_line(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Total-least-squares 3D line. Returns (centroid, unit direction pointing downward, perpendicular residuals)."""
    p = np.asarray(points, float)
    c = p.mean(axis=0)
    _, _, vt = np.linalg.svd(p - c)
    d = vt[0]
    if d[2] > 0:
        d = -d
    diff = p - c
    res = np.linalg.norm(diff - np.outer(diff @ d, d), axis=1)
    return c, d, res


def zenith(direction: np.ndarray) -> float:
    d = np.asarray(direction, float)
    return float(np.arccos(abs(d[2]) / np.linalg.norm(d)))


def azimuth(direction: np.ndarray) -> float:
    return float(np.arctan2(direction[1], direction[0]))


def reconstruct(poses: dict[str, SensorPose], hits_px: dict[str, tuple[float, float]]) -> dict:
    """hits_px: sensor name -> (x_px, y_px). Needs >= 2 sensors. Triples give residuals; pairs give direction only."""
    names = [n for n in hits_px if n in poses]
    pts = np.array([poses[n].to_stack(*hits_px[n]) for n in names])
    c, d, res = fit_line(pts)
    return dict(sensors=names, centroid=c, direction=d, zenith=zenith(d), azimuth=azimuth(d),
                residuals=dict(zip(names, res)), n_hits=len(names))


def intra_sensor_azimuth(angle_rad: float, rot_rad: float = 0.0) -> float:
    """Cluster axis angle (sensor frame, modulo pi) -> stack frame."""
    return (angle_rad + rot_rad) % np.pi
