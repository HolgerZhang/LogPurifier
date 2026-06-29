"""Fixed time-window segmentation (paper Section IV-C)."""

from __future__ import annotations

from .parsing import ParsedEntry

# Seven time-window sizes (seconds) from the paper
WINDOW_SECONDS = (60, 100, 120, 300, 600, 1800, 3600)


def fixed_time_windows(
    entries: list[ParsedEntry], window_seconds: float
) -> tuple[list[list[int]], list[int]]:
    """Split entries into non-overlapping fixed-duration windows.

    Returns (sequences, labels); a window with any anomalous entry is labeled 1.
    Empty windows produce no sequence.
    """
    if not entries:
        return [], []
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    ordered = sorted(entries, key=lambda e: e.timestamp)
    start = ordered[0].timestamp

    sequences: list[list[int]] = []
    labels: list[int] = []

    cur_seq: list[int] = []
    cur_anom = False
    cur_window_idx = 0

    for e in ordered:
        idx = int((e.timestamp - start) // window_seconds)
        if idx != cur_window_idx:
            if cur_seq:
                sequences.append(cur_seq)
                labels.append(1 if cur_anom else 0)
            cur_window_idx = idx
            cur_seq = []
            cur_anom = False
        cur_seq.append(e.template_id)
        cur_anom = cur_anom or e.is_anomaly

    if cur_seq:
        sequences.append(cur_seq)
        labels.append(1 if cur_anom else 0)

    return sequences, labels
