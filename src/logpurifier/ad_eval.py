"""AD evaluation orchestration (paper Section IV-C / V): org vs cleaned, multi-model.

Split per paper: 80% normal for training; test = 20% normal + all anomalous. Cleaning
identifies Tfs on the training set, then removes it from both train and test. Models come
from models.MODEL_REGISTRY (default IM+OCSVM).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from loglizer.preprocessing import FeatureExtractor

from .logging_config import logger, redirect_stdout_to_logger
from .models import PAPER_MODELS, build_model
from .purifier import identify_free_standing, remove_templates


def _safe_metrics(y_pred, y_true) -> tuple[float, float, float]:
    """Binary precision/recall/f1; zeros (not warnings) when no positive prediction."""
    from sklearn.metrics import precision_recall_fscore_support

    p, r, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return float(p), float(r), float(f1)


@dataclass
class ModelResult:
    model: str
    variant: str            # "org" | "cleaned"
    precision: float
    recall: float
    f1: float
    train_seconds: float


def split_train_test(
    sequences: list[list[int]],
    labels: list[int],
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[list[int]], list[list[int]], list[int]]:
    """80% normal for training; test = remaining 20% normal + all anomalous.

    Returns (train_seqs, test_seqs, test_labels); train is all normal.
    """
    rng = np.random.default_rng(seed)
    normal_idx = [i for i, y in enumerate(labels) if y == 0]
    anom_idx = [i for i, y in enumerate(labels) if y == 1]

    rng.shuffle(normal_idx)
    n_train = int(len(normal_idx) * train_ratio)
    train_normal = normal_idx[:n_train]
    test_normal = normal_idx[n_train:]

    train_seqs = [sequences[i] for i in train_normal]
    test_idx = test_normal + anom_idx
    test_seqs = [sequences[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    return train_seqs, test_seqs, test_labels


def _to_array(seqs: list[list[int]]) -> np.ndarray:
    """Convert variable-length sequences to the object array FeatureExtractor expects."""
    arr = np.empty(len(seqs), dtype=object)
    for i, s in enumerate(seqs):
        arr[i] = [str(t) for t in s]  # template id as string event token
    return arr


def _eval_models(
    train_seqs: list[list[int]],
    test_seqs: list[list[int]],
    test_labels: list[int],
    variant: str,
    models: list[str] | None = None,
    oov_min_count: int = 10,
    model_kwargs: dict | None = None,
) -> list[ModelResult]:
    """Train and evaluate the given models on the train/test sets.

    Features use loglizer's native OOV (oov_min_count) to merge low-frequency templates
    into one dimension. models defaults to the paper's IM+OCSVM.
    """
    models = models or PAPER_MODELS
    model_kwargs = model_kwargs or {}
    results: list[ModelResult] = []
    if not train_seqs or not test_seqs:
        logger.warning("[{}] empty train or test set, skipping", variant)
        return results

    fe = FeatureExtractor()
    with redirect_stdout_to_logger("feature"):
        x_train = fe.fit_transform(
            _to_array(train_seqs), oov=True, min_count=oov_min_count
        )
        x_test = fe.transform(_to_array(test_seqs))
    y_test = np.array(test_labels)
    logger.info(
        "[{}] feature matrix train={}x{} test={}x{}",
        variant, x_train.shape[0], x_train.shape[1], x_test.shape[0], x_test.shape[1],
    )

    for i, name in enumerate(models, 1):
        logger.info("[{}] ({}/{}) training {} ...", variant, i, len(models), name)
        model = build_model(name, **model_kwargs.get(name, {}))
        t0 = time.perf_counter()
        model.fit(x_train)
        train_s = time.perf_counter() - t0
        p, r, f1 = _safe_metrics(model.predict(x_test), y_test)
        logger.info(
            "[{}] {} done: P={:.3f} R={:.3f} F1={:.3f} ({:.2f}s)",
            variant, name, p, r, f1, train_s,
        )
        results.append(ModelResult(name, variant, p, r, f1, train_s))

    return results


def evaluate_ad(
    sequences: list[list[int]],
    labels: list[int],
    train_ratio: float = 0.8,
    seed: int = 42,
    strategy: str = "label",
    models: list[str] | None = None,
    oov_min_count: int = 10,
    model_kwargs: dict | None = None,
) -> tuple[list[ModelResult], set[int]]:
    """End-to-end AD evaluation: returns (org+cleaned multi-model results, Tfs).

    Cleaning per paper: identify Tfs on train, then remove from both train and test.
    """
    train_seqs, test_seqs, test_labels = split_train_test(
        sequences, labels, train_ratio, seed
    )

    results = _eval_models(
        train_seqs, test_seqs, test_labels, "org",
        models, oov_min_count, model_kwargs,
    )

    tfs = identify_free_standing(train_seqs, strategy=strategy)
    logger.info("LogPurifier identified {} free-standing templates", len(tfs))
    cl_train = remove_templates(train_seqs, tfs)
    cl_test = remove_templates(test_seqs, tfs)
    cl_train = [s for s in cl_train if s] or cl_train
    results += _eval_models(
        cl_train, cl_test, test_labels, "cleaned",
        models, oov_min_count, model_kwargs,
    )

    return results, tfs


def format_results(results: list[ModelResult]) -> str:
    """Format results as a comparison table."""
    header = f"{'model':<12}{'variant':<10}{'precision':>10}{'recall':>10}{'f1':>10}{'train_s':>10}"
    lines = [header, "-" * len(header)]
    for r in results:
        lines.append(
            f"{r.model:<12}{r.variant:<10}{r.precision:>10.3f}{r.recall:>10.3f}"
            f"{r.f1:>10.3f}{r.train_seconds:>10.3f}"
        )
    return "\n".join(lines)
