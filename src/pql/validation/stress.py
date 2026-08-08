"""M6.1 / M6.2 Cost + Execution stress (D9/D3/D2).

Cost stress: multiplier [1x, 2x, 3x] via the frozen `apply_stress` (scales
fee_rate AND slippage; D3). Every variant is a FULL `run_backtest()` — cost is
fed through the engine so it lands in equity/orders/fees/metrics, never a
post-hoc subtraction from final returns.

Execution stress: the frozen E01-E05 enumeration (M6.2), all executed:
    E01 {execution_bar: 2}
    E02 {execution_price: open}
    E03 {slippage: base + 0.002}        (ADDITIVE, not multiplicative)
    E04 {miss_rate: 0.05, seed: 7}      (deterministic reject-mask, full rerun)
    E05 {execution_bar: 1, execution_price: open}

Execution Revaluation is preserved for every variant: TargetWeightIntent
keeps val_price = close of the bar before the execution bar (execution_bar=1 ->
T close; execution_bar=2 -> T+1 close), and for `execution_price=open` the
portfolio VALUATION stays on raw close while the fill uses raw open (never
close==open). The 5 variants are a FROZEN stress space: no adding / deleting
variants based on results.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

from pql.backtest.api import run_backtest
from pql.backtest.costs import apply_stress
from pql.backtest.engine import ExecutionPerturbation
from pql.data.dataset import DatasetView
from pql.schemas import PortfolioConfig
from pql.signals.registry import effective_params
from pql.timing import TimingContract

from .base import build_intent

# Frozen required execution-stress variants (M6.2). Do not add/remove based on
# observed results.
EXEC_VARIANTS = [
    ("E01", "T+2 execution", {"execution_bar": 2}),
    ("E02", "open execution price", {"execution_price": "open"}),
    ("E03", "slippage +0.002", {"slippage_delta": 0.002}),
    ("E04", "miss 5% seed 7", {"miss_rate": 0.05, "seed": 7}),
    ("E05", "T+1 / open execution price", {"execution_bar": 1, "execution_price": "open"}),
]
COST_MULTIPLIERS = (1, 2, 3)


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _run_variant(
    spec,
    params: dict[str, Any],
    ds: DatasetView,
    cost,
    data_root: str | Path,
    *,
    timing: TimingContract | None = None,
    perturbation: ExecutionPerturbation | None = None,
    start: str | None = None,
    end: str | None = None,
):
    """Full run_backtest on [start, end] with optional timing / cost / execution
    perturbation overrides. Signal is built PIT once over the full in-sample
    research frame (momentum warmup preserved); the window/delay/price/cost
    knobs only affect EXECUTION, never the decision."""
    intent = build_intent(spec, effective_params(spec, params), ds)
    start = start or spec.windows["in_sample"][0]
    end = end or spec.windows["in_sample"][1]
    win = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe, start=start, end=end,
    )
    if timing is None:
        timing = TimingContract(
            execution_bar=int(spec.timing.get("execution_bar", 1)),
            execution_price=spec.timing.get("execution_price", "close"),
        )
    portfolio = PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )
    return run_backtest(
        intent=intent, universe=spec.universe, execution_model=timing,
        cost_model=cost, portfolio_config=portfolio, dataset=win,
        perturbation=perturbation,
    )


def _variant(variant_id: str, name: str, params: dict, res) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "variant_name": name,
        "parameters": params,
        "metrics": dict(res.metrics),
        "sharpe": _num(res.metrics.get("sharpe")),
        "max_drawdown": _num(res.metrics.get("max_drawdown")),
        "cagr": _num(res.metrics.get("cagr")),
        "equity": res.equity,
        "orders": res.orders,
        "run_ref": None,
        "valuation_mode": res.run_meta.get("valuation_mode"),
    }


def cost_stress(
    spec, cost, ds: DatasetView, data_root: str | Path,
    multipliers: tuple[int, ...] = COST_MULTIPLIERS,
) -> list[dict[str, Any]]:
    """Cost stress variants 1x/2x/3x. Each is a full backtest with the stressed
    cost model (apply_stress). The 2x Sharpe is the gate input; 1x is the
    baseline/consistency check; 3x is diagnostic stress evidence."""
    variants: list[dict[str, Any]] = []
    params = effective_params(spec, None)
    for m in multipliers:
        stressed = apply_stress(cost, m)
        res = _run_variant(spec, params, ds, stressed, data_root)
        v = _variant(f"C{m}x", f"cost x{m}", {"multiplier": m}, res)
        v["fee_rate"] = stressed.fee_rate
        v["slippage"] = stressed.slippage
        v["cost_model_version"] = cost.version
        variants.append(v)
    return variants


def execution_stress(spec, cost, ds: DatasetView, data_root: str | Path) -> list[dict[str, Any]]:
    """Run ALL frozen execution variants (E01-E05) on the in-sample window."""
    base_timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    params = effective_params(spec, None)
    variants: list[dict[str, Any]] = []

    def run(timing, cost_model, perturbation=None):
        return _run_variant(spec, params, ds, cost_model, data_root,
                            timing=timing, perturbation=perturbation)

    # E01 execution_bar=2 (Execution Revaluation -> val_price = T+1 close)
    res = run(TimingContract(execution_bar=2, execution_price=base_timing.execution_price), cost)
    variants.append(_variant("E01", "T+2 execution", {"execution_bar": 2}, res))

    # E02 execution_price=open (valuation stays close, fill at open)
    res = run(TimingContract(execution_bar=base_timing.execution_bar, execution_price="open"), cost)
    variants.append(_variant("E02", "open execution price", {"execution_price": "open"}, res))

    # E03 slippage +0.002 (ADDITIVE to base slippage, frozen M6 contract)
    slippy = replace(cost, slippage=cost.slippage + 0.002)
    res = run(base_timing, slippy)
    variants.append(_variant("E03", "slippage +0.002", {"slippage_delta": 0.002}, res))
    variants[-1]["slippage"] = slippy.slippage

    # E04 miss 5% seed 7 (deterministic reject-mask, full engine rerun)
    res = run(base_timing, cost, perturbation=ExecutionPerturbation(miss_rate=0.05, seed=7))
    variants.append(_variant("E04", "miss 5% seed 7", {"miss_rate": 0.05, "seed": 7}, res))

    # E05 execution_bar=1 + execution_price=open
    res = run(TimingContract(execution_bar=1, execution_price="open"), cost)
    variants.append(_variant("E05", "T+1 / open execution price",
                             {"execution_bar": 1, "execution_price": "open"}, res))

    return variants


def worst_exec_max_drawdown(exec_variants: list[dict[str, Any]]) -> float:
    """Conservative gate input: min(max_drawdown) across ALL required execution
    variants (PLAN_CLARIFICATION M6-002: the plan/D9 give no per-variant
    aggregation, so we use the worst required variant, never the prettiest)."""
    mds = [_num(v.get("max_drawdown")) for v in exec_variants if v.get("variant_id") in _REQUIRED_EXEC]
    vals = [m for m in mds if m is not None]
    return min(vals) if vals else 0.0


_REQUIRED_EXEC = {v[0] for v in EXEC_VARIANTS}


__all__ = [
    "COST_MULTIPLIERS",
    "EXEC_VARIANTS",
    "cost_stress",
    "execution_stress",
    "worst_exec_max_drawdown",
]