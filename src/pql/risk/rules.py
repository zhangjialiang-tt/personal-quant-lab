"""M7.1 Risk Rules (plan §17).

Order-level risk policy, all thresholds config-driven from
`config/validation_gates.yaml` -> `risk` section (PLAN_CLARIFICATION M7-002:
added additively; historical M6 gate hashes are untouched).

Rules:
  max_position_weight         projected position value / projected equity <= 0.6
  max_portfolio_exposure      sum_abs(projected positions) / projected equity <= 1.0
  max_turnover_per_rebalance  sum_abs(order_notional) / pre_trade_equity <= 2.0
  max_order_value             abs(order_notional) <= max_order_value (CNY)
  cash_check                  projected cash never negative (BUY consumes gross+fee,
                              SELL releases gross-fee-stamp; deterministic SELL-first
                              then BUY, within each side canonical symbol order)
  stale_price_check           price_date < latest_expected_completed_bar -> reject
  duplicate_order_check       same execution_date + same canonical symbol + same
                              direction (within batch + today's paper ledger)
  invalid_symbol_check        symbol must resolve to canonical and exist in instruments
  tradability_check           execution_date >= instrument.listed_date

Every rejection is recorded as a RiskViolation (rule/symbol/date/reason/actual/
limit) so the result is auditable, never a bare `False`. Order generation /
execution / account mutation MUST stop first if a KILL_SWITCH file exists at the
repo root (KillSwitchActive; CLI exit code 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from pql.data.symbols import SymbolError, resolve_symbol
from pql.schemas import CostModel
from pql.timing import TimingError


class KillSwitchActive(RuntimeError):
    """Order generation/execution must STOP (KILL_SWITCH file present)."""


class RiskError(RuntimeError):
    """Raised for risk-policy configuration / input errors that are not a
    normal order rejection."""


@dataclass(frozen=True)
class RiskViolation:
    rule: str
    symbol: str
    date: str
    reason: str
    actual: float | None = None
    limit: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "symbol": self.symbol,
            "date": self.date,
            "reason": self.reason,
            "actual": self.actual,
            "limit": self.limit,
        }


@dataclass
class RiskDecision:
    """Outcome of a risk evaluation over an order batch. `passed` is True only
    when there are no violations. `rejected_order_ids` lists the orders that
    triggered at least one violation (so the paper engine can skip exactly those
    without executing them)."""
    passed: bool
    violations: list[RiskViolation] = field(default_factory=list)
    rejected_order_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "rejected_order_ids": self.rejected_order_ids,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class RiskOrder:
    """A minimal, execution-oriented order view consumed by the risk rules.
    Filled by the Order Generation layer (execution/orders.py)."""
    order_id: str
    execution_date: str
    symbol: str
    side: str            # BUY | SELL | HOLD
    quantity: float      # signed adjust quantity (BUY>0, SELL<0, HOLD=0)
    execution_price: float
    notional: float      # abs(quantity) * execution_price


@dataclass(frozen=True)
class RiskContext:
    """All inputs the risk rules need. `price_date` maps each symbol to the
    actual date of the price used for execution (stale check). `existing_orders`
    is today's already-executed paper order ledger (duplicate check)."""
    risk_config: dict[str, Any]
    instruments: dict[str, dict[str, Any]]
    calendar_dates: frozenset[pd.Timestamp]
    expected_completed_bar: pd.Timestamp
    execution_date: str
    cash: float
    equity: float                       # pre-trade equity (cash + positions@val)
    positions: dict[str, float]         # symbol -> quantity
    valuation_price: dict[str, float]   # symbol -> valuation price (raw close)
    execution_price: dict[str, float]   # symbol -> raw execution price
    price_date: dict[str, str]          # symbol -> actual price date
    cost: CostModel
    lot_size: dict[str, int]            # symbol -> lot
    existing_orders: list[dict[str, Any]] = field(default_factory=list)


