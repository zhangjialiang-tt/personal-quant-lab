"""M3 vectorbt engine (D10). Routes TradingIntent to vectorbt:
- SignalIntent -> Portfolio.from_signals (shift signals by execution_bar)
- TargetWeightIntent -> Portfolio.from_orders (targetpercent, cash_sharing,
  call_seq='auto', group_by, val_price = Execution Revaluation)

Crucial separation (frozen contract): portfolio VALUATION uses the raw close
series, order EXECUTION uses the raw open/close series (execution_price), and
TargetWeight sizing (val_price) uses the raw close. Adjusted research prices are
never used for execution. Builds the BacktestResult with vectorbt provenance.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import vectorbt as vbt

from pql.schemas import BacktestResult, CostModel, PortfolioConfig
from pql.timing import TimingContract, assert_no_lookahead

from ..data.dataset import DatasetView
from .metrics import compute_metrics


@dataclass(frozen=True)
class SignalIntent:
    """Long-only entries/exits boolean signals (Trend / Buy & Hold)."""

    entries: pd.DataFrame  # bool, index=date, columns=symbol
    exits: pd.DataFrame  # bool, index=date, columns=symbol


@dataclass(frozen=True)
class TargetWeightIntent:
    """Target portfolio weights (Rotation / Allocation). NaN = no adjustment."""

    weights: pd.DataFrame  # float [0,1], index=date, columns=symbol


TradingIntent = SignalIntent | TargetWeightIntent


def _price_frame(dataset: DatasetView, column: str) -> pd.DataFrame:
    frame = dataset.execution_frame()  # [date, symbol, open, close]
    if column not in ("open", "close"):
        raise ValueError(f"column must be 'open' or 'close', got {column!r}")
    pivot = frame.pivot(index="date", columns="symbol", values=column)
    return pivot.sort_index()


def _to_equity_series(value) -> pd.Series:
    """Total portfolio value; a multi-column value frame is summed to one nav."""
    if isinstance(value, pd.DataFrame):
        return value.sum(axis=1)
    return value


def run_backtest_impl(
    intent,
    universe: list[str],
    execution_model: TimingContract,
    cost_model: CostModel,
    portfolio_config: PortfolioConfig,
    dataset: DatasetView,
) -> BacktestResult:
    assert_no_lookahead(execution_model)

    # VALUATION price is always the raw close; EXECUTION price is open or close.
    raw_close = _price_frame(dataset, "close")
    order_price = (
        _price_frame(dataset, "open")
        if execution_model.execution_price == "open"
        else raw_close
    )
    cols = [s for s in universe if s in raw_close.columns]
    raw_close = raw_close.reindex(columns=cols)
    order_price = order_price.reindex(columns=cols)
    n = execution_model.execution_bar
    has_price = order_price.notna()

    skipped: list[tuple] = []
    if isinstance(intent, SignalIntent):
        entries = intent.entries.reindex(
            index=order_price.index, columns=order_price.columns, fill_value=False
        )
        exits = intent.exits.reindex(
            index=order_price.index, columns=order_price.columns, fill_value=False
        )
        # skipped is judged at the EXECUTION day (signal shifted), where the fill
        # would have happened: signal active pre-shift AND no execution price.
        active_exec = (entries | exits).shift(n, fill_value=False)
        skipped = [
            (d.date(), s)
            for d in order_price.index
            for s in order_price.columns
            if not bool(has_price.loc[d, s]) and bool(active_exec.loc[d, s])
        ]
        entries = entries & has_price
        exits = exits & has_price
        pf = vbt.Portfolio.from_signals(
            close=raw_close,
            price=order_price,
            entries=entries.shift(n, fill_value=False),
            exits=exits.shift(n, fill_value=False),
            init_cash=portfolio_config.init_cash,
            fees=cost_model.fee_rate,
            slippage=cost_model.slippage,
            freq="D",
            direction="longonly",
        )
        intent_kind = "signal"
        valuation_mode = "signal_fill"
    else:
        weights = intent.weights.reindex(
            index=order_price.index, columns=order_price.columns
        )
        weights_exec = weights.shift(n)
        skipped = [
            (d.date(), s)
            for d in order_price.index
            for s in order_price.columns
            if not bool(has_price.loc[d, s]) and pd.notna(weights_exec.loc[d, s])
        ]
        weights = weights.where(has_price)
        # Execution Revaluation (frozen): target quantity sized at the close of
        # the bar BEFORE the execution bar; first bar falls back to its own close.
        val_price = raw_close.shift(1).fillna(raw_close)
        pf = vbt.Portfolio.from_orders(
            close=raw_close,
            price=order_price,
            size=weights.shift(n),
            size_type="targetpercent",
            cash_sharing=True,
            call_seq="auto",
            group_by=True,
            val_price=val_price,
            init_cash=portfolio_config.init_cash,
            fees=cost_model.fee_rate,
            slippage=cost_model.slippage,
            freq="D",
            direction="longonly",
        )
        intent_kind = "target_weight"
        valuation_mode = "execution_revaluation"

    equity = _to_equity_series(pf.value())
    asset_value = _to_equity_series(pf.asset_value())
    orders = pf.orders.records
    trades = pf.trades.records
    metrics = compute_metrics(
        equity,
        orders=orders,
        trades=trades,
        asset_value=asset_value,
        dates=order_price.index,
        init_cash=portfolio_config.init_cash,
    )
    run_meta = {
        "engine": "vectorbt",
        "vectorbt_version": vbt.__version__,
        "intent": intent_kind,
        "execution_bar": n,
        "execution_price": execution_model.execution_price,
        "valuation_mode": valuation_mode,
        "cost_model_version": cost_model.version,
        "fee_rate": cost_model.fee_rate,
        "slippage": cost_model.slippage,
        "init_cash": portfolio_config.init_cash,
        "skipped_no_price": skipped,
    }
    return BacktestResult(equity=equity, orders=orders, metrics=metrics, run_meta=run_meta)