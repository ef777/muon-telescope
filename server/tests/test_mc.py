import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import mc  # noqa: E402


def test_cos2_sampling_mean_cos():
    rng = np.random.default_rng(0)
    _, _, theta, *_ = mc.sample_muons(200_000, mc.default_stack()[0], rng)
    # pdf ~ cos^3 sin -> <cos> = 4/5
    assert abs(np.cos(theta).mean() - 0.8) < 0.003


def test_zero_gap_hits_everything_inside():
    st = mc.default_stack(gap_mm=0.0)
    h = mc.geometric_hits(50_000, st, np.random.default_rng(0))
    assert h[:, 0].all()
    # middle sensor smaller than top: area ratio
    assert abs(h[:, 1].mean() - (6.4 * 4.8) / (7.6 * 5.7)) < 0.01


def test_rates_in_expected_range():
    r = mc.expected_rates(mc.default_stack(), n=400_000)
    assert 14 < r["single_top_per_h"] < 19
    assert 1.2 < r["double_per_h"] < 2.3
    assert 0.3 < r["triple_per_h"] < 0.55
