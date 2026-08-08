"""M6.3 Circular Block Bootstrap (D9).

Bootstraps the CANDIDATE parameter set's in-sample DAILY RETURNS (never the
Holdout) with a circular block resampler:

    R = 1000
    seed = spec.seed
    block_len = ceil(n ** (1/3))

Each sample: pick a random block start, take block_len consecutive returns,
circularly wrap at the end, repeat and truncate to exactly n. This is NOT an
iid resample — within-block autocorrelation is preserved. Outputs the full
Sharpe / CAGR / MaxDD distributions plus p05 / p50 / p95 and a 95% CI. The
gate (bootstrap_sharpe_p05_min) uses the p05 of the Sharpe distribution.

Determinism contract: same returns + same seed -> identical distribution;
same returns + different seed -> different distribution. The full 1000 draws
are persisted as a structured artifact (bootstrap.parquet) rather than stuffed
into a Run manifest.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pql.backtest import metrics

R = 1000


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def block_len(n: int) -> int:
    return int(np.ceil(n ** (1 / 3)))


def circular_block_sample(
    returns: np.ndarray, block_len: int, rng: np.random.Generator
) -> np.ndarray:
    """One circular block bootstrap sample of the SAME length as the input.

    Repeatedly: choose a random block start, take block_len consecutive
    returns with circular wrap (index % n), concatenate, truncate to n."""
    n = len(returns)
    if n == 0:
        return np.empty(0)
    out = np.empty(n)
    i = 0
    while i < n:
        start = int(rng.integers(0, n))
        for j in range(block_len):
            if i >= n:
                break
            out[i] = returns[(start + j) % n]
            i += 1
    return out


def _sample_metrics(rets: pd.Series, b_len: int, rng) -> dict[str, float]:
    sample = circular_block_sample(rets.to_numpy(), b_len, rng)
    eq = pd.Series(np.cumprod(1.0 + sample))
    return {
        "sharpe": metrics.sharpe(eq),
        "cagr": metrics.cagr(eq),
        "max_drawdown": metrics.max_drawdown(eq),
    }


def bootstrap(spec, equity: pd.Series, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Circular block bootstrap of the candidate's in-sample daily returns.

    `equity` is the candidate IS backtest equity curve. Returns a report dict
    with the distribution (persisted to bootstrap.parquet when out_dir is
    given) and the summary percentiles + 95% CI."""
    eq = pd.Series(equity).sort_index()
    rets = eq.pct_change().dropna()
    n = len(rets)
    b_len = block_len(n)
    rng = np.random.default_rng(spec.seed)

    rows: list[dict[str, float]] = []
    for _ in range(R):
        rows.append(_sample_metrics(rets, b_len, rng))
    dist = pd.DataFrame(rows)

    def _pct(series: pd.Series, q: float) -> float:
        return float(series.quantile(q))

    def _ci(series: pd.Series) -> list[float]:
        return [round(_pct(series, 0.025), 6), round(_pct(series, 0.975), 6)]

    dist_path = None
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        dist_path = out / "bootstrap.parquet"
        dist.to_parquet(dist_path, index=False)

    summary = {
        "n": int(n),
        "block_len": int(b_len),
        "R": int(R),
        "seed": int(spec.seed),
        "sharpe": {
            "p05": _pct(dist["sharpe"], 0.05),
            "p50": _pct(dist["sharpe"], 0.5),
            "p95": _pct(dist["sharpe"], 0.95),
            "ci95": _ci(dist["sharpe"]),
        },
        "cagr": {
            "p05": _pct(dist["cagr"], 0.05),
            "p50": _pct(dist["cagr"], 0.5),
            "p95": _pct(dist["cagr"], 0.95),
            "ci95": _ci(dist["cagr"]),
        },
        "max_drawdown": {
            "p05": _pct(dist["max_drawdown"], 0.05),
            "p50": _pct(dist["max_drawdown"], 0.5),
            "p95": _pct(dist["max_drawdown"], 0.95),
            "ci95": _ci(dist["max_drawdown"]),
        },
    }
    return {
        "summary": summary,
        "distribution": dist,
        "distribution_path": str(dist_path) if dist_path else None,
    }


def bootstrap_sharpe_p05(report: dict[str, Any]) -> float:
    return float(report["summary"]["sharpe"]["p05"])


__all__ = ["R", "block_len", "bootstrap", "bootstrap_sharpe_p05", "circular_block_sample"]