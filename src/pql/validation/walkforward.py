"""M5.2 walk-forward validation (D8/D9).

Fixed rolling scheme: train=756 trading days, test=252, step=252. Each fold
selects the best grid config on the TRAIN window only (by Sharpe, tie-break
selection_key ascending), then scores it OOS on the TEST window. The signal is
built point-in-time over the full in-sample research, so the test window has
pre-test momentum/MA warmup without leaking test data into selection.

Fold repetition never multiplies the trial count: selection uses the same
DISTINCT selection_keys across folds (dedup by key, D7/A6).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from pql.backtest.metrics import compute_metrics
from pql.registry.experiments import selection_key

from .base import run_window

TRAIN = 756
TEST = 252
STEP = 252
_MIN_DAYS = TRAIN + TEST


class WalkforwardSkipped(Exception):
    """Raised when the data is too short for even one walk-forward fold."""


def segment_folds(n_days: int) -> list[tuple[int, int, int, int]]:
    """[(train_start, train_end, test_start, test_end)] indices, non-overlapping
    test segments, rolling train window of TRAIN days."""
    out: list[tuple[int, int, int, int]] = []
    i = 0
    while i * STEP + TRAIN + TEST <= n_days:
        train_start = i * STEP
        train_end = train_start + TRAIN
        test_start = train_end
        test_end = test_start + TEST
        out.append((train_start, train_end, test_start, test_end))
        i += 1
    return out


def _select_on_train(grid, spec, ds, cost, data_root, start, end) -> tuple[float, str, dict]:
    """Pick the best config by IS Sharpe on the train window only (tie-break:
    selection_key ascending). Returns (best_sharpe, best_key, best_params)."""
    best: tuple[float, str, dict] | None = None
    for cfg in grid:
        res = run_window(spec, cfg, ds, cost, data_root, start, end)
        sharpe = res.metrics.get("sharpe")
        if sharpe is None or math.isnan(float(sharpe)):  # nan -> worst
            sharpe = float("-inf")
        sk = selection_key(cfg)
        if best is None or sharpe > best[0] or (sharpe == best[0] and sk < best[1]):
            best = (float(sharpe), sk, dict(cfg))
    assert best is not None
    return best


def walkforward(
    spec,
    grid: list[dict[str, Any]],
    ds,
    cost,
    data_root: str | Path,
) -> dict[str, Any]:
    """Run walk-forward over the full in-sample range. Returns a report dict
    with per-fold selections/OOS metrics, combined OOS metrics, and the positive
    test-segment Sharpe fraction. If data is too short, returns skipped."""
    dates = pd.to_datetime(pd.Series(ds.research_frame()["date"].dt.normalize()).unique())
    dates = pd.DatetimeIndex(sorted(dates))
    n = len(dates)
    if n < _MIN_DAYS:
        return {
            "status": "skipped",
            "reason": f"insufficient_data: {n} trading days < {_MIN_DAYS} (train+test)",
            "n_days": n,
            "train": TRAIN,
            "test": TEST,
            "step": STEP,
        }

    folds = segment_folds(n)
    fold_reports: list[dict] = []
    combined_equity_parts: list[pd.Series] = []
    prev_value = 1_000_000.0
    for (ts, te, us, ue) in folds:
        train_start = dates[ts].strftime("%Y-%m-%d")
        train_end = dates[te - 1].strftime("%Y-%m-%d")
        test_start = dates[us].strftime("%Y-%m-%d")
        test_end = dates[ue - 1].strftime("%Y-%m-%d")

        best_sharpe, best_key, best_params = _select_on_train(
            grid, spec, ds, cost, data_root, train_start, train_end
        )
        test_res = run_window(spec, best_params, ds, cost, data_root, test_start, test_end)
        test_metrics = test_res.metrics
        # chain the OOS equity so the combined curve is continuous
        test_equity = pd.Series(test_res.equity).sort_index()
        scale = prev_value / test_equity.iloc[0]
        chained = test_equity * scale
        combined_equity_parts.append(chained)
        prev_value = chained.iloc[-1]

        fold_reports.append(
            {
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "selected_params": best_params,
                "selection_key": best_key,
                "train_sharpe": best_sharpe,
                "test_metrics": {k: v for k, v in test_metrics.items()},
            }
        )

    combined_equity = pd.concat(combined_equity_parts)
    combined_metrics = compute_metrics(combined_equity)
    pos_frac = sum(
        1 for f in fold_reports
        if (f["test_metrics"].get("sharpe") or float("-inf")) > 0
    ) / len(fold_reports)

    return {
        "status": "ok",
        "train": TRAIN,
        "test": TEST,
        "step": STEP,
        "fold_count": len(fold_reports),
        "folds": fold_reports,
        "combined_oos_metrics": {k: v for k, v in combined_metrics.items()},
        "positive_sharpe_segment_fraction": pos_frac,
        "combined_oos_equity": combined_equity,
    }


__all__ = ["STEP", "TEST", "TRAIN", "WalkforwardSkipped", "segment_folds", "walkforward"]