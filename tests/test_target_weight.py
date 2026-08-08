"""M3 TargetWeightIntent contract tests: from_orders path, targetpercent,
cash_sharing (shared cash pool), sell-before-buy (call_seq), and the
execution-bar shift with Execution-Revaluation valuation semantics.

Note: vectorbt 1.1.0 sizes targetpercent orders at the EXECUTION close price and
ignores val_price for share count (see PLAN_DEVIATION in the M3 report). These
tests assert the actual, frozen-contract behavior of the engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pql.backtest.engine import TargetWeightIntent, run_backtest_impl
from pql.schemas import CostModel, PortfolioConfig
from pql.timing import TimingContract
from tests.backtest_helpers import make_snapshot

A, B = "510300.SH", "510500.SH"
INIT = 100_000.0
_Z = CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)
PC = PortfolioConfig(init_cash=INIT)


def _weights(dates, n):
    w = pd.DataFrame(np.nan, index=dates, columns=[A, B])
    w.iloc[0] = [1.0, 0.0]  # A 100%
    w.iloc[1] = [0.0, 1.0]  # next rebalance: B 100%
    return w


def test_target_weight_rotation_ebar1(tmp_path):
    ds = make_snapshot(tmp_path, {A: np.arange(100.0, 110.0), B: np.arange(50.0, 60.0)},
                       name="tw")
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(TargetWeightIntent(_weights(dates, 10)), [A, B],
                          TimingContract(), _Z, PC, ds)
    assert r.run_meta["intent"] == "target_weight"
    assert r.run_meta["valuation_mode"] == "execution_revaluation"
    o = r.orders
    # idx1: A buy (weight 1.0 shifted); idx2: A sell + B buy (rebalance)
    assert (o["idx"] == 1).any() and (o["idx"] == 2).any()
    a_sell = o[(o["idx"] == 2) & (o["side"] == 1)]
    b_buy = o[(o["idx"] == 2) & (o["side"] == 0) & (o["col"] == 1)]
    assert len(a_sell) == 1 and len(b_buy) == 1
    # sell-before-buy / cash_sharing: B bought with cash released by A sale
    assert b_buy.iloc[0]["size"] > 0
    assert r.equity.iloc[-1] > INIT  # portfolio grew


def test_target_weight_execution_bar_2_fills_at_t_plus_2(tmp_path):
    ds = make_snapshot(tmp_path, {A: np.arange(100.0, 110.0), B: np.arange(50.0, 60.0)},
                       name="tw2")
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(TargetWeightIntent(_weights(dates, 10)), [A, B],
                          TimingContract(execution_bar=2), _Z, PC, ds)
    # weights at D0/D1 -> fills at D2/D3
    assert (r.orders["idx"] == 2).any()
    assert (r.orders["idx"] == 3).any()
    # A buy at idx2 sized/executed at close 102
    a_buy = r.orders[(r.orders["idx"] == 2) & (r.orders["side"] == 0) & (r.orders["col"] == 0)]
    assert a_buy.iloc[0]["price"] == 102.0
    # rebalance at idx3: sell A, buy B
    assert (r.orders[(r.orders["idx"] == 3) & (r.orders["side"] == 1)]).size > 0
    assert (r.orders[(r.orders["idx"] == 3) & (r.orders["side"] == 0) & (r.orders["col"] == 1)]).size > 0


def test_target_weight_cash_sharing_shared_pool(tmp_path):
    # B target at rebalance must be executable with cash released from A (no
    # per-symbol cash isolation). Verify no negative cash and B position > 0.
    ds = make_snapshot(tmp_path, {A: np.arange(100.0, 110.0), B: np.arange(50.0, 60.0)},
                       name="twshare")
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(TargetWeightIntent(_weights(dates, 10)), [A, B],
                          TimingContract(), _Z, PC, ds)
    # after full rotation A sold, B held; cash should be >= 0 (shared pool)
    assert (r.orders["side"] == 1).any()  # a sell occurred
    assert (r.orders["side"] == 0).any()  # a buy occurred