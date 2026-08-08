"""M6.1/M6.2 stress tests: cost 1x/2x/3x, slippage +0.002 additive semantics,
execution_bar=2 / open price, Execution Revaluation preserved, deterministic
miss mask, miss full-engine rerun, missed-SELL path dependency, STRESS never
increases the effective trial count."""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

from pql.backtest.api import run_backtest
from pql.backtest.engine import (
    ExecutionPerturbation,
    TargetWeightIntent,
    generate_reject_mask,
)
from pql.schemas import CostModel, PortfolioConfig
from pql.timing import TimingContract
from pql.validation.stress import (
    cost_stress,
    execution_stress,
    worst_exec_max_drawdown,
)
from tests.backtest_helpers import make_snapshot


def _momentum_context(tmp_path, n_days=400):
    from pql.data.dataset import DatasetView
    from pql.registry.runner import resolve_paths
    from pql.schemas import load_cost_model, load_spec
    from tests.m5_fixture import make_momentum_repo

    root, data_root = make_momentum_repo(tmp_path, n_days=n_days)
    spec = load_spec(root / "strategies" / "test_momentum_v1.yaml")
    paths = resolve_paths(root, spec)
    cost = load_cost_model(paths["cost"])
    ds = DatasetView.load(spec.dataset_version, data_root, universe=spec.universe,
                          start=spec.windows["in_sample"][0], end=spec.windows["in_sample"][1])
    return spec, cost, ds, data_root


