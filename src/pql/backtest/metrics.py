"""M3 domain metrics (D8). Formulas are frozen by the plan, NOT borrowed from
vectorbt's default statistics: annualization factor 252, Sharpe rf=0, std
ddof=1. Equity-based metrics are independently unit-tested against hand-built
return series. Trade/position FACTS (n_trades, win_rate, exposure, turnover)
are extracted from the executed vectorbt portfolio (trades/orders/asset_value)
and reduced with PQL-defined formulas — the engine supplies facts, PQL defines
the metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ANNUALIZATION = 252


def _returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def cagr(equity: pd.Series) -> float:
    n = len(equity)
    if n < 2 or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return float("nan")
    return float((equity.iloc[-1] / equity.iloc[0]) ** (ANNUALIZATION / (n - 1)) - 1)


def annual_vol(equity: pd.Series) -> float:
    r = _returns(equity)
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * np.sqrt(ANNUALIZATION))


def sharpe(equity: pd.Series) -> float:
    r = _returns(equity)
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float(r.mean() / sd * np.sqrt(ANNUALIZATION))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1).min())


def calmar(cagr_value: float, max_dd: float) -> float:
    if max_dd == 0:
        return float("nan")
    return float(cagr_value / abs(max_dd))


def _turnover(orders: pd.DataFrame, dates: pd.Index, equity: pd.Series) -> float:
    """D8 turnover = daily average of one-sided traded notional / portfolio nav.
    One-sided: each order's gross notional |size*price| counts once per day."""
    if orders is None or orders.empty or dates is None or len(dates) == 0:
        return 0.0
    by_idx: dict[int, list] = {}
    for o in orders.itertuples():
        by_idx.setdefault(int(o.idx), []).append(o)
    daily_traded = []
    for i, _dt in enumerate(dates):
        notional = sum(
            abs(float(o.size) * float(o.price)) for o in by_idx.get(i, [])
        )
        daily_traded.append(notional)
    nav = equity.reindex(dates)
    daily_tov = [
        (t / e if e > 0 else 0.0) for t, e in zip(daily_traded, nav)
    ]
    return float(np.mean(daily_tov)) if daily_tov else 0.0


def _exposure(asset_value: pd.Series, equity: pd.Series) -> float:
    """D8 exposure = daily mean of asset value / total value (0..1)."""
    if asset_value is None or asset_value.empty:
        return float("nan")
    aligned = pd.concat([asset_value, equity], axis=1, join="inner")
    if aligned.empty:
        return float("nan")
    ratio = aligned.iloc[:, 0] / aligned.iloc[:, 1].replace(0, np.nan)
    return float(ratio.mean())


def _trade_stats(trades: pd.DataFrame, orders: pd.DataFrame | None) -> tuple[int, float]:
    """n_trades counts CLOSED round trips; win_rate = fraction with pnl > 0
    (vectorbt pnl is net of entry/exit fees)."""
    if trades is not None and not trades.empty:
        if "status" in trades.columns:
            closed = trades[trades["status"] == 1]
        else:
            closed = trades
        if "pnl" in closed.columns and len(closed):
            return len(closed), float((closed["pnl"] > 0).mean())
        return len(closed), float("nan")
    return (len(orders) if orders is not None else 0), float("nan")


def compute_metrics(
    equity: pd.Series,
    *,
    orders: pd.DataFrame | None = None,
    trades: pd.DataFrame | None = None,
    asset_value: pd.Series | None = None,
    dates: pd.Index | None = None,
) -> dict[str, float]:
    """Full D8 metric set. Equity metrics always; order-derived metrics from the
    executed vectorbt portfolio facts when provided."""
    cagr_v = cagr(equity)
    maxd = max_drawdown(equity)
    metrics: dict[str, float] = {
        "cagr": cagr_v,
        "annual_vol": annual_vol(equity),
        "sharpe": sharpe(equity),
        "max_drawdown": maxd,
        "calmar": calmar(cagr_v, maxd),
    }
    n_trades, win_rate = _trade_stats(trades, orders)
    metrics.update(
        {
            "n_trades": n_trades,
            "turnover": _turnover(orders, dates, equity),
            "exposure": _exposure(asset_value, equity),
            "win_rate": win_rate,
        }
    )
    return metrics


def metrics_vs_benchmark(equity: pd.Series, benchmark_equity: pd.Series) -> dict[str, float]:
    """Excess return and tracking error vs a benchmark equity curve."""
    r = _returns(equity)
    rb = _returns(benchmark_equity)
    excess = (equity.iloc[-1] / equity.iloc[0]) - (benchmark_equity.iloc[-1] / benchmark_equity.iloc[0])
    aligned = pd.concat([r, rb], axis=1, join="inner").dropna()
    te = (
        float(aligned.iloc[:, 0].sub(aligned.iloc[:, 1]).std(ddof=1) * np.sqrt(ANNUALIZATION))
        if len(aligned) > 1
        else float("nan")
    )
    return {"excess_return": float(excess), "tracking_error": te}
