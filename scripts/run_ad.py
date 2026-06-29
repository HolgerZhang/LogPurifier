"""AD reproduction CLI (per-stage caching, loguru logging).

Examples:
    uv run python scripts/run_ad.py --window 300 --max-lines 500000
    uv run python scripts/run_ad.py --window 300 --max-lines 0 --models IM OCSVM PCA IForest
    uv run python scripts/run_ad.py --window 300 --force --log-level DEBUG
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "third_party"))

from logpurifier.ad_eval import format_results
from logpurifier.logging_config import logger, setup_logging
from logpurifier.models import MODEL_REGISTRY
from logpurifier.pipeline import run_pipeline
from logpurifier.windowing import WINDOW_SECONDS


def main():
    ap = argparse.ArgumentParser(description="LogPurifier AD reproduction (BGL)")
    ap.add_argument("--bgl", default="data/BGL/BGL.log")
    ap.add_argument("--dataset", default="BGL")
    ap.add_argument("--window", type=int, default=300, help=f"sizes {WINDOW_SECONDS}")
    ap.add_argument("--max-lines", type=int, default=0, help="0 = all")
    ap.add_argument("--strategy", default="label", choices=["label", "threshold"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--models", nargs="+", default=None,
        choices=list(MODEL_REGISTRY), help="model set, default IM OCSVM",
    )
    ap.add_argument("--oov-min-count", type=int, default=10)
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--force", action="store_true", help="ignore cache and recompute")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    setup_logging(level=args.log_level)

    results, tfs = run_pipeline(
        bgl_path=args.bgl,
        dataset=args.dataset,
        window=args.window,
        max_lines=args.max_lines,
        strategy=args.strategy,
        seed=args.seed,
        models=args.models,
        oov_min_count=args.oov_min_count,
        artifacts_dir=args.artifacts,
        force=args.force,
    )
    logger.info("free-standing templates Tfs ({}): {}", len(tfs), sorted(tfs))
    logger.info("results summary:\n{}", format_results(results))


if __name__ == "__main__":
    main()
