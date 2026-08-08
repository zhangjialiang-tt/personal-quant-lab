"""M5.5 regime tests: Trend/Volatility/Liquidity labels, expanding-median T-1
thresholds, future-leak invariance, only-observed combos, Rate deferred."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pql.validation.regimes import (
    liquidity_label,
    regime_analysis,
    trend_label,
    volatility_label,
)


def _close_series(n: int = 300, drift: float = 0.001, seed: int = 0) -> pd.Series:
    rng = np.random.RandomState(seed)
    rets = rng.normal(drift, 0.01, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.Series(np.cumprod(1 + rets) * 100.0, index=idx)


def test_trend_label_up_when_above_ma200():
    close = _close_series(n=300, drift=0.002, seed=1)
    label = trend_label(close)
    assert label.iloc[-1] == "UP"  # rising above its MA200 near the end


def test_trend_label_down_when_below_ma():
    close = _close_series(n=300, drift=-0.002, seed=2)
    label = trend_label(close)
    assert label.iloc[-1] == "DOWN"


def test_volatility_uses_expanding_median_shift1():
    close = _close_series(n=300, seed=3)
    vol = close.pct_change().rolling(20, min_periods=20).std() * np.sqrt(252)
    thr = vol.expanding(min_periods=1).median().shift(1)
    # the label at T must equal (vol[T] > threshold[T]) where threshold uses <= T-1
    label = volatility_label(close)
    manual = (vol > thr).map({True: "HIGH_VOL", False: "LOW_VOL"}).fillna("LOW_VOL")
    assert (label == manual).all()


def test_liquidity_uses_expanding_median_shift1():
    idx = pd.date_range("2023-01-01", periods=300, freq="B")
    amount = pd.Series(np.abs(np.random.RandomState(4).normal(1e8, 2e7, 300)), index=idx)
    ma = amount.rolling(20, min_periods=20).mean()
    thr = ma.expanding(min_periods=1).median().shift(1)
    label = liquidity_label(amount)
    manual = (ma > thr).map({True: "HIGH_LIQ", False: "LOW_LIQ"}).fillna("LOW_LIQ")
    assert (label == manual).all()


def test_future_leak_does_not_alter_past_labels():
    """Same past + two different futures -> identical labels in the past span."""
    n_past = 200
    past_close = _close_series(n=n_past, seed=5)
    idx = pd.date_range("2023-01-01", periods=300, freq="B")
    # two different futures
    up = np.cumprod(1 + np.random.RandomState(6).normal(0.002, 0.01, 100))
    down = np.cumprod(1 + np.random.RandomState(7).normal(-0.002, 0.01, 100))
    closeA = pd.concat([past_close, pd.Series(past_close.iloc[-1] * up, index=idx[n_past:])])
    closeB = pd.concat([past_close, pd.Series(past_close.iloc[-1] * down, index=idx[n_past:])])
    amount = pd.Series(1e8, index=idx)  # constant amount -> LOW_LIQ everywhere

    from pql.validation.regimes import regime_labels

    labA = regime_labels(closeA, amount)
    labB = regime_labels(closeB, amount)
    past_slice = slice(0, n_past)
    assert (labA.iloc[past_slice] == labB.iloc[past_slice]).all().all()


def _regime_extra():
    pass


def test_rate_regime_not_implemented(tmp_path):
    from pql.validation.base import load_context
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path, n_days=500)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    rg = regime_analysis(spec, ds, cost, data_root)
    assert rg["rate_regime"] == "not_implemented_v0.1"
    assert rg["observed_combo_count"] >= 1
    # only observed combos emitted (no fabricated 8)
    combos = [c["regime_combo"] for c in rg["combos"]]
    assert len(combos) == len(set(combos))
    for c in rg["combos"]:
        assert c["n_days"] > 0