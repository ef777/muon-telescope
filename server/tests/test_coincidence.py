import numpy as np
import synth

from muon import coincidence as co
from muon.events import from_records


def _run(hours=48, seed=3):
    r = synth.generate(synth.default_devices(), hours, seed)
    return r, from_records(r.records)


def test_lag_scan_finds_true_pairs_and_matches_truth():
    r, ev = _run()
    top, mid = ev.device_events("top"), ev.device_events("middle")
    scan = co.lag_scan(top, mid, 200_000_000, 30_000_000_000)
    assert scan["significance"] > 5
    # truth: muons recorded in both devices
    t_ids = set(top.truth_id[top.truth == "muon"]); m_ids = set(mid.truth_id[mid.truth == "muon"])
    n_true = len(t_ids & m_ids)
    # found zero-lag pairs = true pairs + accidentals
    assert scan["n_zero"] >= n_true
    assert abs(scan["excess"] - n_true) < 4 * np.sqrt(max(n_true, 1))


def test_triples_recovered():
    r, ev = _run(seed=4)
    a, b, c = (ev.device_events(n) for n in ("top", "middle", "bottom"))
    tri_all = co.match_triples(a, b, c)
    # real doubles + a noise cluster in the 3rd sensor fake triples (~1/3 here): require track-like clusters
    from muon import classify
    tri = classify.track_triples(tri_all, a, b, c)
    assert len(tri) < len(tri_all)
    ids = [(a.truth_id[i], b.truth_id[j], c.truth_id[k]) for i, j, k in tri]
    true_tri = [t for t in ids if t[0] == t[1] == t[2] >= 0]
    all_true = set(a.truth_id[a.truth == "muon"]) & set(b.truth_id[b.truth == "muon"]) & set(c.truth_id[c.truth == "muon"])
    assert len(true_tri) >= 0.8 * len(all_true)     # track-class cut keeps most real triples (short tracks look like dots)
    assert len(tri) - len(true_tri) <= 1             # accidental triples negligible after the cut


def test_li_ma_sign():
    assert co.li_ma(50, 100, 0.1) > 5
    assert co.li_ma(5, 100, 0.1) < 0
    assert co.li_ma(0, 0, 0.1) == 0


def test_accidental_formula():
    assert abs(co.accidental_rate(0.02, 0.02, 0.15, 0.15) - 1.2e-4) < 1e-9
