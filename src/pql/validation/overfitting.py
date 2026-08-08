"""M6.4 Deflated Sharpe Ratio (Bailey–López de Prado, 2014).

Reference: Bailey, D. H., and López de Prado, M. (2014). "The Deflated Sharpe
Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality."
Journal of Portfolio Management 40(5), 94–107. Eq. (2) is authoritative.

The paper's Eq. (2) uses TWO different variance concepts:

    PSR threshold (multiple-testing deflation):
        SR0 = sqrt( Var[SR-hat across the trials] )
              * [ (1 - gamma) * Z^-1(1 - 1/N)
                  + gamma * Z^-1(1 - 1/(N*e)) ]
        -- Var[SR-hat across the trials] is the CROSS-SECTIONAL variance of the
           N trials' (per-period) Sharpe estimates, NOT the selected strategy's
           sampling variance.

    PSR sampling uncertainty (selected strategy):
        DSR = Z( (SR - SR0) * sqrt(T - 1)
                 / sqrt(1 - gamma3*SR + (gamma4 - 1)/4 * SR^2) )
        -- gamma3 = selected returns skewness, gamma4 = Pearson kurtosis
           (normal = 3, NOT excess), T = sample length.

with gamma = Euler–Mascheroni constant 0.57721..., Z the standard normal CDF.
SR and SR0 are PER-PERIOD (non-annualized) Sharpe ratios; the annualized output
is reported separately. For N <= 1 there is no multiple-testing bias, so
SR0 = 0 and DSR degenerates to PSR(0).

Trial count is a HARD contract: N = effective_trial_count =
COUNT(DISTINCT selection_key across the strategy lineage) where run_kind ==
SELECT. Bootstrap samples / stress variants / kill variants / walk-forward
folds / final holdout NEVER add to N. The cross-trial Sharpe variance is
computed from the SAME ledger fact source (the SELECT runs' metrics.sharpe,
de-duplicated by selection_key), so DSR and the Research Budget share one
trial fact source.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from pql.registry.experiments import (
    effective_trial_count,
    iter_all_runs,
    lineage_root,
    select_run_keys,
)

GAMMA_EULER = 0.57721566490153286060651209008240243104215933593992
# ddof for the cross-sectional variance of the trials' Sharpe estimates.
# Sample variance (ddof=1) is the unbiased estimator for a sample of trials;
# Fynance uses ddof=0. Either preserves the PASS/FAIL on current evidence.
TRIAL_VAR_DDOF = 1


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


def trial_sharpe_variance(
    experiments_root: str | Path, strategy: str, annualization: int = 252
) -> tuple[list[float], float]:
    """Cross-sectional variance of the trials' PER-PERIOD Sharpe estimates, from
    the ledger (SELECT runs' metrics.sharpe, de-duplicated by selection_key).

    Returns (deduped_annual_sharpes, per-period_variance). With fewer than 2
    distinct trials there is no cross-sectional dispersion -> variance 0."""
    root = lineage_root(strategy)
    by_key: dict[str, float] = {}
    for _exp, run in iter_all_runs(experiments_root):
        if run.get("run_kind") != "SELECT":
            continue
        if lineage_root(run.get("strategy", "")) != root:
            continue
        sk = run.get("selection_key")
        s = _num((run.get("metrics") or {}).get("sharpe"))
        if sk and s is not None:
            by_key.setdefault(sk, s)  # first wins for a duplicated key
    annual = sorted(by_key.values())
    if len(annual) < 2:
        return annual, 0.0
    var_annual = float(np.var(np.array(annual, dtype=float), ddof=TRIAL_VAR_DDOF))
    return annual, var_annual / annualization  # per-period variance


def deflated_sharpe_ratio(
    rets: pd.Series,
    n_trials: int,
    sr_variance: float,
    annualization: int = 252,
) -> dict[str, Any]:
    """Deflated Sharpe Ratio (paper Eq. 2) for a daily returns series.

    `sr_variance` is the cross-sectional variance of the trials' PER-PERIOD
    Sharpe estimates (the multiple-testing deflation input). Returns a component
    dict (observed_sharpe is the ANNUALIZED Sharpe for reporting; the formula
    uses the per-period Sharpe). Deterministic for fixed (returns, N, variance).
    """
    r = rets.dropna()
    T = len(r)
    sr = daily_sharpe(r)
    if sr is None or math.isnan(sr):
        return {
            "dsr_probability": float("nan"),
            "observed_sharpe": float("nan"),
            "n_observations": T,
            "skew": float("nan"),
            "kurtosis": float("nan"),
            "n_trials": n_trials,
            "sr_variance": float(sr_variance),
            "note": "insufficient data for DSR",
        }
    skew = float(stats.skew(r, bias=True))
    kurt = float(stats.kurtosis(r, fisher=False, bias=True))  # Pearson kurtosis

    # multiple-testing deflation: SR0 = sqrt(Var[trial Sharpes]) * E[max normal]
    if n_trials <= 1:
        emax = 0.0
    else:
        emax = math.sqrt(max(sr_variance, 0.0)) * (
            (1.0 - GAMMA_EULER) * stats.norm.ppf(1.0 - 1.0 / n_trials)
            + GAMMA_EULER * stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        )
    # PSR sampling uncertainty of the selected strategy (paper Eq. 2)
    denom = math.sqrt(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2)
    dsr = (
        float(stats.norm.cdf((sr - emax) * math.sqrt(T - 1) / denom))
        if denom > 0 and T > 1
        else float("nan")
    )
    return {
        "dsr_probability": dsr,
        "observed_sharpe": float(sr * math.sqrt(annualization)),
        "daily_sharpe": float(sr),
        "n_observations": T,
        "skew": skew,
        "kurtosis": kurt,
        "n_trials": n_trials,
        "sr_variance": float(sr_variance),
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
    - trial_sharpes = the SELECT runs' annualized Sharpes (de-duplicated)
    - sr_variance = cross-sectional variance of the trials' per-period Sharpes
    - candidate_selection_key = the candidate's default params key
    stderr: bootstrap/stress/kill/fold/final never enter N or the trial set.
    """
    keys = sorted(select_run_keys(experiments_root, strategy))
    n = effective_trial_count(experiments_root, strategy)
    annual_sharpes, sr_var = trial_sharpe_variance(experiments_root, strategy)
    eq = pd.Series(equity).sort_index()
    rets = eq.pct_change().dropna()
    comp = deflated_sharpe_ratio(rets, n, sr_var)
    comp["effective_trial_count"] = n
    comp["trial_selection_keys"] = keys
    comp["trial_sharpes"] = annual_sharpes
    comp["trial_var_ddof"] = TRIAL_VAR_DDOF
    comp["candidate_selection_key"] = _candidate_key(spec)
    return comp


def _candidate_key(spec) -> str:
    from pql.registry.experiments import selection_key
    from pql.signals.registry import effective_params

    return selection_key(effective_params(spec, None))


__all__ = [
    "GAMMA_EULER",
    "TRIAL_VAR_DDOF",
    "daily_sharpe",
    "deflated_sharpe_ratio",
    "deflated_sharpe_report",
    "trial_sharpe_variance",
]