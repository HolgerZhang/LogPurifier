"""Unit tests for dependency score.

Golden values from the paper's Fig.1 running example (Section III-A):
dScore_f(memory,send)=0.5, mScore send=check=0.875, memory=0.75.
"""

import math

from logpurifier.dependency import (
    d_score_backward,
    d_score_calc,
    d_score_forward,
    m_score,
)

# Template encoding for the running example (identity only)
SEND, CHECK, MEMORY = 0, 1, 2
# Paper: send={e1,e4,e6,e8}, check={e2,e5,e7,e10}, memory={e3,e9}
L_EG = [[SEND, CHECK, MEMORY, SEND, CHECK, SEND, CHECK, SEND, MEMORY, CHECK]]
T = [SEND, CHECK, MEMORY]


def test_forward_memory_send_equals_half():
    assert math.isclose(d_score_forward(MEMORY, SEND, L_EG), 0.5, abs_tol=1e-9)


def test_mscore_golden_values():
    ms = m_score(L_EG, T)
    assert math.isclose(ms[SEND], 0.875, abs_tol=1e-9)
    assert math.isclose(ms[CHECK], 0.875, abs_tol=1e-9)
    assert math.isclose(ms[MEMORY], 0.75, abs_tol=1e-9)


def test_memory_is_lowest():
    """Free-standing memory should have the lowest mScore."""
    ms = m_score(L_EG, T)
    assert ms[MEMORY] < ms[SEND]
    assert ms[MEMORY] < ms[CHECK]


def test_calc_is_max_of_directions():
    f = d_score_forward(MEMORY, SEND, L_EG)
    b = d_score_backward(MEMORY, SEND, L_EG)
    assert math.isclose(d_score_calc(MEMORY, SEND, L_EG), max(f, b), abs_tol=1e-12)


def test_empty_and_single_template():
    """Absent template scores 0; empty logs are safe."""
    assert d_score_forward(99, SEND, L_EG) == 0.0
    assert m_score([], T) == {SEND: 0.0, CHECK: 0.0, MEMORY: 0.0}
    assert m_score(L_EG, [SEND]) == {SEND: 0.0}


def test_no_first_following_scores_zero():
    """No first-following (NaE) contributes 0; backward still finds it."""
    logs = [[CHECK, SEND]]
    assert d_score_forward(SEND, CHECK, logs) == 0.0
    assert d_score_calc(SEND, CHECK, logs) > 0.0
