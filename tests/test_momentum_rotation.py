"""M5.1 ETF Momentum Rotation tests: relative/absolute momentum, MA filter,
monthly rebalance, Top-K equal weight, cash fallback, deterministic ties,
future-data invariance, TargetWeightIntent type."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pql.backtest.engine import TargetWeightIntent
from pql.signals.momentum_rotation import (
    first_trading_day_of_month,
    momentum_rotation_signal,
)

A, B, C, D = "510300.SH", "510500.SH", "518880.SH", "511010.SH"


def _research_trends(daily: dict[str, float], n: int = 36) -> pd.DataFrame:
    """Each symbol grows at a daily-compounded rate; returns long research frame."""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rows = []
    for sym, g in daily.items():
        price = 10.0 * (1 + g) ** np.arange(n)
        for d, v in zip(dates, price):
            rows.append({"date": d, "symbol": sym, "close_adj": float(v)})
    return pd.DataFrame(rows)


def _signal(research, **kw):
    return momentum_rotation_signal(research, momentum_days=5, top_k=2, **kw)


def test_returns_target_weight_intent():
    r = _research_trends({A: 0.01, B: 0.02, C: 0.03, D: 0.005})
    sig = _signal(r)
    assert isinstance(sig, TargetWeightIntent)


def test_momentum_formula_and_absolute_filter():
    r = _research_trends({A: 0.03, B: 0.01, C: 0.02, D: -0.01})
    sig = _signal(r)
    # D has negative momentum -> never held
    assert not (sig.weights[D] > 0).any()
    # A has the highest momentum -> held
    assert (sig.weights[A] > 0).any()


def test_all_negative_momentum_goes_cash():
    r = _research_trends({A: -0.01, B: -0.02, C: -0.03, D: -0.005})
    sig = _signal(r)
    # any written rebalance row is all-zero (100% cash)
    written = sig.weights.dropna(how="all")
    assert not written.empty  # rebalances happened
    assert not (written != 0).any().any()


def test_ma_filter_warmup_not_eligible():
    # rising data; ma_filter=200 with short data -> all rows below MA -> cash
    r = _research_trends({A: 0.02, B: 0.02}, n=40)
    sig = _signal(r, ma_filter=200)
    written = sig.weights.dropna(how="all")
    assert not (written != 0).any().any()


def test_ma_filter_eligible_above_ma():
    # ma_filter=5; steadily rising -> after warmup above MA -> held
    r = _research_trends({A: 0.02, B: 0.01}, n=40)
    sig = _signal(r, ma_filter=5)
    assert (sig.weights[A] > 0).any()


def test_first_trading_day_of_month():
    dates = pd.to_datetime(["2024-05-31", "2024-06-03", "2024-06-04", "2024-07-01"])
    first = first_trading_day_of_month(dates)
    assert first == [pd.Timestamp("2024-05-31"), pd.Timestamp("2024-06-03"),
                     pd.Timestamp("2024-07-01")]


def test_rebalance_only_first_trading_day_and_nan_elsewhere():
    # business-day calendar: June 2024's first business day is 2024-06-03
    r = _research_trends({A: 0.02, B: 0.01}, n=40)
    sig = _signal(r)
    # non-rebalance rows are entirely NaN
    first_of_month = set(first_trading_day_of_month(sig.weights.index))
    non_rebal = sig.weights[~sig.weights.index.isin(list(first_of_month))]
    assert non_rebal.isna().all().all()


def test_top_k_equal_weight():
    r = _research_trends({A: 0.04, B: 0.03, C: 0.02, D: 0.01}, n=40)
    for k in (1, 2, 3):
        sig = momentum_rotation_signal(r, momentum_days=5, top_k=k)
        written = sig.weights.dropna(how="all")
        row = written.iloc[-1]
        held = row[row > 0]
        assert len(held) == k
        assert np.allclose(held.to_numpy(), 1.0 / k, atol=1e-9)


def test_single_eligible_gets_full_weight():
    r = _research_trends({A: 0.03, B: -0.01, C: -0.02, D: -0.03}, n=40)
    sig = momentum_rotation_signal(r, momentum_days=5, top_k=3)
    written = sig.weights.dropna(how="all")
    row = written.iloc[-1]
    assert row[A] == pytest.approx(1.0)
    assert row[B] == 0.0 and row[C] == 0.0 and row[D] == 0.0


def test_effective_k_respects_max_positions_ceiling():
    r = _research_trends({A: 0.05, B: 0.04, C: 0.03, D: 0.02}, n=40)
    # top_k=3 but max_positions=2 -> effective_k=2
    sig = momentum_rotation_signal(r, momentum_days=5, top_k=3, max_positions=2)
    row = sig.weights.dropna(how="all").iloc[-1]
    assert len(row[row > 0]) == 2


def test_deterministic_tie_break_by_symbol():
    # A and B have IDENTICAL momentum -> tie broken by canonical symbol (A < B)
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    base = 10.0 * 1.02 ** np.arange(30)
    rows = []
    for sym in (A, B):
        for d, v in zip(dates, base):
            rows.append({"date": d, "symbol": sym, "close_adj": float(v)})
    research = pd.DataFrame(rows)
    # shuffle input order to prove result is order-independent
    research = research.sample(frac=1.0, random_state=7).reset_index(drop=True)
    sig = momentum_rotation_signal(research, momentum_days=5, top_k=1)
    row = sig.weights.dropna(how="all").iloc[-1]
    held = row[row > 0].index.tolist()
    assert held == [A]


def test_future_data_invariance():
    research = _research_trends({A: 0.02, B: 0.01, C: 0.015, D: 0.005}, n=40)
    full = momentum_rotation_signal(research, momentum_days=5, top_k=2)
    dates = pd.to_datetime(research["date"].unique())
    for t in dates[10:20:2]:
        trunc = research[research["date"] <= t]
        sig = momentum_rotation_signal(trunc, momentum_days=5, top_k=2)
        for sym in full.weights.columns:
            fv = full.weights.loc[t, sym]
            sv = sig.weights.loc[t, sym]
            if pd.isna(fv) and pd.isna(sv):
                continue
            assert fv == pytest.approx(sv, rel=1e-9) if pd.notna(fv) else np.isnan(sv)