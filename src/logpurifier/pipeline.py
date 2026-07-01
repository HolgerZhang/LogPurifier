"""AD reproduction flow with per-stage on-disk caching under artifacts/.

Line datasets (BGL/Thunderbird): parse -> window -> split -> purify -> evaluate.
HDFS (session): sessions -> split -> purify -> evaluate (no window, win_key=0).
See specs/05-persistence.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .ad_eval import (
    ModelResult,
    _eval_models,
    identify_free_standing,
    remove_templates,
    split_train_test,
)
from .datasets import is_session_dataset
from .logging_config import logger
from .parsing import ParsedEntry, load_hdfs_sessions, parse_line_file
from .windowing import fixed_time_windows


def _save_seqs(path: Path, sequences: list[list[int]], labels: list[int]) -> None:
    """Save variable-length sequences + labels as npz (ragged: flat values + lengths)."""
    flat = np.array([t for s in sequences for t in s], dtype=np.int64)
    lengths = np.array([len(s) for s in sequences], dtype=np.int64)
    np.savez(path, flat=flat, lengths=lengths, labels=np.array(labels, dtype=np.int64))


def _decode_ragged(flat, lengths) -> list[list[int]]:
    seqs, pos = [], 0
    for n in lengths:
        seqs.append(flat[pos : pos + n].tolist())
        pos += n
    return seqs


def _load_seqs(path: Path) -> tuple[list[list[int]], list[int]]:
    d = np.load(path)
    return _decode_ragged(d["flat"], d["lengths"]), d["labels"].tolist()


def stage_parse(
    path: str, dataset: str, max_lines: int, out: Path, force: bool
) -> tuple[list[ParsedEntry], bool]:
    """Parse a line dataset. Returns (entries, cache_hit). Cache key includes max_lines."""
    tag = "all" if not max_lines else str(max_lines)
    cache = out / f"parsed_{tag}.parquet"
    if cache.exists() and not force:
        df = pd.read_parquet(cache)
        entries = [
            ParsedEntry(ts, int(tid), bool(a))
            for ts, tid, a in zip(df.timestamp, df.template_id, df.is_anomaly)
        ]
        return entries, True
    entries = parse_line_file(path, dataset, max_lines=max_lines)
    pd.DataFrame(
        {
            "timestamp": [e.timestamp for e in entries],
            "template_id": [e.template_id for e in entries],
            "is_anomaly": [e.is_anomaly for e in entries],
        }
    ).to_parquet(cache)
    return entries, False


def stage_sessions(
    log_path: str, label_path: str, max_lines: int, out: Path, force: bool
) -> tuple[tuple[list[list[int]], list[int]], bool]:
    """Parse HDFS into (sequences, labels). Returns ((seqs, labels), cache_hit)."""
    tag = "all" if not max_lines else str(max_lines)
    cache = out / f"sessions_{tag}.npz"
    if cache.exists() and not force:
        return _load_seqs(cache), True
    seqs, labels = load_hdfs_sessions(log_path, label_path, max_lines)
    _save_seqs(cache, seqs, labels)
    return (seqs, labels), False


def stage_window(
    entries: list[ParsedEntry], window: int, out: Path, force: bool
) -> tuple[list[list[int]], list[int]]:
    cache = out / f"windows_w{window}.npz"
    if cache.exists() and not force:
        return _load_seqs(cache)
    seqs, labels = fixed_time_windows(entries, window)
    _save_seqs(cache, seqs, labels)
    return seqs, labels


def stage_split(
    seqs: list[list[int]], labels: list[int], window: int, ratio: float, seed: int,
    out: Path, force: bool,
) -> tuple[list[list[int]], list[list[int]], list[int]]:
    cache = out / f"split_w{window}_s{seed}.npz"
    if cache.exists() and not force:
        d = np.load(cache, allow_pickle=True)
        tr = _decode_ragged(d["tr_flat"], d["tr_len"])
        te = _decode_ragged(d["te_flat"], d["te_len"])
        return tr, te, d["te_labels"].tolist()
    tr, te, te_labels = split_train_test(seqs, labels, ratio, seed)
    np.savez(
        cache,
        tr_flat=np.array([t for s in tr for t in s], dtype=np.int64),
        tr_len=np.array([len(s) for s in tr], dtype=np.int64),
        te_flat=np.array([t for s in te for t in s], dtype=np.int64),
        te_len=np.array([len(s) for s in te], dtype=np.int64),
        te_labels=np.array(te_labels, dtype=np.int64),
    )
    return tr, te, te_labels


def stage_purify(
    train_seqs: list[list[int]], window: int, seed: int,
    out: Path, force: bool,
) -> set[int]:
    cache = out / f"tfs_w{window}_s{seed}.json"
    if cache.exists() and not force:
        return set(json.loads(cache.read_text()))
    tfs = identify_free_standing(train_seqs)
    cache.write_text(json.dumps(sorted(tfs)))
    return tfs


def run_pipeline(
    data_path: str = "data/BGL/BGL.log",
    dataset: str = "BGL",
    window: int = 300,
    max_lines: int = 0,
    label_path: str | None = None,
    seed: int = 42,
    train_ratio: float = 0.8,
    models: list[str] | None = None,
    oov_min_count: int = 10,
    model_kwargs: dict | None = None,
    artifacts_dir: str = "artifacts",
    run_id: str | None = None,
    force: bool = False,
) -> tuple[list[ModelResult], set[int]]:
    """Run the full AD reproduction flow with per-stage caching.

    Line datasets use time windows; HDFS uses block_id sessions (window ignored, win_key=0).
    Each run is isolated under artifacts/<dataset>/<run_id>/. If run_id is None, generates
    an ID from current timestamp (YYYYMMDD_HHMMSS) concatenated with a 6-character hex UUID
    fragment to prevent collisions when multiple runs start in the same second.
    """
    if run_id is None:
        from datetime import datetime
        import uuid
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        run_id = f"{ts}_{suffix}"

    out = Path(artifacts_dir) / dataset / run_id
    out.mkdir(parents=True, exist_ok=True)
    session = is_session_dataset(dataset)
    win_key = 0 if session else window
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "max_lines": max_lines, "window": window, "seed": seed}, indent=2)
    )
    logger.info(
        "start AD flow: dataset={} run_id={} {} max_lines={} models={}",
        dataset, run_id, "session" if session else f"window={window}s",
        max_lines or "all", models or "default(IM,OCSVM)",
    )

    t0 = time.perf_counter()
    if session:
        if not label_path:
            raise ValueError("HDFS requires label_path (anomaly_label.csv)")
        (seqs, labels), hit = stage_sessions(data_path, label_path, max_lines, out, force)
        logger.info(
            "[sessions] {} blocks, {} anomalous ({})",
            len(seqs), sum(labels), "cache hit" if hit else f"in {time.perf_counter()-t0:.1f}s",
        )
    else:
        entries, hit = stage_parse(data_path, dataset, max_lines, out, force)
        logger.info(
            "[parse] {} entries ({})",
            len(entries), "cache hit" if hit else f"parsed in {time.perf_counter()-t0:.1f}s",
        )
        seqs, labels = stage_window(entries, window, out, force)
        logger.info("[window] {} window sequences, {} anomalous", len(seqs), sum(labels))

    tr, te, te_labels = stage_split(seqs, labels, win_key, train_ratio, seed, out, force)
    logger.info(
        "[split] train {} / test {} ({} anomalous)", len(tr), len(te), sum(te_labels)
    )

    tfs = stage_purify(tr, win_key, seed, out, force)
    logger.info("[purify] free-standing templates Tfs = {}", len(tfs))

    logger.info("[evaluate] org (uncleaned) ...")
    results = _eval_models(tr, te, te_labels, "org", models, oov_min_count, model_kwargs)
    logger.info("[evaluate] cleaned ...")
    cl_tr = remove_templates(tr, tfs)
    cl_te = remove_templates(te, tfs)
    cl_tr = [s for s in cl_tr if s] or cl_tr
    results += _eval_models(
        cl_tr, cl_te, te_labels, "cleaned", models, oov_min_count, model_kwargs
    )

    _save_results(out, results, win_key, seed)
    logger.info("done, results written to {}", out / f"results_w{win_key}_s{seed}.csv")
    return results, tfs


def _save_results(out: Path, results: list[ModelResult], window, seed) -> None:
    cache = out / f"results_w{window}_s{seed}.csv"
    pd.DataFrame([r.__dict__ for r in results]).to_csv(cache, index=False)
