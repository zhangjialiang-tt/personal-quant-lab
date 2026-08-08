"""M4.1 / M4.22-23 / M4.46 registry tests: EXP/RUN ids, manifest roundtrip,
derived-parquet rebuild from source of truth, REJECTED preserved."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.registry.experiments import (
    ExperimentError,
    decide_experiment,
    effective_trial_count,
    iter_experiments,
    iter_runs,
    load_manifest,
    load_registry,
    next_experiment_id,
    next_run_id,
    rebuild_registry,
    selection_key,
    write_manifest,
    write_run,
)
from pql.registry.provenance import GitState

CLEAN = GitState(commit="abc123", code_dirty=False, patch="", patch_sha256="")


def _write_run(exp_root, exp_id, strategy="s_v1", params=None, run_kind="SELECT",
               selection="ma_period=200", metrics=None):
    return write_run(
        experiments_root=exp_root,
        experiment_id=exp_id,
        strategy=strategy,
        parameters=params or {"ma_period": 200},
        selection_key=selection,
        run_kind=run_kind,
        visible_to_researcher=True,
        dataset_version="market-20260808-v1",
        dataset_checksums={"prices.parquet": "p", "calendar.parquet": "c"},
        market_rule_version="cn-etf-2026-v1",
        cost_model_version="cn-etf-cost-2026-v1",
        cost_config={"version": "cn-etf-cost-2026-v1", "fee_rate": 0.0003, "slippage": 0.001},
        gate_version="gates-2026-v1",
        gate=CLEAN,
        config_sha256="cfg123",
        dependencies={"vectorbt": "1.1.0", "pandas": "3.0.3", "numpy": "2.4.6"},
        seed=42,
        timing={"execution_bar": 1, "execution_price": "close"},
        metrics=metrics or {"cagr": 0.1, "n_trades": 3},
        equity=pd.DataFrame({"date": ["2024-01-01"], "nav": [1e6]}),
        orders=pd.DataFrame(),
    )


def test_experiment_id_increments(tmp_path):
    assert next_experiment_id(tmp_path) == "EXP-0001"
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    assert next_experiment_id(tmp_path) == "EXP-0002"
    write_manifest(tmp_path, experiment_id="EXP-0002", strategy="s")
    assert next_experiment_id(tmp_path) == "EXP-0003"


def test_manifest_roundtrip(tmp_path):
    p = write_manifest(
        tmp_path, experiment_id="EXP-0001", strategy="etf_trend_v1",
        research_question="is MA stable?", experiment_config={"grid": "frozen"},
    )
    m = load_manifest(tmp_path, "EXP-0001")
    assert m["experiment_id"] == "EXP-0001"
    assert m["strategy"] == "etf_trend_v1"
    assert m["research_question"] == "is MA stable?"
    assert m["decision"] == "PENDING"
    assert m["created"]
    assert p.exists()


def test_run_id_increments_per_experiment(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    assert next_run_id(tmp_path, "EXP-0001") == "RUN-00001"
    _write_run(tmp_path, "EXP-0001")
    assert next_run_id(tmp_path, "EXP-0001") == "RUN-00002"
    _write_run(tmp_path, "EXP-0001")
    assert next_run_id(tmp_path, "EXP-0001") == "RUN-00003"


def test_run_metadata_roundtrip(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    _write_run(tmp_path, "EXP-0001", selection="ma_period=150", params={"ma_period": 150})
    runs = iter_runs(tmp_path, "EXP-0001")
    assert len(runs) == 1
    r = runs[0]
    assert r["run_id"] == "RUN-00001"
    assert r["selection_key"] == "ma_period=150"
    assert r["parameters"]["ma_period"] == 150
    assert r["run_kind"] == "SELECT"
    assert r["code_commit"] == "abc123"
    assert r["code_dirty"] is False
    assert r["config_sha256"] == "cfg123"
    assert r["dependencies"]["vectorbt"] == "1.1.0"
    assert r["metrics"]["cagr"] == 0.1


def test_rebuild_eq_from_source_of_truth(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    _write_run(tmp_path, "EXP-0001", selection="ma_period=150", params={"ma_period": 150})
    _write_run(tmp_path, "EXP-0001", selection="ma_period=200", params={"ma_period": 200})
    write_manifest(tmp_path, experiment_id="EXP-0002", strategy="s")
    _write_run(tmp_path, "EXP-0002", selection="ma_period=250", params={"ma_period": 250})

    out = tmp_path / "registry" / "experiment_registry.parquet"
    df1 = rebuild_registry(tmp_path, out)
    assert len(df1) == 3
    assert set(df1["experiment_id"]) == {"EXP-0001", "EXP-0002"}
    assert df1["selection_key"].tolist() == ["ma_period=150", "ma_period=200", "ma_period=250"]


def test_delete_parquet_then_rebuild_recovers(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    _write_run(tmp_path, "EXP-0001", selection="ma_period=200", params={"ma_period": 200})
    out = tmp_path / "experiment_registry.parquet"
    df1 = rebuild_registry(tmp_path, out)
    out.unlink()  # derived parquet is deletable; source of truth is manifest+runs
    df2 = rebuild_registry(tmp_path, out)
    pd.testing.assert_frame_equal(
        df1.sort_values(["experiment_id", "run_id"]).reset_index(drop=True),
        df2.sort_values(["experiment_id", "run_id"]).reset_index(drop=True),
    )


def test_rejected_experiment_is_preserved(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    _write_run(tmp_path, "EXP-0001", selection="ma_period=200", params={"ma_period": 200})
    decide_experiment(tmp_path, "EXP-0001", "REJECTED", "M4 lifecycle verification")
    manifest = load_manifest(tmp_path, "EXP-0001")
    assert manifest["decision"] == "REJECTED"
    assert manifest["reason"] == "M4 lifecycle verification"
    assert manifest["decision_time"]
    # runs survive
    assert len(iter_runs(tmp_path, "EXP-0001")) == 1
    # rebuild still shows it
    out = tmp_path / "reg.parquet"
    rebuild_registry(tmp_path, out)
    df = load_registry(out)
    row = df[df["experiment_id"] == "EXP-0001"].iloc[0]
    assert row["decision"] == "REJECTED"


def test_effective_trial_count_dedup_and_kind(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s_v1")
    _write_run(tmp_path, "EXP-0001", strategy="s_v1", selection="ma_period=200",
               params={"ma_period": 200})
    _write_run(tmp_path, "EXP-0001", strategy="s_v1", selection="ma_period=200",
               params={"ma_period": 200})  # duplicate key
    _write_run(tmp_path, "EXP-0001", strategy="s_v1", selection="ma_period=150",
               params={"ma_period": 150})
    _write_run(tmp_path, "EXP-0001", strategy="s_v1", selection="ma_period=150",
               params={"ma_period": 150}, run_kind="STRESS")
    # 3 SELECT runs but only 2 distinct keys; STRESS excluded
    assert effective_trial_count(tmp_path, "s_v1") == 2


def test_manifest_requires_valid_exp_id(tmp_path):
    with pytest.raises(ExperimentError):
        write_manifest(tmp_path, experiment_id="EXP-1", strategy="s")


def test_duplicate_experiment_rejected(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    with pytest.raises(ExperimentError):
        write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")


def test_selection_key_distinct_params(tmp_path):
    write_manifest(tmp_path, experiment_id="EXP-0001", strategy="s")
    _write_run(tmp_path, "EXP-0001", selection=selection_key({"ma_period": 150}),
               params={"ma_period": 150})
    _write_run(tmp_path, "EXP-0001", selection=selection_key({"ma_period": 220}),
               params={"ma_period": 220})
    assert len(iter_experiments(tmp_path)) == 1
    assert len(iter_runs(tmp_path, "EXP-0001")) == 2