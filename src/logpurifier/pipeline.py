"""AD reproduction flow with per-stage on-disk caching under artifacts/.

Stages: parse -> window -> split -> purify -> evaluate. See specs/05-persistence.md.
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
from .logging_config import logger
from .parsing import ParsedEntry, parse_bgl_file
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
    bgl_path: str, max_lines: int, out: Path, force: bool
) -> tuple[list[ParsedEntry], bool]:
    """Returns (entries, cache_hit). Cache key includes max_lines."""
    tag = "all" if not max_lines else str(max_lines)
    cache = out / f"parsed_{tag}.parquet"
    if cache.exists() and not force:
        df = pd.read_parquet(cache)
        entries = [
            ParsedEntry(ts, int(tid), bool(a))
            for ts, tid, a in zip(df.timestamp, df.template_id, df.is_anomaly)
        ]
        return entries, True
    entries = parse_bgl_file(bgl_path, max_lines=max_lines)
    pd.DataFrame(
        {
            "timestamp": [e.timestamp for e in entries],
            "template_id": [e.template_id for e in entries],
            "is_anomaly": [e.is_anomaly for e in entries],
        }
    ).to_parquet(cache)
    return entries, False


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
    train_seqs: list[list[int]], window: int, seed: int, strategy: str,
    out: Path, force: bool,
) -> set[int]:
    cache = out / f"tfs_w{window}_s{seed}_{strategy}.json"
    if cache.exists() and not force:
        return set(json.loads(cache.read_text()))
    tfs = identify_free_standing(train_seqs, strategy=strategy)
    cache.write_text(json.dumps(sorted(tfs)))
    return tfs


def run_pipeline(
    bgl_path: str = "data/BGL/BGL.log",
    dataset: str = "BGL",
    window: int = 300,
    max_lines: int = 0,
    strategy: str = "label",
    seed: int = 42,
    train_ratio: float = 0.8,
    models: list[str] | None = None,
    oov_min_count: int = 10,
    model_kwargs: dict | None = None,
    artifacts_dir: str = "artifacts",
    force: bool = False,
) -> tuple[list[ModelResult], set[int]]:
    """Run the full AD reproduction flow with per-stage caching."""
    out = Path(artifacts_dir) / dataset
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta.json").write_text(
        json.dumps({"max_lines": max_lines, "window": window, "seed": seed}, indent=2)
    )
    logger.info(
        "start AD flow: dataset={} window={}s max_lines={} strategy={} models={}",
        dataset, window, max_lines or "all", strategy, models or "default(IM,OCSVM)",
    )

    t0 = time.perf_counter()
    entries, hit = stage_parse(bgl_path, max_lines, out, force)
    logger.info(
        "[parse] {} entries ({})",
        len(entries), "cache hit" if hit else f"parsed in {time.perf_counter()-t0:.1f}s",
    )

    seqs, labels = stage_window(entries, window, out, force)
    logger.info("[window] {} window sequences, {} anomalous", len(seqs), sum(labels))

    tr, te, te_labels = stage_split(seqs, labels, window, train_ratio, seed, out, force)
    logger.info(
        "[split] train {} / test {} ({} anomalous)", len(tr), len(te), sum(te_labels)
    )

    tfs = stage_purify(tr, window, seed, strategy, out, force)
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

    _save_results(out, results, window, seed, strategy)
    logger.info("done, results written to {}", out / f"results_w{window}_s{seed}_{strategy}.csv")
    return results, tfs


def _save_results(out: Path, results: list[ModelResult], window, seed, strategy) -> None:
    cache = out / f"results_w{window}_s{seed}_{strategy}.csv"
    pd.DataFrame([r.__dict__ for r in results]).to_csv(cache, index=False)
