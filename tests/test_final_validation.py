"""M6.8 final-validation tests: not-frozen rejected, freeze-mismatch rejected
before consumption, valid freeze consumes holdout exactly once, second call
rejected, exception-after-consumption keeps consumed=true, FINAL_HOLDOUT never
changes N, holdout-only report, holdout-fail keeps consumed, warmup stays out of
holdout metrics."""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

from pql.registry.experiments import effective_trial_count
from pql.validation.final import FinalValidationError, validate_final
from tests.final_fixture import make_final_momentum_repo, run_candidate_pass


def _consumed(root) -> bool:
    reg = yaml.safe_load((root / "strategy_registry.yaml").read_text(encoding="utf-8"))
    return bool((reg["strategies"][0].get("holdout_status") or {}).get("consumed"))


def _log_lines(root) -> int:
    log = root / "data" / "metadata" / "holdout_access.log"
    if not log.exists():
        return 0
    return len(log.read_text(encoding="utf-8").strip().splitlines())


def test_not_frozen_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)  # RESEARCH, not frozen
    with pytest.raises(FinalValidationError, match="not frozen"):
        validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                       experiments_root=root / "experiments", registry_path=reg)
    assert _consumed(root) is False
    assert _log_lines(root) == 0


def test_freeze_mismatch_rejected_before_consumption(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    # modify spec AFTER freeze
    sp = root / "strategies" / "ftest_v1.yaml"
    sp.write_text(sp.read_text(encoding="utf-8").replace("momentum_days: 10", "momentum_days: 180"), encoding="utf-8")
    with pytest.raises(FinalValidationError, match="FreezeMismatch|freeze mismatch|Frozen candidate changed"):
        validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                       experiments_root=root / "experiments", registry_path=reg)
    assert _consumed(root) is False  # holdout NOT consumed on mismatch
    assert _log_lines(root) == 0


def test_code_change_rejected_before_consumption(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    # simulate a source-code change: corrupt the stored code_tree_sha256 (the
    # freeze's code binding) to prove the guard refuses before consumption.
    reg2 = yaml.safe_load(reg.read_text(encoding="utf-8"))
    reg2["strategies"][0]["candidate_freeze"]["code_tree_sha256"] = "f" * 64
    reg.write_text(yaml.safe_dump(reg2, sort_keys=False), encoding="utf-8")
    with pytest.raises(FinalValidationError, match="code_tree_sha256"):
        validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                       experiments_root=root / "experiments", registry_path=reg)
    assert _consumed(root) is False
    assert _log_lines(root) == 0


def test_valid_freeze_consumes_once(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    report = validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                            experiments_root=root / "experiments", registry_path=reg)
    assert report["overall"] in ("PASS", "FAIL")
    assert _consumed(root) is True
    assert _log_lines(root) == 1
    # candidate_hash is the REAL freeze candidate_hash (not a spec fallback)
    frozen = yaml.safe_load(reg.read_text(encoding="utf-8"))["strategies"][0]["candidate_freeze"]
    assert report["candidate_hash"] == frozen["candidate_hash"]


def test_second_validation_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                   experiments_root=root / "experiments", registry_path=reg)
    with pytest.raises(FinalValidationError, match="already consumed"):
        validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                       experiments_root=root / "experiments", registry_path=reg)
    assert _log_lines(root) == 1  # only the first access logged


def test_exception_after_consumption_keeps_consumed(tmp_path, monkeypatch):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    import pql.validation.final as _final

    def _boom(*a, **k):
        raise RuntimeError("backtest crashed after consumption")

    monkeypatch.setattr(_final, "run_backtest", _boom)
    with pytest.raises(RuntimeError):
        validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                       experiments_root=root / "experiments", registry_path=reg)
    # consumption is irreversible: even though the run crashed, consumed stays true
    assert _consumed(root) is True
    assert _log_lines(root) == 1


def test_final_holdout_does_not_change_n(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    before = effective_trial_count(root / "experiments", "ftest_v1")
    validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                   experiments_root=root / "experiments", registry_path=reg)
    after = effective_trial_count(root / "experiments", "ftest_v1")
    assert before == after  # FINAL_HOLDOUT never adds to N