def check_kill_switch(repo_root: str | Path) -> None:
    """Order generation / execution MUST stop if a KILL_SWITCH file exists at
    the repo root. Raised BEFORE any order is generated or account state is
    mutated (M7.21)."""
    if (Path(repo_root) / "KILL_SWITCH").exists():
        raise KillSwitchActive(
            "KILL_SWITCH present at repo root; order generation/execution stopped"
        )


def _threshold(ctx: RiskContext, key: str, default: float) -> float:
    val = ctx.risk_config.get(key, default)
    if val is None:
        val = default
    return float(val)


def _canonical(symbol: str) -> str:
    try:
        return resolve_symbol(symbol)
    except SymbolError:
        return symbol  # reported by invalid_symbol_check


def _gross_notional(qty: float, price: float) -> float:
    return abs(qty) * price


def _projected(ctx: RiskContext, orders: list[RiskOrder]) -> tuple[dict[str, float], float]:
    """Deterministically apply a batch of orders to the current positions/cash:

      - SELL orders first (release cash), then BUY orders (consume cash);
      - within each side, canonical symbol ascending order;
      - BUY fill at raw*(1+slippage), fee=gross*fee_rate, cash -= gross+fee;
      - SELL fill at raw*(1-slippage), fee=gross*fee_rate, stamp=gross*stamp_duty,
        cash += gross-fee-stamp.

    Returns (projected_positions, projected_cash). Does NOT mutate the context.
    """
    sells = sorted(
        (o for o in orders if o.side == "SELL"),
        key=lambda o: (_canonical(o.symbol), o.order_id),
    )
    buys = sorted(
        (o for o in orders if o.side == "BUY"),
        key=lambda o: (_canonical(o.symbol), o.order_id),
    )
    pos: dict[str, float] = dict(ctx.positions)
    cash = ctx.cash
    for o in sells:
        sym = _canonical(o.symbol)
        raw = o.execution_price
        gross = abs(o.quantity) * raw
        fill = gross * (1 - ctx.cost.slippage)
        fee = gross * ctx.cost.fee_rate
        stamp = gross * ctx.cost.stamp_duty
        cash += fill - fee - stamp
        pos[sym] = pos.get(sym, 0.0) - abs(o.quantity)
    for o in buys:
        sym = _canonical(o.symbol)
        raw = o.execution_price
        gross = abs(o.quantity) * raw
        fill = gross * (1 + ctx.cost.slippage)
        fee = gross * ctx.cost.fee_rate
        cash -= fill + fee
        pos[sym] = pos.get(sym, 0.0) + abs(o.quantity)
    return pos, cash


def _projected_equity(ctx: RiskContext, pos: dict[str, float], cash: float) -> float:
    val = cash
    for sym, qty in pos.items():
        val += qty * ctx.valuation_price.get(sym, 0.0)
    if val <= 0:
        return 0.0
    return val


def _rule_invalid_symbol(orders, ctx) -> list[RiskViolation]:
    out = []
    for o in orders:
        try:
            sym = resolve_symbol(o.symbol)
        except SymbolError as exc:
            out.append(RiskViolation(
                "invalid_symbol_check", o.symbol, o.execution_date,
                f"symbol does not resolve to canonical form: {exc}", None, None))
            continue
        if sym not in ctx.instruments:
            out.append(RiskViolation(
                "invalid_symbol_check", sym, o.execution_date,
                "symbol not present in instruments config", None, None))
    return out


def _rule_tradability(orders, ctx) -> list[RiskViolation]:
    out = []
    for o in orders:
        sym = _canonical(o.symbol)
        inst = ctx.instruments.get(sym)
        if inst is None:
            continue  # reported by invalid_symbol_check
        listed = inst.get("listed_date")
        if listed is None:
            continue
        if pd.Timestamp(o.execution_date).normalize() < pd.Timestamp(listed).normalize():
            out.append(RiskViolation(
                "tradability_check", sym, o.execution_date,
                f"execution_date < listed_date ({listed})", o.execution_date, listed))
    return out


