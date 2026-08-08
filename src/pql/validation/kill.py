"""M6.5 Kill Test Families (D9 applied; proposal §16.9).

Eight frozen families, each narrowed to a small set of gate-relevant variants:

    K01 drop_best_year        remove the highest-annual-return natural year
    K02 drop_best_trades      top winning trades (ATTRIBUTION + COUNTERFACTUAL)
    K03 universe_loo          drop each universe symbol, full rerun
    K04 delay_execution       execution_bar + 1 (decision unchanged)
    K05 cost_x2               apply_stress(cost, 2)
    K06 shift_rebalance       decision/rebalance schedule shifted 1 trading day
    K07 perturb_params        numeric research params -10% / +10% (deterministic)
    K08 shift_start           start shifted +60 trading days (Snapshot Calendar)

Variant KILLED definition (frozen): cagr <= 0 AND sharpe <= 0 (AND, not OR).
Family aggregation (PLAN_CLARIFICATION M6-003): family_result = KILLED if ANY
gate-relevant child variant is KILLED; killed_fraction = killed gate-relevant
variants / gate-relevant variants. K02 ATTRIBUTION mode is diagnostic only and
NOT gate-relevant (M6-003). The candidate gate counts KILLED FAMILIES
(max_kill_families_killed), never killed child variants.

K07 perturbed params may fall OUTSIDE the frozen param_grid by design (they are
Kill/Stress, not SELECT): they consume no research budget, add no trial N, and
never modify the StrategySpec.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from pql.backtest.api import run_backtest
from pql.backtest.costs import apply_stress
from pql.backtest.engine import ExecutionPerturbation
from pql.data.dataset import DatasetView
from pql.schemas import PortfolioConfig
from pql.signals.momentum_rotation import (
    first_trading_day_of_month,
    momentum_rotation_signal,
)
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract

KILL_FAMILIES = [
    "K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08",
]
K02_ATTRIBUTION_RELEVANT = False  # attribution is diagnostic, not gate-relevant
K02_COUNTERFACTUAL_RELEVANT = True
K02_MAX_TRADES = 10  # min(10, 10%) cap


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _is_killed(metrics: dict) -> bool:
    """Frozen KILLED definition: cagr <= 0 AND sharpe <= 0 (NaN -> not killed,
    deterministic)."""
    c = _num(metrics.get("cagr"))
    s = _num(metrics.get("sharpe"))
    return c is not None and s is not None and c <= 0 and s <= 0


def _metrics_from_returns(rets: pd.Series) -> dict[str, float]:
    from pql.backtest.metrics import cagr, max_drawdown, sharpe

    eq = np.cumprod(1.0 + rets.to_numpy())
    eq = pd.Series(eq, index=rets.index)
    return {
        "cagr": cagr(eq),
        "sharpe": sharpe(eq),
        "max_drawdown": max_drawdown(eq),
    }


def _make_view(spec, data_root, universe, start, end) -> DatasetView:
    return DatasetView.load(
        spec.dataset_version, data_root, universe=universe, start=start, end=end,
    )


def _default_timing(spec) -> TimingContract:
    return TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )


def _portfolio(spec) -> PortfolioConfig:
    return PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )


def _run(
    spec, cost, data_root,
    *,
    universe: list[str],
    is_view: DatasetView,
    params: dict[str, Any],
    timing: TimingContract | None = None,
    perturbation: ExecutionPerturbation | None = None,
    start: str | None = None,
    end: str | None = None,
    intent=None,
):
    """Full run_backtest over [start, end]. The intent is built from `is_view`
    (the full-in-sample view over `universe`, so warmup is preserved), then
    executed on a fresh window view. `intent` may be supplied directly (K06)."""
    start = start or spec.windows["in_sample"][0]
    end = end or spec.windows["in_sample"][1]
    if intent is None:
        intent = build_signal(
            spec, is_view.research_frame(), effective_params(spec, params),
            calendar_dates=is_view.calendar_dates(),
        )
    timing = timing or _default_timing(spec)
    win = _make_view(spec, data_root, universe, start, end)
    return run_backtest(
        intent=intent, universe=universe, execution_model=timing,
        cost_model=cost, portfolio_config=_portfolio(spec), dataset=win,
        perturbation=perturbation,
    )


def _variant(variant_id: str, name: str, params: dict, res, *, gate_relevant: bool = True) -> dict:
    return {
        "variant_id": variant_id,
        "variant_name": name,
        "parameters": params,
        "metrics": dict(res.metrics),
        "result": "KILLED" if _is_killed(res.metrics) else "PASSED",
        "gate_relevant": gate_relevant,
        "equity": res.equity,
        "orders": res.orders,
        "run_ref": None,
        "valuation_mode": res.run_meta.get("valuation_mode"),
    }


def _family(family_id: str, name: str, variants: list[dict], family_params: dict | None = None) -> dict:
    relevant = [v for v in variants if v["gate_relevant"]]
    killed = [v for v in relevant if v["result"] == "KILLED"]
    killed_fraction = (len(killed) / len(relevant)) if relevant else 0.0
    return {
        "family_id": family_id,
        "family_name": name,
        "variants": variants,
        "family_result": "KILLED" if killed else "PASSED",
        "killed_fraction": killed_fraction,
        "gate_relevant_variant_count": len(relevant),
        "killed_variant_count": len(killed),
        "family_params": family_params or {},
    }


def drop_best_year(rets: pd.Series) -> tuple[int, pd.Series]:
    """Identify the natural year with the highest annual return and return
    (best_year, returns_excluding_that_year). Frozen K01 semantics: highest
    annual (compounded) return per natural year (not Sharpe, not a miscounted
    CAGR field)."""
    year_ret = rets.groupby(rets.index.year).apply(
        lambda r: float(np.prod(1.0 + r.to_numpy()) - 1.0)
    )
    best_year = int(year_ret.idxmax())
    return best_year, rets[rets.index.year != best_year]


# --------------------------------------------------------------------------- #
# K01 drop_best_year
# --------------------------------------------------------------------------- #
def _k01(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=is_start, end=is_end)
    equity = pd.Series(res.equity).sort_index()
    rets = equity.pct_change().dropna()
    best_year, remaining = drop_best_year(rets)
    m = _metrics_from_returns(remaining)
    variant = _variant(
        "K01", f"drop_best_year={best_year}", {"best_year": best_year},
        SimpleRes(m), gate_relevant=True,
    )
    year_ret = rets.groupby(rets.index.year).apply(
        lambda r: float(np.prod(1.0 + r.to_numpy()) - 1.0)
    )
    return _family("K01", "drop_best_year", [variant], {"best_year": best_year,
                                                         "annual_returns": year_ret.to_dict()})


# --------------------------------------------------------------------------- #
# K02 drop_best_trades (ATTRIBUTION + COUNTERFACTUAL)
# --------------------------------------------------------------------------- #
def top_winning_trades(closed_trades: list[dict], n_closed: int) -> list[dict]:
    """k = min(10, max(1, ceil(0.10 * n_closed))) most profitable closed trades
    (PLAN_CLARIFICATION M6-004). Frozen rounding; empty list when no closed
    trades (no fabricated trades)."""
    if n_closed <= 0:
        return []
    k = min(10, max(1, math.ceil(0.10 * n_closed)))
    ranked = sorted(closed_trades, key=lambda t: t["net_pnl"], reverse=True)
    return ranked[:k]


def _k02(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    base = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
                params=effective_params(spec, None), start=is_start, end=is_end)
    closed = [t for t in base.run_meta.get("closed_trades", []) if t.get("status") == 1]
    variants: list[dict] = []
    if not closed:
        variants.append({
            "variant_id": "K02_ATTRIBUTION",
            "variant_name": "drop_best_trades (attribution)",
            "parameters": {"mode": "ATTRIBUTION_TEST"},
            "metrics": {},
            "result": "NOT_APPLICABLE",
            "gate_relevant": False,
            "note": "no_closed_trades",
            "equity": None, "orders": None, "run_ref": None,
        })
        variants.append({
            "variant_id": "K02_COUNTERFACTUAL",
            "variant_name": "drop_best_trades (counterfactual)",
            "parameters": {"mode": "COUNTERFACTUAL_TEST"},
            "metrics": {},
            "result": "NOT_APPLICABLE",
            "gate_relevant": True,
            "note": "no_closed_trades",
            "equity": None, "orders": None, "run_ref": None,
        })
        return _family("K02", "drop_best_trades", variants)

    top = top_winning_trades(closed, len(closed))
    from pql.backtest.metrics import cagr, max_drawdown, sharpe

    # ATTRIBUTION (diagnostic): remove the top winning trades' realized PnL
    # from the equity curve from their EXIT date onward, then recompute metrics.
    # Diagnostic only — NOT gate-relevant (M6-003).
    equity = pd.Series(base.equity).sort_index()
    equity_adj = equity.copy()
    for t in top:
        d = pd.Timestamp(t["exit_date"]).normalize()
        if d in equity_adj.index:
            idx = equity_adj.index.get_loc(d)
            equity_adj.iloc[idx:] -= t["net_pnl"]
    att_metrics = {
        "cagr": cagr(equity_adj), "sharpe": sharpe(equity_adj),
        "max_drawdown": max_drawdown(equity_adj),
    }
    variants.append({
        "variant_id": "K02_ATTRIBUTION",
        "variant_name": "drop_best_trades (attribution)",
        "parameters": {"mode": "ATTRIBUTION_TEST", "k": len(top)},
        "metrics": dict(att_metrics),
        "result": "KILLED" if _is_killed(att_metrics) else "PASSED",
        "gate_relevant": K02_ATTRIBUTION_RELEVANT,
        "note": "diagnostic attribution",
        "equity": None, "orders": None, "run_ref": None,
    })

    # COUNTERFACTUAL (full rerun): reject the top trades' ENTRY orders so the
    # portfolio path evolves naturally (a missed SELL changes cash, breaking a
    # later BUY). Full engine rerun via ExecutionPerturbation.reject_mask.
    mask = pd.DataFrame(
        False, index=pd.to_datetime(equity.index), columns=pd.Index(spec.universe)
    )
    for t in top:
        d = pd.Timestamp(t["entry_date"]).normalize()
        sym = t["symbol"]
        if d in mask.index and sym in mask.columns:
            mask.loc[d, sym] = True
    cf = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
              params=effective_params(spec, None), start=is_start, end=is_end,
              perturbation=ExecutionPerturbation(reject_mask=mask))
    variants.append(_variant(
        "K02_COUNTERFACTUAL", "drop_best_trades (counterfactual)",
        {"mode": "COUNTERFACTUAL_TEST", "k": len(top)}, cf,
        gate_relevant=K02_COUNTERFACTUAL_RELEVANT,
    ))
    return _family("K02", "drop_best_trades", variants, {"k": len(top),
                                                          "n_closed_trades": len(closed)})


# --------------------------------------------------------------------------- #
# K03 universe_loo
# --------------------------------------------------------------------------- #
def _k03(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    variants = []
    for sym in list(spec.universe):
        univ = [s for s in spec.universe if s != sym]
        loo_view = _make_view(spec, data_root, univ, is_start, is_end)
        res = _run(spec, cost, data_root, universe=univ, is_view=loo_view,
                   params=effective_params(spec, None), start=is_start, end=is_end)
        variants.append(_variant(f"K03_{sym}", f"universe_loo drop {sym}",
                                 {"drop_symbol": sym}, res, gate_relevant=True))
    return _family("K03", "universe_loo", variants)


# --------------------------------------------------------------------------- #
# K04 delay_execution (execution_bar + 1, decision unchanged, Execution Revaluation)
# --------------------------------------------------------------------------- #
def _k04(spec, cost, ds, data_root) -> dict:
    base_bar = int(spec.timing.get("execution_bar", 1))
    timing = TimingContract(execution_bar=base_bar + 1,
                            execution_price=spec.timing.get("execution_price", "close"))
    is_start, is_end = spec.windows["in_sample"]
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=is_start, end=is_end,
               timing=timing)
    return _family("K04", "delay_execution",
                   [_variant("K04", f"execution_bar={base_bar}+1",
                             {"execution_bar": base_bar + 1}, res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# K05 cost_x2 (reuse apply_stress(cost, 2))
# --------------------------------------------------------------------------- #
def _k05(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    stressed = apply_stress(cost, 2)
    res = _run(spec, stressed, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=is_start, end=is_end)
    return _family("K05", "cost_x2",
                   [_variant("K05", "cost_x2", {"multiplier": 2}, res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# K06 shift_rebalance (decision schedule shifted 1 actual trading day)
# --------------------------------------------------------------------------- #
def _shift_rebalance_days(calendar_dates, rebal_days) -> list:
    sched = np.array(
        sorted({pd.Timestamp(d).normalize() for d in calendar_dates})
    )
    out = []
    for d in rebal_days:
        pos = np.searchsorted(sched, pd.Timestamp(d).normalize(), side="right")
        if pos < len(sched):
            out.append(sched[pos])
    return [pd.Timestamp(x) for x in out]


def _k06(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    kind = spec.signal.get("kind")
    if kind != "momentum_rotation":
        # No rebalance schedule to shift for this signal kind (trend/buy_hold
        # rebalance continuously via the signal). K06 is not gate-relevant here.
        return _family("K06", "shift_rebalance", [{
            "variant_id": "K06",
            "variant_name": "shift_rebalance",
            "parameters": {"rebalance_shift_days": 1},
            "metrics": {},
            "result": "NOT_APPLICABLE",
            "gate_relevant": False,
            "note": f"no rebalance schedule for signal kind {kind!r}",
            "equity": None, "orders": None, "run_ref": None,
        }])
    cal = ds.calendar_dates()
    base_rebal = first_trading_day_of_month(cal)
    shifted = _shift_rebalance_days(cal, base_rebal)
    params = effective_params(spec, None)
    research = ds.research_frame()
    intent = momentum_rotation_signal(
        research, calendar_dates=cal,
        momentum_days=int(params.get("momentum_days")),
        ma_filter=int(params.get("ma_filter", 0)),
        top_k=int(params.get("top_k")),
        max_positions=spec.risk.get("max_positions"),
        rebalance_days=shifted,
    )
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=params, start=is_start, end=is_end, intent=intent)
    return _family("K06", "shift_rebalance",
                   [_variant("K06", "rebalance_shifted_1_trading_day",
                             {"rebalance_shift_days": 1}, res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# K07 perturb_params (±10% numeric research params, deterministic rounding)
# --------------------------------------------------------------------------- #
def _perturb_value(value) -> tuple[float | None, float | None]:
    """(-10%, +10%) with deterministic rounding to int when the value is
    integral. Returns (lo, hi) or (None, None) for non-numeric / disabled."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (None, None)
    lo = value * 0.9
    hi = value * 1.1
    if float(value).is_integer():
        lo = float(round(lo))
        hi = float(round(hi))
    return (lo, hi)


