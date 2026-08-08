"""M5.5 market regime analysis (v0.1: Trend / Volatility / Liquidity; Rate
deferred as not_implemented_v0.1).

All labels are point-in-time (use only data <= T):
- Trend: benchmark close_adj > MA200 -> UP else DOWN.
- Volatility: 20-day realized vol; HIGH when vol > expanding median(vol <= T-1).
- Liquidity: 20-day mean amount; HIGH when amount > expanding median(<= T-1).

Thresholds use the EXPANDING median shifted by one day (<= T-1), never the
full-sample median, so future data cannot leak into historical regime labels.
Per-combo metrics are computed from the strategy's daily returns grouped by the
day's regime combo (only observed combos are emitted).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import run_window

ANNUALIZATION = 252
VOL_WINDOW = 20
LIQ_WINDOW = 20
TREND_MA = 200


class RegimeError(RuntimeError):
    """Raised for regime computation problems."""


def _expanding_median_shift1(series: pd.Series) -> pd.Series:
    """expanding median of values <= T-1 (shifted by one), so the label at T
    never uses its own or future values."""
    return series.expanding(min_periods=1).median().shift(1)


def trend_label(close: pd.Series) -> pd.Series:
    ma = close.rolling(TREND_MA, min_periods=TREND_MA).mean()
    return (close > ma).map({True: "UP", False: "DOWN"}).fillna("DOWN")


def volatility_label(close: pd.Series) -> pd.Series:
    daily = close.pct_change()
    vol = daily.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * np.sqrt(ANNUALIZATION)
    thr = _expanding_median_shift1(vol)
    label = (vol > thr).map({True: "HIGH_VOL", False: "LOW_VOL"}).fillna("LOW_VOL")
    return label


def liquidity_label(amount: pd.Series) -> pd.Series:
    ma = amount.rolling(LIQ_WINDOW, min_periods=LIQ_WINDOW).mean()
    thr = _expanding_median_shift1(ma)
    label = (ma > thr).map({True: "HIGH_LIQ", False: "LOW_LIQ"}).fillna("LOW_LIQ")
    return label


def regime_labels(benchmark_close: pd.Series, benchmark_amount: pd.Series) -> pd.DataFrame:
    """Full regime label frame (index=date, columns trend/volatility/liquidity)."""
    idx = benchmark_close.index
    return pd.DataFrame(
        {
            "trend": trend_label(benchmark_close),
            "volatility": volatility_label(benchmark_close),
            "liquidity": liquidity_label(benchmark_amount.reindex(idx)),
        }
    )


def _metrics_for_returns(rets: pd.Series) -> dict[str, float]:
    if len(rets) < 2:
        return {"n_days": len(rets), "status": "insufficient_data"}
    sd = rets.std(ddof=1)
    return {
        "n_days": len(rets),
        "sharpe": float(rets.mean() / sd * np.sqrt(ANNUALIZATION)) if sd != 0 else float("nan"),
        "annual_vol": float(sd * np.sqrt(ANNUALIZATION)),
        "mean_daily_return": float(rets.mean()),
        "status": "ok",
    }


def regime_analysis(spec, ds, cost, data_root) -> dict[str, Any]:
    """Run the strategy once on the full in-sample range, label each day's
    regime combo, and compute per-combo metrics from the grouped daily returns.
    Only observed combos are emitted; Rate is explicitly not implemented."""
    res = run_window(
        spec, _default_params(spec), ds, cost, data_root,
        spec.windows["in_sample"][0], spec.windows["in_sample"][1],
    )
    equity = pd.Series(res.equity).sort_index()
    rets = equity.pct_change().dropna()

    research = ds.research_frame()
    bench = spec.benchmark
    b_close = (
        research[research["symbol"] == bench]
        .set_index("date")["close_adj"].sort_index()
    )
    amount = ds.amount_frame()
    b_amount = (
        amount[amount["symbol"] == bench]
        .set_index("date")["amount"].sort_index()
    )
    labels = regime_labels(b_close, b_amount)

    # align returns with labels on common dates
    frames = pd.concat([rets.rename("ret"), labels], axis=1, join="inner").dropna(subset=["ret"])
    combos: dict[str, list] = {}
    for _dt, row in frames.iterrows():
        key = f"{row['trend']}|{row['volatility']}|{row['liquidity']}"
        combos.setdefault(key, []).append(row["ret"])

    combo_rows = [
        {"regime_combo": key, **_metrics_for_returns(pd.Series(vals))}
        for key, vals in sorted(combos.items())
    ]
    return {
        "combos": combo_rows,
        "observed_combo_count": len(combos),
        "trend_ma": TREND_MA,
        "vol_window": VOL_WINDOW,
        "liq_window": LIQ_WINDOW,
        "rate_regime": "not_implemented_v0.1",
    }


def _default_params(spec) -> dict[str, Any]:
    from pql.signals.registry import effective_params

    return effective_params(spec, None)


__all__ = [
    "liquidity_label",
    "regime_analysis",
    "regime_labels",
    "trend_label",
    "volatility_label",
]