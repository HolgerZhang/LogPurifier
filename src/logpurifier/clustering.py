"""Mean-Shift clustering segmentation (paper Section III-B).

Cluster mScores in 1-D and take the lowest-center cluster as free-standing set Tfs.
See specs/02-clustering.md for the algorithm and the bandwidth rationale.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import MeanShift, estimate_bandwidth


def _silverman_bandwidth(values: np.ndarray) -> float:
    """Silverman's rule-of-thumb KDE bandwidth (Silverman 1986).

    h = 0.9 * min(std, IQR/1.34) * n^(-1/5). Used as a principled fallback when
    sklearn's estimate_bandwidth degenerates to 0 on tie-heavy data.
    """
    n = len(values)
    std = float(values.std(ddof=1))
    q1, q3 = np.percentile(values, [25, 75])
    iqr = float(q3 - q1)
    a = min(std, iqr / 1.34) if iqr > 0 else std
    if a <= 0:
        a = std
    return 0.9 * a * n ** (-1 / 5)


def _fit_meanshift(values: np.ndarray) -> MeanShift:
    """Fit Mean-Shift on 1-D data.

    Bandwidth: sklearn estimate_bandwidth by default; fall back to Silverman's
    rule when it returns <= 0 (happens on tie-heavy data, which would otherwise
    make MeanShift raise on bandwidth=0).
    """
    X = values.reshape(-1, 1)
    bandwidth = estimate_bandwidth(X)
    if not bandwidth or bandwidth <= 0:
        bandwidth = _silverman_bandwidth(values)
    ms = MeanShift(bandwidth=bandwidth, bin_seeding=False)
    ms.fit(X)
    return ms


def segment_free_standing(m_scores: dict[int, float]) -> set[int]:
    """Identify free-standing template set Tfs (lowest-center cluster, paper §III-B)."""
    if len(m_scores) <= 1:
        return set()

    templates = list(m_scores.keys())
    values = np.array([m_scores[t] for t in templates], dtype=float)

    if float(values.max() - values.min()) == 0.0:
        return set()

    ms = _fit_meanshift(values)
    labels = ms.labels_
    centers = ms.cluster_centers_.ravel()

    if len(set(labels)) <= 1:
        return set()

    lowest_label = int(np.argmin(centers))
    return {templates[i] for i in range(len(templates)) if labels[i] == lowest_label}
