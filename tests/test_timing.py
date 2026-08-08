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

# --------------------------------------------------------------------------- #
# M7 latest_expected_completed_bar (PLAN_CLARIFICATION M7-004)
# --------------------------------------------------------------------------- #
from pql.timing import latest_expected_completed_bar as _lec

_CAL = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"])


def test_trading_morning_previous_bar_completed():
    # Tue 09:30 (before 15:00 close) -> Mon's bar is the latest completed one
    assert _lec(_CAL, "2026-01-06 09:30") == pd.Timestamp("2026-01-05")


def test_trading_after_close_today_bar_completed():
    assert _lec(_CAL, "2026-01-06 15:30") == pd.Timestamp("2026-01-06")


def test_trading_exactly_at_close_completed():
    assert _lec(_CAL, "2026-01-06 15:00") == pd.Timestamp("2026-01-06")


def test_weekend_most_recent_trading_bar():
    # Saturday -> Friday's bar
    assert _lec(_CAL, "2026-01-10 12:00") == pd.Timestamp("2026-01-09")


def test_holiday_most_recent_trading_bar():
    # Sunday -> Friday's bar
    assert _lec(_CAL, "2026-01-11 12:00") == pd.Timestamp("2026-01-09")


def test_latest_expected_not_equal_today_morning():
    # on a trading morning the latest completed bar is NOT today
    today = pd.Timestamp("2026-01-06")
    assert _lec(_CAL, "2026-01-06 09:30") != today


def test_stale_when_price_before_expected_bar():
    from pql.risk.rules import RiskContext, RiskOrder, evaluate_batch
    from pql.schemas import CostModel as _CM

    cost = _CM(version="c", fee_rate=0.0003, stamp_duty=0.0, slippage=0.001)
    ctx = RiskContext(
        risk_config={"version": "r", "max_position_weight": 0.6,
                     "max_portfolio_exposure": 1.0, "max_turnover_per_rebalance": 2.0,
                     "max_order_value": 100000},
        instruments={"510300.SH": {"symbol": "510300.SH", "lot_size": 100,
                                   "listed_date": "2020-01-01"}},
        calendar_dates=frozenset(_CAL),
        expected_completed_bar=_lec(_CAL, "2026-01-06 15:00"),
        execution_date="2026-01-06", cash=100000.0, equity=100000.0,
        positions={}, valuation_price={"510300.SH": 100.0},
        execution_price={"510300.SH": 100.0}, price_date={"510300.SH": "2026-01-05"},
        cost=cost, lot_size={"510300.SH": 100},
    )
    dec = evaluate_batch([RiskOrder("o1", "2026-01-06", "510300.SH", "BUY",
                                    100.0, 100.0, 10000.0)], ctx)
    assert {v.rule for v in dec.violations} == {"stale_price_check"}


def test_not_stale_when_price_on_expected_bar():
    from pql.risk.rules import RiskContext, RiskOrder, evaluate_batch
    from pql.schemas import CostModel as _CM

    cost = _CM(version="c", fee_rate=0.0003, stamp_duty=0.0, slippage=0.001)
    ctx = RiskContext(
        risk_config={"version": "r", "max_position_weight": 0.6,
                     "max_portfolio_exposure": 1.0, "max_turnover_per_rebalance": 2.0,
                     "max_order_value": 100000},
        instruments={"510300.SH": {"symbol": "510300.SH", "lot_size": 100,
                                   "listed_date": "2020-01-01"}},
        calendar_dates=frozenset(_CAL),
        expected_completed_bar=_lec(_CAL, "2026-01-06 15:00"),
        execution_date="2026-01-06", cash=100000.0, equity=100000.0,
        positions={}, valuation_price={"510300.SH": 100.0},
        execution_price={"510300.SH": 100.0}, price_date={"510300.SH": "2026-01-06"},
        cost=cost, lot_size={"510300.SH": 100},
    )
    dec = evaluate_batch([RiskOrder("o1", "2026-01-06", "510300.SH", "BUY",
                                    100.0, 100.0, 10000.0)], ctx)
    assert "stale_price_check" not in {v.rule for v in dec.violations}
