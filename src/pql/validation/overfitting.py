"""M6.4 Deflated Sharpe Ratio (Bailey–López de Prado, 2014).

Reference: Bailey, D. H., and López de Prado, M. (2014). "The Deflated Sharpe
Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality."
Journal of Portfolio Management 40(5), 94–107.

Formulas (per-observation, non-annualized Sharpe):

    V(SR) = (1 - gamma3*SR + (gamma4 - 1)/4 * SR^2) / (T - 1)

    E[max_SR | N] = sqrt(V) * [ (1 - gamma) * Z^-1(1 - 1/N)
                                + gamma * Z^-1(1 - 1/(N*e)) ]     (N >= 2)

    DSR = Z( (SR - E[max_SR]) / sqrt(V) )

with gamma = Euler–Mascheroni constant 0.57721..., Z the standard normal CDF,
gamma3 the sample skewness, gamma4 the sample PEARSON kurtosis (normal = 3,
NOT excess kurtosis), T the number of daily observations, and N the number of
independent trials. V(SR) is the sampling variance of the selected strategy's
Sharpe estimator (Lo, 2002); the SAME V is used for both the PSR denominator
and the expected-maximum deflation term — the standard Bailey–López de Prado
DSR does NOT use a cross-sectional variance of trial Sharpes. For N <= 1 there
is no multiple-testing bias, so E[max_SR] = 0 and DSR degenerates to PSR(0).

Trial count is a HARD contract: N = effective_trial_count =
COUNT(DISTINCT selection_key across the strategy lineage) where run_kind ==
SELECT. Bootstrap samples / stress variants / kill variants / walk-forward
folds / final holdout NEVER add to N. This module never re-implements trial
counting: it calls pql.registry.experiments.effective_trial_count /
select_run_keys (the SAME fact source as the Research Budget).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from scipy import stats

from pql.registry.experiments import (
    effective_trial_count,
    select_run_keys,
)

GAMMA_EULER = 0.57721566490153286060651209008240243104215933593992


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def daily_sharpe(rets: pd.Series) -> float:
    r = rets.dropna()
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float(r.mean() / sd)


def deflated_sharpe_ratio(
    rets: pd.Series,
    n_trials: int,
    annualization: int = 252,
) -> dict[str, Any]:
    """Deflated Sharpe Ratio for a daily returns series and N trials.

    Returns a component dict (observed_sharpe is the ANNUALIZED Sharpe for
    reporting; the formula itself uses the per-observation daily Sharpe).
    Deterministic for fixed (returns, N): locked by a numerical reference test.
    """
    r = rets.dropna()
    T = len(r)
    sr_daily = daily_sharpe(r)
    if sr_daily is None or math.isnan(sr_daily):
        return {
            "dsr_probability": float("nan"),
            "observed_sharpe": float("nan"),
            "n_observations": T,
            "skew": float("nan"),
            "kurtosis": float("nan"),
            "n_trials": n_trials,
            "note": "insufficient data for DSR",
        }
    skew = float(stats.skew(r, bias=True))
    # gamma4 is the Pearson kurtosis (normal = 3), NOT excess kurtosis (normal
    # = 0). The DSR formula's (gamma4 - 1)/4 term derives from the Lo (2002)
    # variance (1 + gamma4/... ) with gamma4 = fourth standardized moment, so
    # fisher=False. Using excess kurtosis here would be off by 3 (review P0-1B).
    kurt = float(stats.kurtosis(r, fisher=False, bias=True))  # Pearson kurtosis
    V = (1.0 - skew * sr_daily + (kurt - 1.0) / 4.0 * sr_daily**2) / (T - 1)
    if V <= 0:
        V = 0.0
    sqrt_V = math.sqrt(V) if V > 0 else 0.0

    if n_trials <= 1:
        emax = 0.0
    else:
        emax = sqrt_V * (
            (1.0 - GAMMA_EULER) * stats.norm.ppf(1.0 - 1.0 / n_trials)
            + GAMMA_EULER * stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        )
    dsr = (
        float(stats.norm.cdf((sr_daily - emax) / sqrt_V))
        if V > 0
        else float("nan")
    )
    return {
        "dsr_probability": dsr,
        "observed_sharpe": float(sr_daily * math.sqrt(annualization)),
        "daily_sharpe": float(sr_daily),
        "n_observations": T,
        "skew": skew,
        "kurtosis": kurt,
        "n_trials": int(n_trials),
        "annualization": int(annualization),
    }


def deflated_sharpe_report(
    spec,
    equity: pd.Series,
    experiments_root: str | Path,
    strategy: str,
) -> dict[str, Any]:
    """DSR report with full provenance for the candidate validation:

    - N = effective_trial_count (DISTINCT SELECT selection_key across lineage)
    - trial_selection_keys = the actual SELECT keys (ledger fact source)
    - candidate_selection_key = the candidate's default params key
    stderr: bootstrap/stress/kill/fold/final never enter N.
    """
    keys = select_run_keys(experiments_root, strategy)
    n = effective_trial_count(experiments_root, strategy)
    eq = pd.Series(equity).sort_index()
    rets = eq.pct_change().dropna()
    comp = deflated_sharpe_ratio(rets, n)
    comp["effective_trial_count"] = n
    comp["trial_selection_keys"] = sorted(keys)
    comp["candidate_selection_key"] = _candidate_key(spec)
    return comp


def _candidate_key(spec) -> str:
    from pql.registry.experiments import selection_key
    from pql.signals.registry import effective_params

    return selection_key(effective_params(spec, None))


__all__ = [
    "GAMMA_EULER",
    "daily_sharpe",
    "deflated_sharpe_ratio",
    "deflated_sharpe_report",
]