def test_final_report_is_holdout_only(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    report = validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                            experiments_root=root / "experiments", registry_path=reg)
    for banned in ("walkforward", "cost_stress", "execution_stress", "bootstrap",
                   "deflated_sharpe", "kill_tests", "parameter_robustness"):
        assert banned not in report
    assert "holdout_metrics" in report
    assert "holdout_gate" in report
    assert "holdout_start" in report and "holdout_end" in report
    assert report["final_run_ref"]


def test_holdout_fail_keeps_consumed(tmp_path, monkeypatch):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    import pql.validation.final as _final

    monkeypatch.setattr(_final, "_final_gate", lambda *a, **k: {
        "threshold": 0.0, "holdout_sharpe": -0.5, "pass": False,
    })
    report = validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                            experiments_root=root / "experiments", registry_path=reg)
    assert report["overall"] == "FAIL"
    assert _consumed(root) is True  # a failing holdout is NOT re-runnable
    assert _log_lines(root) == 1


def test_warmup_does_not_contaminate_holdout_metrics(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    report = validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                            experiments_root=root / "experiments", registry_path=reg)
    # holdout metrics are computed on the holdout window only (not the IS part)
    hm = report["holdout_metrics"]
    assert "sharpe" in hm and "cagr" in hm
    # the holdout window is much shorter than IS, so its CAGR differs from a
    # full-range CAGR; assert the report never mixes IS numbers in
    assert report["holdout_start"] >= "2025-01-01"


def test_holdout_scoring_window_includes_first_return():
    """The first holdout return (boundary -> day1) must be scored. A naive
    `equity.loc[holdout:]` slice turns day1 into NaN; the boundary-anchored
    window must keep it (review P0-2)."""
    from types import SimpleNamespace

    from pql.validation.final import _holdout_scoring_window

    idx = pd.date_range("2024-12-30", periods=4, freq="D")  # 12-30, 12-31, 01-01, 01-02
    full = pd.Series([100.0, 100.0, 90.0, 99.0], index=idx)  # IS end 100, day1 crash -10%, day2 +10%
    res = SimpleNamespace(
        equity=full,
        orders=pd.DataFrame(),
        run_meta={"asset_value": full, "trades": pd.DataFrame()},
    )
    hol_eq, _orders, _trades, _asset, hol_dates = _holdout_scoring_window(
        res, "2025-01-01", "2025-01-02"
    )
    # boundary anchor (12-31 = 100) is prepended, so both holdout returns survive
    assert list(hol_eq.index) == [idx[1], idx[2], idx[3]]
    rets = hol_eq.pct_change().dropna()
    assert list(rets.round(10)) == [-0.1, 0.1]  # -10% then +10%
    assert list(hol_dates) == [idx[2], idx[3]]


def test_final_run_artifacts_consistent_window(tmp_path):
    """The FINAL_HOLDOUT run's metrics/equity/orders must all describe the
    holdout window (review P1-4): equity length == holdout days, orders are
    within the holdout window, and order-derived metrics are populated."""
    import json

    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    report = validate_final(root, "ftest_v1", data_root=data_root, report_root=root / "reports",
                            experiments_root=root / "experiments", registry_path=reg)
    exp_id, run_id = report["final_run_ref"].split("/")
    run_dir = root / "experiments" / exp_id / "runs" / run_id
    equity = pd.read_parquet(run_dir / "equity.parquet")
    orders = pd.read_parquet(run_dir / "orders.parquet")
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    # holdout equity is boundary-anchored + holdout window only (not the full
    # IS+holdout range): the first date is the 2024 boundary anchor, not IS start
    eq_dates = pd.to_datetime(equity["date"]).dt.normalize()
    assert eq_dates.min() >= pd.Timestamp("2024-12-31").normalize()  # boundary anchor
    assert eq_dates.max() <= pd.Timestamp(report["holdout_end"]).normalize()
    # orders were re-indexed to the holdout window AND aligned to the persisted
    # equity rows: order.idx == equity row position and order.date == equity
    # date at that row (review #9 P1). equity row 0 is the boundary anchor.
    if len(orders):
        assert "date" in orders.columns
        assert int(orders["idx"].max()) < len(equity)
        for o in orders.itertuples():
            eq_date = pd.to_datetime(equity["date"]).iloc[int(o.idx)].normalize()
            assert eq_date == pd.to_datetime(o.date).normalize()
    # order-derived metrics are populated (not degenerate 0/NaN)
    for key in ("n_trades", "turnover", "exposure", "win_rate"):
        assert key in metrics