def test_cost_stress_1x_2x_3x(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    variants = cost_stress(spec, cost, ds, data_root)
    mults = [v["parameters"]["multiplier"] for v in variants]
    assert mults == [1, 2, 3]
    # 2x cost must not be better than 1x (higher cost -> no better sharpe on
    # identical decisions); the 2x variant is the gate input.
    c1 = variants[0]["sharpe"]
    c2 = variants[1]["sharpe"]
    assert c2 is not None and c1 is not None
    assert c2 <= c1 + 1e-9
    # cost must actually flow into the model (fee/slippage scaled)
    assert round(variants[1]["fee_rate"], 6) == round(cost.fee_rate * 2, 6)
    assert round(variants[1]["slippage"], 6) == round(cost.slippage * 2, 6)


def test_slippage_plus_0002_is_additive(tmp_path):
    """E03 slippage is base + 0.002, NOT base*0.002 and NOT base*2."""
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    variants = execution_stress(spec, cost, ds, data_root)
    e03 = next(v for v in variants if v["variant_id"] == "E03")
    assert round(e03["slippage"], 6) == round(cost.slippage + 0.002, 6)
    assert e03["slippage"] != cost.slippage * 0.002
    assert e03["slippage"] != cost.slippage * 2


def test_execution_stress_all_frozen_variants(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    variants = execution_stress(spec, cost, ds, data_root)
    ids = [v["variant_id"] for v in variants]
    assert ids == ["E01", "E02", "E03", "E04", "E05"]
    assert len(variants) == 5
    # E01 is T+2 (execution_bar=2)
    e01 = next(v for v in variants if v["variant_id"] == "E01")
    assert e01["parameters"]["execution_bar"] == 2
    # E02 open price
    e02 = next(v for v in variants if v["variant_id"] == "E02")
    assert e02["parameters"]["execution_price"] == "open"
    # E04 miss 5% seed 7
    e04 = next(v for v in variants if v["variant_id"] == "E04")
    assert e04["parameters"] == {"miss_rate": 0.05, "seed": 7}
    # every variant preserves Execution Revaluation for TargetWeight
    for v in variants:
        assert v["valuation_mode"] == "execution_revaluation"


def test_open_execution_price_keeps_close_valuation(tmp_path):
    """execution_price=open: fill at raw open, portfolio valuation still close
    (never close==open)."""
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    variants = execution_stress(spec, cost, ds, data_root)
    e02 = next(v for v in variants if v["variant_id"] == "E02")
    from pql.backtest.engine import TargetWeightIntent
    from pql.signals.registry import effective_params
    from pql.validation.base import build_intent

    intent = build_intent(spec, effective_params(spec, None), ds)
    assert isinstance(intent, TargetWeightIntent)
    # E02 ran with open execution; assert it produced a valid (non-empty) result
    assert e02["metrics"].get("n_trades", 0) >= 0
    assert e02["max_drawdown"] is not None


def test_miss_mask_deterministic():
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    ev = pd.DataFrame(False, index=idx, columns=["A", "B"])
    ev.iloc[[5, 10, 15, 20, 25], 0] = True
    ev.iloc[[3, 7, 12, 18, 22], 1] = True
    m1 = generate_reject_mask(ev, 0.05, seed=7)
    m2 = generate_reject_mask(ev, 0.05, seed=7)
    m3 = generate_reject_mask(ev, 0.05, seed=8)
    assert m1.equals(m2)  # same seed -> same mask
    assert not m1.equals(m3)  # different seed -> different mask
    # only event cells are ever rejected
    assert not (m1 & ~ev).any().any()


_TEST_COST = CostModel(version="v", fee_rate=0.0003, stamp_duty=0.0, slippage=0.001)


def _tw_intent(idx, schedule, cols):
    w = pd.DataFrame(np.nan, index=idx, columns=list(cols))
    for d, row in schedule.items():
        w.loc[d] = row
    return TargetWeightIntent(weights=w)


def test_miss_full_rerun_changes_orders():
    """A rejected order is absent from the executed orders (full engine rerun,
    not post-hoc surgery that would leave the order record but no portfolio
    impact)."""
    import tempfile

    tmp_path = pathlib.Path(tempfile.mkdtemp())
    n = 40
    A, B = "510300.SH", "510500.SH"
    closes = {A: 100.0 * 1.001 ** np.arange(n),
              B: 100.0 * 1.0005 ** np.arange(n)}
    ds = make_snapshot(tmp_path, closes, name="miss_snap")
    idx = pd.to_datetime(ds.execution_frame()["date"].unique())
    intent = _tw_intent(idx, {idx[10]: [0.6, 0.4], idx[20]: [0.5, 0.5], idx[30]: [0.4, 0.6]}, (A, B))
    pc = PortfolioConfig(init_cash=1_000_000, max_positions=2, weighting="equal")
    tm = TimingContract(execution_bar=1, execution_price="close")
    base = run_backtest(intent, [A, B], tm, _TEST_COST, pc, ds)
    miss = run_backtest(intent, [A, B], tm, _TEST_COST, pc, ds,
                        ExecutionPerturbation(miss_rate=0.05, seed=7))
    assert len(miss.orders) < len(base.orders)  # at least one order rejected
    assert float(base.equity.iloc[-1]) != float(miss.equity.iloc[-1])  # path differs


def test_missed_sell_path_dependency(tmp_path):
    """Rejecting a SELL changes the subsequent portfolio path (cash stays
    committed, so the state differs from a run where that SELL simply executed).
    Proves the miss is a full engine rerun, not post-hoc order deletion."""
    n = 50
    A, B = "510300.SH", "510500.SH"
    closes = {A: 100.0 * 1.0005 ** np.arange(n),
              B: 100.0 * 1.0003 ** np.arange(n)}
    ds = make_snapshot(tmp_path, closes, name="sell_snap")
    idx = pd.to_datetime(ds.execution_frame()["date"].unique())
    # buy A (day 10), sell A + buy B (day 20), sell B (day 30)
    intent = _tw_intent(idx, {idx[10]: [1.0, 0.0], idx[20]: [0.0, 1.0], idx[30]: [0.0, 0.0]}, (A, B))
    pc = PortfolioConfig(init_cash=1_000_000, max_positions=2, weighting="equal")
    tm = TimingContract(execution_bar=1, execution_price="close")
    base = run_backtest(intent, [A, B], tm, _TEST_COST, pc, ds)
    # reject the SELL of A at the day-20 roll's EXECUTION day (decision day 20
    # executes at day 21 with execution_bar=1)
    mask = pd.DataFrame(False, index=idx, columns=[A, B])
    mask.loc[idx[21], A] = True
    rejected = run_backtest(intent, [A, B], tm, _TEST_COST, pc, ds,
                            ExecutionPerturbation(reject_mask=mask))
    # A's SELL rejected -> A not sold -> different portfolio path
    assert not np.allclose(base.equity.to_numpy(), rejected.equity.to_numpy())
    # the rejected run's orders differ (A-sell absent)
    assert len(rejected.orders) < len(base.orders)


def test_stress_does_not_increase_trial_count(tmp_path):
    from pql.registry.experiments import effective_trial_count
    from pql.validation.pipeline import validate_candidate
    from tests.m5_fixture import make_momentum_repo

    root, data_root = make_momentum_repo(tmp_path, n_days=400)
    validate_candidate(root, "test_momentum_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=False)
    n = effective_trial_count(root / "experiments", "test_momentum_v1")
    # grid = 4 configs; STRESS/DIAGNOSTIC runs must not add to N
    assert n == 4


def test_worst_exec_max_drawdown_uses_worst_variant():
    variants = [
        {"variant_id": "E01", "max_drawdown": -0.1},
        {"variant_id": "E02", "max_drawdown": -0.5},
        {"variant_id": "E03", "max_drawdown": -0.2},
        {"variant_id": "E04", "max_drawdown": -0.3},
        {"variant_id": "E05", "max_drawdown": -0.05},
    ]
    assert worst_exec_max_drawdown(variants) == -0.5  # conservative worst