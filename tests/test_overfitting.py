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
    # sr_variance = cross-sectional (per-period) variance of trial Sharpes
    out = deflated_sharpe_ratio(rets, 5, sr_variance=0.01)
    # Locked value for the STANDARD Bailey–López de Prado DSR (paper Eq. 2:
    # cross-trial Sharpe variance for the deflation, Pearson kurtosis for the
    # PSR denominator). If the formula is ever changed this test fails.
    assert out["dsr_probability"] == pytest.approx(0.0352588620719399, abs=1e-12)
    assert out["n_observations"] == 500
    assert out["n_trials"] == 5
    assert out["observed_sharpe"] == pytest.approx(0.60978582042015, abs=1e-9)


def test_dsr_uses_pearson_kurtosis_not_excess():
    """The DSR formula's gamma4 is Pearson kurtosis (normal=3). feeding excess
    kurtosis (normal=0) into (gamma4-1)/4 must change the result."""
    from scipy import stats

    rng = np.random.default_rng(3)
    rets = pd.Series(rng.normal(0.0005, 0.01, 400))
    out = deflated_sharpe_ratio(rets, 5, sr_variance=0.01)
    # reported kurtosis must be Pearson (>= 2.9, not near 0)
    assert out["kurtosis"] > 2.0
    assert out["kurtosis"] == pytest.approx(stats.kurtosis(rets, fisher=False, bias=True), abs=1e-9)


def test_dsr_uses_cross_trial_variance_not_sampling_variance():
    """The multiple-testing deflation must use the CROSS-SECTIONAL variance of
    the trials' Sharpe estimates (paper Eq. 2), NOT the selected strategy's
    sampling variance. A zero cross-trial variance (single trial) must give
    DSR = PSR(0) with no deflation."""
    rng = np.random.default_rng(11)
    rets = pd.Series(rng.normal(0.0005, 0.01, 400))
    # one trial -> no cross-sectional dispersion -> no deflation
    out1 = deflated_sharpe_ratio(rets, 1, sr_variance=0.0)
    # many trials with the SAME cross-trial variance but larger N -> more deflation
    out_many = deflated_sharpe_ratio(rets, 50, sr_variance=0.01)
    assert out1["dsr_probability"] > out_many["dsr_probability"]
    # a larger cross-trial variance must deflate more (all else equal)
    out_hi = deflated_sharpe_ratio(rets, 50, sr_variance=0.04)
    assert out_many["dsr_probability"] > out_hi["dsr_probability"]


def test_dsr_deterministic_for_fixed_inputs():
    rets = pd.Series(np.random.default_rng(5).normal(0.0005, 0.01, 400))
    a = deflated_sharpe_ratio(rets, 10, sr_variance=0.01)
    b = deflated_sharpe_ratio(rets, 10, sr_variance=0.01)
    assert a["dsr_probability"] == b["dsr_probability"]
    assert not np.isnan(a["dsr_probability"])


def test_dsr_n_one_edge_deterministic():
    rets = pd.Series(np.random.default_rng(1).normal(0.0005, 0.01, 300))
    out = deflated_sharpe_ratio(rets, 1, sr_variance=0.0)
    assert 0.0 <= out["dsr_probability"] <= 1.0
    assert out["n_trials"] == 1


# --------------------------------------------------------------------------- #
# Ledger fact source: N = COUNT(DISTINCT selection_key, run_kind == SELECT)
# --------------------------------------------------------------------------- #
def _write_run(exp_root: pathlib.Path, exp: str, run: str, strategy: str,
               run_kind: str, params: dict, sharpe: float | None = None):
    d = exp_root / exp / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    from pql.registry.experiments import selection_key

    metrics = {"sharpe": sharpe} if sharpe is not None else {}
    (d / "run.yaml").write_text(
        json.dumps({
            "run_id": run, "experiment_id": exp, "strategy": strategy,
            "parameters": params, "selection_key": selection_key(params),
            "run_kind": run_kind, "visible_to_researcher": True,
            "dataset_version": "v", "dataset_checksums": {}, "market_rule_version": "m",
            "cost_model_version": "c", "cost_config": {}, "gate_version": "g",
            "code_commit": "c", "code_dirty": False, "git_diff_sha256": "",
            "config_sha256": "", "dependencies": {}, "seed": 42, "timing": {},
            "metrics": metrics, "created": "2026-01-01T00:00:00",
        }),
        encoding="utf-8",
    )
    (d / "equity.parquet").write_bytes(b"")
    exp_root / exp / "manifest.yaml"


def test_trial_sharpe_variance_from_ledger():
    """Cross-trial Sharpe variance is computed from the SELECT ledger, de-duped
    by selection_key, and excludes non-SELECT runs."""
    from pql.validation.overfitting import trial_sharpe_variance

    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "s_v1")
    # 3 distinct SELECT configs with annual Sharpes 1.0, 2.0, 3.0
    _write_run(tmp, "EXP-0001", "RUN-00001", "s_v1", "SELECT", {"p": 1}, sharpe=1.0)
    _write_run(tmp, "EXP-0001", "RUN-00002", "s_v1", "SELECT", {"p": 2}, sharpe=2.0)
    _write_run(tmp, "EXP-0001", "RUN-00003", "s_v1", "SELECT", {"p": 3}, sharpe=3.0)
    # a DUPLICATE selection_key (same config) must NOT double count
    _write_run(tmp, "EXP-0001", "RUN-00004", "s_v1", "SELECT", {"p": 2}, sharpe=9.0)
    # non-SELECT runs must not enter the trial set
    _write_run(tmp, "EXP-0001", "RUN-00005", "s_v1", "STRESS", {"p": 99}, sharpe=99.0)
    annual, var_period = trial_sharpe_variance(tmp, "s_v1", annualization=4)  # 4 periods/yr
    assert sorted(annual) == [1.0, 2.0, 3.0]  # deduped, 3 distinct
    # per-period var = var(annual, ddof=1)/annualization
    expected = float(np.var([1.0, 2.0, 3.0], ddof=1)) / 4.0
    assert var_period == pytest.approx(expected, abs=1e-12)


def test_dsr_fail_closed_on_trial_count_mismatch():
    """If some SELECT trials have an unmeasurable (NaN) Sharpe, the cross-trial
    variance is ill-defined: the DSR must be marked invalid (fail-closed), not
    silently computed with N counting trials that have no Sharpe (review #10 P2)."""
    from pql.validation.overfitting import deflated_sharpe_report

    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "s_v1")
    _write_run(tmp, "EXP-0001", "RUN-00001", "s_v1", "SELECT", {"p": 1}, sharpe=1.0)
    _write_run(tmp, "EXP-0001", "RUN-00002", "s_v1", "SELECT", {"p": 2}, sharpe=2.0)
    # a SELECT config with a NaN (unmeasurable) Sharpe still counts as a trial
    _write_run(tmp, "EXP-0001", "RUN-00003", "s_v1", "SELECT", {"p": 3}, sharpe=float("nan"))
    eq = pd.Series(np.random.default_rng(1).normal(0.0005, 0.01, 300))
    comp = deflated_sharpe_report(_spec(42), eq, tmp, "s_v1")
    assert np.isnan(comp["dsr_probability"])  # fail-closed
    assert "FAIL-CLOSED" in comp.get("note", "")


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

    return SimpleNamespace(seed=seed, signal={"kind": "x"})