"""Review P1-1 regression: ONE frozen fill-economics function used by the risk
dry-run, the paper fill (mutation) and independent reconciliation. A risk
cash_check PASS must predict exactly the same final cash as the fill."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.execution.economics import compute_fill_economics
from pql.schemas import CostModel

COST = CostModel(version="cn-etf-cost-2026-v1", fee_rate=0.0003, stamp_duty=0.0,
                 slippage=0.001)


def test_buy_economics():
    ec = compute_fill_economics("BUY", 1000.0, 100.0, COST)
    assert ec["fill_price"] == pytest.approx(100.0 * 1.001)
    assert ec["gross_notional"] == pytest.approx(1000.0 * 100.1)
    assert ec["fee"] == pytest.approx(1000.0 * 100.1 * 0.0003)
    assert ec["stamp"] == 0.0
    # slippage cost = |fill - raw| * qty = 0.1 * 1000 = 100 (NOT gross*slippage)
    assert ec["slippage_cost"] == pytest.approx(100.0)
    assert ec["cash_delta"] == pytest.approx(-(ec["gross_notional"] + ec["fee"]))


def test_sell_economics():
    ec = compute_fill_economics("SELL", 1000.0, 100.0, COST)
    assert ec["fill_price"] == pytest.approx(100.0 * 0.999)
    assert ec["gross_notional"] == pytest.approx(1000.0 * 99.9)
    assert ec["fee"] == pytest.approx(1000.0 * 99.9 * 0.0003)
    assert ec["stamp"] == 0.0
    assert ec["slippage_cost"] == pytest.approx(100.0)
    assert ec["cash_delta"] == pytest.approx(+(ec["gross_notional"]
                                               - ec["fee"] - ec["stamp"]))


def test_boundary_cash_consistency():
    """A risk cash_check PASS must predict the same final cash as the fill: the
    risk dry-run and the paper fill MUST agree to float precision (review P1-1).
    At a tight cash boundary the OLD risk formula (fee on RAW notional) predicted
    +0.01 (PASS) while the real fill (fee on slippage-adjusted notional) went
    -0.02 (negative). After the unification the risk dry-run uses the SAME
    economics, so it correctly rejects at this boundary."""
    from pql.risk.rules import RiskContext, RiskOrder, evaluate_batch

    qty = 100_000.0
    raw = 1.0
    cash = 100_130.01  # old-formula PASS (+0.01) but real fill goes negative
    risk_config = {"version": "r", "max_position_weight": 0.6,
                   "max_portfolio_exposure": 1.0,
                   "max_turnover_per_rebalance": 2.0, "max_order_value": 100000}
    ctx = RiskContext(
        risk_config=risk_config,
        instruments={"510300.SH": {"symbol": "510300.SH", "lot_size": 100,
                                   "listed_date": "2020-01-01"}},
        calendar_dates=frozenset([pd.Timestamp("2026-01-06")]),
        expected_completed_bar=pd.Timestamp("2026-01-06"),
        execution_date="2026-01-06", cash=cash, equity=cash,
        positions={}, valuation_price={"510300.SH": raw},
        execution_price={"510300.SH": raw},
        price_date={"510300.SH": "2026-01-06"}, cost=COST,
        lot_size={"510300.SH": 100},
    )
    order = RiskOrder("o1", "2026-01-06", "510300.SH", "BUY", qty, raw, qty * raw)
    dec = evaluate_batch([order], ctx)
    # the fill with the SAME economics lands at exactly the risk-projected cash
    ec = compute_fill_economics("BUY", qty, raw, COST)
    fill_final = cash + ec["cash_delta"]
    assert fill_final < 0  # the real fill would go negative here
    # risk must therefore REJECT (it uses the same economics, no divergence)
    assert dec.passed is False
    assert "cash_check" in {v.rule for v in dec.violations}