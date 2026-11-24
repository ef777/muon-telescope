"""Phase 0: choose camera + format per phone from the probe JSON reports and write config/devices.yaml.

    python scripts/select_device_config.py docs/devices/redmi_note13.json docs/devices/galaxy_a37.json ...
Device id = file stem. Rules (CLAUDE.md 4.2): manual sensor required; RAW_SENSOR preferred over YUV; HOT_PIXEL_MODE OFF
available is strongly preferred (dynamic hot-pixel correction erased muon tracks, eff 0.27 vs 0.7-0.87); REALTIME timestamp
preferred; back camera; then largest sensor area (thicker/bigger active region and more area -> more rate).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def score(c: dict) -> tuple[float, list[str]]:
    s, why = 0.0, []
    if not c.get("manual_sensor"):
        return -1e9, ["no MANUAL_SENSOR"]
    if 0 in (c.get("hot_pixel_modes") or []):
        s += 100; why.append("HOT_PIXEL_MODE OFF available")
    else:
        why.append("WARNING: no HOT_PIXEL_MODE OFF (muon tracks may be erased)")
    if c.get("raw_supported"):
        s += 50; why.append("RAW_SENSOR supported")
    if c.get("timestamp_source") == "REALTIME":
        s += 30; why.append("timestamp REALTIME (same base as elapsedRealtime)")
    if 0 in (c.get("noise_reduction_modes") or []):
        s += 20; why.append("noise reduction OFF available")
    if c.get("lens_facing") == "BACK":
        s += 5
    ps = c.get("physical_size_mm")
    if ps:
        s += ps[0] * ps[1]; why.append(f"sensor {ps[0]:.2f}x{ps[1]:.2f} mm")
    return s, why


def choose(report: dict) -> dict:
    best = max(report["cameras"], key=lambda c: score(c)[0])
    sc, why = score(best)
    fmts = best.get("output_formats", {})
    fmt = "RAW_SENSOR" if best.get("raw_supported") and "RAW_SENSOR" in fmts else "YUV_420_888"
    sizes = fmts.get(fmt, [])
    full = sizes[0] if sizes else None            # sorted by area descending in the probe
    fps_dur = full["min_frame_duration_ns"] if full else None
    iso = best.get("max_analog_iso") or (best.get("iso_range") or [None, None])[1]
    return dict(camera_id=best["id"], format=fmt, size=full["size"] if full else None,
                min_frame_duration_ns=fps_dur, iso=iso, pixel_pitch_um=best.get("pixel_pitch_um"),
                physical_size_mm=best.get("physical_size_mm"), score=sc, rationale="; ".join(why),
                hot_pixel_off=0 in (best.get("hot_pixel_modes") or []))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="+")
    ap.add_argument("--out", default="config/devices.yaml")
    a = ap.parse_args()
    devices = []
    for p in a.reports:
        r = json.loads(Path(p).read_text(encoding="utf-8"))
        devices.append(dict(id=Path(p).stem, **choose(r)))
    Path(a.out).write_text(yaml.safe_dump({"devices": devices}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    for d in devices:
        print(d["id"], "->", d["camera_id"], d["format"], d["size"], "|", d["rationale"])


if __name__ == "__main__":
    main()
