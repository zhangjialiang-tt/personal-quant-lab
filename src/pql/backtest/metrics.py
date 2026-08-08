"""M3 domain metrics (D8). Formulas are frozen by the plan, NOT borrowed from
vectorbt's default statistics: annualization factor 252, Sharpe rf=0, std
ddof=1. Equity-based metrics are independently unit-tested against hand-built
return series; order-derived metrics (turnover/exposure/n_trades/win_rate) are
reconstructed from the order record via a small FIFO position ledger.
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


def _order_metrics(
    orders: pd.DataFrame,
    equity: pd.Series,
    price: pd.DataFrame,
    init_cash: float,
) -> dict:
    dates = list(equity.index)
    symbols = list(price.columns)
    by_idx: dict[int, list] = {}
    for o in orders.itertuples():
        by_idx.setdefault(int(o.idx), []).append(o)

    cash = float(init_cash)
    pos = np.zeros(len(symbols))
    daily_traded: list[float] = []
    daily_exposure: list[float] = []
    cost_basis: dict[str, list[float]] = {}
    closed_pnls: list[float] = []

    for i, dt in enumerate(dates):
        day_notional = 0.0
        for o in by_idx.get(i, []):
            sym = symbols[int(o.col)]
            signed = float(o.size) if int(o.side) == 0 else -float(o.size)
            day_notional += abs(float(o.size) * float(o.price))
            cash -= signed * float(o.price) + float(o.fees)
            if int(o.side) == 0:  # buy
                cb = cost_basis.setdefault(sym, [0.0, 0.0])
                cb[0] += float(o.size)
                cb[1] += float(o.size) * float(o.price)
                pos[int(o.col)] += float(o.size)
            else:  # sell -> FIFO round trip
                cb = cost_basis.setdefault(sym, [0.0, 0.0])
                sell_size = min(float(o.size), cb[0])
                if sell_size > 0 and cb[0] > 0:
                    avg_cost = cb[1] / cb[0]
                    closed_pnls.append((float(o.price) - avg_cost) * sell_size)
                cb[0] = max(cb[0] - float(o.size), 0.0)
                pos[int(o.col)] -= float(o.size)
        pos_val = sum(
            pos[c] * float(price.loc[dt, symbols[c]]) for c in range(len(symbols))
        )
        total = cash + pos_val
        daily_traded.append(day_notional)
        daily_exposure.append(pos_val / total if total > 0 else 0.0)

    daily_tov = [t / e if e > 0 else 0.0 for t, e in zip(daily_traded, equity)]
    turnover = float(np.mean(daily_tov)) if daily_tov else 0.0
    exposure = float(np.mean(daily_exposure)) if daily_exposure else 0.0
    win_rate = (
        float(sum(1 for p in closed_pnls if p > 0) / len(closed_pnls))
        if closed_pnls
        else float("nan")
    )
    return {
        "n_trades": len(orders),
        "turnover": turnover,
        "exposure": exposure,
        "win_rate": win_rate,
    }


def compute_metrics(
    equity: pd.Series,
    orders: pd.DataFrame | None = None,
    *,
    init_cash: float | None = None,
    price: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Full D8 metric set. `orders`/`price` enable the order-derived metrics."""
    cagr_v = cagr(equity)
    maxd = max_drawdown(equity)
    metrics: dict[str, float] = {
        "cagr": cagr_v,
        "annual_vol": annual_vol(equity),
        "sharpe": sharpe(equity),
        "max_drawdown": maxd,
        "calmar": calmar(cagr_v, maxd),
    }
    if orders is not None and price is not None and not orders.empty:
        metrics.update(_order_metrics(orders, equity, price, init_cash or 0.0))
    else:
        metrics.update(
            {
                "n_trades": len(orders) if orders is not None else 0,
                "turnover": 0.0,
                "exposure": float("nan"),
                "win_rate": float("nan"),
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
