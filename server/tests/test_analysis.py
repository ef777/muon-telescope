import numpy as np
import synth

from muon import alignment, classify, coincidence as co, depletion, timesync, tracks
from muon.events import from_records


def _poses(devs, mid_override=None):
    p = {}
    for d in devs:
        w, h = d.size_px
        p[d.name] = tracks.SensorPose(d.sensor.z_mm, 0, 0, 0, d.pitch_um, w, h)
    return p


def _triples(seed, devs, hours=300):
    r = synth.generate(devs, hours, seed)
    ev = from_records(r.records)
    a, b, c = (ev.device_events(n) for n in ("top", "middle", "bottom"))
    tri = co.match_triples(a, b, c)
    keep = [(i, j, k) for i, j, k in tri if a.truth_id[i] == b.truth_id[j] == c.truth_id[k] >= 0]
    hits = np.array([[a.cols["x_px"][i], a.cols["y_px"][i], b.cols["x_px"][j], b.cols["y_px"][j],
                      c.cols["x_px"][k], c.cols["y_px"][k]] for i, j, k in keep])
    th = np.array([r.muon_theta[a.truth_id[i]] for i, _, _ in keep])
    lens = np.array([[a.cols["length_px"][i], b.cols["length_px"][j], c.cols["length_px"][k]] for i, j, k in keep])
    return ev, hits, th, lens


def test_classifier_confusion_on_synth():
    ev = from_records(synth.generate(synth.default_devices(), 48, 5).records)
    pred = classify.classify(ev)
    cm = classify.confusion_matrix(ev.truth, pred)
    assert cm[1, 1] / cm[1].sum() > 0.95          # worms
    assert cm[0, 0] / cm[0].sum() > 0.9           # dots
    long_tracks = (ev.truth == "muon") & (ev.cols["length_px"] > 4)
    assert np.mean(pred[long_tracks] == "track") > 0.95


def test_reconstruction_zenith_matches_truth():
    devs = synth.default_devices()
    _, hits, th, _ = _triples(7, devs)
    poses = _poses(devs)
    rec = [tracks.reconstruct(poses, dict(top=h[0:2], middle=h[2:4], bottom=h[4:6]))["zenith"] for h in hits]
    assert len(hits) > 20
    assert np.median(np.abs(np.array(rec) - th)) < 0.02


def test_alignment_recovers_misalignment_and_reduces_residuals():
    devs = synth.default_devices()
    devs[1].offset_mm = (0.15, -0.10)
    devs[1].rot_rad = 0.02
    _, hits, _, _ = _triples(8, devs, hours=600)
    poses = _poses(devs)
    new, info = alignment.align_middle(poses["top"], poses["middle"], poses["bottom"], hits)
    assert len(hits) > 40
    assert info["median_after"] < 0.5 * info["median_before"]
    assert abs(new.x_mm - 0.15) < 0.05 and abs(new.y_mm + 0.10) < 0.05
    assert abs(new.rot_rad - 0.02) < 0.01


def test_depletion_mle_and_angle_calibration():
    devs = synth.default_devices()
    _, hits, th, lens = _triples(9, devs, hours=300)
    rng = np.random.default_rng(0)
    # large sample for MLE: cos^3 sin pdf samples
    theta = np.arccos((1 - rng.uniform(size=5000)) ** 0.25)
    L = 25.0 * np.tan(theta)
    f = depletion.fit_H(L, lmin=3.0)
    assert abs(f["H"] - 25) < 3 * f["err"] + 0.5
    cal = depletion.H_from_angles(lens[:, 0], th)
    assert abs(cal["H"] - 25) < 4 * cal["err"] + 1


def test_ntp_offset_and_drift():
    rng = np.random.default_rng(0)
    true_off, drift = 12_000_000.0, 20e-6
    samples = []
    for k in range(400):
        t1 = int(k * 1e9)
        o = true_off + drift * t1
        d_up, d_dn = rng.exponential(2e6) + 1e6, rng.exponential(2e6) + 1e6
        t2 = int(t1 + d_up + o); t3 = t2 + 100_000; t4 = int(t3 - o + d_dn)
        samples.append((t1, t2, t3, t4))
    est = timesync.estimate_offset_drift(samples)
    corrected = timesync.apply_offset(np.array([200e9]), est)[0]
    assert abs(corrected - (200e9 + true_off + drift * 200e9)) < 2e6
    assert abs(est["drift_ppm"] - 20) < 5


def test_tap_offset():
    a = np.array([1e9, 5e9, 9e9]); b = a + 3e6 + np.array([0.2e6, -0.1e6, 0.0])
    r = timesync.tap_offset(a, b)
    assert abs(r["offset_ns"] - 3e6) < 0.5e6 and r["n"] == 3


def test_elapsed_to_utc():
    pairs = [(int(i * 1e9), int(1.7e18 + i * 1e9 + n)) for i, n in enumerate([1e6, -2e6, 0, 3e5, 1e5])]
    r = timesync.elapsed_to_utc_offset(pairs)
    assert abs(r["offset_ns"] - 1.7e18) < 1e6
