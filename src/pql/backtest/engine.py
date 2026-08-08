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

import numpy as np
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


@dataclass(frozen=True)
class ExecutionPerturbation:
    """M6 miss-stress perturbation (path-dependent, full engine rerun — NOT
    post-hoc order surgery).

    The caller passes EITHER an explicit `reject_mask` (bool grid on
    date x symbol: True = the order is rejected) OR `miss_rate` + `seed` (the
    engine builds the deterministic mask aligned to the actual order-event
    grid). Rejected cells are dropped from the execution input BEFORE vectorbt
    runs, so the whole portfolio path (cash, subsequent buys/sells) evolves
    naturally — a missed SELL changes cash and can break a later BUY, which a
    post-hoc deletion could never reproduce.
    """

    reject_mask: pd.DataFrame | None = None
    miss_rate: float = 0.0
    seed: int = 0

    def validate(self) -> None:
        if self.reject_mask is not None and (self.miss_rate or self.seed):
            raise ValueError("provide either reject_mask or miss_rate/seed, not both")
        if self.reject_mask is None and (self.miss_rate < 0 or self.miss_rate > 1):
            raise ValueError(f"miss_rate must be in [0, 1], got {self.miss_rate}")


def generate_reject_mask(
    event_cells: pd.DataFrame, miss_rate: float, seed: int
) -> pd.DataFrame:
    """Deterministic reject mask over the order-event grid.

    Selects ceil(miss_rate * n_events) event cells via a seeded RNG. Same seed
    -> same mask; different seed -> different mask (frozen M6 contract). Cells
    that are not order events are never rejected. Returns True where the order
    is REJECTED.
    """
    rng = np.random.default_rng(seed)
    mask = pd.DataFrame(False, index=event_cells.index, columns=event_cells.columns)
    locs = np.argwhere(event_cells.to_numpy())
    n = len(locs)
    if n == 0:
        return mask
    k = int(np.ceil(miss_rate * n))
    if k > 0:
        chosen = rng.choice(n, size=min(k, n), replace=False)
        for i in chosen:
            r, c = locs[i]
            mask.iat[r, c] = True
    return mask


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


def _closed_trades(trades, cols: list[str], dates: pd.Index) -> list[dict]:
    """Normalize vectorbt closed-trade records into PQL `ClosedTrade` facts
    (K02 drop_best_trades needs entry/exit dates, symbol, size, net PnL, fees).
    vectorbt `pnl` is net of entry/exit fees; `fees` is the total trade fee."""
    out: list[dict] = []
    if trades is None or len(trades) == 0:
        return out
    for t in trades.itertuples():
        entry_idx = int(t.entry_idx)
        exit_idx = int(t.exit_idx)
        col = int(t.col)
        symbol = cols[col] if col < len(cols) else str(col)
        entry_date = str(dates[entry_idx].date()) if entry_idx < len(dates) else None
        exit_date = str(dates[exit_idx].date()) if exit_idx < len(dates) else None
        fees = float(getattr(t, "entry_fees", 0.0)) + float(getattr(t, "exit_fees", 0.0))
        out.append(
            {
                "symbol": symbol,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "size": float(t.size),
                "net_pnl": float(t.pnl),
                "fees": fees,
                "status": int(t.status),
            }
        )
    return out


