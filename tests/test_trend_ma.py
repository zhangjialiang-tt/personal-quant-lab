"""M4.5 / M4.36-39 ETF Trend signal tests: MA filter, point-in-time, max_positions
truncation, deterministic tie-break."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pql.signals.trend_ma import trend_ma_signal


def _research(closes: dict[str, np.ndarray]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(next(iter(closes.values()))), freq="D")
    rows = []
    for sym, c in closes.items():
        for d, v in zip(dates, c):
            rows.append({"date": d, "symbol": sym, "close_adj": float(v)})
    return pd.DataFrame(rows)


def test_basic_above_ma_risk_on_below_cash():
    # rising series: close > its own 3-day MA after warmup
    closes = {"A.SH": np.arange(10.0, 20.0)}  # 10 bars
    sig = trend_ma_signal(_research(closes), ma_period=3)
    entries = sig.entries["A.SH"]
    # first 2 bars are warmup (MA undefined) -> not held
    assert not entries.iloc[0] and not entries.iloc[1]
    # once above MA -> an entry fires (rising edge)
    assert entries.any()


def test_rising_series_enters_and_stays():
    closes = {"A.SH": np.arange(10.0, 20.0)}
    sig = trend_ma_signal(_research(closes), ma_period=3)
    held = sig.entries["A.SH"].cumsum() - sig.exits["A.SH"].cumsum()
    # after the first entry there is no exit on a monotonically rising series
    assert held.max() == held.iloc[-1] == 1


def test_point_in_time_uses_only_leT():
    # A price series that crosses exactly once; the signal at T must depend only
    # on data <= T. Truncate and compare.
    closes = {"A.SH": np.array([10, 11, 12, 13, 14, 13, 12, 11, 10, 11.0])}
    research = _research(closes)
    full = trend_ma_signal(research, ma_period=4)
    for t in pd.to_datetime(research["date"].unique())[4:]:
        trunc = research[research["date"] <= t]
        sig = trend_ma_signal(trunc, ma_period=4)
        assert bool(sig.entries.loc[t, "A.SH"]) == bool(full.entries.loc[t, "A.SH"])
        assert bool(sig.exits.loc[t, "A.SH"]) == bool(full.exits.loc[t, "A.SH"])


def test_warmup_is_cash():
    closes = {"A.SH": np.arange(10.0, 20.0)}
    sig = trend_ma_signal(_research(closes), ma_period=5)
    # first 4 bars (index 0..3) are warmup -> cash
    assert not sig.entries.iloc[:4]["A.SH"].any()
    assert not sig.exits.iloc[:4]["A.SH"].any()


def _trend_research(n: int = 12):
    """4 exponentially rising symbols with distinct growth rates; all become
    risk-on after warmup, but with different momentum strengths."""
    idx = np.arange(n)
    growth = {"510300.SH": 0.010, "510500.SH": 0.020,
              "518880.SH": 0.030, "511010.SH": 0.005}
    closes = {s: 10.0 * (1 + g) ** idx for s, g in growth.items()}
    return _research(closes)


def test_max_positions_truncates_to_top_k():
    sig = trend_ma_signal(_trend_research(), ma_period=5, max_positions=2)
    held = sig.entries.cumsum() - sig.exits.cumsum()
    # once all above MA, at most 2 symbols concurrently held
    assert held.max().max() <= 2
    # the two strongest (518880 > 510500 > 510300 > 511010) are the ones held
    final_held = held.iloc[-1]
    assert final_held["518880.SH"] == 1
    assert final_held["510500.SH"] == 1
    assert final_held["510300.SH"] == 0
    assert final_held["511010.SH"] == 0


def test_tie_break_deterministic_by_symbol():
    # Two symbols with IDENTICAL momentum strength -> tie broken by canonical
    # symbol order (lower symbol first), not by frame row order.
    idx = np.arange(12)
    data = 10.0 * 1.02 ** idx
    closes = {"510300.SH": data.copy(), "510500.SH": data.copy()}
    research = _research(closes)
    # shuffle row order to prove row order does not decide the winner
    research = research.sample(frac=1.0, random_state=0).reset_index(drop=True)
    sig = trend_ma_signal(research, ma_period=5, max_positions=1)
    held = sig.entries.cumsum() - sig.exits.cumsum()
    # exactly one held; deterministic (510300.SH < 510500.SH)
    final = held.iloc[-1]
    assert final["510300.SH"] == 1
    assert final["510500.SH"] == 0


def test_invalid_ma_period_rejected():
    with pytest.raises(ValueError):
        trend_ma_signal(_research({"A.SH": np.arange(10.0, 20.0)}), ma_period=0)