"""Signal dispatch (M4). Maps a StrategySpec.signal kind + effective params to
a concrete TradingIntent. Kept here so the experiment runner and the
deterministic validator reproduce the SAME signal from the SAME inputs.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from pql.schemas import StrategySpec

from ..backtest.api import TradingIntent
from .buy_hold import buy_hold_signal
from .momentum_rotation import momentum_rotation_signal
from .trend_ma import trend_ma_signal


class SignalBuildError(ValueError):
    """Raised for an unknown signal kind or invalid signal inputs."""


def effective_params(spec: StrategySpec, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Signal params = spec defaults merged with CLI overrides (validated against
    param_grid by the runner). Excludes the `kind` discriminator."""
    base = {k: v for k, v in (spec.signal or {}).items() if k != "kind"}
    base.update(overrides or {})
    return base


def build_signal(spec: StrategySpec, research: pd.DataFrame,
                 params: dict[str, Any], calendar_dates=None) -> TradingIntent:
    """Build the TradingIntent for a spec using the given effective params and a
    point-in-time research frame. SignalIntent kinds route to from_signals /
    equal-weight orders; momentum_rotation is a TargetWeightIntent (monthly
    Top-K rotation) routed to from_orders targetpercent. `calendar_dates` is the
    authoritative Snapshot trading calendar used for the momentum rebalance
    schedule."""
    kind = spec.signal.get("kind")
    if kind == "buy_hold":
        symbol = spec.signal.get("symbol", spec.universe[0])
        return buy_hold_signal(research["date"].unique(), symbol)
    if kind == "trend_ma":
        ma_period = int(params.get("ma_period"))
        max_positions = spec.risk.get("max_positions")
        return trend_ma_signal(
            research, ma_period=ma_period, max_positions=max_positions
        )
    if kind == "momentum_rotation":
        if calendar_dates is None:
            calendar_dates = research["date"]
        return momentum_rotation_signal(
            research,
            calendar_dates=calendar_dates,
            momentum_days=int(params.get("momentum_days")),
            ma_filter=int(params.get("ma_filter", 0)),
            top_k=int(params.get("top_k")),
            max_positions=spec.risk.get("max_positions"),
        )
    raise SignalBuildError(f"unknown signal kind: {kind!r}")


__all__ = ["SignalBuildError", "build_signal", "effective_params"]