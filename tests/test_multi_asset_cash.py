"""M4.40-41 multi-asset SignalIntent cash semantics contract test.

A single Strategy Run's init_cash is ONE shared portfolio account, NOT N
independent per-symbol portfolios. With group_by+cash_sharing the equity curve
must start at init_cash (not init_cash * num_symbols) and capital released by a
sell must be reusable to buy another symbol.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pql.backtest.engine import SignalIntent, run_backtest_impl
from pql.schemas import CostModel, PortfolioConfig
from pql.timing import TimingContract
from tests.backtest_helpers import make_snapshot

A, B, C, D = "510300.SH", "510500.SH", "518880.SH", "511010.SH"
INIT = 1_000_000.0
_Z = CostModel(version="z", fee_rate=0.0, stamp_duty=0.0, slippage=0.0)
PC = PortfolioConfig(init_cash=INIT)


def test_single_portfolio_not_n_independent(tmp_path):
    """Two symbols risk-on from bar 0 -> ONE shared portfolio worth INIT."""
    n = 6
    ds = make_snapshot(
        tmp_path,
        {A: np.arange(100.0, 100.0 + n), B: np.arange(50.0, 50.0 + n)},
        name="shared",
    )
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[A, B])
    entries.iloc[0] = True
    exits = pd.DataFrame(False, index=dates, columns=[A, B])
    r = run_backtest_impl(
        SignalIntent(entries, exits), [A, B], TimingContract(), _Z, PC, ds
    )
    # equity[0] is the single portfolio nav == INIT (NOT 2*INIT)
    assert r.equity.iloc[0] == INIT
    assert abs(r.equity.iloc[0] - INIT) < 1e-6


def test_equity_is_scalar_series_not_per_symbol(tmp_path):
    n = 6
    ds = make_snapshot(
        tmp_path,
        {A: np.arange(100.0, 100.0 + n), B: np.arange(50.0, 50.0 + n)},
        name="scalar",
    )
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[A, B])
    entries.iloc[0] = True
    exits = pd.DataFrame(False, index=dates, columns=[A, B])
    r = run_backtest_impl(
        SignalIntent(entries, exits), [A, B], TimingContract(), _Z, PC, ds
    )
    assert isinstance(r.equity, pd.Series)
    assert not isinstance(r.equity, pd.DataFrame)


def test_cash_reused_after_sell(tmp_path):
    """A sold -> cash released -> B bought with the SAME pool (cash_sharing)."""
    n = 6
    ds = make_snapshot(
        tmp_path,
        {A: np.arange(100.0, 100.0 + n), B: np.arange(50.0, 50.0 + n)},
        name="reuse",
    )
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[A, B])
    exits = pd.DataFrame(False, index=dates, columns=[A, B])
    entries.iloc[0, 0] = True  # buy A at bar 0
    entries.iloc[2, 1] = True  # buy B at bar 2 (after A sold at T+1)
    exits.iloc[1, 0] = True  # sell A at bar 1
    r = run_backtest_impl(
        SignalIntent(entries, exits), [A, B], TimingContract(), _Z, PC, ds
    )
    # B was bought with cash released from A in the same account
    b_buys = r.orders[(r.orders["side"] == 0) & (r.orders["col"] == 1)]
    assert len(b_buys) == 1
    assert b_buys.iloc[0]["size"] > 0


def test_four_asset_trend_uses_one_million(tmp_path):
    """The M4.45 Trend universe, all risk-on, must still be a 1M portfolio."""
    n = 8
    closes = {s: np.arange(100.0, 100.0 + n) for s in (A, B, C, D)}
    ds = make_snapshot(tmp_path, closes, name="four")
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[A, B, C, D])
    entries.iloc[0] = True
    exits = pd.DataFrame(False, index=dates, columns=[A, B, C, D])
    r = run_backtest_impl(
        SignalIntent(entries, exits), [A, B, C, D], TimingContract(), _Z, PC, ds
    )
    assert r.equity.iloc[0] == INIT  # 1M, not 4M


def test_two_simultaneous_entries_allocate_equal_weight(tmp_path):
    """Two symbols entering on the same bar must split the shared pool EQUALLY
    (50/50), NOT 100%/0% (the from_signals default-size degenerate)."""
    n = 6
    ds = make_snapshot(
        tmp_path,
        {A: np.arange(100.0, 100.0 + n), B: np.arange(100.0, 100.0 + n)},
        name="equal",
    )
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[A, B])
    entries.iloc[0] = True  # both enter the same bar
    exits = pd.DataFrame(False, index=dates, columns=[A, B])
    r = run_backtest_impl(
        SignalIntent(entries, exits), [A, B], TimingContract(), _Z, PC, ds
    )
    buys = r.orders[r.orders["side"] == 0]
    assert len(buys) == 2  # BOTH symbols actually bought
    sizes = sorted(buys["size"].tolist())
    # each bought ~0.5 * INIT / 100 = 5000 shares (equal weight, not 10000/0).
    # vectorbt fills a shared pool sequentially, so the last order ends slightly
    # below the earlier one; assert "approximately equal" (same tolerance the
    # frozen TargetWeightIntent targetpercent design accepts).
    for s in sizes:
        assert s == pytest.approx(0.5 * INIT / 100.0, rel=0.06)


def test_four_simultaneous_entries_allocate_equal_quarter(tmp_path):
    """Four symbols entering the same bar -> each gets 1/4 of the pool."""
    n = 6
    closes = {s: np.arange(100.0, 100.0 + n) for s in (A, B, C, D)}
    ds = make_snapshot(tmp_path, closes, name="quarter")
    dates = ds.execution_frame()["date"].unique()
    entries = pd.DataFrame(False, index=dates, columns=[A, B, C, D])
    entries.iloc[0] = True
    exits = pd.DataFrame(False, index=dates, columns=[A, B, C, D])
    r = run_backtest_impl(
        SignalIntent(entries, exits), [A, B, C, D], TimingContract(), _Z, PC, ds
    )
    buys = r.orders[r.orders["side"] == 0]
    assert len(buys) == 4
    for _, o in buys.iterrows():
        assert o["size"] == pytest.approx(0.25 * INIT / 100.0, rel=0.06)


def _dyn_run(tmp_path, entries_at, exits_at):
    """A+B both price 100+; entries_at/exits_at = lists of (bar_index, col 0|1)."""
    n = 8
    ds = make_snapshot(tmp_path, {A: np.arange(100.0, 100.0 + n),
                                  B: np.arange(100.0, 100.0 + n)}, name="dyn")
    dates = ds.execution_frame()["date"].unique()
    e = pd.DataFrame(False, index=dates, columns=[A, B])
    x = pd.DataFrame(False, index=dates, columns=[A, B])
    for bar, col in entries_at:
        e.iloc[bar, col] = True
    for bar, col in exits_at:
        x.iloc[bar, col] = True
    return run_backtest_impl(SignalIntent(e, x), [A, B], TimingContract(), _Z, PC, ds)


def test_rebalance_when_bside_exits_a_goes_full(tmp_path):
    """A+B = 50/50; B exits -> A must rebalance to ~100% (not stay at 50%)."""
    r = _dyn_run(tmp_path, [(0, 0), (0, 1)], [(3, 1)])  # A+B enter, B exits bar3
    # at idx4: B sold AND A bought up (the freed cash is redeployed to A)
    b_sell = r.orders[(r.orders["idx"] == 4) & (r.orders["side"] == 1) & (r.orders["col"] == 1)]
    a_fill = r.orders[(r.orders["idx"] == 4) & (r.orders["side"] == 0) & (r.orders["col"] == 0)]
    assert len(b_sell) == 1
    assert len(a_fill) == 1  # A IS rebalanced (was the bug)
    # A's rebalance buy notional ≈ the cash released by B ≈ 0.5 * INIT
    a_buy_value = a_fill.iloc[0]["size"] * a_fill.iloc[0]["price"]
    assert a_buy_value == pytest.approx(0.5 * INIT, rel=0.06)


def test_rebalance_when_b_enrolls_a_halves(tmp_path):
    """A = ~100%; B enrolls -> A must drop to ~50% and B reach ~50%."""
    r = _dyn_run(tmp_path, [(0, 0), (3, 1)], [])  # A enters bar0, B enters bar3
    # at bar 3 B enters -> idx4: A sells half (~minus 50% of INIT/100), B buys
    a_sell = r.orders[(r.orders["idx"] == 4) & (r.orders["side"] == 1) & (r.orders["col"] == 0)]
    b_buy = r.orders[(r.orders["idx"] == 4) & (r.orders["side"] == 0) & (r.orders["col"] == 1)]
    assert len(a_sell) == 1
    assert len(b_buy) == 1
    assert b_buy.iloc[0]["size"] == pytest.approx(0.5 * INIT / 100.0, rel=0.06)