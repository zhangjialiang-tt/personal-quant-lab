"""M7.5 Independent Reconciliation (plan §M7.5 / M7.40-42).

Does NOT trust the PaperAccount's persisted positions/cash. It reconstructs the
expected state from first principles:

    initial_cash
    + executed order ledger (fill prices, fees, cash_delta)

and compares against the persisted state. Any mismatch raises `unreconciled`.
Per-order cash_delta is independently re-derived from fill_price/quantity/fee
(so a tampered ledger is also caught), and structural invariants are enforced:
negative position impossible, order lot conformity, order date ordering.

This is NOT `read positions then compare to positions`.
"""
from __future__ import annotations

from typing import Any

from pql.schemas import CostModel


class ReconcileError(RuntimeError):
    """Raised when reconciliation cannot be performed (bad ledger, ...)."""


def _recompute_cash_delta(order: dict, cost: CostModel, lot_size: int) -> float:
    """Independently re-derive the cash_delta a fill SHOULD have produced from
    its recorded fill_price / quantity / fee. A mismatch with the recorded
    cash_delta means the ledger was tampered."""
    side = order.get("side")
    qty = abs(float(order.get("adjust_quantity", 0.0)))
    fill = float(order.get("fill_price", 0.0)) if order.get("fill_price") is not None else 0.0
    gross = qty * fill  # fill_price already includes slippage
    fee = float(order.get("fee", 0.0)) if order.get("fee") is not None else gross * cost.fee_rate
    if side == "BUY":
        return -(gross + fee)
    stamp = gross * cost.stamp_duty
    return +(gross - fee - stamp)


def reconcile(
    account,
    *,
    cost: CostModel,
    instruments: dict[str, dict[str, Any]] | None = None,
    init_cash: float | None = None,
) -> dict[str, Any]:
    """Reconstruct expected positions/cash from the executed order ledger and
    compare against the PaperAccount's persisted state. Returns a report with
    per-symbol mismatches and an `unreconciled` count (0 when clean)."""
    orders = account.executed_orders()
    if init_cash is None:
        init_cash = account.init_cash
    instruments = instruments or {}

    # strict date-ordered replay of the ledger
    orders_sorted = sorted(
        orders, key=lambda o: (str(o.get("execution_date", "")), str(o.get("order_id", ""))))
    expected_positions: dict[str, float] = {}
    expected_cash = float(init_cash)
    order_issues: list[dict[str, Any]] = []
    prev_date = ""
    for o in orders_sorted:
        sym = o.get("symbol", "")
        date = str(o.get("execution_date", ""))
        # order date ordering invariant
        if prev_date and str(prev_date) > date:
            order_issues.append({"type": "order_date_ordering", "symbol": sym,
                                 "message": f"execution_date {date} < prior {prev_date}"})
        prev_date = date
        side = o.get("side")
        if side == "HOLD":
            order_issues.append({"type": "hold_in_ledger", "symbol": sym,
                                 "message": "HOLD must not enter the executed ledger"})
            continue
        qty = abs(float(o.get("adjust_quantity", 0.0)))
        lot = int(instruments.get(sym, {}).get("lot_size", 100))
        if lot > 0 and abs(int(qty) % lot) != 0:
            order_issues.append({"type": "lot_conformity", "symbol": sym,
                                 "message": f"quantity {qty} not a multiple of lot {lot}"})
        # derive cash_delta independently from the recorded fill
        derived = _recompute_cash_delta(o, cost, lot)
        recorded = o.get("cash_delta")
        if recorded is None or abs(derived - float(recorded)) > 1e-6:
            order_issues.append({"type": "cash_delta_mismatch", "symbol": sym,
                                 "message": f"derived {derived:.4f} != recorded {recorded}"})
        cash_delta = float(recorded) if recorded is not None else derived
        sign = +1 if side == "BUY" else -1
        expected_positions[sym] = expected_positions.get(sym, 0.0) + sign * qty
        expected_cash += cash_delta

    # negative position impossible invariant
    for sym, q in expected_positions.items():
        if q < -1e-6:
            order_issues.append({"type": "negative_position", "symbol": sym,
                                 "message": f"expected position {q} < 0"})

    actual_positions = account.current_positions()
    actual_cash = account.current_cash()

    mismatches: list[dict[str, Any]] = []
    for sym in sorted(set(list(expected_positions) + list(actual_positions))):
        exp = expected_positions.get(sym, 0.0)
        act = actual_positions.get(sym, 0.0)
        if abs(exp - act) > 1e-6:
            mismatches.append({"type": "position", "symbol": sym,
                               "expected": exp, "actual": act, "delta": exp - act})
    if abs(expected_cash - actual_cash) > 1e-6:
        mismatches.append({"type": "cash", "symbol": "",
                           "expected": expected_cash, "actual": actual_cash,
                           "delta": expected_cash - actual_cash})

    unreconciled = len(mismatches) + len(order_issues)
    return {
        "unreconciled": unreconciled,
        "expected_cash": expected_cash,
        "actual_cash": actual_cash,
        "cash_mismatch": abs(expected_cash - actual_cash) > 1e-6,
        "expected_positions": expected_positions,
        "actual_positions": actual_positions,
        "position_mismatches": [m for m in mismatches if m["type"] == "position"],
        "order_issues": order_issues,
        "mismatches": mismatches,
    }


__all__ = ["ReconcileError", "reconcile"]