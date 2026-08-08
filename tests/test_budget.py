"""M4.2 / M4.50 research budget tests: unique SELECT consumes budget, duplicate
selection_key does not consume a new trial, non-SELECT runs never consume a
trial, max_total_selection_runs / max_variants_per_param rejection, lineage
de-duplication."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.registry.budget import BudgetError, check_would_exceed
from pql.registry.experiments import write_manifest, write_run
from pql.registry.provenance import GitState
from pql.schemas import StrategySpec

CLEAN = GitState(commit="abc", code_dirty=False, patch="", patch_sha256="")


def _spec(name="etf_trend_v1", max_total=10, max_variants=None) -> StrategySpec:
    return StrategySpec(
        name=name,
        hypothesis="h",
        universe=["510300.SH"],
        benchmark="510300.SH",
        signal={"kind": "trend_ma", "ma_period": 200},
        rebalance="daily",
        risk={"max_positions": 2},
        dataset_version="market-20260808-v1",
        market_rule_version="cn-etf-2026-v1",
        cost_model_version="cn-etf-cost-2026-v1",
        timing={"execution_bar": 1, "execution_price": "close"},
        windows={"in_sample": ["2020-01-02", "2024-12-31"],
                 "holdout": ["2025-01-01", "2026-08-07"]},
        param_grid={"ma_period": [150, 180, 200, 220, 250]},
        research_budget={
            "max_total_selection_runs": max_total,
            "max_variants_per_param": max_variants or {},
            "holdout_access": {"allowed": False},
        },
        seed=42,
    )


def _add_run(exp_root, exp, strategy, params, run_kind="SELECT"):
    write_run(
        experiments_root=exp_root,
        experiment_id=exp,
        strategy=strategy,
        parameters=params,
        selection_key=f"ma_period={params['ma_period']}",
        run_kind=run_kind,
        visible_to_researcher=True,
        dataset_version="market-20260808-v1",
        dataset_checksums={"prices.parquet": "p"},
        market_rule_version="cn-etf-2026-v1",
        cost_model_version="cn-etf-cost-2026-v1",
        cost_config={"version": "cn-etf-cost-2026-v1", "fee_rate": 0.0003, "slippage": 0.001},
        gate_version="gates-2026-v1",
        gate=CLEAN,
        config_sha256="c",
        dependencies={},
        seed=42,
        timing={"execution_bar": 1, "execution_price": "close"},
        metrics={"cagr": 0.1},
        equity=pd.DataFrame({"date": ["2024-01-01"], "nav": [1e6]}),
        orders=pd.DataFrame(),
    )


def test_unique_select_consumes_budget(tmp_path):
    spec = _spec(max_total=3)
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 150})
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 180})
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200})
    with pytest.raises(BudgetError):
        check_would_exceed(spec, tmp_path, {"ma_period": 220})


def test_duplicate_selection_key_does_not_consume_new_trial(tmp_path):
    spec = _spec(max_total=2)
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200})
    # re-running the same SELECT is allowed (budget not consumed) and passes
    check_would_exceed(spec, tmp_path, {"ma_period": 200})
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200})
    # still only 1 distinct trial; a second distinct one hits exactly the cap
    check_would_exceed(spec, tmp_path, {"ma_period": 150})
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 150})
    # a THIRD distinct selection now exceeds cap 2
    with pytest.raises(BudgetError):
        check_would_exceed(spec, tmp_path, {"ma_period": 220})


def test_non_select_run_does_not_consume_trial(tmp_path):
    spec = _spec(max_total=1)
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200}, run_kind="STRESS")
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200}, run_kind="DIAGNOSTIC")
    # SELECT budget still has room for its first distinct trial
    check_would_exceed(spec, tmp_path, {"ma_period": 150})


def test_max_variants_per_param_exceeded(tmp_path):
    spec = _spec(max_variants={"ma_period": 3})
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 150})
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 180})
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200})
    with pytest.raises(BudgetError):
        check_would_exceed(spec, tmp_path, {"ma_period": 220})


def test_duplicate_variant_value_does_not_exceed_variant_cap(tmp_path):
    spec = _spec(max_variants={"ma_period": 1})
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 200})
    # same value again is fine (not a new variant)
    check_would_exceed(spec, tmp_path, {"ma_period": 200})


def test_budget_message_directs_new_hypothesis(tmp_path):
    spec = _spec(max_total=1)
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 150})
    with pytest.raises(BudgetError, match="new hypothesis/strategy version"):
        check_would_exceed(spec, tmp_path, {"ma_period": 200})


def test_budget_exceed_blocks_backtest_execution(monkeypatch, tmp_path):
    """A budget-exceed SELECT must be rejected BEFORE the backtest engine runs:
    execute_run() is never invoked (orchestration gate, M4 review P1)."""
    from pql.registry.runner import run_pipeline

    spec = _spec(max_total=1)
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy=spec.name)
    _add_run(tmp_path, "EXP-0001", spec.name, {"ma_period": 150})  # cap 1 reached

    monkeypatch.setattr("pql.registry.runner.load_spec", lambda _p: spec)
    called = {"n": 0}

    def _fake_execute(**kwargs):  # pragma: no cover - must not be reached
        called["n"] += 1
        raise AssertionError("execute_run must not be called when budget is exceeded")

    monkeypatch.setattr("pql.registry.runner.execute_run", _fake_execute)
    with pytest.raises(BudgetError):
        run_pipeline(
            repo_root_path=tmp_path, experiments_root=tmp_path,
            strategy=spec.name, params={"ma_period": 200},
            experiment_id="EXP-0001",
        )
    assert called["n"] == 0


def test_lineage_dedup_across_vN(tmp_path):
    # s_v1 uses 2 distinct trials; s_v2 shares the lineage and must NOT reset
    spec_v2 = _spec(name="s_v2", max_total=2)
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s_v1")
    _add_run(tmp_path, "EXP-0001", "s_v1", {"ma_period": 150})
    _add_run(tmp_path, "EXP-0001", "s_v1", {"ma_period": 180})
    write_manifest(tmp_path, experiment_id="EXP-0002", strategy="s_v2")
    # s_v2 trying a THIRD distinct value exceeds the shared lineage budget
    with pytest.raises(BudgetError):
        check_would_exceed(spec_v2, tmp_path, {"ma_period": 200})