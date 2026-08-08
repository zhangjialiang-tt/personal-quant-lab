"""Shared fill economics (review P1-1 / D3).

ONE frozen cost formula, used by all three consumers so a risk dry-run, a paper
fill (mutation) and an independent reconciliation can never disagree:

  BUY  fill_price = raw * (1 + slippage)
       gross      = qty * fill_price
       fee        = gross * fee_rate
       stamp      = 0
       slippage_cost = |fill_price - raw| * qty = qty * raw * slippage
       cash_delta   = -(gross + fee)

  SELL fill_price = raw * (1 - slippage)
       gross      = qty * fill_price
       fee        = gross * fee_rate
       stamp      = gross * stamp_duty
       slippage_cost = |fill_price - raw| * qty = qty * raw * slippage
       cash_delta   = +(gross - fee - stamp)

`slippage_cost` is the absolute price impact (|fill - raw| * qty), NOT
`gross * slippage` (which double-counts slippage because gross already embeds
it). Reconcile re-derives cash_delta from this same function and compares to
the recorded value, so a tampered order ledger is caught.
"""
from __future__ import annotations

from typing import Any

from pql.schemas import CostModel


def compute_fill_economics(
    side: str,
    quantity: float,
    raw_price: float,
    cost: CostModel,
) -> dict[str, Any]:
    """Return the complete fill economics for one order (side BUY/SELL).
    `quantity` is the unsigned trade size. Callers apply the signed cash_delta
    to their account."""
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")
    qty = abs(quantity)
    if side == "BUY":
        fill_price = raw_price * (1 + cost.slippage)
    else:
        fill_price = raw_price * (1 - cost.slippage)
    gross = qty * fill_price
    fee = gross * cost.fee_rate
    stamp = gross * cost.stamp_duty if side == "SELL" else 0.0
    slippage_cost = abs(fill_price - raw_price) * qty
    if side == "BUY":
        cash_delta = -(gross + fee)
    else:
        cash_delta = +(gross - fee - stamp)
    return {
        "fill_price": fill_price,
        "gross_notional": gross,
        "fee": fee,
        "stamp": stamp,
        "slippage_cost": slippage_cost,
        "cash_delta": cash_delta,
    }


__all__ = ["compute_fill_economics"]