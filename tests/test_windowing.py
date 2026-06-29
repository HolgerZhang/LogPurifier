"""Unit tests for time-window segmentation."""

from logpurifier.parsing import parse_structured
from logpurifier.windowing import WINDOW_SECONDS, fixed_time_windows


def test_basic_windowing_groups_by_time():
    # window=100s: t=0,10,20 -> window 0; t=150,160 -> window 1
    records = [
        (0, 1, False), (10, 2, False), (20, 3, False),
        (150, 4, False), (160, 5, False),
    ]
    seqs, labels = fixed_time_windows(parse_structured(records), 100)
    assert seqs == [[1, 2, 3], [4, 5]]
    assert labels == [0, 0]


def test_anomaly_label_propagates_to_window():
    records = [
        (0, 1, False), (10, 2, True),     # window 0 has an anomaly -> 1
        (150, 4, False), (160, 5, False), # window 1 all normal -> 0
    ]
    _, labels = fixed_time_windows(parse_structured(records), 100)
    assert labels == [1, 0]


def test_empty_windows_skipped():
    records = [(0, 1, False), (350, 2, False)]  # windows 1,2 empty -> skipped
    seqs, labels = fixed_time_windows(parse_structured(records), 100)
    assert seqs == [[1], [2]]
    assert labels == [0, 0]


def test_unsorted_input_is_sorted():
    records = [(160, 5, False), (0, 1, False), (10, 2, False)]
    seqs, _ = fixed_time_windows(parse_structured(records), 100)
    assert seqs == [[1, 2], [5]]


def test_empty_input():
    assert fixed_time_windows([], 100) == ([], [])


def test_window_seconds_constant():
    assert WINDOW_SECONDS == (60, 100, 120, 300, 600, 1800, 3600)
