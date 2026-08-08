"""M7.6 Paper Report (plan §M7.6 / M7.43-47).

`pql paper report --strategy X` produces reports/paper/<strategy>/:
  - paper_report.json              (5 Paper Gate metrics + provenance)
  - equity_vs_benchmark.png        (paper NAV / initial NAV vs benchmark)

The five gate metrics are read from config/validation_gates.yaml `paper` section
(never hardcoded a second set):
  trading_days       unique trading dates processed in the replay window
  rebalance_cycles   scheduled rebalance decisions
  sim_orders         actually simulated-executed BUY + SELL (HOLD excluded)
  unreconciled       independent reconciliation mismatches
  silent_failures    runtime failure events with NO captured failures.jsonl record

silent_failures is NOT `len(failures.jsonl)` (M7.38): it is the count of
failure-kind events whose failure_id has no matching captured failure record.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from pql.data.dataset import DatasetView
from pql.execution.paper import PaperAccount
from pql.execution.reconcile import reconcile
from pql.registry.runner import resolve_paths
from pql.risk.rules import load_instruments, load_risk_config
from pql.schemas import load_cost_model, load_spec
from pql.validation.freeze import code_tree_sha256


class PaperReportError(RuntimeError):
    """Raised for paper-report generation failures."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_paper_gate(repo_root: str | Path) -> tuple[dict[str, Any], str]:
    path = Path(repo_root) / "config" / "validation_gates.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("paper") or {}), str(data.get("version", ""))


def silent_failures(account: PaperAccount) -> int:
    """Failure-kind events whose failure_id has no matching captured failure
    record in failures.jsonl (M7.38). Normal captured failures are NOT silent."""
    captured = {f.get("failure_id") for f in account.read_failures()}
    n = 0
    for ev in account.read_events():
        if ev.get("kind") == "failure" and ev.get("failure_id") not in captured:
            n += 1
    return n


