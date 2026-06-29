"""Unit tests for the LogPurifier main flow (Algorithm 1)."""

from logpurifier.purifier import identify_free_standing, purify, remove_templates

A, B, C, D = 1, 2, 3, 4      # regular: stable transition A->B->C->D
HEARTBEAT = 99               # free-standing: randomly inserted heartbeat


def _make_logs_with_heartbeat():
    """Normal A->B->C->D logs with HEARTBEAT inserted at varying positions.

    HEARTBEAT forms no stable adjacency with any template, so its mScore is much lower
    than regular templates and it should be flagged free-standing.
    """
    return [
        [A, B, HEARTBEAT, C, D],
        [A, B, C, HEARTBEAT, D],
        [HEARTBEAT, A, B, C, D],
        [A, B, C, D, HEARTBEAT],
        [A, HEARTBEAT, B, C, D],
        [A, B, C, D],
        [A, B, C, D],
        [A, B, C, D],
    ]


def test_identify_heartbeat_as_free_standing():
    logs = _make_logs_with_heartbeat()
    tfs = identify_free_standing(logs)
    assert HEARTBEAT in tfs
    assert A not in tfs and B not in tfs and C not in tfs and D not in tfs


def test_purify_removes_heartbeat_lines():
    logs = _make_logs_with_heartbeat()
    cleaned, tfs = purify(logs)
    assert HEARTBEAT in tfs
    assert all(HEARTBEAT not in log for log in cleaned)
    for log in cleaned:
        assert log == [A, B, C, D]


def test_remove_templates_noop_on_empty_set():
    logs = [[A, B, C]]
    assert remove_templates(logs, set()) == [[A, B, C]]


def test_purify_no_free_standing_keeps_logs():
    logs = [[A, B, C, D], [A, B, C, D], [A, B, C, D]]
    cleaned, tfs = purify(logs)
    assert tfs == set()
    assert cleaned == logs
