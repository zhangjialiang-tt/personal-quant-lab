"""M4.4 / M4.53-57 deterministic validator tests.

Happy path: a real trend run on a temp synthetic snapshot validates to all-PASS.
Negative tests manufacture each FAIL path: execution_bar=0, fee_rate=0,
future-looking signal, dataset checksum mismatch, illegal trading date.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from pql.backtest.api import SignalIntent
from pql.registry.experiments import next_experiment_id, write_manifest
from pql.registry.runner import run_pipeline
from pql.validation import deterministic as det
from tests.backtest_helpers import make_snapshot

A, B, C, D = "510300.SH", "510500.SH", "518880.SH", "511010.SH"


def _git(url: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(url), capture_output=True, check=True)


def _make_trend_repo(tmp_path: Path, n: int = 60) -> tuple[Path, Path]:
    """Build a self-contained repo: git + config + trend spec + synthetic
    snapshot. Returns (repo_root, data_root)."""
    root = Path(tmp_path)
    for sub in ("config/costs", "config/markets", "config/instruments",
                "strategies", "experiments", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "config" / "costs" / "test.yaml").write_text(
        "version: cn-etf-cost-2026-v1\nfee_rate: 0.0003\nstamp_duty: 0.0\nslippage: 0.001\n",
        encoding="utf-8")
    (root / "config" / "markets" / "test.yaml").write_text(
        "version: cn-etf-2026-v1\nmarket_name: CN_ETF\nlot_size: 100\n"
        "trading_calendar: snapshot\nbenchmark: 510300\n", encoding="utf-8")
    (root / "config" / "validation_gates.yaml").write_text(
        "version: gates-2026-v1\ncandidate: {}\nfinal: {}\n", encoding="utf-8")
    for s in (A, B, C, D):
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n", encoding="utf-8")

    closes = {s: np.cumsum(np.random.RandomState(i).normal(0.001, 0.01, n)) + 100.0
              for i, s in enumerate((A, B, C, D))}
    ds = make_snapshot(root / "data", closes, name="market-test-v1")
    start = str(pd.to_datetime(ds.execution_frame()["date"].min()).date())
    end = str(pd.to_datetime(ds.execution_frame()["date"].max()).date())

    (root / "strategies" / "test_trend_v1.yaml").write_text(
        f"name: test_trend_v1\nhypothesis: \"h\"\n"
        f"universe: [{', '.join(repr(s) for s in (A, B, C, D))}]\n"
        f"benchmark: \"{A}\"\nsignal: {{kind: trend_ma, ma_period: 5}}\n"
        "rebalance: daily\nrisk: {max_positions: 2}\n"
        "dataset_version: market-test-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        f"windows:\n  in_sample: [\"{start}\", \"{end}\"]\n"
        "  holdout: [\"2025-01-01\", \"2026-08-07\"]\n"
        "param_grid: {ma_period: [5, 10, 20]}\n"
        "research_budget:\n  max_total_selection_runs: 10\n"
        "  max_variants_per_param: {ma_period: 3}\n"
        "  holdout_access: {allowed: false}\nseed: 42\n", encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root, root / "data"


def _run_one(root: Path, data_root: Path, params: dict) -> dict:
    exp = next_experiment_id(root / "experiments")
    write_manifest(root / "experiments", experiment_id=exp, strategy="test_trend_v1")
    return run_pipeline(
        repo_root_path=root, experiments_root=root / "experiments",
        strategy="test_trend_v1", params=params, experiment_id=exp,
        data_root=data_root,
    )


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_validate_run_all_pass(tmp_path):
    root, data_root = _make_trend_repo(tmp_path)
    r = _run_one(root, data_root, {"ma_period": 5})
    report = det.validate_run(
        root, root / "experiments", r["experiment_id"], r["run_id"],
        data_root=data_root, report_root=root / "reports",
    )
    assert report["overall"] == "PASS"
    for name, res in report["checks"].items():
        assert res["status"] == "PASS", f"{name}: {res.get('detail')}"
    assert report["checks"]["reproducible"]["semantic_result_hash"]
    # report persisted
    assert (root / "reports" / "validation" / r["experiment_id"] / r["run_id"]
            / "deterministic.json").exists()


# --------------------------------------------------------------------------- #
# Negative tests (each FAIL path)
# --------------------------------------------------------------------------- #


def test_no_same_bar_fill_fails_on_execution_bar_zero(tmp_path):
    run = {"timing": {"execution_bar": 0, "execution_price": "close"}}
    res = det.check_no_same_bar_fill(run, Path(tmp_path))
    assert res["status"] == "FAIL"


def test_no_same_bar_fill_fails_on_pre_shift_fill(tmp_path):
    """An order filling before the earliest legal bar (idx < execution_bar) is a
    same-bar fill and must FAIL."""
    run_dir = Path(tmp_path) / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"id": 0, "col": 0, "idx": 0, "size": 100.0,
                   "price": 1.0, "fees": 0.0, "side": 0}]
                 ).to_parquet(run_dir / "orders.parquet", index=False)
    run = {"timing": {"execution_bar": 1, "execution_price": "close"}}
    res = det.check_no_same_bar_fill(run, run_dir)
    assert res["status"] == "FAIL"


def test_cost_nonzero_fails_on_zero_fee(tmp_path):
    run = {"cost_config": {"fee_rate": 0.0}}
    assert det.check_cost_nonzero(run)["status"] == "FAIL"


def test_dataset_pinned_fails_on_checksum_mismatch(tmp_path):
    make_snapshot(tmp_path, {A: np.arange(100.0, 110.0)}, name="snap")
    run = {"dataset_version": "snap",
           "dataset_checksums": {"prices.parquet": "WRONG", "calendar.parquet": "WRONG"}}
    res = det.check_dataset_pinned(run, tmp_path)
    assert res["status"] == "FAIL"


def test_dataset_pinned_fails_on_missing_version(tmp_path):
    run = {"dataset_version": "does-not-exist", "dataset_checksums": {}}
    assert det.check_dataset_pinned(run, tmp_path)["status"] == "FAIL"


def test_valid_trading_dates_fails_on_illegal_date(tmp_path):
    make_snapshot(tmp_path, {A: np.arange(100.0, 110.0)}, name="cal")
    run_dir = Path(tmp_path) / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    # idx 0 is a real trading date; idx 999 is out of range -> illegal
    pd.DataFrame([
        {"id": 0, "col": 0, "idx": 0, "size": 100.0, "price": 100.0, "fees": 0.0, "side": 0},
        {"id": 1, "col": 0, "idx": 999, "size": 100.0, "price": 100.0, "fees": 0.0, "side": 0},
    ]).to_parquet(run_dir / "orders.parquet", index=False)
    run = {"dataset_version": "cal"}
    res = det.check_valid_trading_dates(run, run_dir, tmp_path)
    assert res["status"] == "FAIL"


def _leaking_signal(_spec, research, _params):
    """Cheat signal: close[t+1] > close[t] — uses FUTURE data (must FAIL)."""
    df = research.pivot(index="date", columns="symbol", values="close_adj").sort_index()
    future = df.shift(-1) > df
    return SignalIntent(entries=future.fillna(False), exits=pd.DataFrame(
        False, index=future.index, columns=future.columns))


def test_no_future_data_fails_on_lookahead_signal(monkeypatch, tmp_path):
    root, data_root = _make_trend_repo(tmp_path)
    monkeypatch.setattr(det, "build_signal", _leaking_signal)
    run = {"strategy": "test_trend_v1", "dataset_version": "market-test-v1",
           "parameters": {"ma_period": 5}}
    res = det.check_no_future_data(root, run, root / "experiments", data_root)
    assert res["status"] == "FAIL"


def test_no_future_data_passes_on_pit_signal(tmp_path):
    root, data_root = _make_trend_repo(tmp_path)
    run = {"strategy": "test_trend_v1", "dataset_version": "market-test-v1",
           "parameters": {"ma_period": 5}}
    res = det.check_no_future_data(root, run, root / "experiments", data_root)
    assert res["status"] == "PASS"


def test_holdout_compliance_fails_on_illegal_access(monkeypatch, tmp_path):
    root, data_root = _make_trend_repo(tmp_path)
    log = data_root / "metadata"
    log.mkdir(parents=True, exist_ok=True)
    (log / "holdout_access.log").write_text(
        json.dumps({"time": "t", "strategy": "test_trend_v1", "purpose": "final_holdout"})
        + "\n", encoding="utf-8")
    run = {"strategy": "test_trend_v1"}
    res = det.check_holdout_compliance(run, data_root, root)
    assert res["status"] == "FAIL"


def test_holdout_compliance_nan_for_clean_run(tmp_path):
    root, data_root = _make_trend_repo(tmp_path)
    run = {"strategy": "test_trend_v1"}
    res = det.check_holdout_compliance(run, data_root, root)
    assert res["status"] == "PASS"