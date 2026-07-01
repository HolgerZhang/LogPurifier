"""AD reproduction CLI (per-stage caching, loguru logging).

Examples:
    uv run python scripts/run_ad.py --dataset BGL --window 300 --max-lines 500000
    uv run python scripts/run_ad.py --dataset HDFS
    uv run python scripts/run_ad.py --dataset Thunderbird --max-lines 1000000 --models IM OCSVM PCA
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "third_party"))

from logpurifier.ad_eval import format_results
from logpurifier.datasets import (
    ALL_DATASETS,
    default_data_path,
    default_label_path,
    is_session_dataset,
)
from logpurifier.logging_config import logger, setup_logging
from logpurifier.models import MODEL_REGISTRY
from logpurifier.pipeline import run_pipeline
from logpurifier.windowing import WINDOW_SECONDS


def main():
    ap = argparse.ArgumentParser(description="LogPurifier AD reproduction")
    ap.add_argument("--dataset", default="BGL", choices=ALL_DATASETS)
    ap.add_argument("--data-path", default=None, help="log file; default data/<dataset>/<dataset>.log")
    ap.add_argument("--label-path", default=None, help="HDFS anomaly_label.csv; default data/HDFS/anomaly_label.csv")
    ap.add_argument("--window", type=int, default=300, help=f"sizes {WINDOW_SECONDS} (line datasets)")
    ap.add_argument("--max-lines", type=int, default=0, help="0 = all")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--models", nargs="+", default=None,
        choices=list(MODEL_REGISTRY), help="model set, default IM OCSVM",
    )
    ap.add_argument("--oov-min-count", type=int, default=10)
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--run-id", default=None, help="run identifier; default auto-generated timestamp+random")
    ap.add_argument("--force", action="store_true", help="ignore cache and recompute")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    setup_logging(level=args.log_level)

    data_path = args.data_path or default_data_path(args.dataset)
    label_path = args.label_path
    if is_session_dataset(args.dataset) and not label_path:
        label_path = default_label_path(args.dataset)

    results, tfs = run_pipeline(
        data_path=data_path,
        dataset=args.dataset,
        window=args.window,
        max_lines=args.max_lines,
        label_path=label_path,
        seed=args.seed,
        models=args.models,
        oov_min_count=args.oov_min_count,
        artifacts_dir=args.artifacts,
        run_id=args.run_id,
        force=args.force,
    )
    logger.info("free-standing templates Tfs ({}): {}", len(tfs), sorted(tfs))
    logger.info("results summary:\n{}", format_results(results))


if __name__ == "__main__":
    main()
