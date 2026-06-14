"""Hand-computed unit tests for Brier + calibration math."""

import pytest

from hunchlog.services import scoring


def test_brier_none_when_empty():
    assert scoring.brier_score([]) is None


def test_brier_known_set():
    # (0.9-0)^2=.81, (0.8-1)^2=.04, (0.5-1)^2=.25, (0.2-0)^2=.04
    # sum = 1.14 / 4 = 0.285
    resolved = [(0.9, 0), (0.8, 1), (0.5, 1), (0.2, 0)]
    assert scoring.brier_score(resolved) == pytest.approx(0.285)


def test_brier_perfect_is_zero():
    assert scoring.brier_score([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("brier", "label"),
    [
        (None, None),
        (0.05, "sharp"),
        (0.1, "sharp"),
        (0.15, "well-calibrated"),
        (0.2, "well-calibrated"),
        (0.3, "decent"),
        (0.35, "decent"),
        (0.5, "overconfident or noisy"),
    ],
)
def test_brier_labels(brier, label):
    assert scoring.brier_label(brier) == label


def test_calibration_buckets():
    # Two in [80-90%): 0.8 hit, 0.85 miss → mean 0.825, hit_rate 0.5, n 2
    # One in [20-30%): 0.25 hit → mean 0.25, hit_rate 1.0, n 1
    resolved = [(0.8, 1), (0.85, 0), (0.25, 1)]
    points = scoring.calibration_curve(resolved)
    assert len(points) == 2
    # Ordered ascending by bucket.
    assert points[0].bucket == "20-30%"
    assert points[0].mean_prob == pytest.approx(0.25)
    assert points[0].hit_rate == pytest.approx(1.0)
    assert points[0].n == 1
    assert points[1].bucket == "80-90%"
    assert points[1].mean_prob == pytest.approx(0.825)
    assert points[1].hit_rate == pytest.approx(0.5)
    assert points[1].n == 2


def test_calibration_p_one_in_last_bucket():
    points = scoring.calibration_curve([(1.0, 1)])
    assert len(points) == 1
    assert points[0].bucket == "90-100%"


def test_calibration_empty():
    assert scoring.calibration_curve([]) == []
