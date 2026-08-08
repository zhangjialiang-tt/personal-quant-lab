"""M3 metrics unit tests (D8 domain formulas, independent of vectorbt statistics):
CAGR / annual vol / Sharpe (rf=0, ddof=1, x252) / Max Drawdown / Calmar, plus
metrics_vs_benchmark. Verified against hand-built return series."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pql.backtest.metrics import (
    ANNUALIZATION,
    annual_vol,
    cagr,
    calmar,
    compute_metrics,
    max_drawdown,
    metrics_vs_benchmark,
    sharpe,
)

# equity over 3 return intervals: rets = [0.1, 0.1, -0.1]
_EQ = pd.Series([100.0, 110.0, 121.0, 108.9])
_RETS = pd.Series([0.1, 0.1, -0.1])


def test_cagr_formula():
    expected = (108.9 / 100.0) ** (ANNUALIZATION / 3) - 1
    assert cagr(_EQ) == pytest.approx(expected)


def test_annual_vol_formula():
    expected = _RETS.std(ddof=1) * np.sqrt(ANNUALIZATION)
    assert annual_vol(_EQ) == pytest.approx(expected)


def test_sharpe_formula_rf0_ddof1():
    expected = _RETS.mean() / _RETS.std(ddof=1) * np.sqrt(ANNUALIZATION)
    assert sharpe(_EQ) == pytest.approx(expected)


def test_max_drawdown_negative():
    # peak 121 -> trough 108.9 => -10%
    assert max_drawdown(_EQ) == pytest.approx(-0.1)


def test_calmar_formula():
    dd = max_drawdown(_EQ)
    assert calmar(cagr(_EQ), dd) == pytest.approx(cagr(_EQ) / abs(dd))


def test_compute_metrics_contains_d8_set():
    m = compute_metrics(_EQ)
    assert set(m) == {
        "cagr", "annual_vol", "sharpe", "max_drawdown", "calmar",
        "n_trades", "turnover", "exposure", "win_rate",
    }


def test_metrics_vs_benchmark():
    bench = pd.Series([100.0, 105.0, 110.0, 115.0])
    out = metrics_vs_benchmark(_EQ, bench)
    exp_excess = (_EQ.iloc[-1] / _EQ.iloc[0]) - (bench.iloc[-1] / bench.iloc[0])
    assert out["excess_return"] == pytest.approx(exp_excess)
    # tracking error = std((eq_ret - bench_ret), ddof=1) * sqrt(252)
    r, rb = _EQ.pct_change().dropna(), bench.pct_change().dropna()
    assert out["tracking_error"] == pytest.approx((r - rb).std(ddof=1) * np.sqrt(ANNUALIZATION))