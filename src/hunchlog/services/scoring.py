"""Brier score and calibration-curve computation.

All math is intentionally pure (no I/O) so it is trivially unit-testable.
A resolved prediction is a (probability p in 0..1, outcome o in {0, 1}) pair.
"""

from collections.abc import Sequence

from hunchlog.schemas.prediction import CalibrationPoint

# Decile bucket edges and their display labels. The last bucket is closed on
# the right so that p == 1.0 (100%) falls into "90-100%".
_BUCKET_LABELS = [
    "0-10%",
    "10-20%",
    "20-30%",
    "30-40%",
    "40-50%",
    "50-60%",
    "60-70%",
    "70-80%",
    "80-90%",
    "90-100%",
]


def _bucket_index(p: float) -> int:
    """Return the decile bucket index 0..9 for probability p in 0..1."""
    idx = int(p * 10)
    # p == 1.0 → idx 10; fold it back into the last decile.
    return min(idx, 9)


def brier_score(resolved: Sequence[tuple[float, int]]) -> float | None:
    """Mean of (p - o)^2 over resolved predictions, or None if empty."""
    if not resolved:
        return None
    return sum((p - o) ** 2 for p, o in resolved) / len(resolved)


def brier_label(brier: float | None) -> str | None:
    """Friendly label for a Brier score (lower is better)."""
    if brier is None:
        return None
    if brier <= 0.1:
        return "sharp"
    if brier <= 0.2:
        return "well-calibrated"
    if brier <= 0.35:
        return "decent"
    return "overconfident or noisy"


def calibration_curve(
    resolved: Sequence[tuple[float, int]],
) -> list[CalibrationPoint]:
    """Bucket resolved predictions into deciles; emit non-empty buckets.

    For each non-empty bucket: mean_prob = mean of p, hit_rate = fraction
    with o == 1, n = count. Returned ordered by ascending bucket.
    """
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(10)]
    for p, o in resolved:
        buckets[_bucket_index(p)].append((p, o))

    points: list[CalibrationPoint] = []
    for idx, rows in enumerate(buckets):
        if not rows:
            continue
        n = len(rows)
        mean_prob = sum(p for p, _ in rows) / n
        hit_rate = sum(o for _, o in rows) / n
        points.append(
            CalibrationPoint(
                bucket=_BUCKET_LABELS[idx],
                mean_prob=mean_prob,
                hit_rate=hit_rate,
                n=n,
            )
        )
    return points
