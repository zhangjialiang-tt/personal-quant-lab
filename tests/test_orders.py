"""M7.64 order generation tests: lot rounding, SELL-before-BUY, cash including
fees/slippage, target/current/adjust quantity, HOLD zero mutation, deterministic
symbol ordering, risk rejection."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.execution.orders import (
    Order,
    generate_orders,
    lot_round_quantity,
    reset_order_counter,
    to_risk_order,
)
from pql.portfolio.target import TargetPortfolio
from pql.risk.rules import RiskContext, evaluate_batch


def _reset():
    reset_order_counter()


def _instruments():
    return {s: {"symbol": s, "lot_size": 100, "listed_date": "2020-01-01"}
            for s in ("510300.SH", "510500.SH")}


def _target(weights):
    return TargetPortfolio(date="2026-01-05", weights=weights,
                           cash_weight=1 - sum(weights.values()))


def test_lot_round_quantity():
    assert lot_round_quantity(1050.0, 100) == 1000.0
    assert lot_round_quantity(1000.0, 100) == 1000.0
    assert lot_round_quantity(99.0, 100) == 0.0
    assert lot_round_quantity(-1050.0, 100) == -1000.0
    assert lot_round_quantity(1234.0, 100) == 1200.0
    with pytest.raises(ValueError):
        lot_round_quantity(100.0, 0)


def test_target_current_adjust_quantity():
    _reset()
    orders = generate_orders(
        decision_date="2026-01-05", execution_date="2026-01-06",
        current_positions={"510300.SH": 500.0},
        cash=100_000.0, target=_target({"510300.SH": 0.5}),
        valuation_prices={"510300.SH": 100.0},
        execution_prices={"510300.SH": 100.0},
        instruments=_instruments())
    o = orders[0]
    assert o.symbol == "510300.SH"
    assert o.current_quantity == 500.0
    # target = 0.5 * equity(100k + 50k = 150k) = 75k / 100 / 100 -> 750 raw shares,
    # floored to a legal lot -> 700 shares
    assert o.target_quantity == 700.0
    assert o.adjust_quantity == 200.0
    assert o.side == "BUY"
    assert o.lot_size == 100


def test_buy_floor_toward_zero_lot():
    _reset()
    orders = generate_orders(
        decision_date="d", execution_date="e",
        current_positions={}, cash=100_000.0, target=_target({"510300.SH": 0.5}),
        valuation_prices={"510300.SH": 130.0},
        execution_prices={"510300.SH": 130.0}, instruments=_instruments())
    o = orders[0]
    # raw target = 50000/130 = 384.6 shares -> floor to 300 shares (never round up)
    assert o.adjust_quantity == 300.0


def test_sell_before_buy_order():
    _reset()
    orders = generate_orders(
        decision_date="d", execution_date="e",
        current_positions={"510300.SH": 800.0, "510500.SH": 0.0},
        cash=100_000.0, target=_target({"510300.SH": 0.2, "510500.SH": 0.3}),
        valuation_prices={"510300.SH": 100.0, "510500.SH": 100.0},
        execution_prices={"510300.SH": 100.0, "510500.SH": 100.0},
        instruments=_instruments())
    sides = [o.side for o in orders]
    assert sides[0] == "SELL"  # 510300.SH reduces (SELL released first)
    assert "BUY" in sides
    sell_idx = sides.index("SELL")
    buy_idx = [i for i, s in enumerate(sides) if s == "BUY"]
    assert all(buy_idx[i] > sell_idx for i in range(len(buy_idx)))


def test_deterministic_symbol_ordering():
    _reset()
    kw = {"decision_date": "d", "execution_date": "e", "current_positions": {},
          "cash": 100_000.0, "target": _target({"510500.SH": 0.4, "510300.SH": 0.4}),
          "valuation_prices": {"510500.SH": 100.0, "510300.SH": 100.0},
          "execution_prices": {"510500.SH": 100.0, "510300.SH": 100.0},
          "instruments": _instruments()}
    a = generate_orders(**kw)
    b = generate_orders(**kw)
    assert [o.symbol for o in a] == [o.symbol for o in b]
    # canonical symbol ascending within BUY side
    buys = [o for o in a if o.side == "BUY"]
    assert [o.symbol for o in buys] == sorted(o.symbol for o in buys)


def test_hold_zero_mutation():
    _reset()
    orders = generate_orders(
        decision_date="d", execution_date="e",
        current_positions={"510300.SH": 500.0},
        cash=100_000.0, target=_target({"510300.SH": 0.5}),
        valuation_prices={"510300.SH": 150.0},  # target = 0.5*150k/150 = 500 = current
        execution_prices={"510300.SH": 150.0}, instruments=_instruments())
    assert orders and orders[0].side == "HOLD"
    # HOLD must not enter executable sim / cash / positions / turnover
    _ = to_risk_order(orders[0])
    assert orders[0].adjust_quantity == 0.0


def test_risk_rejection():
    from pql.schemas import CostModel

    risk_config = {"version": "r", "max_position_weight": 0.6,
                   "max_portfolio_exposure": 1.0,
                   "max_turnover_per_rebalance": 2.0, "max_order_value": 100000}
    cost = CostModel(version="c", fee_rate=0.0003, stamp_duty=0.0, slippage=0.001)
    ctx = RiskContext(
        risk_config=risk_config,
        instruments=_instruments(),
        calendar_dates=frozenset([pd.Timestamp("2026-01-06")]),
        expected_completed_bar=pd.Timestamp("2026-01-06"),
        execution_date="2026-01-06", cash=100_000.0, equity=100_000.0,
        positions={}, valuation_price={"510300.SH": 100.0},
        execution_price={"510300.SH": 100.0}, price_date={"510300.SH": "2026-01-06"},
        cost=cost, lot_size={"510300.SH": 100},
    )
    _reset()
    orders = generate_orders(
        decision_date="2026-01-05", execution_date="2026-01-06",
        current_positions={}, cash=100_000.0, target=_target({"510300.SH": 1.0}),
        valuation_prices={"510300.SH": 100.0},
        execution_prices={"510300.SH": 100.0}, instruments=_instruments())
    # full-investment single BUY of 100% -> projected cash negative after fees
    risk_orders = [to_risk_order(o) for o in orders]
    dec = evaluate_batch(risk_orders, ctx)
    assert dec.passed is False
    assert "cash_check" in {v.rule for v in dec.violations}


def test_order_to_dict_from_dict_roundtrip():
    _reset()
    o = Order(order_id="x", decision_date="d", execution_date="e", symbol="s",
              side="BUY", target_weight=0.5, current_quantity=0.0,
              target_quantity=500.0, adjust_quantity=500.0, lot_size=100,
              valuation_price=100.0, expected_execution_price=100.0, reason="r")
    d = o.to_dict()
    o2 = Order.from_dict(d)
    assert o2.order_id == o.order_id
    assert o2.side == o.side