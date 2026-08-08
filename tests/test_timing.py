"""M3 timing contract tests (M3.7): reject execution_bar=0, prove T->T+1 real
fill from the final orders, and verify execution_bar=2. Also empty-signal and
missing-price behaviors."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pql.backtest.engine import SignalIntent, run_backtest_impl
from pql.schemas import CostModel, PortfolioConfig
from pql.signals.buy_hold import buy_hold_signal
from pql.timing import TimingContract, TimingError, assert_no_lookahead
from tests.backtest_helpers import make_snapshot

SYMBOL = "510300.SH"
CLOSES = np.arange(100.0, 110.0)
INIT = 100_000.0
_Z = CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)
PC = PortfolioConfig(init_cash=INIT)


def test_execution_bar_0_rejected():
    with pytest.raises(TimingError):
        assert_no_lookahead(TimingContract(execution_bar=0))


def test_execution_price_invalid_rejected():
    with pytest.raises(TimingError):
        TimingContract(execution_price="vwap").validate()


def test_t_plus_1_real_fill_from_orders(tmp_path):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="t1")
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(
        buy_hold_signal(dates, SYMBOL), [SYMBOL], TimingContract(), _Z, PC, ds
    )
    # signal at D0 (entry) -> first fill is at idx 1 (T+1), not idx 0
    assert r.orders.iloc[0]["idx"] == 1
    assert r.orders.iloc[0]["price"] == 101.0
    assert r.orders.iloc[0]["side"] == 0


def test_execution_bar_2_fills_at_t_plus_2(tmp_path):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="t2")
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(
        buy_hold_signal(dates, SYMBOL),
        [SYMBOL],
        TimingContract(execution_bar=2),
        _Z,
        PC,
        ds,
    )
    assert r.orders.iloc[0]["idx"] == 2
    assert r.orders.iloc[0]["price"] == 102.0


def test_empty_signal_flat_equity(tmp_path):
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="empty")
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[SYMBOL])
    exits = pd.DataFrame(False, index=dates, columns=[SYMBOL])
    r = run_backtest_impl(SignalIntent(entries, exits), [SYMBOL], TimingContract(), _Z, PC, ds)
    assert len(r.orders) == 0
    assert np.allclose(r.equity, INIT)  # stays in cash, no exception


def test_missing_price_skipped_no_fake_fill(tmp_path):
    # A has all 10 days; B is missing day index 5 -> B's execution price is NaN
    # there. A B signal firing on that day must NOT fake a fill and must be
    # recorded as skipped_no_price.
    import datetime as _dt

    A, B = "510300.SH", "510500.SH"
    ds = make_snapshot(tmp_path, {A: CLOSES, B: CLOSES * 0.5},
                       name="missing", drop_days={B: [5]})
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    entries = pd.DataFrame(False, index=dates, columns=[A, B])
    entries.iloc[4] = {A: False, B: True}  # B entry -> fill idx5 (B missing)
    exits = pd.DataFrame(False, index=dates, columns=[A, B])
    r = run_backtest_impl(SignalIntent(entries, exits), [A, B], TimingContract(), _Z, PC, ds)
    assert (_dt.date(2024, 1, 6), B) in r.run_meta["skipped_no_price"]
    assert not (r.orders["idx"] == 5).any()


def test_execution_price_open_fills_at_open_not_close(tmp_path):
    # execution_price=open: valuation uses raw close, fills use raw open
    # (open = close - 0.1 in make_snapshot). Fill at idx1 must be 100.9.
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="open")
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(
        buy_hold_signal(dates, SYMBOL), [SYMBOL],
        TimingContract(execution_price="open"), _Z, PC, ds,
    )
    assert r.orders.iloc[0]["idx"] == 1
    assert r.orders.iloc[0]["price"] == pytest.approx(100.9)  # open at D1, not 101


def test_research_price_not_used_as_execution_price(tmp_path):
    # close_adj (research) differs from raw close; the fill must use raw close.
    ds = make_snapshot(tmp_path, {SYMBOL: CLOSES}, name="pit",
                       research={SYMBOL: CLOSES * 1.5})
    dates = ds.execution_frame()["date"].unique()
    r = run_backtest_impl(
        buy_hold_signal(dates, SYMBOL), [SYMBOL], TimingContract(), _Z, PC, ds
    )
    # fill price must be the RAW close at idx 1 (101), not the adjusted 151.5
    assert r.orders.iloc[0]["price"] == 101.0
    assert r.orders.iloc[0]["price"] != 101.0 * 1.5