def _rule_stale_price(orders, ctx) -> list[RiskViolation]:
    out = []
    for o in orders:
        pdate = ctx.price_date.get(_canonical(o.symbol))
        if pdate is None:
            out.append(RiskViolation(
                "stale_price_check", _canonical(o.symbol), o.execution_date,
                "no price date available for execution", None, None))
            continue
        if pd.Timestamp(pdate).normalize() < ctx.expected_completed_bar.normalize():
            out.append(RiskViolation(
                "stale_price_check", _canonical(o.symbol), o.execution_date,
                f"price_date {pdate} < latest_expected_completed_bar "
                f"{ctx.expected_completed_bar.date()}", pdate,
                str(ctx.expected_completed_bar.date())))
    return out


def _rule_duplicate(orders, ctx) -> list[RiskViolation]:
    seen: dict[tuple[str, str, str], str] = {}
    out = []
    def _check(o):
        if o.side == "HOLD":
            return
        sym = _canonical(o.symbol)
        key = (o.execution_date, sym, o.side)
        if key in seen:
            out.append(RiskViolation(
                "duplicate_order_check", sym, o.execution_date,
                f"duplicate executable order (same date/symbol/direction); "
                f"first order_id={seen[key]}", None, None))
        else:
            seen[key] = o.order_id
    for o in orders:
        _check(o)
    for rec in ctx.existing_orders:
        side = rec.get("side")
        if side == "HOLD":
            continue
        sym = _canonical(rec.get("symbol", ""))
        key = (rec.get("execution_date") or rec.get("date", ""), sym, side)
        if key in seen:
            out.append(RiskViolation(
                "duplicate_order_check", sym, rec.get("execution_date", ""),
                f"duplicate versus paper ledger (same date/symbol/direction); "
                f"ledger order_id={rec.get('order_id')}", None, None))
        else:
            seen[key] = str(rec.get("order_id"))
    return out


def _rule_max_order_value(orders, ctx) -> list[RiskViolation]:
    limit = _threshold(ctx, "max_order_value", 100_000)
    out = []
    for o in orders:
        if o.side == "HOLD":
            continue
        if o.notional > limit:
            out.append(RiskViolation(
                "max_order_value", _canonical(o.symbol), o.execution_date,
                f"order notional {o.notional:.2f} exceeds {limit:.2f} CNY",
                o.notional, limit))
    return out


def _rule_cash(orders, ctx) -> list[RiskViolation]:
    """BUY must not push projected cash negative (gross + fee). SELLs already
    released cash first (deterministic order). Reject the BUY that would go
    negative."""
    out = []
    _, cash = _projected(ctx, orders)
    if cash < -1e-6:
        # attribute to the last BUY that caused the shortfall
        buys = sorted(
            (o for o in orders if o.side == "BUY"),
            key=lambda o: (_canonical(o.symbol), o.order_id),
        )
        culprit = buys[-1] if buys else None
        sym = _canonical(culprit.symbol) if culprit else ""
        out.append(RiskViolation(
            "cash_check", sym, ctx.execution_date,
            f"projected cash {cash:.2f} < 0 after batch (gross+fee, SELL-first)",
            cash, 0.0))
    return out


def _rule_max_position_weight(orders, ctx) -> list[RiskViolation]:
    limit = _threshold(ctx, "max_position_weight", 0.6)
    pos, cash = _projected(ctx, orders)
    eq = _projected_equity(ctx, pos, cash)
    out = []
    if eq <= 0:
        return out
    for sym, qty in pos.items():
        val = qty * ctx.valuation_price.get(sym, 0.0)
        w = val / eq
        if w > limit + 1e-9:
            out.append(RiskViolation(
                "max_position_weight", sym, ctx.execution_date,
                f"projected position weight {w:.4f} exceeds {limit}",
                w, limit))
    return out


