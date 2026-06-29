"""Mean-Shift clustering segmentation (paper Section III-B).

Cluster mScores in 1-D and take the lowest-center cluster as free-standing set Tfs.
See specs/02-clustering.md for the algorithm and the known boundary-deletion risk.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import MeanShift, estimate_bandwidth


def _fit_meanshift(values: np.ndarray) -> MeanShift:
    """Fit Mean-Shift on 1-D data; auto bandwidth with fallback."""
    X = values.reshape(-1, 1)
    bandwidth = estimate_bandwidth(X)
    if not bandwidth or bandwidth <= 0:
        span = float(values.max() - values.min())
        bandwidth = span / 3.0 if span > 0 else 1.0
    ms = MeanShift(bandwidth=bandwidth, bin_seeding=False)
    ms.fit(X)
    return ms


def segment_free_standing(
    m_scores: dict[int, float], strategy: str = "label"
) -> set[int]:
    """Identify free-standing template set Tfs.

    strategy: "label" (default, lowest-center cluster) or "threshold"
    (midpoint between lowest and second-lowest cluster).
    """
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

    if strategy == "label":
        return {
            templates[i] for i in range(len(templates)) if labels[i] == lowest_label
        }

    if strategy == "threshold":
        sorted_centers = np.sort(centers)
        second_center = sorted_centers[1]
        upper_of_lowest = float(values[labels == lowest_label].max())
        second_label = int(np.where(centers == second_center)[0][0])
        lower_of_second = float(values[labels == second_label].min())
        threshold = (upper_of_lowest + lower_of_second) / 2.0
        return {templates[i] for i in range(len(templates)) if values[i] < threshold}

    raise ValueError(f"unknown strategy: {strategy!r}")
