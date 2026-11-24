"""Event container: nested JSONL records (CLAUDE.md 4.5) <-> flat numpy arrays."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

CLUSTER_KEYS = ["x_px", "y_px", "n_pix", "sum_adu", "max_adu", "length_px", "width_px", "angle_rad", "eccentricity"]


@dataclass
class Events:
    device: np.ndarray            # str
    frame_idx: np.ndarray
    utc_ns: np.ndarray            # int64, exposure start in UTC
    utc_unc_ns: np.ndarray
    exposure_ns: np.ndarray
    cols: dict[str, np.ndarray] = field(default_factory=dict)  # cluster columns
    truth: np.ndarray | None = None     # synthetic only: 'muon'|'dot'|'worm'
    truth_id: np.ndarray | None = None  # synthetic only: muon id or -1

    def __len__(self) -> int:
        return len(self.utc_ns)

    @property
    def start(self) -> np.ndarray:
        return self.utc_ns

    @property
    def end(self) -> np.ndarray:
        return self.utc_ns + self.exposure_ns

    def select(self, mask: np.ndarray) -> "Events":
        return Events(self.device[mask], self.frame_idx[mask], self.utc_ns[mask], self.utc_unc_ns[mask],
                      self.exposure_ns[mask], {k: v[mask] for k, v in self.cols.items()},
                      None if self.truth is None else self.truth[mask],
                      None if self.truth_id is None else self.truth_id[mask])

    def device_events(self, dev: str) -> "Events":
        return self.select(self.device == dev)


def from_records(recs: list[dict]) -> Events:
    cols = {k: np.array([r["cluster"][k] for r in recs], float) for k in CLUSTER_KEYS}
    has_truth = bool(recs) and "truth" in recs[0]
    return Events(
        np.array([r["device_id"] for r in recs]),
        np.array([r["frame_idx"] for r in recs], np.int64),
        np.array([r["utc_ns"] for r in recs], np.int64),
        np.array([r.get("utc_uncertainty_ns", 0) for r in recs], np.int64),
        np.array([r["exposure_ns"] for r in recs], np.int64),
        cols,
        np.array([r["truth"] for r in recs]) if has_truth else None,
        np.array([r.get("truth_id", -1) for r in recs], np.int64) if has_truth else None,
    )


def load_jsonl(path: str) -> Events:
    with open(path, encoding="utf-8") as f:
        return from_records([json.loads(line) for line in f if line.strip()])
