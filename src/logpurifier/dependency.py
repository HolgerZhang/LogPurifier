"""Dependency score computation (paper Section III-A).

A log ``l`` is a sequence of template ids; ``L`` is a list of logs.
See specs/01-dependency-score.md for the algorithm.
"""

from __future__ import annotations

from typing import Iterable

Log = list[int]
Logs = list[Log]


def _first_following_distances(x: int, y: int, log: Log) -> list[float]:
    """cScore contributions of each occurrence of x toward y (0 if no first-following)."""
    x_positions = [i for i, t in enumerate(log) if t == x]
    contributions: list[float] = []
    for k, i in enumerate(x_positions):
        next_x = x_positions[k + 1] if k + 1 < len(x_positions) else len(log)
        c = 0.0
        for j in range(i + 1, next_x):
            if log[j] == y:
                c = 1.0 / (j - i)
                break
        contributions.append(c)
    return contributions


def _count_occurrences(x: int, logs: Logs) -> int:
    """Total occurrences of x across L."""
    return sum(log.count(x) for log in logs)


def d_score_forward(x: int, y: int, logs: Logs) -> float:
    """Forward dependency score."""
    n = _count_occurrences(x, logs)
    if n == 0:
        return 0.0
    total = 0.0
    for log in logs:
        total += sum(_first_following_distances(x, y, log))
    return total / n


def d_score_backward(x: int, y: int, logs: Logs) -> float:
    """Backward dependency score (forward on reversed logs)."""
    reversed_logs = [list(reversed(log)) for log in logs]
    return d_score_forward(x, y, reversed_logs)


def d_score_calc(x: int, y: int, logs: Logs) -> float:
    """Dependency score = max(forward, backward)."""
    return max(d_score_forward(x, y, logs), d_score_backward(x, y, logs))


def m_score(logs: Logs, templates: Iterable[int]) -> dict[int, float]:
    """mScore[x] = max over y != x of dScoreCalc(x, y, L)."""
    templates = list(templates)
    scores: dict[int, float] = {}
    for x in templates:
        best = 0.0
        for y in templates:
            if y == x:
                continue
            best = max(best, d_score_calc(x, y, logs))
        scores[x] = best
    return scores
