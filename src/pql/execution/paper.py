"""M7.4 PaperAccount + Paper Replay (plan §M7.4).

`pql paper replay --strategy X --start YYYY-MM-DD --end YYYY-MM-DD` runs a
day-by-day paper execution on the Snapshot calendar:

  T ── read data <= T ── signal/target ── decision at T ── schedule execution at
  T+execution_bar ── on the execution day: Execution Revaluation, generate
  executable orders, Risk Rules, raw execution price, fees/slippage, update
  PaperAccount.

Hard constraints implemented here:
  - T signal -> T fill is ABSOLUTELY FORBIDDEN (fill at T+execution_bar).
  - execution uses RAW open/close (execution_price); adjusted research prices
    are never used for fills.
  - fees/slippage enter CASH immediately (never deducted only at report time).
  - missing raw execution price -> NO FILL (no forward fill / adjusted price /
    prior-day raw price); logged to failures.jsonl and the strategy continues
    deterministically.
  - KILL_SWITCH at repo root stops before ANY order generation / account
    mutation (KillSwitchActive; CLI exit 3).
  - replay overlap is fail-closed: if the account already holds executed state
    at or after the requested start, replay is refused (PLAN_CLARIFICATION
    M7-005) unless a fresh data root is used.

State lands in `data/paper/<strategy>/`: positions.parquet, cash.parquet,
orders.jsonl, events.jsonl, failures.jsonl, equity.parquet, meta.json.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pql.data.dataset import DatasetView
from pql.execution.orders import Order, generate_orders, to_risk_order
from pql.portfolio.target import build_target_portfolio_series, target_for_series_row
from pql.registry.runner import resolve_paths
from pql.risk.rules import (
    RiskContext,
    check_kill_switch,
    evaluate_batch,
    load_instruments,
    load_risk_config,
)
from pql.schemas import PortfolioConfig, load_cost_model, load_spec
from pql.signals.registry import effective_params
from pql.timing import TimingContract, latest_expected_completed_bar


class PaperError(RuntimeError):
    """Raised for paper-account / replay configuration errors."""


class ReplayOverlapError(PaperError):
    """Raised when a replay would overlap already-executed paper state."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class PaperAccount:
    """Persistent paper trading account state under paper_root/<strategy>/."""

    strategy: str
    paper_root: str | Path
    init_cash: float = field(default=1_000_000)

    def __post_init__(self) -> None:
        self.dir = Path(self.paper_root) / self.strategy
        self.dir.mkdir(parents=True, exist_ok=True)
        # a persisted account carries the init_cash it was actually replayed
        # with (meta.json); reconcile/report must reconstruct from that, not a
        # caller-side default that may differ from the replay.
        if self.meta_path.exists():
            try:
                import json as _json

                meta = _json.loads(self.meta_path.read_text(encoding="utf-8"))
                if "init_cash" in meta:
                    self.init_cash = float(meta["init_cash"])
            except (ValueError, OSError, KeyError):
                pass

    # -- paths ---------------------------------------------------------------
    @property
    def positions_path(self): return self.dir / "positions.parquet"
    @property
    def cash_path(self): return self.dir / "cash.parquet"
    @property
    def orders_path(self): return self.dir / "orders.jsonl"
    @property
    def events_path(self): return self.dir / "events.jsonl"
    @property
    def failures_path(self): return self.dir / "failures.jsonl"
    @property
    def equity_path(self): return self.dir / "equity.parquet"
    @property
    def meta_path(self): return self.dir / "meta.json"

    # -- state ---------------------------------------------------------------
    def has_state(self) -> bool:
        return self.orders_path.exists() and self.orders_path.stat().st_size > 0

    def current_positions(self) -> dict[str, float]:
        if not self.positions_path.exists():
            return {}
        df = pd.read_parquet(self.positions_path)
        if df.empty:
            return {}
        last = df["date"].max()
        sub = df[df["date"] == last]
        return {str(r.symbol): float(r.quantity) for r in sub.itertuples()}

    def current_cash(self) -> float:
        if not self.cash_path.exists():
            return self.init_cash
        df = pd.read_parquet(self.cash_path)
        if df.empty:
            return self.init_cash
        return float(df.sort_values("date")["cash"].iloc[-1])

    def executed_orders(self) -> list[dict[str, Any]]:
        if not self.orders_path.exists():
            return []
        return [json.loads(line) for line in
                self.orders_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in
                self.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def read_failures(self) -> list[dict[str, Any]]:
        if not self.failures_path.exists():
            return []
        return [json.loads(line) for line in
                self.failures_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def assert_no_overlap(self, requested_start: str) -> None:
        """Fail-closed (M7-005): refuse a replay whose window overlaps already
        executed paper state. Requires a fresh fixture/data root for re-runs."""
        if not self.has_state():
            return
        start = pd.Timestamp(requested_start).normalize()
        for o in self.executed_orders():
            if pd.Timestamp(o.get("execution_date", "")).normalize() >= start:
                raise ReplayOverlapError(
                    f"paper account for {self.strategy} already has executed state "
                    f"at/after requested start {requested_start} "
                    "(execution_date "
                    f"{o.get('execution_date')}); overlap would double-execute. "
                    "Use a fresh fixture/data root (PLAN_CLARIFICATION M7-005)."
                )

    # -- mutations -----------------------------------------------------------
    def persist(self, date, positions: dict[str, float], cash: float, equity: float) -> None:
        d = pd.Timestamp(date).normalize()
        pos_rows = pd.DataFrame(
            [{"date": d, "symbol": s, "quantity": q} for s, q in positions.items()])
        if self.positions_path.exists():
            old = pd.read_parquet(self.positions_path)
            pos_rows = pd.concat([old, pos_rows], ignore_index=True)
        pos_rows.to_parquet(self.positions_path, index=False)

        cash_rows = pd.DataFrame([{"date": d, "cash": cash}])
        if self.cash_path.exists():
            cash_rows = pd.concat(
                [pd.read_parquet(self.cash_path), cash_rows], ignore_index=True)
        cash_rows.to_parquet(self.cash_path, index=False)

        eq_rows = pd.DataFrame([{"date": d, "equity": equity}])
        if self.equity_path.exists():
            eq_rows = pd.concat(
                [pd.read_parquet(self.equity_path), eq_rows], ignore_index=True)
        eq_rows.to_parquet(self.equity_path, index=False)

        self.write_meta({"last_persisted": str(d.date())})

    def write_meta(self, extra: dict[str, Any] | None = None) -> None:
        meta = {"strategy": self.strategy, "init_cash": self.init_cash}
        if self.meta_path.exists():
            try:
                meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        meta.update(extra or {})
        meta["init_cash"] = self.init_cash
        self.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_order(self, order: Order) -> None:
        with self.orders_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(order.to_dict(), ensure_ascii=False) + "\n")

    def append_event(self, event: dict[str, Any]) -> None:
        event = {"event_id": event.get("event_id", _new_id("evt")),
                 "time": _now(), **event}
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_failure(self, *, date, failure_type, symbol, message, strategy=None) -> str:
        """Record a captured failure to failures.jsonl AND a correlated failure
        event to events.jsonl (same failure_id). A captured failure is NOT a
        silent failure (M7.38)."""
        failure_id = _new_id("fail")
        record = {
            "failure_id": failure_id,
            "date": str(date),
            "type": failure_type,
            "strategy": strategy or self.strategy,
            "symbol": symbol,
            "message": message,
            "captured": True,
        }
        with self.failures_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.append_event({
            "kind": "failure",
            "failure_id": failure_id,
            "date": str(date),
            "type": failure_type,
            "symbol": symbol,
            "message": message,
            "captured": True,
        })
        return failure_id


def _next_trading_day(calendar: list[pd.Timestamp], day, k: int) -> pd.Timestamp | None:
    """The k-th trading day strictly after `day` (k>=1)."""
    idx = [i for i, d in enumerate(calendar) if d > pd.Timestamp(day).normalize()]
    if not idx:
        return None
    first = idx[0]
    j = first + k - 1
    if j >= len(calendar):
        return None
    return calendar[j]


def _execute_orders(
    *,
    account: PaperAccount,
    orders: list[Order],
    day,
    cost,
    instruments: dict,
    risk_config: dict,
    calendar: list[pd.Timestamp],
    positions: dict[str, float],
    cash: float,
    exec_price: dict[str, float | None],
    val_close: dict[str, float],
):
    """Execute a batch of orders scheduled for `day`: build the risk context,
    run every risk rule, fill accepted BUY/SELL, log rejected / missing-price as
    captured failures. Returns (positions, cash, n_sim, decision)."""
    exec_prices = {s: p for s, p in exec_price.items() if p is not None}
    price_dates: dict[str, str] = {s: str(pd.Timestamp(day).date()) for s in exec_prices}
    val_prices = dict(val_close)
    expected_bar = latest_expected_completed_bar(
        calendar, pd.Timestamp(day).normalize().strftime("%Y-%m-%d 15:00"))

    # Missing execution price is a NO-FILL (recorded directly), BEFORE risk: an
    # order with no price is not executable and must not be misreported as a
    # stale-price / other risk rejection (M7.36).
    no_price_ids: set[str] = set()
    for o in orders:
        if o.side != "HOLD" and exec_prices.get(o.symbol) is None:
            no_price_ids.add(o.order_id)
            account.log_failure(
                date=str(pd.Timestamp(day).date()), failure_type="missing_execution_price",
                symbol=o.symbol, strategy=account.strategy,
                message=f"no execution price on {day.date()}")
            o.status = "NO_FILL"

    pre_equity = cash + sum(q * val_prices.get(s, 0.0) for s, q in positions.items())
    ctx = RiskContext(
        risk_config=risk_config,
        instruments=instruments,
        calendar_dates=frozenset(calendar),
        expected_completed_bar=expected_bar,
        execution_date=str(pd.Timestamp(day).date()),
        cash=cash,
        equity=pre_equity,
        positions=dict(positions),
        valuation_price=val_prices,
        execution_price=val_prices,   # projected marking at execution-day price
        price_date=price_dates,
        cost=cost,
        lot_size={s: int(instruments.get(s, {}).get("lot_size", 100)) for s in
                  set(list(positions) + list(exec_prices))},
        existing_orders=account.executed_orders(),
    )
    risk_orders = [to_risk_order(o, exec_prices.get(o.symbol)) for o in orders]
    decision = evaluate_batch(risk_orders, ctx)
    rejected_ids = set(decision.rejected_order_ids)

    n_sim = 0
    for o in orders:
        if o.side == "HOLD":
            account.append_event({"kind": "order_generated", "date": str(day.date()),
                                  "order": o.to_dict()})
            continue
        if o.order_id in no_price_ids:
            continue  # already logged as missing_execution_price
        if o.order_id in rejected_ids:
            account.log_failure(
                date=str(pd.Timestamp(day).date()), failure_type="risk_rejected_order",
                symbol=o.symbol, strategy=account.strategy,
                message=next((v.reason for v in decision.violations
                              if v.symbol in ("", o.symbol) and v.date == o.execution_date),
                             "risk rejection"))
            o.status = "REJECTED"
            continue
        price = exec_prices.get(o.symbol)
        if price is None:  # pragma: no cover - defensive
            account.log_failure(
                date=str(pd.Timestamp(day).date()), failure_type="missing_execution_price",
                symbol=o.symbol, strategy=account.strategy,
                message=f"no execution price on {day.date()}")
            o.status = "NO_FILL"
            continue
        # fill
        qty = abs(o.adjust_quantity)
        if o.side == "BUY":
            fill = price * (1 + cost.slippage)
            gross = qty * fill
            fee = gross * cost.fee_rate
            cash_delta = -(gross + fee)
            positions[o.symbol] = positions.get(o.symbol, 0.0) + qty
        else:  # SELL
            fill = price * (1 - cost.slippage)
            gross = qty * fill
            fee = gross * cost.fee_rate
            stamp = gross * cost.stamp_duty
            cash_delta = +(gross - fee - stamp)
            positions[o.symbol] = positions.get(o.symbol, 0.0) - qty
        o.fill_price = fill
        o.gross_notional = gross
        o.fee = fee
        o.slippage_cost = gross * cost.slippage
        o.cash_delta = cash_delta
        o.status = "EXECUTED"
        cash += cash_delta
        n_sim += 1
        account.append_order(o)
        account.append_event({
            "kind": "fill", "date": str(pd.Timestamp(day).date()),
            "order_id": o.order_id, "symbol": o.symbol, "side": o.side,
            "fill_price": fill, "gross_notional": gross, "fee": fee,
            "slippage_cost": o.slippage_cost, "cash_delta": cash_delta,
        })
    return positions, cash, n_sim, decision


def paper_replay(
    repo_root: str | Path,
    strategy: str,
    start: str,
    end: str,
    *,
    data_root: str | Path = "data",
    paper_root: str | Path | None = None,
    init_cash: float | None = None,
    approver: str = "paper",
) -> dict[str, Any]:
    """Run the paper replay for a strategy over [start, end] on the Snapshot
    calendar. Returns a summary dict (persisted meta + metrics)."""
    repo = Path(repo_root)
    # KILL_SWITCH FIRST: before any account mutation / order generation (M7.21).
    check_kill_switch(repo)

    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    risk_config = load_risk_config(repo)
    instruments = load_instruments(repo)
    params = effective_params(spec, None)
    init_cash = init_cash if init_cash is not None else PortfolioConfig().init_cash

    timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    timing.validate()

    # dataset spanning warmup (in-sample start) -> replay end so trailing
    # signal windows (MA / momentum) have legal pre-window history (PIT).
    ds = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=spec.windows["in_sample"][0], end=end,
    )
    research = ds.research_frame()
    calendar = sorted(ds.calendar_dates())

    # precompute raw execution price + close per (day, symbol) once
    exec_col = spec.timing.get("execution_price", "close")
    frame = ds.execution_frame()
    exec_map: dict[pd.Timestamp, dict[str, float | None]] = {}
    close_map: dict[pd.Timestamp, dict[str, float]] = {}
    for date, grp in frame.groupby("date"):
        e = {}
        c = {}
        for r in grp.itertuples():
            cl = r.close
            if pd.notna(cl):
                c[r.symbol] = float(cl)
            ex = getattr(r, exec_col)
            e[r.symbol] = float(ex) if pd.notna(ex) else None
        exec_map[date.normalize()] = e
        close_map[date.normalize()] = c

    # build the target-weight series ONCE (PIT: trailing windows, no look-ahead)
    target_series = build_target_portfolio_series(spec, research, params, calendar)

    p_root = Path(paper_root) if paper_root else Path(data_root) / "paper"
    account = PaperAccount(strategy, p_root, init_cash=init_cash)
    account.assert_no_overlap(start)

    replay_days = [d for d in calendar
                   if pd.Timestamp(start).normalize() <= d <= pd.Timestamp(end).normalize()]

    positions: dict[str, float] = dict(account.current_positions())
    cash = account.current_cash() if account.has_state() else init_cash

    pending: dict[pd.Timestamp, list[Order]] = {}
    decision_days: list[pd.Timestamp] = []
    n_sim = 0
    n_holds = 0
    history: list[dict[str, Any]] = []

    for day in replay_days:
        # 1) execute orders scheduled for this day (fill at day's raw price)
        todays = pending.pop(day.normalize(), [])
        if todays:
            positions, cash, n_exec, _dec = _execute_orders(
                account=account, orders=todays, day=day, cost=cost,
                instruments=instruments, risk_config=risk_config,
                calendar=calendar, positions=positions, cash=cash,
                exec_price=exec_map.get(day.normalize(), {}),
                val_close=close_map.get(day.normalize(), {}))
            n_sim += n_exec
        # 2) decision at day close -> schedule execution at T+execution_bar
        tp = target_for_series_row(target_series, day, spec,
                                   reason=f"rebalance at {day.date()}")
        if tp is not None:
            decision_days.append(day)
            exec_day = _next_trading_day(calendar, day, timing.execution_bar)
            if exec_day is not None and exec_day <= pd.Timestamp(end).normalize():
                val_prices = close_map.get(day.normalize(), {})
                orders = generate_orders(
                    decision_date=str(day.date()),
                    execution_date=str(exec_day.date()),
                    current_positions=positions,
                    cash=cash,
                    target=tp,
                    valuation_prices=val_prices,
                    execution_prices={},
                    instruments=instruments,
                    reason_prefix=f"rebalance {day.date()}",
                )
                n_holds += sum(1 for o in orders if o.side == "HOLD")
                pending[exec_day.normalize()] = orders
                account.append_event({
                    "kind": "decision", "date": str(day.date()),
                    "execution_date": str(exec_day.date()),
                    "weights": tp.weights, "cash_weight": tp.cash_weight,
                })
        # daily equity marked at the day's raw close
        eq = cash + sum(q * close_map.get(day.normalize(), {}).get(s, 0.0)
                        for s, q in positions.items())
        history.append({"date": pd.Timestamp(day).normalize(),
                        "positions": dict(positions), "cash": cash, "equity": eq})

    # persist accumulated state once (parquet + meta)
    if history:
        pos_rows = pd.DataFrame(
            [{"date": h["date"], "symbol": s, "quantity": q}
             for h in history for s, q in h["positions"].items()])
        cash_rows = pd.DataFrame([{"date": h["date"], "cash": h["cash"]} for h in history])
        eq_rows = pd.DataFrame([{"date": h["date"], "equity": h["equity"]} for h in history])
        account.positions_path.parent.mkdir(parents=True, exist_ok=True)
        pos_rows.to_parquet(account.positions_path, index=False)
        cash_rows.to_parquet(account.cash_path, index=False)
        eq_rows.to_parquet(account.equity_path, index=False)

    # meta summary
    summary = {
        "strategy": strategy,
        "dataset_version": spec.dataset_version,
        "replay_start": start,
        "replay_end": end,
        "trading_days": len(replay_days),
        "rebalance_cycles": len(decision_days),
        "sim_orders": n_sim,
        "hold_orders": n_holds,
        "initial_cash": init_cash,
        "final_cash": cash,
        "decision_days": [str(d.date()) for d in decision_days],
    }
    account.write_meta(summary)
    return summary


__all__ = [
    "PaperAccount",
    "PaperError",
    "ReplayOverlapError",
    "paper_replay",
]