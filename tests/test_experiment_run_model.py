"""M4.5 / M4.44-45 Experiment != Run contract: one Experiment holds many Runs;
the CLI/registry never collapses a Run into an Experiment."""
from __future__ import annotations

import pandas as pd

from pql.registry.experiments import (
    effective_trial_count,
    iter_runs,
    next_experiment_id,
    write_manifest,
    write_run,
)
from pql.registry.provenance import GitState

CLEAN = GitState(commit="abc", code_dirty=False, patch="", patch_sha256="")


def _run(exp_root, exp, strategy, params):
    write_run(
        experiments_root=exp_root, experiment_id=exp, strategy=strategy,
        parameters=params, selection_key=f"ma_period={params['ma_period']}",
        run_kind="SELECT", visible_to_researcher=True,
        dataset_version="market-20260808-v1",
        dataset_checksums={"prices.parquet": "p"},
        market_rule_version="cn-etf-2026-v1", cost_model_version="cn-etf-cost-2026-v1",
        cost_config={"version": "cn-etf-cost-2026-v1", "fee_rate": 0.0003, "slippage": 0.001},
        gate_version="gates-2026-v1", gate=CLEAN, config_sha256="c",
        dependencies={}, seed=42, timing={"execution_bar": 1, "execution_price": "close"},
        metrics={"cagr": 0.1, "n_trades": 2},
        equity=pd.DataFrame({"date": ["2024-01-01"], "nav": [1e6]}), orders=pd.DataFrame(),
    )


def test_one_experiment_holds_three_runs(tmp_path):
    exp = next_experiment_id(tmp_path)
    write_manifest(tmp_path, experiment_id=exp, strategy="etf_trend_v1")
    for p in (150, 200, 250):
        _run(tmp_path, exp, "etf_trend_v1", {"ma_period": p})
    runs = iter_runs(tmp_path, exp)
    assert [r["run_id"] for r in runs] == ["RUN-00001", "RUN-00002", "RUN-00003"]
    assert len(runs) == 3
    # one EXP, three RUNs -> Experiment != Run
    assert next_experiment_id(tmp_path) == "EXP-0002"
    assert effective_trial_count(tmp_path, "etf_trend_v1") == 3


def test_duplicate_run_does_not_add_trial(tmp_path):
    exp = next_experiment_id(tmp_path)
    write_manifest(tmp_path, experiment_id=exp, strategy="etf_trend_v1")
    _run(tmp_path, exp, "etf_trend_v1", {"ma_period": 200})
    _run(tmp_path, exp, "etf_trend_v1", {"ma_period": 200})  # duplicate SELECT
    assert len(iter_runs(tmp_path, exp)) == 2  # run count up
    assert effective_trial_count(tmp_path, "etf_trend_v1") == 1  # trial count unchanged


def test_sequential_experiments_are_distinct(tmp_path):
    e1 = next_experiment_id(tmp_path)
    write_manifest(tmp_path, experiment_id=e1, strategy="s1")
    _run(tmp_path, e1, "s1", {"ma_period": 150})
    e2 = next_experiment_id(tmp_path)
    write_manifest(tmp_path, experiment_id=e2, strategy="s2")
    _run(tmp_path, e2, "s2", {"ma_period": 200})
    assert e1 == "EXP-0001" and e2 == "EXP-0002"
    assert iter_runs(tmp_path, e1)[0]["run_id"] == "RUN-00001"
    assert iter_runs(tmp_path, e2)[0]["run_id"] == "RUN-00001"