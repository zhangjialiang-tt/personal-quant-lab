"""M5.3 / M5.4 parameter + time robustness (D8/D9).

Parameter robustness: evaluate the FULL frozen param_grid Cartesian product on
the in-sample range; param_stability = mean(sharpe >= 0.5 * best_sharpe),
using the frozen formula verbatim (even when best_sharpe < 0).

Time robustness: slice the in-sample range by CALENDAR YEAR (never fixed 252-day
blocks); each year reports the D8 metric set; positive_cagr_fraction = fraction
of valid years with CAGR > 0. Years with insufficient data are reported as
`insufficient_data` and excluded from the denominator (never silently PASSed).
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from pql.registry.experiments import selection_key

from .base import grid_configs, run_window

# Minimum trading days for a calendar-year slice to count as a valid year in
# the positive-CAGR denominator (partial/insufficient years are excluded).
MIN_YEAR_DAYS = 60


def parameter_robustness(spec, ds, cost, data_root) -> dict[str, Any]:
    """Full-grid in-sample evaluation. Returns grid rows, best params, best
    sharpe, and the frozen param_stability fraction. Sharpe=NaN is treated as
    -inf for best-selection (a config that doesn't trade never wins)."""
    grid = grid_configs(spec)
    rows: list[dict] = []
    best_sharpe = float("-inf")
    best_cfg = None
    for cfg in grid:
        res = run_window(
            spec, cfg, ds, cost, data_root, spec.windows["in_sample"][0],
            spec.windows["in_sample"][1],
        )
        sharpe = res.metrics.get("sharpe")
        s = float(sharpe) if sharpe is not None and not math.isnan(float(sharpe)) else float("-inf")
        rows.append(
            {"params": cfg, "selection_key": selection_key(cfg), "metrics": dict(res.metrics),
             "result": res}
        )
        if s > best_sharpe:
            best_sharpe = s
            best_cfg = cfg

    def _stable(row):
        s = row["metrics"].get("sharpe")
        if s is None or math.isnan(float(s)):  # nan -> not stable
            return 0.0
        return 1.0 if float(s) >= 0.5 * best_sharpe else 0.0

    stable = [_stable(r) for r in rows]
    param_stability = sum(stable) / len(rows) if rows else 0.0
    return {
        "grid_size": len(grid),
        "rows": rows,
        "best_params": best_cfg,
        "best_selection_key": selection_key(best_cfg) if best_cfg else None,
        "best_sharpe": best_sharpe,
        "param_stability": param_stability,
    }


def _year_slices(ds) -> list[tuple[str, str, str]]:
    """Calendar-year slices of the in-sample range: [(year, start, end)]."""
    dates = pd.to_datetime(pd.Series(ds.research_frame()["date"].dt.normalize()).unique())
    years = sorted({d.year for d in dates})
    out = []
    for yr in years:
        y_dates = [d for d in dates if d.year == yr]
        out.append((str(yr), y_dates[0].strftime("%Y-%m-%d"), y_dates[-1].strftime("%Y-%m-%d")))
    return out


def time_robustness(spec, ds, cost, data_root) -> dict[str, Any]:
    """Per-calendar-year IS metrics + positive CAGR fraction over valid years.
    A year is valid only if it has >= MIN_YEAR_DAYS trading days and a
    computable CAGR; partial/insufficient years are recorded as
    `insufficient_data` and excluded from the denominator."""
    slices = _year_slices(ds)
    year_rows: list[dict] = []
    valid_cagr_years = 0
    positive_cagr_years = 0
    for year, start, end in slices:
        days = _days(ds, int(year))
        res = run_window(spec, _default_params(spec), ds, cost, data_root, start, end)
        m = dict(res.metrics)
        cagr = m.get("cagr")
        if days < MIN_YEAR_DAYS or cagr is None or math.isnan(float(cagr)):
            year_rows.append({"year": year, "trading_days": days,
                              "status": "insufficient_data", "metrics": m})
            continue
        valid_cagr_years += 1
        if cagr > 0:
            positive_cagr_years += 1
        year_rows.append({"year": year, "trading_days": days,
                          "status": "ok", "metrics": m})
    pos_cagr_frac = (
        positive_cagr_years / valid_cagr_years if valid_cagr_years else 0.0
    )
    return {
        "years": year_rows,
        "valid_year_count": valid_cagr_years,
        "positive_cagr_year_count": positive_cagr_years,
        "positive_cagr_fraction": pos_cagr_frac,
        "min_year_days": MIN_YEAR_DAYS,
    }


def _days(ds, year: int) -> int:
    """Number of UNIQUE trading dates in the calendar year (M5 review P1: the
    long research frame has one row per symbol per date, so counting rows would
    inflate by the universe size)."""
    dates = pd.to_datetime(ds.research_frame()["date"]).dt.normalize()
    return int(dates[dates.dt.year == year].nunique())


def _default_params(spec) -> dict[str, Any]:
    from pql.signals.registry import effective_params

    return effective_params(spec, None)


__all__ = ["grid_configs", "parameter_robustness", "time_robustness"]