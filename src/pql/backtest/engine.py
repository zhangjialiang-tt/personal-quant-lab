"""M3 vectorbt engine (D10). Routes TradingIntent to vectorbt:
- SignalIntent -> Portfolio.from_signals (shift signals by execution_bar)
- TargetWeightIntent -> Portfolio.from_orders (targetpercent, cash_sharing,
  call_seq='auto', group_by, val_price = Execution Revaluation)

Execution prices come from DatasetView.execution_frame() (raw), never from the
adjusted research series. Builds the BacktestResult (equity/orders/metrics/
run_meta) with vectorbt-version provenance.
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


def _execution_price_frame(dataset: DatasetView, execution_price: str) -> pd.DataFrame:
    frame = dataset.execution_frame()  # [date, symbol, open, close]
    if execution_price not in ("open", "close"):
        raise ValueError(f"execution_price must be 'open' or 'close', got {execution_price!r}")
    pivot = frame.pivot(index="date", columns="symbol", values=execution_price)
    return pivot.sort_index()


def _to_equity_series(value) -> pd.Series:
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
    price = _execution_price_frame(dataset, execution_model.execution_price)
    price = price.reindex(columns=[s for s in universe if s in price.columns])
    n = execution_model.execution_bar
    has_price = price.notna()

    skipped: list[tuple] = []
    if isinstance(intent, SignalIntent):
        entries = intent.entries.reindex(
            index=price.index, columns=price.columns, fill_value=False
        )
        exits = intent.exits.reindex(
            index=price.index, columns=price.columns, fill_value=False
        )
        # skipped is judged at the EXECUTION day (signal shifted), where the fill
        # would have happened: signal active pre-shift AND no price at that day.
        active_exec = (entries | exits).shift(n, fill_value=False)
        skipped = [
            (d.date(), s)
            for d in price.index
            for s in price.columns
            if not bool(has_price.loc[d, s]) and bool(active_exec.loc[d, s])
        ]
        entries = entries & has_price
        exits = exits & has_price
        pf = vbt.Portfolio.from_signals(
            close=price,
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
        weights = intent.weights.reindex(index=price.index, columns=price.columns)
        weights_exec = weights.shift(n)
        skipped = [
            (d.date(), s)
            for d in price.index
            for s in price.columns
            if not bool(has_price.loc[d, s]) and pd.notna(weights_exec.loc[d, s])
        ]
        weights = weights.where(has_price)
        # Execution Revaluation (frozen): val_price = close of the bar before the
        # execution bar; first bar falls back to its own close (no prior bar).
        val_price = price.shift(1).fillna(price)
        pf = vbt.Portfolio.from_orders(
            close=price,
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
    orders = pf.orders.records
    metrics = compute_metrics(
        equity, orders, init_cash=portfolio_config.init_cash, price=price
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
