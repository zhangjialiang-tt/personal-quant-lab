"""M7.2 TargetPortfolio (plan §M7.2 / D10 TargetWeight).

Strategy decisions (existing signals) are normalized into a target portfolio:
equal-weight among the held set, bounded by max_positions, cash remainder.
This module does NOT reimplement any strategy logic (no Trend MA / Momentum /
monthly rebalance / ranking here) — it reuses `signals/` and only normalizes the
result into `TargetPortfolio{date, weights, cash_weight}`.

Invariants (M7.24):
    weight >= 0
    sum(weights) <= 1
    nonzero count <= max_positions
    risk-off -> all weights 0, cash_weight = 1
    Top-K equal weight -> each active = 1/N, cash = 1 - sum(weights)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pql.schemas import StrategySpec
from pql.signals.momentum_rotation import momentum_rotation_signal
from pql.signals.registry import effective_params
from pql.signals.trend_ma import trend_ma_signal


class TargetPortfolioError(ValueError):
    """Raised for an invalid target portfolio."""


@dataclass(frozen=True)
class TargetPortfolio:
    date: str
    weights: dict[str, float]           # canonical symbol -> weight in [0,1]
    cash_weight: float = field(default=0.0)
    reason: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def validate(self, max_positions: int | None = None) -> None:
        for sym, w in self.weights.items():
            if w < -1e-9:
                raise TargetPortfolioError(f"negative weight for {sym}: {w}")
        if sum(self.weights.values()) > 1 + 1e-9:
            raise TargetPortfolioError(
                f"sum(weights)={sum(self.weights.values())} exceeds 1")
        if self.cash_weight < -1e-9:
            raise TargetPortfolioError(f"negative cash_weight: {self.cash_weight}")
        if self.cash_weight > 1 + 1e-9:
            raise TargetPortfolioError(f"cash_weight > 1: {self.cash_weight}")
        nz = sum(1 for w in self.weights.values() if w > 1e-9)
        if max_positions is not None and nz > max_positions:
            raise TargetPortfolioError(
                f"nonzero weight count {nz} exceeds max_positions {max_positions}")


def _normalize_weights(weights: pd.Series, max_positions: int | None = None) -> dict[str, float]:
    """From a per-symbol weight Series (already signal-derived) to a validated
    {symbol: weight} dict. Rounds tiny negatives to 0 and enforces the
    max_positions / sum<=1 invariants."""
    w = weights.fillna(0.0).clip(lower=0.0)
    nz = {s: float(v) for s, v in w.items() if v > 1e-9}
    if max_positions is not None and len(nz) > max_positions:
        # defensive: signals already cap at max_positions; never silently drop
        raise TargetPortfolioError(
            f"signal produced {len(nz)} nonzero weights > max_positions {max_positions}")
    return nz


def build_target_portfolio_series(
    spec: StrategySpec,
    research: pd.DataFrame,
    params: dict[str, Any] | None,
    calendar_dates,
) -> pd.DataFrame:
    """Compute the date-indexed target-weight Series (columns = canonical
    symbols) for a strategy over the research frame. Reuses the existing
    signals (zero strategy-logic duplication). Non-rebalance rows (monthly
    rotation off-schedule) are NaN -> hold current allocation.

    - momentum_rotation -> momentum_rotation_signal TargetWeightIntent.weights (NaN off-schedule)
    - trend_ma -> equal-weight held set each day
    - buy_hold -> constant 1.0 on the target symbol
    """
    eff = effective_params(spec, params)
    kind = spec.signal.get("kind")
    max_positions = spec.risk.get("max_positions")
    if kind == "momentum_rotation":
        intent = momentum_rotation_signal(
            research,
            calendar_dates=calendar_dates,
            momentum_days=int(eff.get("momentum_days")),
            ma_filter=int(eff.get("ma_filter", 0)),
            top_k=int(eff.get("top_k")),
            max_positions=max_positions,
        )
        return intent.weights.copy()
    if kind == "trend_ma":
        intent = trend_ma_signal(
            research, ma_period=int(eff.get("ma_period")), max_positions=max_positions
        )
        entries = intent.entries.reindex(columns=sorted(intent.entries.columns))
        exits = intent.exits.reindex(columns=sorted(intent.exits.columns))
        held = (entries.cumsum() - exits.cumsum()).clip(0, 1).astype(bool)
        n_held = held.sum(axis=1).replace(0, np.nan)
        weights = held.div(n_held, axis=0).where(held, 0.0)
        return weights
    if kind == "buy_hold":
        symbol = spec.signal.get("symbol", spec.universe[0])
        dates = pd.to_datetime(pd.Series(sorted(set(research["date"])))).dt.normalize()
        return pd.DataFrame(1.0, index=dates, columns=[symbol])
    raise TargetPortfolioError(f"unsupported signal kind for target: {kind!r}")


def target_for_series_row(
    series: pd.DataFrame,
    day,
    spec: StrategySpec,
    reason: str = "",
) -> TargetPortfolio | None:
    """TargetPortfolio for a single day from a precomputed target-weight series
    (or None if that day is not a scheduled rebalance: all-NaN -> hold)."""
    day_ts = pd.Timestamp(day).normalize()
    if series is None or day_ts not in series.index:
        return None
    row = series.loc[day_ts]
    if not isinstance(row, pd.Series):
        return None
    if row.isna().all():
        return None
    weights = _normalize_weights(row, spec.risk.get("max_positions"))
    wsum = sum(weights.values())
    tp = TargetPortfolio(
        date=str(day_ts.date()),
        weights=weights,
        cash_weight=round(1.0 - wsum, 12),
        reason=reason,
        provenance={"signal_kind": spec.signal.get("kind"),
                    "params": effective_params(spec, None)},
    )
    tp.validate(spec.risk.get("max_positions"))
    return tp


def target_portfolio_for_day(
    spec: StrategySpec,
    research: pd.DataFrame,
    params: dict[str, Any] | None,
    calendar_dates,
    day,
    reason: str = "",
) -> TargetPortfolio | None:
    """TargetPortfolio for a single decision day, or None if that day is not a
    scheduled rebalance (all-NaN row -> hold current allocation)."""
    series = build_target_portfolio_series(spec, research, params, calendar_dates)
    return target_for_series_row(series, day, spec, reason=reason)


__all__ = [
    "TargetPortfolio",
    "TargetPortfolioError",
    "build_target_portfolio_series",
    "target_for_series_row",
    "target_portfolio_for_day",
]