"""Review P0-1 regressions: Execution Revaluation (execution_bar=2 sizes at
T+1 close, not T close) and open-execution risk must never read the execution
day's close (no same-day lookahead)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.backtest_helpers import make_snapshot

A, B = "510300.SH", "510500.SH"


def _build_repo(tmp_path, closes, *, name, signal, exec_bar, exec_price, top_k=2,
                opens: dict | None = None):
    root = Path(tmp_path)
    for sub in ("config/costs", "config/markets", "config/instruments", "strategies",
                "experiments", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "config" / "costs" / "test.yaml").write_text(
        "version: cn-etf-cost-2026-v1\nfee_rate: 0.0003\nstamp_duty: 0.0\nslippage: 0.001\n")
    (root / "config" / "markets" / "test.yaml").write_text(
        "version: cn-etf-2026-v1\nmarket_name: CN_ETF\nlot_size: 100\n"
        "trading_calendar: snapshot\nbenchmark: 510300\n")
    (root / "config" / "validation_gates.yaml").write_text(
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
        "  max_order_value: 100000\n")
    for s in closes:
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n")
    n = len(next(iter(closes.values())))
    research = {s: pd.Series(closes[s], index=pd.date_range("2024-01-01", periods=n, freq="D"),
                             name=s) for s in closes}
    if opens is not None:
        _make_snapshot_opens(root, closes, opens, name)
    else:
        make_snapshot(root / "data", closes, name=name, research=research)
    syms = ", ".join(repr(s) for s in closes)
    spec = (
        f"name: rv_v1\nhypothesis: \"h\"\nuniverse: [{syms}]\nbenchmark: \"{A}\"\n"
        f"signal: {signal}\nrebalance: monthly\nrisk: {{max_positions: 4}}\n"
        f"dataset_version: {name}\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        f"timing: {{execution_bar: {exec_bar}, execution_price: {exec_price}}}\n"
        "windows:\n  in_sample: [\"2024-01-01\", \"2024-04-30\"]\n"
        "  holdout: [\"2026-01-01\", \"2026-12-31\"]\n"
        f"param_grid: {{momentum_days: [5], ma_filter: [0], top_k: [{top_k}]}}\n"
        "research_budget:\n  max_total_selection_runs: 50\n"
        "  max_variants_per_param: {}\n  holdout_access: {allowed: false}\nseed: 42\n")
    (root / "strategies" / "rv_v1.yaml").write_text(spec)
    subprocess.run(["git", "init", "-q"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), capture_output=True, check=True)
    return root, root / "data"


def _make_snapshot_opens(root, closes, opens, name):
    """Build a snapshot where open and close are DECOUPLED per symbol."""
    from pql.data.adapters import FixtureProvider
    from pql.data.calendar import CalendarAdapter, FixtureCalendar
    from pql.data.snapshot import build_snapshot

    n = len(next(iter(closes.values())))
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    data = {}
    for sym, close in closes.items():
        close = np.asarray(close, dtype=float)
        op = np.asarray(opens.get(sym, close - 0.1), dtype=float)
        raw = pd.DataFrame({
            "date": dates, "open": op,
            "high": np.maximum(op, close) + 0.1, "low": np.minimum(op, close) - 0.1,
            "close": close, "volume": np.full(n, 1_000_000),
            "amount": close * 1_000_000,
        })
        data[sym] = {"raw": raw,
                     "research": pd.Series(close, index=dates, name=sym)}
    provider = FixtureProvider(data)
    cal_dates = [d.strftime("%Y-%m-%d") for d in dates]
    calendar = CalendarAdapter([FixtureCalendar(cal_dates)])
    build_snapshot(source="fixture", symbols=list(closes), start="2024-01-01",
                   end=str(dates[-1].date()), data_root=root / "data",
                   from_fixture=True, provider=provider,
                   calendar_adapter=calendar, name=name)


def _calendar(root):
    from pql.data.dataset import DatasetView

    ds = DatasetView.load("market-rv-v1", root / "data")
    return sorted(ds.calendar_dates())


def _close_at(root, day, symbol):
    from pql.data.dataset import DatasetView

    ds = DatasetView.load("market-rv-v1", root / "data")
    row = ds.execution_frame()[(ds.execution_frame()["symbol"] == symbol) &
                               (ds.execution_frame()["date"] == pd.Timestamp(day).normalize())]
    return float(row["close"].iloc[0])


def test_execution_bar_2_revalues_at_T_plus_1_close(tmp_path):
    """execution_bar=2: the fill quantity is sized at T+1 (revaluation bar)
    close, NOT the decision-day T close. A 2x close jump between T and T+1 must
    halve the quantity."""
    n = 90
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    t = np.arange(n)
    # both symbols trend up so momentum is positive (eligible), and A jumps
    # 100 -> 200 exactly on 2024-02-02 (the revaluation bar after the first real
    # decision at 2024-02-01)
    closes_a = 100.0 * (1.001) ** t
    closes_a[dates == pd.Timestamp("2024-02-02")] = 200.0
    closes_b = 50.0 * (1.001) ** t
    root, data_root = _build_repo(
        tmp_path, {A: closes_a, B: closes_b}, name="market-rv-v1",
        signal="{kind: momentum_rotation, momentum_days: 5, ma_filter: 0, top_k: 2}",
        exec_bar=2, exec_price="close")

    from pql.execution.paper import PaperAccount, paper_replay

    paper_replay(root, "rv_v1", "2024-01-01", "2024-04-30",
                 data_root=data_root, paper_root=data_root / "paper", init_cash=100_000)
    account = PaperAccount("rv_v1", data_root / "paper")
    orders = account.executed_orders()
    # first executed BUY with no prior position in that symbol
    buys = [o for o in orders if o["side"] == "BUY" and o["current_quantity"] == 0]
    assert buys, "expected at least one fresh BUY"
    o = buys[0]
    dec = pd.Timestamp(o["decision_date"]).normalize()
    exe = pd.Timestamp(o["execution_date"]).normalize()
    cal = _calendar(root)
    ei = cal.index(exe)
    reval = cal[ei - 1]  # the revaluation bar is the trading day before execution
    assert reval == cal[cal.index(dec) + 1]  # revalue = T+1, execution = T+2
    # revaluation-bar sizing: equity = init_cash (no prior fills at revalue), so
    # qty = floor(0.5 * init_cash / close(reval) / lot) * lot
    close_reval = _close_at(root, reval, o["symbol"])
    expected = int(0.5 * 100_000 / close_reval // 100) * 100
    assert abs(o["adjust_quantity"] - expected) < 1e-6
    # and this is NOT the decision-bar (T) sizing — T close = 100 -> qty 500,
    # revalue close = 200 -> qty 200 (for A; proves revaluation happened)
    close_dec = _close_at(root, dec, o["symbol"])
    t_sized = int(0.5 * 100_000 / close_dec // 100) * 100
    if o["symbol"] == A:
        # revaluate at T+1 close = 200 -> qty 200, NOT the decision-bar sizing
        assert expected == 200
        assert t_sized != expected  # proves revaluation (not T-close sizing)


def test_execution_bar_1_open_risk_unaffected_by_close(tmp_path):
    """execution_bar=1 + execution_price=open: the risk decision must be based
    on the execution-day OPEN, never the execution-day CLOSE (future data at
    open). A huge same-day close must not trigger a max_position_weight reject."""
    n = 90
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    t = np.arange(n)
    # A: trending up (momentum positive) with close jumping to 1000 and open
    # staying ~99 on 2024-02-02 (the execution day). Open decoupled from close.
    closes_a = 100.0 * (1.001) ** t
    closes_a[dates == pd.Timestamp("2024-02-02")] = 1000.0
    opens_a = np.full(n, 99.0)
    closes_b = 50.0 * (1.001) ** t
    root, data_root = _build_repo(
        tmp_path, {A: closes_a, B: closes_b}, name="market-rv-v1",
        signal="{kind: momentum_rotation, momentum_days: 5, ma_filter: 0, top_k: 2}",
        exec_bar=1, exec_price="open", opens={A: opens_a, B: np.full(n, 49.0)})

    from pql.execution.paper import PaperAccount, paper_replay

    paper_replay(root, "rv_v1", "2024-01-01", "2024-04-30",
                 data_root=data_root, paper_root=data_root / "paper", init_cash=100_000)
    account = PaperAccount("rv_v1", data_root / "paper")
    orders = account.executed_orders()
    a_buys = [o for o in orders if o["side"] == "BUY" and o["symbol"] == A]
    # If the risk used the execution-day CLOSE (1000), A's projected position
    # weight would be ~10x and max_position_weight would reject it. It must NOT:
    # the risk uses the OPEN, so A's BUY executes and fills at the open (~99).
    assert a_buys, "A BUY must execute (risk must not see the 1000 close)"
    assert a_buys[0]["fill_price"] == pytest.approx(99.0 * (1 + 0.001), rel=1e-9)