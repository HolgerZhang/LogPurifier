"""Anomaly detection model registry.

Unified interface: fit(X) trains (normal data only); predict(X) returns 0/1 (1=anomaly).
- IM: vendored loglizer.InvariantsMiner (unsupervised).
- OCSVM: sklearn OneClassSVM (semi-supervised, matches the paper; loglizer's own SVM is a
  supervised LinearSVC, see specs/00-overview.md and README "paper inconsistencies").
- PCA / IsolationForest / LogClustering: loglizer models, for comparison and case study.

To add a model, write a wrapper and register it in MODEL_REGISTRY.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from sklearn.svm import OneClassSVM

from loglizer.models import (
    PCA,
    InvariantsMiner,
    IsolationForest,
    LogClustering,
)
from loglizer.utils import metrics

from .logging_config import logger, redirect_stdout_to_logger


class _Model:
    """Base interface: predict returns 0/1 (1=anomaly)."""

    name = "base"

    def fit(self, X) -> None:  # pragma: no cover
        raise NotImplementedError

    def predict(self, X) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def evaluate(self, X, y_true) -> tuple[float, float, float]:
        return metrics(self.predict(X), np.asarray(y_true))


class IMModel(_Model):
    """Invariant Mining (loglizer, unsupervised, unbounded length)."""

    name = "IM"

    def __init__(self, epsilon: float = 0.5):
        self._m = InvariantsMiner(epsilon=epsilon)

    def fit(self, X):
        with redirect_stdout_to_logger("IM"):
            self._m.fit(X)

    def predict(self, X) -> np.ndarray:
        with redirect_stdout_to_logger("IM"):
            return np.asarray(self._m.predict(X)).astype(int)


class OCSVMModel(_Model):
    """one-class SVM (sklearn, semi-supervised, normal data only)."""

    name = "OCSVM"

    def __init__(self, nu: float = 0.1, kernel: str = "rbf", gamma: str = "auto"):
        self._m = OneClassSVM(kernel=kernel, nu=nu, gamma=gamma)

    def fit(self, X):
        self._m.fit(X)

    def predict(self, X) -> np.ndarray:
        return (self._m.predict(X) == -1).astype(int)  # +1 normal / -1 anomaly -> 0/1


class PCAModel(_Model):
    """PCA anomaly detection (loglizer, unsupervised)."""

    name = "PCA"

    def __init__(self, n_components: float = 0.95, c_alpha: float = 3.2905):
        self._m = PCA(n_components=n_components, c_alpha=c_alpha)

    def fit(self, X):
        with redirect_stdout_to_logger("PCA"):
            self._m.fit(X)

    def predict(self, X) -> np.ndarray:
        with redirect_stdout_to_logger("PCA"):
            return np.asarray(self._m.predict(X)).astype(int)


class IsolationForestModel(_Model):
    """Isolation Forest (loglizer, unsupervised)."""

    name = "IForest"

    def __init__(self, n_estimators: int = 100, contamination: float = 0.03):
        self._m = IsolationForest(
            n_estimators=n_estimators, contamination=contamination
        )

    def fit(self, X):
        with redirect_stdout_to_logger("IForest"):
            self._m.fit(X)

    def predict(self, X) -> np.ndarray:
        with redirect_stdout_to_logger("IForest"):
            return np.asarray(self._m.predict(X)).astype(int)


class LogClusteringModel(_Model):
    """Log Clustering (loglizer, semi-supervised, normal data only)."""

    name = "LogCluster"

    def __init__(self, max_dist: float = 0.3, anomaly_threshold: float = 0.3):
        self._m = LogClustering(
            max_dist=max_dist, anomaly_threshold=anomaly_threshold
        )

    def fit(self, X):
        with redirect_stdout_to_logger("LogCluster"):
            self._m.fit(X)

    def predict(self, X) -> np.ndarray:
        with redirect_stdout_to_logger("LogCluster"):
            return np.asarray(self._m.predict(X)).astype(int)


# Registry: name -> factory (takes **kwargs)
MODEL_REGISTRY: dict[str, Callable[..., _Model]] = {
    "IM": IMModel,
    "OCSVM": OCSVMModel,
    "PCA": PCAModel,
    "IForest": IsolationForestModel,
    "LogCluster": LogClusteringModel,
}

# Paper's two models (Section IV-C); the rest are for comparison / case study
PAPER_MODELS = ["IM", "OCSVM"]


def build_model(name: str, **kwargs) -> _Model:
    """Construct a model by name."""
    if name not in MODEL_REGISTRY:
        raise ValueError(f"unknown model {name!r}; available: {list(MODEL_REGISTRY)}")
    logger.debug("building model {} kwargs={}", name, kwargs)
    return MODEL_REGISTRY[name](**kwargs)


__all__ = ["MODEL_REGISTRY", "PAPER_MODELS", "build_model", "metrics"]
