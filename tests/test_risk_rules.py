"""M7.61 risk rules tests: every rule has at least one REJECT counterexample and
there is at least one all-rules PASS legal batch. KILL_SWITCH stops before any
order generation / account mutation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pql.risk.rules import (
    KillSwitchActive,
    RiskContext,
    RiskDecision,
    RiskError,
    RiskOrder,
    check_kill_switch,
    evaluate_batch,
    load_instruments,
    load_risk_config,
)

DAYS = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"])
_COST = __import__("pql.schemas", fromlist=["CostModel"]).CostModel(
    version="cn-etf-cost-2026-v1", fee_rate=0.0003, stamp_duty=0.0, slippage=0.001)

SYM = "510300.SH"
INSTRUMENTS = {SYM: {"symbol": SYM, "lot_size": 100, "listed_date": "2020-01-01"}}


def _risk_config(**over):
    cfg = {"version": "risk-2026-v1", "max_position_weight": 0.6,
           "max_portfolio_exposure": 1.0, "max_turnover_per_rebalance": 2.0,
           "max_order_value": 100000}
    cfg.update(over)
    return cfg


def _ctx(*, positions=None, cash=100_000.0, equity=None, execution_date="2026-01-06",
         price=100.0, price_date="2026-01-06", risk_config=None, instruments=None,
         existing_orders=None):
    positions = positions or {}
    equity = equity if equity is not None else cash + sum(
        q * price for q in positions.values())
    return RiskContext(
        risk_config=risk_config or _risk_config(),
        instruments=instruments if instruments is not None else dict(INSTRUMENTS),
        calendar_dates=frozenset(DAYS),
        expected_completed_bar=pd.Timestamp("2026-01-06"),
        execution_date=execution_date,
        cash=cash,
        equity=equity,
        positions=dict(positions),
        valuation_price={SYM: price},
        execution_price={SYM: price},
        price_date={SYM: price_date},
        cost=_COST,
        lot_size={SYM: 100},
        existing_orders=list(existing_orders or []),
    )


def _order(symbol=SYM, side="BUY", qty=100.0, price=100.0, eid="o1", date="2026-01-06"):
    q = abs(qty) if side in ("BUY", "SELL") else 0.0
    signed = q if side == "BUY" else (-q if side == "SELL" else 0.0)
    return RiskOrder(order_id=eid, execution_date=date, symbol=symbol, side=side,
                     quantity=signed, execution_price=price, notional=q * price)


def _violated_rules(decision: RiskDecision) -> set[str]:
    return {v.rule for v in decision.violations}


def test_load_risk_config_from_file():
    cfg = load_risk_config(".")
    assert cfg["version"] == "risk-2026-v1"
    assert cfg["max_position_weight"] == 0.6
    assert cfg["max_order_value"] == 100000


def test_load_instruments_canonical():
    inst = load_instruments(".")
    assert "510300.SH" in inst
    assert inst["510300.SH"]["lot_size"] == 100


def test_all_rules_pass():
    # a legal single BUY well within every limit
    ctx = _ctx()
    dec = evaluate_batch([_order(qty=100)], ctx)
    assert dec.passed is True
    assert dec.violations == []
    assert dec.rejected_order_ids == []


def test_max_position_weight_reject():
    # projected weight after buying 800 shares @100 = 80000/100000 = 0.8 > 0.6
    ctx = _ctx(cash=100_000.0)
    dec = evaluate_batch([_order(qty=800, price=100.0)], ctx)
    assert "max_position_weight" in _violated_rules(dec)
    assert dec.passed is False


def test_max_position_weight_edge_pass():
    ctx = _ctx(cash=100_000.0)
    dec = evaluate_batch([_order(qty=500, price=100.0)], ctx)  # 0.5 <= 0.6
    assert dec.passed is True


def test_max_portfolio_exposure_reject():
    # projected: A grows to 60000 + 50000 = 110000, cash goes negative -> exposure
    # is defined on projected positions over projected equity; supply a context
    # where projected cash would be negative (long-only exposure > 1.0 requires
    # it, which is exactly what cash_check forbids). Assert exposure rule fires.
    ctx = _ctx(positions={SYM: 60000.0}, cash=0.0, equity=60000.0)
    dec = evaluate_batch([_order(qty=50000, price=1.0)], ctx)
    assert "max_portfolio_exposure" in _violated_rules(dec)


def test_max_turnover_reject():
    # sell 100% + buy 100% -> turnover = 2.0; exceed with 110% -> 2.2 > 2.0
    ctx = _ctx(positions={SYM: 100000.0}, cash=0.0, equity=100000.0)
    # SELL 100000 + BUY 50000 (500% of a 100k base would be too much; use 2.2x)
    orders = [_order(side="SELL", qty=100000, price=1.0, eid="s1"),
              _order(side="BUY", qty=120000, price=1.0, eid="b1")]
    dec = evaluate_batch(orders, ctx)
    # turnover = (100000 + 120000)/100000 = 2.2 > 2.0
    assert "max_turnover_per_rebalance" in _violated_rules(dec)


def test_max_order_value_reject():
    ctx = _ctx()
    dec = evaluate_batch([_order(qty=1500, price=100.0)], ctx)  # 150000 > 100000
    assert "max_order_value" in _violated_rules(dec)
    assert dec.passed is False


def test_cash_check_reject():
    # BUY 120% of cash -> projected cash negative
    ctx = _ctx(cash=100_000.0)
    dec = evaluate_batch([_order(qty=120000, price=1.0)], ctx)
    assert "cash_check" in _violated_rules(dec)


def test_stale_price_reject():
    # price_date (2026-01-05) < expected completed bar (2026-01-06)
    ctx = _ctx(price_date="2026-01-05")
    dec = evaluate_batch([_order()], ctx)
    assert "stale_price_check" in _violated_rules(dec)


def test_stale_price_not_stale_when_equal():
    ctx = _ctx(price_date="2026-01-06")  # == expected bar
    dec = evaluate_batch([_order()], ctx)
    assert "stale_price_check" not in _violated_rules(dec)


def test_duplicate_order_reject():
    ctx = _ctx()
    orders = [_order(eid="o1"), _order(eid="o2")]  # same date/symbol/direction
    dec = evaluate_batch(orders, ctx)
    assert "duplicate_order_check" in _violated_rules(dec)


def test_duplicate_against_ledger_reject():
    ctx = _ctx(existing_orders=[{"order_id": "led1", "execution_date": "2026-01-06",
                                 "symbol": SYM, "side": "BUY"}])
    dec = evaluate_batch([_order(eid="o1")], ctx)
    assert "duplicate_order_check" in _violated_rules(dec)


def test_hold_not_duplicate():
    ctx = _ctx()
    dec = evaluate_batch([_order(eid="h1", side="HOLD", qty=0)], ctx)
    assert "duplicate_order_check" not in _violated_rules(dec)


def test_invalid_symbol_reject():
    ctx = _ctx()
    dec = evaluate_batch([_order(symbol="999999.XX")], ctx)
    assert "invalid_symbol_check" in _violated_rules(dec)


def test_tradability_reject():
    # listed_date 2020-01-01, execution 2026-01-06 -> fine; craft a listed_date
    # in the future to force rejection
    inst = {SYM: {"symbol": SYM, "lot_size": 100, "listed_date": "2027-01-01"}}
    ctx = _ctx(instruments=inst)
    dec = evaluate_batch([_order()], ctx)
    assert "tradability_check" in _violated_rules(dec)


def test_kill_switch_raises(tmp_path):
    root = Path(tmp_path)
    assert check_kill_switch(root) is None  # no KILL_SWITCH -> no-op
    (root / "KILL_SWITCH").write_text("", encoding="utf-8")
    with pytest.raises(KillSwitchActive):
        check_kill_switch(root)


def test_load_risk_config_missing_section(tmp_path):
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "config" / "validation_gates.yaml").write_text(
        "version: gates-2026-v1\ncandidate: {}\n", encoding="utf-8")
    with pytest.raises(RiskError):
        load_risk_config(tmp_path)