import importlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import synth
from fastapi.testclient import TestClient

from muon import alignment, cnn, coincidence as co, stability, tracks
from muon.events import from_records

ROOT = Path(__file__).resolve().parents[2]


def test_cnn_confusion_on_synthetic():
    pytest.importorskip("torch")
    X, y = cnn.synthetic_dataset(400, seed=1)
    Xt, yt = cnn.synthetic_dataset(150, seed=2)
    net = cnn.train(X, y, epochs=10)
    cm = cnn.confusion(yt, cnn.predict(net, Xt))
    assert np.trace(cm) / cm.sum() > 0.9, cm


def test_stability_detects_dropout_and_flat_rate():
    r = synth.generate(synth.default_devices(), 30, 5)
    ev = from_records(r.records)
    h = stability.hourly_rates(ev, "top")
    assert h["stable"], h["max_dev"]
    # remove 4 hours of data: instability must be detected, duty-cycle drops
    keep = ~((ev.utc_ns - ev.utc_ns.min() > 10 * 3.6e12) & (ev.utc_ns - ev.utc_ns.min() < 14 * 3.6e12))
    ev2 = ev.select(keep)
    assert not stability.hourly_rates(ev2, "top")["stable"]
    assert stability.duty_cycle(ev2, "top") < stability.duty_cycle(ev, "top")


def test_align_sensors_general_matches_middle_only():
    devs = synth.default_devices()
    devs[1].offset_mm, devs[1].rot_rad = (0.1, -0.12), 0.01
    ev = from_records(synth.generate(devs, 500, 8).records)
    a, b, c = (ev.device_events(n) for n in ("top", "middle", "bottom"))
    from muon import classify
    tri = classify.track_triples(co.match_triples(a, b, c), a, b, c)
    hits = {n: np.array([[e.cols["x_px"][t[i]], e.cols["y_px"][t[i]]] for t in tri])
            for i, (n, e) in enumerate((("top", a), ("middle", b), ("bottom", c)))}
    poses = {d.name: tracks.SensorPose(d.sensor.z_mm, 0, 0, 0, d.pitch_um, *d.size_px) for d in devs}
    new, info = alignment.align_sensors(poses, hits, free=["middle"])
    assert info["median_after"] < 0.5 * info["median_before"]
    assert abs(new["middle"].x_mm - 0.1) < 0.05 and abs(new["middle"].y_mm + 0.12) < 0.05
    with pytest.raises(ValueError):
        alignment.align_sensors(poses, hits, free=["middle", "bottom"])


def test_select_device_config_on_probe_report(tmp_path):
    rep = ROOT / "docs" / "devices" / "emulator_pixel6_api35.json"
    out = tmp_path / "devices.yaml"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "select_device_config.py"), str(rep), "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import yaml
    d = yaml.safe_load(out.read_text(encoding="utf-8"))["devices"][0]
    assert d["camera_id"] == "1" or d["camera_id"] == "0" or d["camera_id"]
    assert d["format"] in ("RAW_SENSOR", "YUV_420_888") and d["hot_pixel_off"] is True


def test_flux_compare_math():
    sys.path.insert(0, str(ROOT / "scripts"))
    fc = importlib.import_module("flux_compare")
    r = fc.compare(400, 100.0, 380, 100.0)
    assert abs(r["ratio"] - 0.95) < 1e-9 and r["ratio_err"] > 0


def test_server_tap_gnss_crop_stability(tmp_path, monkeypatch):
    monkeypatch.setenv("MUON_DB", str(tmp_path / "t.db"))
    import app as appmod
    importlib.reload(appmod)
    c = TestClient(appmod.app)
    t = np.arange(10) * 7_000_000_000
    c.post("/tap", json={"device_id": "a", "times_utc_ns": t.tolist()})
    c.post("/tap", json={"device_id": "b", "times_utc_ns": (t + 3_000_000).tolist()})
    assert abs(c.get("/tapsync", params={"ref": "a", "other": "b"}).json()["offset_ns"] - 3e6) < 1e3
    pairs = [[i * 10**9, 1_700_000_000_000_000_000 + i * 10**9 + 1000] for i in range(5)]
    assert abs(c.post("/gnss", json={"device_id": "a", "pairs": pairs}).json()["offset_ns"] - 1.7e18) < 1e6
    assert c.put("/crop/r/a/1_0.npy", content=b"abc").json()["ok"]
    assert (tmp_path / "crops" / "r" / "a" / "1_0.npy").read_bytes() == b"abc"
    recs = synth.generate(synth.default_devices(), 12, 3).records
    for r in recs:
        r["run_id"] = "s"
    c.post("/ingest", json=recs)
    assert "top" in c.get("/stability").json()


def test_json_report_is_valid():
    d = json.loads((ROOT / "docs" / "devices" / "emulator_pixel6_api35.json").read_text(encoding="utf-8"))
    assert d["cameras"]


def test_stability_endpoint_short_run_has_no_nan(tmp_path, monkeypatch):
    monkeypatch.setenv("MUON_DB", str(tmp_path / "s.db"))
    import app as appmod
    importlib.reload(appmod)
    c = TestClient(appmod.app)
    recs = synth.generate(synth.default_devices(), 0.4, 3).records      # < 1 h: no complete hour
    for r in recs:
        r["run_id"] = "short"
    c.post("/ingest", json=recs)
    r = c.get("/stability")
    assert r.status_code == 200
