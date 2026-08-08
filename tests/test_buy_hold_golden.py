"""M3 golden tests (M3.6): Buy & Hold Control against hand-computed values.
Case A: ZeroCostFixture. Case B: fee_rate = 0.001 enters real equity.
Prices: 10 trading days, close = 100, 101, ..., 109. Entry signal at D0,
execution_bar=1 -> fill at D1 close (101)."""
from __future__ import annotations

import numpy as np

from pql.backtest.engine import run_backtest_impl
from pql.schemas import CostModel, PortfolioConfig
from pql.signals.buy_hold import buy_hold_signal
from pql.timing import TimingContract
from tests.backtest_helpers import make_snapshot

SYMBOL = "510300.SH"
CLOSES = np.arange(100.0, 110.0)  # D0=100 ... D9=109
INIT = 100_000.0


def _setup(tmp_path, name):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name=name)
    dates = ds.execution_frame()["date"].unique()
    sig = buy_hold_signal(dates, SYMBOL)
    return ds, sig


def test_buy_hold_zero_cost_golden(tmp_path):
    ds, sig = _setup(tmp_path, "golden_zero")
    z = CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)
    r = run_backtest_impl(
        sig, [SYMBOL], TimingContract(), z, PortfolioConfig(init_cash=INIT), ds
    )
    # first (and only) fill is at idx 1 (D1), price 101, buy side
    assert len(r.orders) == 1
    assert r.orders.iloc[0]["idx"] == 1
    assert r.orders.iloc[0]["price"] == 101.0
    assert r.orders.iloc[0]["side"] == 0
    # no position on D0 (cash flat), position from D1
    assert np.allclose(r.equity.iloc[0], INIT)
    assert np.allclose(r.equity.iloc[1], INIT)
    # hand-computed final equity: buy 100000/101 shares at 101, hold to 109
    shares = INIT / 101.0
    expected_final = shares * 109.0
    assert np.allclose(r.equity.iloc[-1], expected_final)
    assert np.allclose(r.equity.tolist(), [
        INIT, INIT,
        shares * 102.0, shares * 103.0, shares * 104.0, shares * 105.0,
        shares * 106.0, shares * 107.0, shares * 108.0, shares * 109.0,
    ])


def test_buy_hold_fee_enters_equity_golden(tmp_path):
    ds, sig = _setup(tmp_path, "golden_fee")
    z = CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)
    f = CostModel(version="f", fee_rate=0.001, stamp_duty=0.0, slippage=0.0)
    pc = PortfolioConfig(init_cash=INIT)
    rz = run_backtest_impl(sig, [SYMBOL], TimingContract(), z, pc, ds)
    rf = run_backtest_impl(sig, [SYMBOL], TimingContract(), f, pc, ds)
    # same prices/signals -> fee equity strictly below zero-cost equity
    assert rf.equity.iloc[-1] < rz.equity.iloc[-1]
    # hand-computed: shares = INIT / (price * (1+fee)) -> INIT/(101*1.001)
    shares = INIT / (101.0 * 1.001)
    expected_final = shares * 109.0
    assert np.allclose(rf.equity.iloc[-1], expected_final)
    # fee recorded per order
    assert rf.orders.iloc[0]["fees"] > 0


def test_production_policy_rejects_zero_cost_at_api(tmp_path):
    # public run_backtest enforces fee_rate > 0; ZeroCostFixture is engine-only
    from pql.backtest.api import run_backtest
    from pql.backtest.costs import CostModelError

    ds, sig = _setup(tmp_path, "golden_policy")
    z = CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)
    try:
        run_backtest(sig, [SYMBOL], TimingContract(), z, PortfolioConfig(init_cash=INIT), ds)
        assert False, "expected CostModelError"
    except CostModelError:
        pass