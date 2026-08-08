"""M3 order/trade-derived D8 metrics regression tests (review/3): lock the
behavior of n_trades / win_rate / exposure / turnover so they cannot silently
regress to order-counting or a hand-maintained FIFO cost ledger."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pql.backtest.engine import SignalIntent, TargetWeightIntent, run_backtest_impl
from pql.schemas import CostModel, PortfolioConfig
from pql.timing import TimingContract
from tests.backtest_helpers import make_snapshot

A = "510300.SH"
INIT = 100_000.0
PC = PortfolioConfig(init_cash=INIT)


def _z():
    return CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)


def test_n_trades_counts_closed_round_trips_not_orders(tmp_path):
    # BUY/SELL/BUY/SELL -> 4 orders, 2 closed trades -> n_trades == 2
    px = np.array([100.0, 101, 102, 103, 104, 105, 104, 103, 102, 101])
    ds = make_snapshot(tmp_path, {A: px}, name="nt")
    dates = ds.execution_frame()["date"].unique()
    e = pd.DataFrame(False, index=dates, columns=[A])
    x = pd.DataFrame(False, index=dates, columns=[A])
    e.iloc[0] = True  # trade1: fill D1@101, exit D3@103
    x.iloc[2] = True
    e.iloc[4] = True  # trade2: fill D5@105, exit D9@101
    x.iloc[8] = True
    r = run_backtest_impl(SignalIntent(e, x), [A], TimingContract(), _z(), PC, ds)
    assert len(r.orders) == 4
    assert r.metrics["n_trades"] == 2


def test_win_rate_from_closed_trade_pnl(tmp_path):
    # one winning, one losing trade -> win_rate == 0.5
    px = np.array([100.0, 101, 102, 103, 104, 105, 104, 103, 102, 101])
    ds = make_snapshot(tmp_path, {A: px}, name="wr")
    dates = ds.execution_frame()["date"].unique()
    e = pd.DataFrame(False, index=dates, columns=[A])
    x = pd.DataFrame(False, index=dates, columns=[A])
    e.iloc[0], x.iloc[2] = True, True  # win (101 -> 103)
    e.iloc[4], x.iloc[8] = True, True  # loss (105 -> 101)
    r = run_backtest_impl(SignalIntent(e, x), [A], TimingContract(), _z(), PC, ds)
    assert r.metrics["win_rate"] == pytest.approx(0.5)


def test_win_rate_uses_fee_net_pnl_not_gross_price(tmp_path):
    # gross price move is positive (101 -> 103, +2/share) but fee 1% each side
    # (1.01 + 1.03 = 2.04/share) makes the trade NET losing -> win_rate == 0.
    px = np.arange(100.0, 110.0)
    fee = CostModel(version="f", fee_rate=0.01, stamp_duty=0.0, slippage=0.0)
    ds = make_snapshot(tmp_path, {A: px}, name="wnet")
    dates = ds.execution_frame()["date"].unique()
    e = pd.DataFrame(False, index=dates, columns=[A])
    x = pd.DataFrame(False, index=dates, columns=[A])
    e.iloc[0], x.iloc[2] = True, True
    r = run_backtest_impl(SignalIntent(e, x), [A], TimingContract(), fee, PC, ds)
    assert r.orders.iloc[0]["price"] == 101.0  # buy
    assert r.orders.iloc[1]["price"] == 103.0  # sell (gross +price)
    assert r.metrics["win_rate"] == pytest.approx(0.0)  # net pnl < 0


def test_exposure_from_asset_value_for_half_hold(tmp_path):
    # 50% target hold: day0 cash (exposure 0), days1-9 ~50% invested -> mean ~0.46
    ds = make_snapshot(tmp_path, {A: np.arange(100.0, 110.0)}, name="exp")
    dates = ds.execution_frame()["date"].unique()
    w = pd.DataFrame(np.nan, index=dates, columns=[A])
    w.iloc[0] = 0.5
    r = run_backtest_impl(TargetWeightIntent(w), [A], TimingContract(), _z(), PC, ds)
    assert 0.44 < r.metrics["exposure"] < 0.48
    assert 0.0 <= r.metrics["exposure"] <= 1.0


def test_turnover_one_sided_notional_over_nav(tmp_path):
    # single 20% buy (~20000 notional on NAV ~100000, one day) -> mean ~0.02
    ds = make_snapshot(tmp_path, {A: np.arange(100.0, 110.0)}, name="tov")
    dates = ds.execution_frame()["date"].unique()
    w = pd.DataFrame(np.nan, index=dates, columns=[A])
    w.iloc[0] = 0.2
    r = run_backtest_impl(TargetWeightIntent(w), [A], TimingContract(), _z(), PC, ds)
    assert r.metrics["turnover"] == pytest.approx(0.020, abs=0.005)
    assert r.metrics["turnover"] > 0.0