def run_backtest_impl(
    intent,
    universe: list[str],
    execution_model: TimingContract,
    cost_model: CostModel,
    portfolio_config: PortfolioConfig,
    dataset: DatasetView,
    perturbation: ExecutionPerturbation | None = None,
) -> BacktestResult:
    assert_no_lookahead(execution_model)
    if perturbation is not None:
        perturbation.validate()

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

        # Multi-asset SignalIntent = ONE shared portfolio account (single
        # init_cash pool), not N independent per-symbol portfolios.
        #
        # Allocation: with PortfolioConfig.weighting == "equal", the held set is
        # allocated EQUAL portfolio weight (1/n_held). from_signals cannot
        # express this for multiple simultaneous entries: its `size` is in
        # shares (size_type='amount'), so two simultaneous entries degenerate to
        # 100%/0% (the first symbol consumes the whole pool). We therefore route
        # the multi-asset equal-weight case through the same from_orders
        # targetpercent machinery as TargetWeightIntent.
        # PLAN_DEVIATION (M4 review): multi-asset equal-weight SignalIntent no
        # longer maps strictly to from_signals; documented in the M4 report.
        val_price = raw_close.shift(1).fillna(raw_close)
        if portfolio_config.weighting == "equal" and len(cols) > 1:
            held = (entries.cumsum() - exits.cumsum()).clip(0, 1).astype(bool)
            n_held = held.sum(axis=1).replace(0, 1.0)
            weights = held.div(n_held, axis=0).where(held, 0.0)
            # ROW-level rebalance (M4 rev2): whenever the held set CHANGES at a
            # bar (any entry/exit), submit the FULL target vector so every held
            # symbol (existing AND newly added) is re-weighted to 1/N. A
            # cell-level mask would leave untouched symbols at their stale
            # weight (e.g. A stays 50% when B exits, instead of rebalancing to
            # 100%). On bars with no held-set change the whole row is NaN ->
            # no rebalancing (pure SignalIntent enter/exit semantics).
            held_changed = (entries | exits).any(axis=1)
            weights = weights.where(held_changed, other=float("nan"), axis=0)
            weights = weights.where(has_price)
            weights_exec = weights.shift(n)
            if perturbation is not None:
                reject = (
                    perturbation.reject_mask
                    if perturbation.reject_mask is not None
                    else generate_reject_mask(
                        weights_exec.notna(), perturbation.miss_rate, perturbation.seed
                    )
                )
                reject = reject.reindex(
                    index=weights_exec.index, columns=weights_exec.columns, fill_value=False
                )
                weights_exec = weights_exec.where(~reject)
            pf = vbt.Portfolio.from_orders(
                close=raw_close,
                price=order_price,
                size=weights_exec,
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
            intent_kind = "signal"
            valuation_mode = "equal_weight_signal"
        else:
            entries_exec = entries.shift(n, fill_value=False)
            exits_exec = exits.shift(n, fill_value=False)
            if perturbation is not None:
                reject = (
                    perturbation.reject_mask
                    if perturbation.reject_mask is not None
                    else generate_reject_mask(
                        (entries_exec | exits_exec), perturbation.miss_rate, perturbation.seed
                    )
                )
                reject = reject.reindex(
                    index=entries_exec.index, columns=entries_exec.columns, fill_value=False
                )
                entries_exec = entries_exec & ~reject
                exits_exec = exits_exec & ~reject
            pf = vbt.Portfolio.from_signals(
                close=raw_close,
                price=order_price,
                entries=entries_exec,
                exits=exits_exec,
                init_cash=portfolio_config.init_cash,
                fees=cost_model.fee_rate,
                slippage=cost_model.slippage,
                freq="D",
                direction="longonly",
                group_by=True,
                cash_sharing=True,
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
        weights_exec = weights.shift(n)
        if perturbation is not None:
            reject = (
                perturbation.reject_mask
                if perturbation.reject_mask is not None
                else generate_reject_mask(
                    weights_exec.notna(), perturbation.miss_rate, perturbation.seed
                )
            )
            reject = reject.reindex(
                index=weights_exec.index, columns=weights_exec.columns, fill_value=False
            )
            weights_exec = weights_exec.where(~reject)
        pf = vbt.Portfolio.from_orders(
            close=raw_close,
            price=order_price,
            size=weights_exec,
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
        "closed_trades": _closed_trades(trades, cols, order_price.index),
        "asset_value": asset_value,
        "trades": trades,
        "perturbation": (
            {
                "miss_rate": perturbation.miss_rate,
                "seed": perturbation.seed,
                "reject_mask": perturbation.reject_mask is not None,
            }
            if perturbation is not None
            else None
        ),
    }
    return BacktestResult(equity=equity, orders=orders, metrics=metrics, run_meta=run_meta)