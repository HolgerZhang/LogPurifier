"""LogPurifier main flow (paper Algorithm 1): L,T -> mScore -> Tfs -> remove -> Lcl."""

from __future__ import annotations

from typing import Iterable

from .clustering import segment_free_standing
from .dependency import Logs, m_score


def identify_free_standing(
    logs: Logs, templates: Iterable[int] | None = None
) -> set[int]:
    """Identify free-standing template set Tfs (logs unchanged). Templates collected if None."""
    if templates is None:
        templates = sorted({t for log in logs for t in log})
    else:
        templates = list(templates)
    scores = m_score(logs, templates)
    return segment_free_standing(scores)


def remove_templates(logs: Logs, to_remove: set[int]) -> Logs:
    """Remove messages of templates in to_remove from each log."""
    if not to_remove:
        return [list(log) for log in logs]
    return [[t for t in log if t not in to_remove] for log in logs]


def purify(
    logs: Logs, templates: Iterable[int] | None = None
) -> tuple[Logs, set[int]]:
    """Return (cleaned logs Lcl, free-standing set Tfs)."""
    tfs = identify_free_standing(logs, templates)
    cleaned = remove_templates(logs, tfs)
    return cleaned, tfs