def _rule_max_portfolio_exposure(orders, ctx) -> list[RiskViolation]:
    limit = _threshold(ctx, "max_portfolio_exposure", 1.0)
    pos, cash = _projected(ctx, orders)
    eq = _projected_equity(ctx, pos, cash)
    if eq <= 0:
        return [RiskViolation(
            "max_portfolio_exposure", "", ctx.execution_date,
            "projected equity <= 0", eq, limit)]
    gross = sum(abs(qty) * ctx.valuation_price.get(sym, 0.0) for sym, qty in pos.items())
    expo = gross / eq
    if expo > limit + 1e-9:
        return [RiskViolation(
            "max_portfolio_exposure", "", ctx.execution_date,
            f"long gross exposure {expo:.4f} exceeds {limit}", expo, limit)]
    return []


def _rule_max_turnover(orders, ctx) -> list[RiskViolation]:
    limit = _threshold(ctx, "max_turnover_per_rebalance", 2.0)
    pre = ctx.equity
    if pre <= 0:
        return []
    total = sum(o.notional for o in orders if o.side in ("BUY", "SELL"))
    turnover = total / pre
    if turnover > limit + 1e-9:
        return [RiskViolation(
            "max_turnover_per_rebalance", "", ctx.execution_date,
            f"rebalance turnover {turnover:.4f} exceeds {limit} "
            f"(denominator = pre_trade_equity, PLAN_CLARIFICATION M7-003)",
            turnover, limit)]
    return []


_RULES = [
    ("invalid_symbol_check", _rule_invalid_symbol),
    ("tradability_check", _rule_tradability),
    ("stale_price_check", _rule_stale_price),
    ("duplicate_order_check", _rule_duplicate),
    ("max_order_value", _rule_max_order_value),
    ("max_position_weight", _rule_max_position_weight),
    ("max_portfolio_exposure", _rule_max_portfolio_exposure),
    ("max_turnover_per_rebalance", _rule_max_turnover),
    ("cash_check", _rule_cash),
]

_RULE_NAMES = tuple(name for name, _ in _RULES)


def evaluate_batch(orders: list[RiskOrder], ctx: RiskContext) -> RiskDecision:
    """Run every risk rule over the order batch. HOLD orders are checked for
    symbol/tradability/stale only; they never consume cash, change positions or
    turnover (M7.28). Returns an auditable RiskDecision (never a bare bool)."""
    violations: list[RiskViolation] = []
    rejected: list[str] = []
    for name, fn in _RULES:
        try:
            res = fn(orders, ctx)
        except (SymbolError, TimingError) as exc:
            raise RiskError(f"risk rule {name} failed to evaluate: {exc}") from exc
        if not isinstance(res, list):
            raise RiskError(f"risk rule {name} must return a list of violations")
        violations.extend(res)
    # an order is rejected when any violation references its symbol on its
    # execution date (symbol-agnostic violations like turnover/exposure reject
    # every executable order in the batch).
    rejected = sorted({
        o.order_id for o in orders
        if o.side in ("BUY", "SELL")
        and any(
            (v.symbol in ("", _canonical(o.symbol)) and v.date == o.execution_date)
            for v in violations
        )
    })
    return RiskDecision(
        passed=not violations,
        violations=violations,
        rejected_order_ids=rejected,
    )


def load_risk_config(repo_root: str | Path) -> dict[str, Any]:
    """Load the `risk` section from config/validation_gates.yaml (config-driven
    thresholds; never hardcoded in the rules)."""
    import yaml

    path = Path(repo_root) / "config" / "validation_gates.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    risk = dict(data.get("risk") or {})
    if not risk:
        raise RiskError("validation_gates.yaml has no `risk:` section")
    return risk


def load_instruments(repo_root: str | Path) -> dict[str, dict[str, Any]]:
    """Load all instrument configs keyed by canonical symbol."""
    import yaml

    base = Path(repo_root) / "config" / "instruments"
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        sym = resolve_symbol(data.get("symbol", p.stem))
        inst = dict(data)
        inst["symbol"] = sym
        inst["lot_size"] = int(inst.get("lot_size", 100))
        out[sym] = inst
    return out


__all__ = [
    "KillSwitchActive",
    "RiskContext",
    "RiskDecision",
    "RiskError",
    "RiskOrder",
    "RiskViolation",
    "check_kill_switch",
    "evaluate_batch",
    "load_instruments",
    "load_risk_config",
]