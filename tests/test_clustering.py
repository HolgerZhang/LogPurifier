"""Unit tests for Mean-Shift segmentation."""

from logpurifier.clustering import segment_free_standing

SEND, CHECK, MEMORY = 0, 1, 2


def test_running_example_memory_lowest_or_empty():
    """Either memory is flagged free-standing, or (three near-equal points in one cluster)
    nothing is removed. Either way send/check must not be removed."""
    ms = {SEND: 0.875, CHECK: 0.875, MEMORY: 0.75}
    tfs = segment_free_standing(ms)
    assert SEND not in tfs and CHECK not in tfs
    assert tfs in ({MEMORY}, set())


def test_separated_groups_identifies_low_group():
    ms = {
        0: 0.90, 1: 0.88, 2: 0.92, 3: 0.85,   # regular (high)
        4: 0.10, 5: 0.08, 6: 0.12,            # free-standing (low)
    }
    assert segment_free_standing(ms) == {4, 5, 6}


def test_threshold_strategy_also_identifies_low_group():
    ms = {0: 0.90, 1: 0.88, 2: 0.92, 4: 0.10, 5: 0.08, 6: 0.12}
    assert segment_free_standing(ms, strategy="threshold") == {4, 5, 6}


def test_single_template_returns_empty():
    assert segment_free_standing({0: 0.5}) == set()


def test_all_equal_returns_empty():
    assert segment_free_standing({0: 0.5, 1: 0.5, 2: 0.5}) == set()


def test_empty_returns_empty():
    assert segment_free_standing({}) == set()
