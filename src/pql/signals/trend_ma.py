"""M4.5 Trend-following signal (long-only, point-in-time).

Hypothesis-driven (D6): when the intermediate/long-term price lies above its
long moving average, the risk/reward of trend continuation / risk exposure may
be superior to unconditional holding; otherwise hold cash.

Signal (uses ONLY data <= T, never future/execution prices):
    risk_on[symbol, T] = close_adj[T] > MA(ma_period)[T]
With max_positions = K, when more than K symbols are simultaneously risk-on,
keep the K strongest by momentum strength (close_adj/MA - 1, computed at T),
truncating deterministically: ties break by canonical symbol order (the columns
are sorted before ranking, so pandas row-order cannot decide the winner).

Returns a SignalIntent whose entries/exits are the RISING EDGES of the held
set (enter when a symbol becomes held, exit when it stops being held); the
engine fills at T+execution_bar per the TimingContract.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..backtest.api import SignalIntent


def trend_momentum_strength(pivot: pd.DataFrame, ma: pd.DataFrame) -> pd.DataFrame:
    """close_adj/MA - 1 at each bar (<= T data only). warmup -> -inf."""
    strength = (pivot / ma - 1.0).where(ma.notna(), -np.inf)
    return strength


def trend_ma_signal(
    research: pd.DataFrame,
    *,
    ma_period: int,
    max_positions: int | None = None,
) -> SignalIntent:
    """Build a long-only trend SignalIntent from a research frame
    ([date, symbol, close_adj]). `ma_period > 0`; `max_positions` truncates the
    concurrent held set to the strongest K by momentum strength."""
    if ma_period < 1:
        raise ValueError(f"ma_period must be >= 1, got {ma_period}")
    df = research[["date", "symbol", "close_adj"]]
    pivot = df.pivot(index="date", columns="symbol", values="close_adj")
    pivot = pivot.sort_index()
    # Deterministic tie-break: sort columns by canonical symbol before any
    # row-order-sensitive ranking.
    cols_sorted = sorted(pivot.columns)
    pivot = pivot[cols_sorted]

    ma = pivot.rolling(ma_period, min_periods=ma_period).mean()
    risk_on = (pivot > ma).fillna(False)

    if max_positions and max_positions < len(pivot.columns):
        strength = trend_momentum_strength(pivot, ma)
        ranked = strength.rank(axis=1, method="first", ascending=False)
        held = risk_on & (ranked <= max_positions)
    else:
        held = risk_on

    entries = held & ~held.shift(1, fill_value=False)
    exits = ~held & held.shift(1, fill_value=False)
    return SignalIntent(entries=entries, exits=exits)


__all__ = ["trend_ma_signal", "trend_momentum_strength"]