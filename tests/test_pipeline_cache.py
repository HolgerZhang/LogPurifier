"""Unit tests for per-stage on-disk caching (format round-trip, no real BGL needed)."""

from logpurifier.parsing import parse_structured
from logpurifier.pipeline import stage_purify, stage_split, stage_window


def _entries():
    # Two time windows (>300s apart), each with a few templates
    recs = []
    for t in range(0, 50, 5):
        recs.append((t, 1 + (t // 5) % 3, False))
    for t in range(1000, 1050, 5):
        recs.append((t, 1 + (t // 5) % 3, t >= 1030))  # later part has anomalies
    return parse_structured(recs)


def test_window_cache_roundtrip(tmp_path):
    entries = _entries()
    s1, l1 = stage_window(entries, 300, tmp_path, force=False)  # write
    assert (tmp_path / "windows_w300.npz").exists()
    s2, l2 = stage_window(entries, 300, tmp_path, force=False)  # read
    assert s1 == s2 and l1 == l2


def test_split_cache_roundtrip(tmp_path):
    entries = _entries()
    seqs, labels = stage_window(entries, 300, tmp_path, force=False)
    tr1, te1, tl1 = stage_split(seqs, labels, 300, 0.8, 42, tmp_path, force=False)
    tr2, te2, tl2 = stage_split(seqs, labels, 300, 0.8, 42, tmp_path, force=False)
    assert tr1 == tr2 and te1 == te2 and tl1 == tl2


def test_purify_cache_roundtrip(tmp_path):
    train = [[1, 2, 3], [1, 2, 3], [1, 2, 99, 3]]
    tfs1 = stage_purify(train, 300, 42, "label", tmp_path, force=False)
    assert (tmp_path / "tfs_w300_s42_label.json").exists()
    tfs2 = stage_purify(train, 300, 42, "label", tmp_path, force=False)
    assert tfs1 == tfs2


def test_force_recomputes(tmp_path):
    entries = _entries()
    stage_window(entries, 300, tmp_path, force=False)
    s, l = stage_window(entries, 300, tmp_path, force=True)
    assert len(s) == len(l) > 0
