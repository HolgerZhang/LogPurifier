"""End-to-end tests on a real BGL slice (data/BGL/BGL_200k.log).

The slice is generated from data/BGL/BGL.log on demand. Tests skip only when neither the
slice nor the full BGL.log is available.
"""

from pathlib import Path

import pytest

from logpurifier.parsing import parse_bgl_file
from logpurifier.pipeline import run_pipeline
from logpurifier.windowing import fixed_time_windows

BGL_FULL = Path("data/BGL/BGL.log")
BGL_SLICE = Path("data/BGL/BGL_200k.log")
SLICE_LINES = 200_000


@pytest.fixture(scope="session", autouse=True)
def ensure_slice():
    """Ensure the 200k slice exists; generate it from BGL.log if needed."""
    if BGL_SLICE.exists():
        return
    if not BGL_FULL.exists():
        pytest.skip("neither BGL_200k.log nor BGL.log is available")
    with open(BGL_FULL, encoding="utf-8", errors="ignore") as src:
        lines = [next(src, None) for _ in range(SLICE_LINES)]
    with open(BGL_SLICE, "w", encoding="utf-8") as dst:
        dst.writelines(line for line in lines if line is not None)


def test_parse_real_bgl_slice():
    entries = parse_bgl_file(str(BGL_SLICE), max_lines=SLICE_LINES)
    assert len(entries) > 0
    n_anom = sum(e.is_anomaly for e in entries)
    assert 0 < n_anom < len(entries)  # both classes present (~1.4% anomaly)


def test_windowing_real_bgl_slice():
    entries = parse_bgl_file(str(BGL_SLICE), max_lines=SLICE_LINES)
    seqs, labels = fixed_time_windows(entries, 300)
    assert len(seqs) == len(labels) > 0
    assert any(labels) and not all(labels)


def test_end_to_end_pipeline_real_bgl(tmp_path):
    """Real BGL slice runs org vs cleaned multi-model and yields valid metrics."""
    results, _ = run_pipeline(
        bgl_path=str(BGL_SLICE),
        dataset="BGL_200k_test",
        window=300,
        max_lines=SLICE_LINES,
        models=["OCSVM", "PCA"],
        artifacts_dir=str(tmp_path),
    )
    variants = {(r.model, r.variant) for r in results}
    assert ("OCSVM", "org") in variants
    assert ("OCSVM", "cleaned") in variants
    for r in results:
        assert 0.0 <= r.precision <= 1.0
        assert 0.0 <= r.recall <= 1.0
        assert 0.0 <= r.f1 <= 1.0
    assert (tmp_path / "BGL_200k_test" / "parsed_200000.parquet").exists()


def test_pipeline_cache_hit_second_run(tmp_path):
    """Second run hits the parse cache (parsed file not rewritten)."""
    kw = dict(
        bgl_path=str(BGL_SLICE), dataset="BGL_cache_test", window=300,
        max_lines=SLICE_LINES, models=["OCSVM"], artifacts_dir=str(tmp_path),
    )
    run_pipeline(**kw)
    parsed = tmp_path / "BGL_cache_test" / "parsed_200000.parquet"
    mtime1 = parsed.stat().st_mtime
    run_pipeline(**kw)
    assert parsed.stat().st_mtime == mtime1
