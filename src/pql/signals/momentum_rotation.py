"""M5.1 ETF Momentum Rotation signal (long-only, monthly rebalance).

Relative momentum = close_adj.pct_change(momentum_days) (<= T data only).
Absolute-momentum filter: momentum > 0. Optional MA filter: close_adj > MA(ma_filter)
when ma_filter > 0 (0 = disabled). Rolling windows use <= T data (never centered).

Rebalance contract (D6): the FIRST actual trading day of each calendar month,
derived from the research/trading dates — never a fixed 21-day cycle or month-end.

On a rebalance day the full target vector is written: rank eligible assets by
momentum DESCENDING (tie-break: canonical symbol ASCENDING), keep the top
effective_k = min(top_k, risk.max_positions), equal weight 1/K, others 0. If no
asset is eligible the target is 100% cash (all weights 0). Non-rebalance rows
are NaN (hold current allocation, no forced rebalance).

Outputs a TargetWeightIntent so the engine routes it through from_orders
(targetpercent, cash_sharing, group_by, Execution Revaluation) per D10.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..backtest.engine import TargetWeightIntent


class MomentumError(ValueError):
    """Raised for invalid momentum signal inputs."""


def first_trading_day_of_month(dates) -> list[pd.Timestamp]:
    """First actual trading day of each calendar month, in ascending order.
    Accepts any iterable (including a set); the input is sorted first."""
    s = pd.Series(pd.to_datetime(pd.Series(sorted(dates))).dt.normalize())
    s = s.drop_duplicates().sort_values()
    ym = s.dt.strftime("%Y-%m")
    first = s.groupby(ym).first()
    return [pd.Timestamp(d) for d in first.tolist()]


def momentum_rotation_signal(
    research: pd.DataFrame,
    *,
    calendar_dates,
    momentum_days: int,
    ma_filter: int = 0,
    top_k: int = 2,
    max_positions: int | None = None,
    rebalance_days: list | None = None,
) -> TargetWeightIntent:
    """Build a monthly Top-K equal-weight TargetWeightIntent from a research
    frame ([date, symbol, close_adj]). Point-in-time: every decision at T uses
    only data <= T.

    Rebalance SCHEDULE is derived from the authoritative Snapshot trading
    calendar (calendar_dates), not from the price data: the first actual trading
    day of each calendar month is the scheduled rebalance day, exactly as frozen.
    A scheduled day with no price data simply cannot execute (the weight row for
    that date is dropped by the engine) — it is never silently redefined as the
    next available price day.

    `rebalance_days` (optional) overrides the schedule (K06 shift_rebalance
    passes a schedule shifted by one actual trading day; the decision at each
    shifted day regenerates targets using only data <= that day)."""
    if momentum_days < 1:
        raise MomentumError(f"momentum_days must be >= 1, got {momentum_days}")
    if ma_filter < 0:
        raise MomentumError(f"ma_filter must be >= 0, got {ma_filter}")
    if top_k < 1:
        raise MomentumError(f"top_k must be >= 1, got {top_k}")

    df = research[["date", "symbol", "close_adj"]]
    pivot = df.pivot(index="date", columns="symbol", values="close_adj").sort_index()
    # deterministic column order (canonical symbol ascending) for tie-breaks
    pivot = pivot[np.sort(pivot.columns)]

    momentum = pivot.pct_change(momentum_days)
    eligible = momentum > 0
    if ma_filter > 0:
        ma = pivot.rolling(ma_filter, min_periods=ma_filter).mean()
        eligible = eligible & (pivot > ma)

    effective_k = min(top_k, max_positions) if max_positions else top_k
    # schedule from the CALENDAR; only dates with prices can actually rebalance
    if rebalance_days is None:
        rebal = [d for d in first_trading_day_of_month(calendar_dates) if d in pivot.index]
    else:
        rebal = [pd.Timestamp(d) for d in rebalance_days if pd.Timestamp(d) in pivot.index]

    weights = pd.DataFrame(np.nan, index=pivot.index, columns=pivot.columns)
    for d in rebal:
        m = momentum.loc[d]
        elig = eligible.loc[d]
        sel = m[elig]
        row = pd.Series(0.0, index=pivot.columns)
        if sel.empty:
            weights.loc[d, row.index] = row  # 100% cash
            continue
        # momentum DESCENDING; ties broken by canonical symbol ASCENDING (the
        # pivot columns are pre-sorted by symbol and the sort is stable).
        ranked = sel.sort_values(ascending=False, kind="stable")
        picks = ranked.head(effective_k).index
        row[picks] = 1.0 / len(picks)
        weights.loc[d, row.index] = row

    return TargetWeightIntent(weights=weights)


__all__ = ["MomentumError", "first_trading_day_of_month", "momentum_rotation_signal"]