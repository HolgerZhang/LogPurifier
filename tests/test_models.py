"""Unit tests for the model registry."""

import numpy as np
import pytest

from logpurifier.models import MODEL_REGISTRY, PAPER_MODELS, build_model


def _toy_data():
    """Normal samples with concentrated counts; last 10 test rows clearly deviate."""
    rng = np.random.default_rng(0)
    x_train = rng.integers(0, 2, size=(40, 5)).astype(float)
    x_test = np.vstack([x_train[:10], x_train[:10] + 5])
    y_test = np.array([0] * 10 + [1] * 10)
    return x_train, x_test, y_test


def test_registry_contains_paper_models():
    assert "IM" in MODEL_REGISTRY and "OCSVM" in MODEL_REGISTRY
    assert PAPER_MODELS == ["IM", "OCSVM"]


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        build_model("NoSuchModel")


@pytest.mark.parametrize("name", list(MODEL_REGISTRY))
def test_each_model_fit_predict_binary(name):
    """Every registered model fits normal data and outputs 0/1 predictions."""
    x_train, x_test, _ = _toy_data()
    model = build_model(name)
    model.fit(x_train)
    pred = model.predict(x_test)
    assert pred.shape == (x_test.shape[0],)
    assert set(np.unique(pred)).issubset({0, 1})


def test_ocsvm_semi_supervised_fit_only_normal():
    """OCSVM fits on normal data only (no labels)."""
    x_train, x_test, y_test = _toy_data()
    model = build_model("OCSVM", nu=0.1)
    model.fit(x_train)
    p, r, f1 = model.evaluate(x_test, y_test)
    assert 0.0 <= f1 <= 1.0
