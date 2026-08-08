"""M3 vectorbt contract tests: verify the frozen engine->vectorbt arguments are
actually applied (fees/slippage enter equity, long-only, provenance in run_meta)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pql.backtest.engine import SignalIntent, run_backtest_impl
from pql.schemas import CostModel, PortfolioConfig
from pql.signals.buy_hold import buy_hold_signal
from pql.timing import TimingContract
from tests.backtest_helpers import make_snapshot

SYMBOL = "510300.SH"
CLOSES = np.arange(100.0, 110.0)
INIT = 100_000.0
PC = PortfolioConfig(init_cash=INIT)


def _z():
    return CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)


def test_fees_and_slippage_enter_equity(tmp_path):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="cost")
    dates = ds.execution_frame()["date"].unique()
    sig = buy_hold_signal(dates, SYMBOL)
    z = _z()
    f = CostModel(version="f", fee_rate=0.001, stamp_duty=0.0, slippage=0.0)
    s = CostModel(version="s", fee_rate=0.0, stamp_duty=0.0, slippage=0.002)
    rz = run_backtest_impl(sig, [SYMBOL], TimingContract(), z, PC, ds)
    rf = run_backtest_impl(sig, [SYMBOL], TimingContract(), f, PC, ds)
    rs = run_backtest_impl(sig, [SYMBOL], TimingContract(), s, PC, ds)
    assert rf.equity.iloc[-1] < rz.equity.iloc[-1]
    assert rs.equity.iloc[-1] < rz.equity.iloc[-1]


def test_longonly_no_short_from_bare_exit(tmp_path):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="longonly")
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[SYMBOL])
    exits = pd.DataFrame(False, index=dates, columns=[SYMBOL])
    exits.iloc[0] = True  # a bare exit with no position must not short
    r = run_backtest_impl(SignalIntent(entries, exits), [SYMBOL], TimingContract(), _z(), PC, ds)
    assert len(r.orders) == 0
    assert np.allclose(r.equity, INIT)


def test_run_meta_provenance(tmp_path):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="meta")
    dates = ds.execution_frame()["date"].unique()
    f = CostModel(version="cn-etf-cost-2026-v1", fee_rate=0.0003, stamp_duty=0.0, slippage=0.001)
    r = run_backtest_impl(
        buy_hold_signal(dates, SYMBOL), [SYMBOL],
        TimingContract(execution_bar=1, execution_price="close"), f, PC, ds,
    )
    m = r.run_meta
    assert m["engine"] == "vectorbt"
    assert "vectorbt_version" in m
    assert m["execution_bar"] == 1
    assert m["execution_price"] == "close"
    assert m["valuation_mode"] == "signal_fill"
    assert m["cost_model_version"] == "cn-etf-cost-2026-v1"
    assert m["fee_rate"] == 0.0003
    assert m["slippage"] == 0.001
