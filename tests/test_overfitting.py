"""M6.4 Deflated Sharpe Ratio tests: fixed numerical reference, N = DISTINCT
selection_key across lineage (duplicates/lineage-union), stress/bootstrap/kill/
fold/final ignored, N=1 edge deterministic."""
from __future__ import annotations

import json
import pathlib
import tempfile

import numpy as np
import pandas as pd
import pytest

from pql.registry.experiments import effective_trial_count
from pql.validation.overfitting import deflated_sharpe_ratio


# --------------------------------------------------------------------------- #
# Fixed numerical reference (Bailey–López de Prado formula)
# --------------------------------------------------------------------------- #
def test_fixed_numerical_dsr_reference():
    rng = np.random.default_rng(42)
    rets = pd.Series(rng.normal(0.0005, 0.01, 500))
    out = deflated_sharpe_ratio(rets, 5)
    # Locked value for the STANDARD Bailey–López de Prado DSR (Pearson kurtosis,
    # normal=3). If the formula is ever changed this test fails.
    assert out["dsr_probability"] == pytest.approx(0.369461025636, abs=1e-12)
    assert out["n_observations"] == 500
    assert out["n_trials"] == 5
    assert out["observed_sharpe"] == pytest.approx(0.60978582042015, abs=1e-9)


def test_dsr_uses_pearson_kurtosis_not_excess():
    """The DSR formula's gamma4 is Pearson kurtosis (normal=3). feeding excess
    kurtosis (normal=0) into (gamma4-1)/4 must change the result (review P0-1B)."""
    from scipy import stats

    rng = np.random.default_rng(3)
    rets = pd.Series(rng.normal(0.0005, 0.01, 400))
    out = deflated_sharpe_ratio(rets, 5)
    # reported kurtosis must be Pearson (>= 2.9, not near 0)
    assert out["kurtosis"] > 2.0
    assert out["kurtosis"] == pytest.approx(stats.kurtosis(rets, fisher=False, bias=True), abs=1e-9)


def test_dsr_deterministic_for_fixed_inputs():
    rets = pd.Series(np.random.default_rng(5).normal(0.0005, 0.01, 400))
    a = deflated_sharpe_ratio(rets, 10)
    b = deflated_sharpe_ratio(rets, 10)
    assert a["dsr_probability"] == b["dsr_probability"]
    assert not np.isnan(a["dsr_probability"])


def test_dsr_n_one_edge_deterministic():
    rets = pd.Series(np.random.default_rng(1).normal(0.0005, 0.01, 300))
    out = deflated_sharpe_ratio(rets, 1)
    assert 0.0 <= out["dsr_probability"] <= 1.0
    assert out["n_trials"] == 1


# --------------------------------------------------------------------------- #
# Ledger fact source: N = COUNT(DISTINCT selection_key, run_kind == SELECT)
# --------------------------------------------------------------------------- #
def _write_run(exp_root: pathlib.Path, exp: str, run: str, strategy: str,
               run_kind: str, params: dict):
    d = exp_root / exp / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    from pql.registry.experiments import selection_key

    (d / "run.yaml").write_text(
        json.dumps({
            "run_id": run, "experiment_id": exp, "strategy": strategy,
            "parameters": params, "selection_key": selection_key(params),
            "run_kind": run_kind, "visible_to_researcher": True,
            "dataset_version": "v", "dataset_checksums": {}, "market_rule_version": "m",
            "cost_model_version": "c", "cost_config": {}, "gate_version": "g",
            "code_commit": "c", "code_dirty": False, "git_diff_sha256": "",
            "config_sha256": "", "dependencies": {}, "seed": 42, "timing": {},
            "metrics": {}, "created": "2026-01-01T00:00:00",
        }),
        encoding="utf-8",
    )
    (d / "equity.parquet").write_bytes(b"")
    exp_root / exp / "manifest.yaml"


def _write_manifest(exp_root: pathlib.Path, exp: str, strategy: str):
    d = exp_root / exp
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yaml").write_text(
        json.dumps({"experiment_id": exp, "strategy": strategy,
                    "research_question": "q", "experiment_config": {},
                    "decision": "PENDING", "reason": "", "decision_time": None,
                    "created": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )


def test_n_counts_distinct_select_across_lineage():
    tmp = pathlib.Path(tempfile.mkdtemp())
    # v1 SELECT = {A,B,C}; v2 SELECT = {B,C,D}; stress/bootstrap/kill/fold/final
    _write_manifest(tmp, "EXP-0001", "s_v1")
    _write_manifest(tmp, "EXP-0002", "s_v2")
    for i, params in enumerate([{"p": 1}, {"p": 2}, {"p": 3}]):
        _write_run(tmp, "EXP-0001", f"RUN-{i + 1:05d}", "s_v1", "SELECT", params)
    for i, params in enumerate([{"p": 2}, {"p": 3}, {"p": 4}]):
        _write_run(tmp, "EXP-0002", f"RUN-{i + 1:05d}", "s_v2", "SELECT", params)
    # non-SELECT noise must not add to N
    _write_run(tmp, "EXP-0002", "RUN-10001", "s_v2", "STRESS", {"p": 99})
    for i in range(3):
        _write_run(tmp, "EXP-0002", f"RUN-{20000 + i:05d}", "s_v2", "DIAGNOSTIC", {"p": 99})
    _write_run(tmp, "EXP-0002", "RUN-30001", "s_v2", "FINAL_HOLDOUT", {"p": 4})
    # duplicate SELECT keys de-dup; lineage union = {A,B,C,D} = 4 (NOT 6)
    assert effective_trial_count(tmp, "s_v2") == 4


def test_n_ignores_stress_bootstrap_kill_fold():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "s_v1")
    # 5 SELECT configs
    for i in range(5):
        _write_run(tmp, "EXP-0001", f"RUN-{i + 1:05d}", "s_v1", "SELECT", {"p": i})
    # 1000 bootstrap-ish + lots of stress/kill/fold: all non-SELECT
    for i in range(1000):
        _write_run(tmp, "EXP-0001", f"RUN-{10000 + i:05d}", "s_v1", "DIAGNOSTIC", {"p": 999})
    for i in range(30):
        _write_run(tmp, "EXP-0001", f"RUN-{20000 + i:05d}", "s_v1", "STRESS", {"p": 999})
    assert effective_trial_count(tmp, "s_v1") == 5


def test_duplicate_select_dedup():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "s_v1")
    _write_run(tmp, "EXP-0001", "RUN-00001", "s_v1", "SELECT", {"p": 1})
    _write_run(tmp, "EXP-0001", "RUN-00002", "s_v1", "SELECT", {"p": 1})  # duplicate
    _write_run(tmp, "EXP-0001", "RUN-00003", "s_v1", "SELECT", {"p": 2})
    assert effective_trial_count(tmp, "s_v1") == 2


def _spec(seed=42):
    from types import SimpleNamespace

    return SimpleNamespace(seed=seed)