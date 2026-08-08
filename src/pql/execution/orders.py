"""M7.3 Order Generation (plan §M7.3 / §19).

Transforms current positions + cash + TargetPortfolio into a deterministic
order list (BUY/SELL/HOLD) with lot-size rounding:

    BUY   floor toward zero (never round up past target / cash)
    SELL  floor magnitude (always a legal lot)
    HOLD  adjust == 0 -> informational only (no cash/position/turnover change)

Orders are emitted SELL-first then BUY, each side in canonical symbol order
(M7.15), so a rebalance's cash projection is independent of iteration order.

Target quantity is sized from the target weight against the CURRENT portfolio
equity (cash + positions at valuation price), then floored to lots.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pql.portfolio.target import TargetPortfolio
from pql.risk.rules import RiskOrder

# number of orders counter for deterministic order_id
_index = [0]


def _next_index() -> int:
    _index[0] += 1
    return _index[0]


def reset_order_counter() -> None:
    _index[0] = 0


@dataclass
class Order:
    order_id: str
    decision_date: str
    execution_date: str
    symbol: str
    side: str                          # BUY | SELL | HOLD
    target_weight: float
    current_quantity: float
    target_quantity: float
    adjust_quantity: float
    lot_size: int
    valuation_price: float | None
    expected_execution_price: float | None
    reason: str
    risk_warnings: list[str] = field(default_factory=list)
    status: str = "PENDING"            # PENDING | EXECUTED | REJECTED | NO_FILL
    # fill fields appended after execution (for independent reconciliation)
    fill_price: float | None = None
    gross_notional: float | None = None
    fee: float | None = None
    slippage_cost: float | None = None
    cash_delta: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "decision_date": self.decision_date,
            "execution_date": self.execution_date,
            "symbol": self.symbol,
            "side": self.side,
            "target_weight": self.target_weight,
            "current_quantity": self.current_quantity,
            "target_quantity": self.target_quantity,
            "adjust_quantity": self.adjust_quantity,
            "lot_size": self.lot_size,
            "valuation_price": self.valuation_price,
            "expected_execution_price": self.expected_execution_price,
            "reason": self.reason,
            "risk_warnings": list(self.risk_warnings),
            "status": self.status,
            "fill_price": self.fill_price,
            "gross_notional": self.gross_notional,
            "fee": self.fee,
            "slippage_cost": self.slippage_cost,
            "cash_delta": self.cash_delta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Order:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def lot_round_quantity(raw_qty: float, lot_size: int) -> float:
    """Floor toward zero to a legal lot (lot_size shares). raw 1050, lot 100 ->
    1000. Negative raw (SELL magnitude) floors toward zero too."""
    if lot_size <= 0:
        raise ValueError(f"lot_size must be > 0, got {lot_size}")
    whole = int(abs(raw_qty) // lot_size) * lot_size
    return float(whole * (1 if raw_qty >= 0 else -1))


def generate_orders(
    *,
    decision_date: str,
    execution_date: str,
    current_positions: dict[str, float],
    cash: float,
    target: TargetPortfolio,
    valuation_prices: dict[str, float],
    execution_prices: dict[str, float],
    instruments: dict[str, dict[str, Any]],
    lot_size: dict[str, int] | None = None,
    reason_prefix: str = "rebalance",
) -> list[Order]:
    """Generate the order list for a decision targeting `target` on
    `execution_date`. Returns SELL-first, BUY-second, canonical-symbol-ordered
    (HOLD orders appended last; they never mutate account state)."""
    total_equity = cash + sum(
        qty * valuation_prices.get(sym, 0.0) for sym, qty in current_positions.items()
    )
    if total_equity <= 0:
        total_equity = cash

    universe = sorted(set(list(current_positions.keys()) + list(target.weights.keys())))
    orders: list[Order] = []
    for sym in universe:
        inst = instruments.get(sym) or {}
        lot = lot_size.get(sym) if lot_size else None
        if lot is None:
            lot = int(inst.get("lot_size", 100))
        w = target.weights.get(sym, 0.0)
        val = valuation_prices.get(sym)
        if val is None or val <= 0:
            # cannot size without a valuation price -> skip (paper engine logs
            # missing price / cannot fill)
            continue
        target_value = w * total_equity
        target_qty = lot_round_quantity(target_value / val, lot)
        current_qty = float(current_positions.get(sym, 0.0))
        adjust = target_qty - current_qty
        if abs(adjust) < 1e-9:
            side = "HOLD"
            adj = 0.0
        elif adjust > 0:
            side = "BUY"
            adj = lot_round_quantity(adjust, lot)
        else:
            side = "SELL"
            adj = -lot_round_quantity(abs(adjust), lot)
        orders.append(Order(
            order_id=f"{execution_date}-{sym}-{side}-{_next_index()}",
            decision_date=decision_date,
            execution_date=execution_date,
            symbol=sym,
            side=side,
            target_weight=float(w),
            current_quantity=current_qty,
            target_quantity=target_qty,
            adjust_quantity=float(adj),
            lot_size=lot,
            valuation_price=float(val),
            expected_execution_price=execution_prices.get(sym),
            reason=f"{reason_prefix}: target_weight={w}",
        ))

    # deterministic order: SELL first, BUY second, each side canonical symbol;
    # HOLD appended last (no mutation).
    def _key(o: Order):
        rank = {"SELL": 0, "BUY": 1, "HOLD": 2}[o.side]
        return (rank, o.symbol, o.order_id)

    return sorted(orders, key=_key)


def to_risk_order(order: Order, execution_price: float | None = None) -> RiskOrder:
    """Convert a generated Order to the risk-rule view. HOLD notional 0."""
    price = execution_price if execution_price is not None else order.expected_execution_price
    price = price if price is not None else 0.0
    notional = abs(order.adjust_quantity) * price
    return RiskOrder(
        order_id=order.order_id,
        execution_date=order.execution_date,
        symbol=order.symbol,
        side=order.side,
        quantity=order.adjust_quantity,
        execution_price=price,
        notional=notional,
    )


__all__ = [
    "Order",
    "generate_orders",
    "lot_round_quantity",
    "reset_order_counter",
    "to_risk_order",
]