def _k07(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    base_params = effective_params(spec, None)
    variants: list[dict] = []
    for key, value in sorted(base_params.items()):
        lo, hi = _perturb_value(value)
        if lo is None:
            continue
        for direction, pv in (("-10%", lo), ("+10%", hi)):
            if pv == value:
                continue  # degenerate (unchanged after rounding) -> no perturbation
            perturbed = dict(base_params)
            perturbed[key] = pv
            res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
                       params=perturbed, start=is_start, end=is_end)
            variants.append(_variant(
                f"K07_{key}{direction}", f"perturb {key} {direction}",
                {key: pv}, res, gate_relevant=True,
            ))
    return _family("K07", "perturb_params", variants)


# --------------------------------------------------------------------------- #
# K08 shift_start (start +60 actual trading days, warmup from IS history)
# --------------------------------------------------------------------------- #
def _shift_start_date(ds, start: str, n: int) -> str:
    dates = sorted({pd.Timestamp(d) for d in ds.calendar_dates()})
    idx = next((i for i, d in enumerate(dates) if d >= pd.Timestamp(start).normalize()), 0)
    target = min(idx + n, len(dates) - 1)
    return str(dates[target].date())


def _k08(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    shifted = _shift_start_date(ds, is_start, 60)
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=shifted, end=is_end)
    return _family("K08", "shift_start",
                   [_variant("K08", f"start_shifted_{60}_trading_days",
                             {"shift_trading_days": 60, "start": shifted},
                             res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
def kill_tests(spec, cost, ds, data_root) -> dict[str, Any]:
    """Run all 8 kill families on the candidate parameter set (IS only, never
    holdout). Returns a dict keyed by family_id."""
    families = {
        "K01": _k01(spec, cost, ds, data_root),
        "K02": _k02(spec, cost, ds, data_root),
        "K03": _k03(spec, cost, ds, data_root),
        "K04": _k04(spec, cost, ds, data_root),
        "K05": _k05(spec, cost, ds, data_root),
        "K06": _k06(spec, cost, ds, data_root),
        "K07": _k07(spec, cost, ds, data_root),
        "K08": _k08(spec, cost, ds, data_root),
    }
    for fid in KILL_FAMILIES:
        families[fid]["result"] = families[fid]["family_result"]
    return families


def killed_family_count(families: dict[str, Any]) -> int:
    return sum(1 for f in families.values() if f.get("family_result") == "KILLED")


class SimpleRes:
    """Minimal BacktestResult-like shim for metrics-only variants (K01)."""

    def __init__(self, metrics: dict, equity=None, orders=None):
        self.metrics = metrics
        self.equity = equity
        self.orders = orders
        self.run_meta = {"valuation_mode": "returns-based"}


__all__ = [
    "KILL_FAMILIES",
    "drop_best_year",
    "kill_tests",
    "killed_family_count",
    "top_winning_trades",
]