"""M5.6 pipeline tests: happy M5 path, fail path, holdout never called, no
promotion, M6 pending semantics."""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from pql.validation.pipeline import validate_candidate


def _fake_result(metrics=None):
    m = {
        "cagr": 0.1, "sharpe": 2.0, "max_drawdown": -0.1, "annual_vol": 0.2,
        "calmar": 1.0, "n_trades": 10, "turnover": 0.1, "exposure": 0.9,
        "win_rate": 0.5,
    }
    m.update(metrics or {})
    return SimpleNamespace(
        metrics=m,
        equity=pd.Series([1_000_000.0, 1_000_001.0, 1_000_002.0]),
        orders=pd.DataFrame(),
    )


def test_happy_path_incomplete_pending_m6(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    report = validate_candidate(root, "test_momentum_v1", data_root=data_root,
                                report_root=root / "reports",
                                experiments_root=root / "experiments", persist=False)
    assert report["overall"] == "INCOMPLETE_PENDING_M6"
    assert all(v is True for v in report["gate_results"].values())
    assert report["m6_pending"] == {k: "PENDING_M6" for k in
                                    ("cost_stress", "exec_stress", "bootstrap",
                                     "deflated_sharpe", "kill_tests")}
    assert report["strategy_state"] == "RESEARCH"
    assert report["holdout_untouched"] is True


def test_fail_when_is_sharpe_below_gate(monkeypatch, tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    monkeypatch.setattr(
        "pql.validation.pipeline.run_window",
        lambda *a, **k: _fake_result({"sharpe": 0.1, "cagr": -0.05, "max_drawdown": -0.4}),
    )
    report = validate_candidate(root, "test_momentum_v1", data_root=data_root,
                                report_root=root / "reports",
                                experiments_root=root / "experiments", persist=False)
    assert report["overall"] == "FAIL"
    assert report["gate_results"]["min_is_sharpe"] is False


def test_holdout_slice_never_called(monkeypatch, tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("candidate pipeline must never call holdout_slice")

    monkeypatch.setattr("pql.registry.holdout.HoldoutGuard.holdout_slice", _boom)
    validate_candidate(root, "test_momentum_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=False)
    assert calls["n"] == 0


def test_no_promotion_strategy_stays_research(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    validate_candidate(root, "test_momentum_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=False)
    # The candidate pipeline must not create a lifecycle registry entry or
    # promote the strategy; if a registry exists it must not hold CANDIDATE.
    reg_path = root / "strategy_registry.yaml"
    if reg_path.exists():
        import yaml
        reg = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
        for s in reg.get("strategies", []):
            assert s.get("state") != "CANDIDATE"
            assert "candidate_freeze" not in s
    # no holdout permission was granted
    spec_data = (root / "strategies" / "test_momentum_v1.yaml").read_text(encoding="utf-8")
    assert "allowed: true" not in spec_data


def test_holdout_access_log_unchanged(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    log = data_root / "metadata" / "holdout_access.log"
    before = log.read_bytes() if log.exists() else None
    report = validate_candidate(root, "test_momentum_v1", data_root=data_root,
                                report_root=root / "reports",
                                experiments_root=root / "experiments", persist=False)
    after = log.read_bytes() if log.exists() else None
    assert before == after  # still absent (candidate pipeline never consumes holdout)
    assert report["holdout_untouched"] is True


def test_budget_preflight_blocks_all_backtests(monkeypatch, tmp_path):
    """A grid that exceeds the research budget must abort with ZERO backtests
    and no SELECT runs (M5 review P0)."""
    from pql.registry.budget import BudgetError
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)  # grid = 4 configs
    spec_path = root / "strategies" / "test_momentum_v1.yaml"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8").replace(
            "max_total_selection_runs: 50", "max_total_selection_runs: 1"),
        encoding="utf-8")

    calls = {"n": 0}

    def _fake_run_window(*a, **k):
        calls["n"] += 1
        return _fake_result()

    monkeypatch.setattr("pql.validation.pipeline.run_window", _fake_run_window)
    with pytest.raises(BudgetError):
        validate_candidate(root, "test_momentum_v1", data_root=data_root,
                           report_root=root / "reports",
                           experiments_root=root / "experiments", persist=False)
    assert calls["n"] == 0  # no backtest executed
    # no experiment / SELECT runs written
    exp_manifests = list((root / "experiments").glob("EXP-*/manifest.yaml"))
    assert exp_manifests == []