def paper_state_fingerprint(account: PaperAccount) -> str:
    """SHA256 over the FULL PaperAccount state the report is derived from:
    executed order ledger, events, failures, persisted equity/cash/positions and
    the replay window + init_cash. The promotion gate recomputes this from the
    CURRENT account and compares to the report's recorded fingerprint, so a
    stale report (state changed after report generation) is rejected (review
    P1-2)."""
    import hashlib
    import json as _json

    h = hashlib.sha256()

    def _add(b: bytes) -> None:
        h.update(b)

    for o in account.executed_orders():
        _add(_json.dumps(o, sort_keys=True, default=str).encode("utf-8"))
    for e in account.read_events():
        _add(_json.dumps(e, sort_keys=True, default=str).encode("utf-8"))
    for f in account.read_failures():
        _add(_json.dumps(f, sort_keys=True, default=str).encode("utf-8"))
    for path in (account.equity_path, account.cash_path, account.positions_path):
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if len(df):
                    if "date" in df.columns:
                        df = df.sort_values("date")
                    _add(df.to_csv(index=False).encode())
                else:
                    _add(f"<empty:{path.name}>".encode())
            except (ValueError, OSError, KeyError):  # pragma: no cover - defensive
                _add(f"<missing:{path.name}>".encode())
    meta = {}
    if account.meta_path.exists():
        try:
            import json as _json2

            meta = _json2.loads(account.meta_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):  # pragma: no cover - defensive
            meta = {}
    scope = {k: meta.get(k) for k in
             ("replay_start", "replay_end", "last_persisted", "initial_cash", "init_cash")}
    _add(_json.dumps(scope, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()


def market_evidence(source: str) -> bool:
    """Explicit allowlist: only real-market adapters count as market evidence.
    synthetic / fixture / unknown (including an empty source on error) are
    FALSE (review P1-2: never fail open to market_evidence=true)."""
    return source in ("akshare", "tushare")


def load_paper_report(
    repo_root: str | Path,
    strategy: str,
    *,
    data_root: str | Path = "data",
    paper_root: str | Path | None = None,
    report_root: str | Path = "reports",
    persist: bool = True,
) -> dict[str, Any]:
    """Build the paper report for a strategy. Gate thresholds come ONLY from
    config/validation_gates.yaml. Returns the report dict (persisted as
    reports/paper/<strategy>/paper_report.json), plus writes the NAV-vs-bench
    chart when benchmark data is available."""
    repo = Path(repo_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    risk_config = load_risk_config(repo)
    instruments = load_instruments(repo)

    p_root = Path(paper_root) if paper_root else Path(data_root) / "paper"
    account = PaperAccount(strategy, p_root, init_cash=100_000)
    # init_cash from meta if present
    if account.meta_path.exists():
        try:
            import json as _json

            meta = _json.loads(account.meta_path.read_text(encoding="utf-8"))
            account.init_cash = float(meta.get("init_cash", account.init_cash))
        except (ValueError, OSError, KeyError):
            pass

    rec = reconcile(account, cost=cost, instruments=instruments)
    meta = {}
    if account.meta_path.exists():
        try:
            import json as _json

            meta = _json.loads(account.meta_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            meta = {}

    trading_days = int(meta.get("trading_days", 0))
    rebalance_cycles = int(meta.get("rebalance_cycles", 0))
    sim_orders = int(meta.get("sim_orders", 0))
    unreconciled = int(rec["unreconciled"])
    silent = silent_failures(account)

    paper_gate, gate_version = _load_paper_gate(repo)
    gates = {
        "trading_days": {"actual": trading_days,
                         "threshold": paper_gate.get("min_trading_days"),
                         "pass": trading_days >= int(paper_gate.get("min_trading_days", 0))},
        "rebalance_cycles": {"actual": rebalance_cycles,
                             "threshold": paper_gate.get("min_rebalance_cycles"),
                             "pass": rebalance_cycles >= int(paper_gate.get("min_rebalance_cycles", 0))},
        "sim_orders": {"actual": sim_orders,
                       "threshold": paper_gate.get("min_sim_orders"),
                       "pass": sim_orders >= int(paper_gate.get("min_sim_orders", 0))},
        "unreconciled": {"actual": unreconciled,
                         "threshold": paper_gate.get("max_unreconciled"),
                         "pass": unreconciled <= int(paper_gate.get("max_unreconciled", 0))},
        "silent_failures": {"actual": silent,
                            "threshold": paper_gate.get("max_silent_failures"),
                            "pass": silent <= int(paper_gate.get("max_silent_failures", 0))},
    }
    overall = "PASS" if all(g["pass"] for g in gates.values()) else "FAIL"

    # provenance
    registry = {}
    reg_path = repo / "strategy_registry.yaml"
    if reg_path.exists():
        registry = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    entry = next((e for e in registry.get("strategies", []) if e.get("id") == strategy), None)
    candidate_hash = ""
    if entry:
        candidate_hash = str((entry.get("candidate_freeze") or {}).get("candidate_hash", ""))
        state = entry.get("state", "UNREGISTERED")
    else:
        state = "UNREGISTERED"

    gates_path = Path(repo) / "config" / "validation_gates.yaml"
    cost_path = Path(paths["cost"])
    source = _dataset_source(repo, spec, data_root)
    report = {
        "strategy": strategy,
        "strategy_state": state,
        "dataset_version": spec.dataset_version,
        "dataset_source": source,
        "market_evidence": market_evidence(source),
        "replay_start": meta.get("replay_start", ""),
        "replay_end": meta.get("replay_end", ""),
        "trading_days": trading_days,
        "rebalance_cycles": rebalance_cycles,
        "sim_orders": sim_orders,
        "unreconciled": unreconciled,
        "silent_failures": silent,
        "paper_state_fingerprint": paper_state_fingerprint(account),
        "reconciliation": {
            "expected_cash": rec["expected_cash"],
            "actual_cash": rec["actual_cash"],
            "cash_mismatch": rec["cash_mismatch"],
            "position_mismatches": rec["position_mismatches"],
            "order_issues": rec["order_issues"],
        },
        "paper_gate": gates,
        "gate_version": gate_version,
        "overall": overall,
        "provenance": {
            "code_tree_sha256": code_tree_sha256(repo),
            "candidate_hash": candidate_hash,
            "risk_policy_version": risk_config.get("version", ""),
            "risk_config_sha256": _file_sha256(gates_path),
            "cost_config_sha256": _file_sha256(cost_path),
            "market_rule_version": spec.market_rule_version,
            "timing": dict(spec.timing),
            "initial_cash": account.init_cash,
        },
        "report_created": _now(),
    }

    # benchmark chart (visualization only; never affects the gate)
    chart_path = _write_benchmark_chart(repo, spec, data_root, account, report_root, strategy)
    report["chart_path"] = str(chart_path) if chart_path else None

    if persist:
        import json as _json

        out = Path(report_root) / "paper" / strategy / "paper_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(report, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")
        report["report_path"] = str(out)
    return report


def _dataset_source(repo, spec, data_root) -> str:
    from pql.data.dataset import DatasetVersionNotFound, SnapshotIntegrityError

    try:
        view = DatasetView.load(spec.dataset_version, data_root)
        return view.manifest().get("source", "")
    except (DatasetVersionNotFound, SnapshotIntegrityError, OSError):
        return ""


def _write_benchmark_chart(repo, spec, data_root, account, report_root, strategy) -> Path | None:
    """Paper NAV / initial NAV vs benchmark close_adj / replay-start close_adj.
    If the benchmark has no data in the replay window, return None (report keeps
    an explicit diagnostic; no fabricated curve)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover - optional dep
        return None
    meta = {}
    if account.meta_path.exists():
        try:
            import json as _json

            meta = _json.loads(account.meta_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            meta = {}
    start = meta.get("replay_start")
    end = meta.get("replay_end")
    if not start or not end or not account.equity_path.exists():
        return None
    from pql.data.dataset import DatasetVersionNotFound, SnapshotIntegrityError

    try:
        view = DatasetView.load(spec.dataset_version, data_root, universe=[spec.benchmark],
                                start=start, end=end)
        bench = view.research_frame()[["date", "close_adj"]].dropna().sort_values("date")
    except (DatasetVersionNotFound, SnapshotIntegrityError, OSError, ValueError, KeyError):
        return None
    eq = pd.read_parquet(account.equity_path).sort_values("date")
    if eq.empty or bench.empty:
        return None
    base = meta.get("initial_cash", account.init_cash)
    paper_nav = eq["equity"] / base
    bench_nav = bench["close_adj"] / bench["close_adj"].iloc[0]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(pd.to_datetime(eq["date"]), paper_nav.values, label="paper NAV")
    ax.plot(pd.to_datetime(bench["date"]), bench_nav.values,
            label=f"benchmark {spec.benchmark}")
    ax.set_title(f"Paper vs Benchmark — {strategy}")
    ax.set_ylabel("NAV (replay-start = 1)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    out = Path(report_root) / "paper" / strategy / "equity_vs_benchmark.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


__all__ = ["PaperReportError", "load_paper_report", "silent_failures"]