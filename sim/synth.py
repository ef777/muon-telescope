"""Synthetic event stream: muons through the stack + gamma dots + beta worms + timing noise.

Truth labels are attached ('truth', 'truth_id') but never used by the analysis code.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mc  # noqa: E402


@dataclass
class DeviceCfg:
    name: str
    sensor: mc.Sensor
    pitch_um: float = 1.0
    depletion_um: float = 25.0     # true H assumed by the simulation
    frame_ns: int = 200_000_000
    exposure_ns: int = 150_000_000
    phase_ns: int = 0
    dot_rate_per_min: float = 1.0
    worm_rate_per_min: float = 0.3
    offset_mm: tuple[float, float] = (0.0, 0.0)   # true misalignment vs nominal (x, y)
    rot_rad: float = 0.0
    time_jitter_ns: float = 2e6
    pixel_noise_px: float = 1.0

    @property
    def size_px(self):
        return (self.sensor.w_mm * 1000 / self.pitch_um, self.sensor.h_mm * 1000 / self.pitch_um)

    @property
    def H_px(self):
        return self.depletion_um / self.pitch_um


def default_devices(eff: float = 0.7) -> list[DeviceCfg]:
    st = mc.default_stack(eff=eff)
    names = ["top", "middle", "bottom"]
    return [DeviceCfg(n, s, phase_ns=p) for n, s, p in zip(names, st, [0, 37_000_000, 91_000_000])]


@dataclass
class SynthResult:
    records: list[dict] = field(default_factory=list)
    n_muons: int = 0
    muon_theta: np.ndarray | None = None


def _record(d, frame_idx, ts_start, rng, cl, truth, truth_id):
    return {
        "device_id": d.name, "frame_idx": int(frame_idx), "sensor_ts_ns": int(ts_start),
        "exposure_ns": d.exposure_ns, "frame_duration_ns": d.frame_ns,
        "utc_ns": int(ts_start + rng.normal(0, d.time_jitter_ns)), "utc_uncertainty_ns": int(d.time_jitter_ns),
        "cluster": cl, "truth": truth, "truth_id": int(truth_id),
    }


def generate(devs: list[DeviceCfg], hours: float, seed: int = 1) -> SynthResult:
    rng = np.random.default_rng(seed)
    top = devs[0].sensor
    T_ns = int(hours * 3600e9)
    rate_per_ns = mc.FLUX_PER_CM2_MIN * (top.w_mm * top.h_mm / 100.0) / 60e9
    n_mu = rng.poisson(rate_per_ns * T_ns)
    t_mu = np.sort(rng.uniform(0, T_ns, n_mu))
    x, y, theta, phi, _, _ = mc.sample_muons(n_mu, top, rng)
    out = SynthResult(n_muons=int(n_mu), muon_theta=theta)
    for d in devs:
        s = d.sensor
        dz = top.z_mm - s.z_mm
        xs = x + dz * np.tan(theta) * np.cos(phi)
        ys = y + dz * np.tan(theta) * np.sin(phi)
        # the sensor's physical window is shifted by its true misalignment
        inside = ((np.abs(xs - d.offset_mm[0]) <= s.w_mm / 2) & (np.abs(ys - d.offset_mm[1]) <= s.h_mm / 2)
                  & (rng.uniform(size=n_mu) < s.eff)
                  & (((t_mu - d.phase_ns) % d.frame_ns) < d.exposure_ns))   # muon during readout gap is lost
        w_px, h_px = d.size_px
        c, sn = np.cos(d.rot_rad), np.sin(d.rot_rad)
        for k in np.nonzero(inside)[0]:
            px, py = xs[k] - d.offset_mm[0], ys[k] - d.offset_mm[1]
            lx, ly = c * px + sn * py, -sn * px + c * py     # stack frame -> sensor frame
            xpx = lx * 1000 / d.pitch_um + w_px / 2 + rng.normal(0, d.pixel_noise_px)
            ypx = ly * 1000 / d.pitch_um + h_px / 2 + rng.normal(0, d.pixel_noise_px)
            L = d.H_px * np.tan(theta[k]) * rng.lognormal(0, 0.08) + 1.0
            ang = (phi[k] - d.rot_rad) % np.pi
            n_pix = max(1, int(round(L + rng.normal(0, 1) + 2)))
            cl = dict(x_px=float(xpx), y_px=float(ypx), n_pix=n_pix, sum_adu=float(n_pix * rng.normal(300, 40)),
                      max_adu=float(rng.normal(380, 40)), length_px=float(L), width_px=float(rng.uniform(1.0, 2.0)),
                      angle_rad=float(ang), eccentricity=float(min(0.999, 1 - 1.5 / max(L, 1.6))))
            fi = int((t_mu[k] - d.phase_ns) // d.frame_ns)
            out.records.append(_record(d, fi, fi * d.frame_ns + d.phase_ns, rng, cl, "muon", k))
        for kind, rate in (("dot", d.dot_rate_per_min), ("worm", d.worm_rate_per_min)):
            n_b = rng.poisson(rate * hours * 60)
            for t in rng.uniform(0, T_ns, n_b):
                fi = int((t - d.phase_ns) // d.frame_ns)
                if kind == "dot":
                    n_pix = int(rng.integers(1, 4)); L = float(rng.uniform(0.5, 1.8)); ecc = float(rng.uniform(0, 0.5))
                    wid = float(rng.uniform(0.8, 1.6)); adu = float(rng.normal(500, 150))
                else:
                    n_pix = int(rng.integers(6, 30)); L = float(rng.uniform(4, 14)); ecc = float(rng.uniform(0.2, 0.7))
                    wid = float(rng.uniform(2.5, 5)); adu = float(rng.normal(250, 60))
                adu = max(adu, 60.0)
                cl = dict(x_px=float(rng.uniform(0, w_px)), y_px=float(rng.uniform(0, h_px)), n_pix=n_pix,
                          sum_adu=float(n_pix * adu), max_adu=float(adu * 1.5), length_px=L,
                          width_px=wid, angle_rad=float(rng.uniform(0, np.pi)), eccentricity=ecc)
                out.records.append(_record(d, fi, fi * d.frame_ns + d.phase_ns, rng, cl, kind, -1))
    out.records.sort(key=lambda r: r["utc_ns"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a synthetic muon-stack event stream (JSONL)")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = generate(default_devices(), a.hours, a.seed)
    with open(a.out, "w", encoding="utf-8") as f:
        for rec in r.records:
            f.write(json.dumps(rec) + "\n")
    print(f"{len(r.records)} events, {r.n_muons} muons through top plane -> {a.out}")


if __name__ == "__main__":
    main()
