"""M7.66 paper replay tests: T signal -> T+1 execution, raw execution price,
adj research price never used for fills, fees/slippage enter cash, positions
updated, missing price logged, risk rejection logged, logged failure != silent
failure, KILL_SWITCH zero mutation, overlap replay refused."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pql.execution.orders import Order
from pql.execution.paper import (
    PaperAccount,
    ReplayOverlapError,
    _execute_orders,
    paper_replay,
)
from pql.risk.rules import KillSwitchActive, check_kill_switch
from tests.m7_fixture import make_momentum_repo

A, B = "510300.SH", "510500.SH"


def _load_config(root):
    from pql.registry.runner import resolve_paths
    from pql.schemas import load_cost_model, load_spec

    spec = load_spec(root / "strategies" / "test_momentum_v1.yaml")
    paths = resolve_paths(root, spec)
    return spec, load_cost_model(paths["cost"])


def _calendar(ds):
    return sorted(ds.calendar_dates())


def test_t_signal_executes_at_t_plus_1(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    spec, _cost = _load_config(root)
    is0, is1 = spec.windows["in_sample"]
    paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                 paper_root=data_root / "paper", init_cash=100_000)
    account = PaperAccount("test_momentum_v1", data_root / "paper")
    from pql.data.dataset import DatasetView

    ds = DatasetView.load(spec.dataset_version, data_root)
    calendar = _calendar(ds)
    cal_index = {d: i for i, d in enumerate(calendar)}
    for o in account.executed_orders():
        dec = pd.Timestamp(o["decision_date"]).normalize()
        exe = pd.Timestamp(o["execution_date"]).normalize()
        assert cal_index[exe] == cal_index[dec] + 1  # fills at T+1, never T


def test_raw_price_and_no_research_price_for_fill(tmp_path):
    # Build a 2-symbol momentum repo whose close_adj (research) differs from raw
    # close; fills must use RAW close * (1+slippage), never the adjusted price.
    import subprocess

    from tests.backtest_helpers import make_snapshot

    root = Path(tmp_path) / "r2"
    for sub in ("config/costs", "config/markets", "config/instruments",
                "strategies", "experiments", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "config" / "costs" / "test.yaml").write_text(
        "version: cn-etf-cost-2026-v1\nfee_rate: 0.0003\nstamp_duty: 0.0\nslippage: 0.001\n")
    (root / "config" / "markets" / "test.yaml").write_text(
        "version: cn-etf-2026-v1\nmarket_name: CN_ETF\nlot_size: 100\n"
        "trading_calendar: snapshot\nbenchmark: 510300\n")
    (root / "config" / "validation_gates.yaml").write_text(_GATES())
    (root / "config" / "instruments").mkdir(parents=True, exist_ok=True)
    for s in (A, B):
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n")
    n = 90
    closes = {A: 100.0 * (1.001) ** np.arange(n),
              B: 100.0 * (1.0008) ** np.arange(n)}
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    research = {s: pd.Series(closes[s] * 1.5, index=dates, name=s) for s in closes}
    make_snapshot(root / "data", closes, name="market-single-v1", research=research)
    spec_yaml = (
        f"name: ro_v1\nhypothesis: \"h\"\nuniverse: [\"{A}\", \"{B}\"]\n"
        f"benchmark: \"{A}\"\n"
        "signal: {kind: momentum_rotation, momentum_days: 5, ma_filter: 0, top_k: 2}\n"
        "rebalance: monthly\nrisk: {max_positions: 2}\n"
        "dataset_version: market-single-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        "windows:\n  in_sample: [\"2024-01-01\", \"2024-03-30\"]\n"
        "  holdout: [\"2026-01-01\", \"2026-12-31\"]\n"
        "param_grid: {momentum_days: [5], ma_filter: [0], top_k: [2]}\n"
        "research_budget:\n  max_total_selection_runs: 50\n"
        "  max_variants_per_param: {}\n  holdout_access: {allowed: false}\nseed: 42\n")
    (root / "strategies" / "ro_v1.yaml").write_text(spec_yaml)
    subprocess.run(["git", "init", "-q"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), capture_output=True, check=True)

    from pql.data.dataset import DatasetView
    from pql.execution.paper import paper_replay

    paper_replay(root, "ro_v1", "2024-01-01", "2024-03-30",
                 data_root=root / "data", paper_root=root / "data" / "paper",
                 init_cash=100_000)
    account = PaperAccount("ro_v1", root / "data" / "paper")
    assert len(account.executed_orders()) > 0
    ds = DatasetView.load("market-single-v1", root / "data")
    raw = ds.execution_frame()
    for o in account.executed_orders():
        if o["side"] != "BUY":
            continue
        row = raw[(raw["symbol"] == o["symbol"]) &
                  (raw["date"] == pd.Timestamp(o["execution_date"]).normalize())]
        assert len(row) == 1
        raw_close = float(row["close"].iloc[0])
        assert o["fill_price"] == pytest.approx(raw_close * (1 + 0.001), rel=1e-9)
        # the adjusted research price (1.5x raw) is NEVER the fill price
        assert o["fill_price"] != pytest.approx(raw_close * 1.5)


def test_fees_and_slippage_enter_cash(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    spec, _cost = _load_config(root)
    is0, is1 = spec.windows["in_sample"]
    paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                 paper_root=data_root / "paper", init_cash=100_000)
    cash_df = pd.read_parquet(data_root / "paper" / "test_momentum_v1" / "cash.parquet")
    pos_df = pd.read_parquet(data_root / "paper" / "test_momentum_v1" / "positions.parquet")
    assert not pos_df.empty  # positions updated
    assert not cash_df.empty
    # cash never negative (cash_check enforced)
    assert (cash_df["cash"] >= -1e-6).all()
    # fees/slippage represented: init 100k, final cash < 100k (costs paid)
    assert float(cash_df["cash"].iloc[-1]) < 100_000


def test_positions_updated(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    spec, _cost = _load_config(root)
    is0, is1 = spec.windows["in_sample"]
    paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                 paper_root=data_root / "paper", init_cash=100_000)
    pos_df = pd.read_parquet(data_root / "paper" / "test_momentum_v1" / "positions.parquet")
    assert len(pos_df) > 0
    last = pos_df[pos_df["date"] == pos_df["date"].max()]
    assert (last["quantity"] > 0).any()  # holds at least one position


def test_missing_price_logged(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    spec, cost = _load_config(root)
    account = PaperAccount("test_momentum_v1", data_root / "paper")
    # craft an order whose execution day has no price -> NO_FILL + captured failure
    order = Order(order_id="x1", decision_date="2026-01-05", execution_date="2026-01-06",
                  symbol=A, side="BUY", target_weight=0.5, current_quantity=0.0,
                  target_quantity=500.0, adjust_quantity=500.0, lot_size=100,
                  valuation_price=100.0, expected_execution_price=None,
                  reason="test")
    from pql.data.dataset import DatasetView
    from pql.risk.rules import load_instruments, load_risk_config

    ds = DatasetView.load(spec.dataset_version, data_root)
    calendar = _calendar(ds)
    risk_config = load_risk_config(root)
    instruments = load_instruments(root)
    _positions, _cash, n_sim, _ = _execute_orders(
        account=account, orders=[order], day=pd.Timestamp("2026-01-06"), cost=cost,
        instruments=instruments, risk_config=risk_config, calendar=calendar,
        positions={}, cash=100_000.0, exec_price={A: None}, val_close={A: 100.0})
    assert n_sim == 0
    fails = account.read_failures()
    assert any(f["type"] == "missing_execution_price" for f in fails)


def test_risk_rejection_logged(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    spec, cost = _load_config(root)
    account = PaperAccount("test_momentum_v1", data_root / "paper")
    # an order exceeding max_order_value (100000) -> rejected + captured failure
    order = Order(order_id="x1", decision_date="2026-01-05", execution_date="2026-01-06",
                  symbol=A, side="BUY", target_weight=2.0, current_quantity=0.0,
                  target_quantity=200_000.0, adjust_quantity=200_000.0, lot_size=100,
                  valuation_price=1.0, expected_execution_price=1.0, reason="test")
    from pql.data.dataset import DatasetView
    from pql.risk.rules import load_instruments, load_risk_config

    ds = DatasetView.load(spec.dataset_version, data_root)
    calendar = _calendar(ds)
    risk_config = load_risk_config(root)
    instruments = load_instruments(root)
    _positions, _cash, n_sim, dec = _execute_orders(
        account=account, orders=[order], day=pd.Timestamp("2026-01-06"), cost=cost,
        instruments=instruments, risk_config=risk_config, calendar=calendar,
        positions={}, cash=100_000.0, exec_price={A: 1.0}, val_close={A: 1.0})
    assert n_sim == 0
    fails = account.read_failures()
    assert any(f["type"] == "risk_rejected_order" for f in fails)
    assert dec.passed is False


def test_logged_failure_not_silent(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    _, _cost = _load_config(root)
    account = PaperAccount("test_momentum_v1", data_root / "paper")
    account.log_failure(date="2026-01-06", failure_type="test", symbol=A,
                        message="captured", strategy="test_momentum_v1")
    from pql.execution.report import silent_failures

    assert silent_failures(account) == 0  # captured -> not silent


def test_silent_failure_when_event_without_record(tmp_path):
    _root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    from pql.execution.paper import PaperAccount
    from pql.execution.report import silent_failures

    account = PaperAccount("test_momentum_v1", data_root / "paper")
    # a failure EVENT with no matching failures.jsonl record
    account.append_event({"kind": "failure", "failure_id": "orphan-1",
                          "date": "2026-01-06", "type": "test", "symbol": A,
                          "message": "orphan", "captured": True})
    assert silent_failures(account) == 1


def test_kill_switch_zero_mutation(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    (root / "KILL_SWITCH").write_text("", encoding="utf-8")
    spec, _cost = _load_config(root)
    is0, is1 = spec.windows["in_sample"]
    with pytest.raises(KillSwitchActive):
        paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                     paper_root=data_root / "paper", init_cash=100_000)
    # zero mutation: no paper state written
    paper_dir = data_root / "paper" / "test_momentum_v1"
    assert not paper_dir.exists() or not any(paper_dir.iterdir())


def test_overlap_replay_refused(tmp_path):
    root, data_root, _reg = make_momentum_repo(tmp_path, n_days=300)
    spec, _cost = _load_config(root)
    is0, is1 = spec.windows["in_sample"]
    paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                 paper_root=data_root / "paper", init_cash=100_000)
    with pytest.raises(ReplayOverlapError):
        paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                     paper_root=data_root / "paper", init_cash=100_000)


def test_kill_switch_check_direct():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        assert check_kill_switch(td) is None
        Path(td, "KILL_SWITCH").write_text("x")
        with pytest.raises(KillSwitchActive):
            check_kill_switch(td)


def _GATES():
    return (
        "version: gates-2026-v1\ncandidate:\n  min_is_sharpe: 0.5\n"
        "  max_drawdown_floor: -0.35\n  walkforward_min_segment_sharpe_frac: 0.5\n"
        "  param_stability_min_frac: 0.5\n  time_windows_min_pos_cagr_frac: 0.5\n"
        "  cost_2x_min_sharpe: 0.0\n  exec_stress_max_drawdown_floor: -0.45\n"
        "  bootstrap_sharpe_p05_min: -0.3\n  deflated_sharpe_min: 0.95\n"
        "  max_kill_families_killed: 2\n  require_code_clean: true\n"
        "final:\n  holdout_min_sharpe: 0.0\n"
        "paper:\n  min_trading_days: 40\n  min_rebalance_cycles: 3\n"
        "  min_sim_orders: 10\n  max_unreconciled: 0\n  max_silent_failures: 0\n"
        "risk:\n  version: risk-2026-v1\n  max_position_weight: 0.6\n"
        "  max_portfolio_exposure: 1.0\n  max_turnover_per_rebalance: 2.0\n"
        "  max_order_value: 100000\n"
    )