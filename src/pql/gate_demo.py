"""M7.8 Gate Demo (plan §M7.8 / M7.58-60).

`pql gate demo` runs the full lifecycle in an ISOLATED deterministic sandbox
(PLAN_CLARIFICATION M7-001): production strategy_registry.yaml, holdout
state/log and paper state are NEVER touched. The sandbox uses a momentum
fixture strategy + its OWN fixture snapshot (IS + fixture holdout), so the demo
consumes only the fixture's Final Holdout — never a production one.

Chain demonstrated: IDEA → SPECIFIED → RESEARCH → candidate validation →
CANDIDATE (freeze) → fixture final holdout → VALIDATED → paper replay →
paper report → PAPER. Optionally PAPER → LIVE with human (PASS) vs AI (REJECT).

Prints STEP / STATE BEFORE / PRECONDITION / EVIDENCE / STATE AFTER per step and
ends with DEMO_RESULT=PASS + the sandbox path.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pql.data.adapters import FixtureProvider
from pql.data.calendar import CalendarAdapter, FixtureCalendar
from pql.data.snapshot import build_snapshot
from pql.gate import GateError, promote
from pql.lifecycle import register_strategy


class GateDemoError(RuntimeError):
    """Raised when the gate demo cannot complete."""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, check=True)


def _build_sandbox(sandbox: Path) -> tuple[Path, Path, Path]:
    """Build a self-contained git repo with a momentum fixture strategy +
    snapshot spanning IS (2024) and a fixture holdout (2025-). Returns
    (repo_root, data_root, registry_path)."""
    root = Path(sandbox)
    for sub in ("config/costs", "config/markets", "config/instruments",
                "strategies", "experiments", "data", "src/pql/_fixture"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "src" / "pql" / "_fixture" / "code.py").write_text(
        "FIXTURE_CODE_VERSION = 1\n", encoding="utf-8")
    (root / "config" / "costs" / "test.yaml").write_text(
        "version: cn-etf-cost-2026-v1\nfee_rate: 0.0003\nstamp_duty: 0.0\nslippage: 0.001\n",
        encoding="utf-8")
    (root / "config" / "markets" / "test.yaml").write_text(
        "version: cn-etf-2026-v1\nmarket_name: CN_ETF\nlot_size: 100\n"
        "trading_calendar: snapshot\nbenchmark: 510300\n", encoding="utf-8")
    (root / "config" / "validation_gates.yaml").write_text(
        "version: gates-2026-v1\ncandidate:\n"
        "  min_is_sharpe: 0.5\n  max_drawdown_floor: -0.35\n"
        "  walkforward_min_segment_sharpe_frac: 0.5\n"
        "  param_stability_min_frac: 0.5\n"
        "  time_windows_min_pos_cagr_frac: 0.5\n"
        "  cost_2x_min_sharpe: 0.0\n"
        "  exec_stress_max_drawdown_floor: -0.45\n"
        "  bootstrap_sharpe_p05_min: -0.3\n"
        "  deflated_sharpe_min: 0.95\n"
        "  max_kill_families_killed: 2\n  require_code_clean: true\n"
        "final:\n  holdout_min_sharpe: 0.0\n"
        "paper:\n  min_trading_days: 40\n  min_rebalance_cycles: 3\n"
        "  min_sim_orders: 10\n  max_unreconciled: 0\n  max_silent_failures: 0\n"
        "risk:\n  version: risk-2026-v1\n  max_position_weight: 0.6\n"
        "  max_portfolio_exposure: 1.0\n  max_turnover_per_rebalance: 2.0\n"
        "  max_order_value: 100000\n", encoding="utf-8")
    symbols = ["510300.SH", "510500.SH", "518880.SH", "511010.SH"]
    for s in symbols:
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    n_days = 2000
    t = np.arange(n_days)
    phases = [0.0, 1.5, 3.0, 4.5]
    # Rotating leadership: each symbol's drift is phase-shifted so the momentum
    # top-2 rotates month to month (generating real paper trades) while all
    # symbols trend up (candidate validation passes).
    closes = {}
    for s, ph in zip(symbols, phases):
        rets = 0.0011 + 0.0014 * np.sin(t / 45 + ph) + 0.0006 * np.sin(t / 7 + ph)
        closes[s] = 100.0 * np.exp(np.cumsum(rets))
    ds = _make_snapshot(root / "data", closes, name="market-demo-v1")
    dates = pd.to_datetime(ds.execution_frame()["date"].unique())
    start = str(dates.min().date())
    hol_end = str(dates.max().date())

    spec_yaml = (
        "name: demo_v1\nhypothesis: \"fixture hypothesis for gate demo\"\n"
        f"universe: [{', '.join(repr(s) for s in symbols)}]\n"
        f"benchmark: \"{symbols[0]}\"\n"
        "signal: {kind: momentum_rotation, momentum_days: 10, ma_filter: 0, top_k: 2}\n"
        "rebalance: monthly\nrisk: {max_positions: 3}\n"
        "dataset_version: market-demo-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        f"windows:\n  in_sample: [\"{start}\", \"2024-12-31\"]\n"
        f"  holdout: [\"2025-01-01\", \"{hol_end}\"]\n"
        "param_grid: {momentum_days: [5, 10], ma_filter: [0], top_k: [1, 2]}\n"
        "research_budget:\n  max_total_selection_runs: 50\n"
        "  max_variants_per_param: {momentum_days: 2, ma_filter: 1, top_k: 2}\n"
        "  holdout_access: {allowed: false}\nseed: 42\n"
    )
    (root / "strategies" / "demo_v1.yaml").write_text(spec_yaml, encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "demo@demo")
    _git(root, "config", "user.name", "demo")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")

    reg = root / "strategy_registry.yaml"
    return root, root / "data", reg


def _make_snapshot(tmp_path, closes, *, name):
    from pql.data.dataset import DatasetView

    n = len(next(iter(closes.values())))
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    data: dict[str, dict] = {}
    for sym, close in closes.items():
        close = np.asarray(close, dtype=float)
        raw = pd.DataFrame({
            "date": dates, "open": close - 0.1, "high": close + 0.2,
            "low": close - 0.2, "close": close,
            "volume": np.full(n, 1_000_000), "amount": close * 1_000_000,
        })
        data[sym] = {"raw": raw,
                     "research": pd.Series(close, index=dates, name=sym)}
    provider = FixtureProvider(data)
    cal_dates = [d.strftime("%Y-%m-%d") for d in dates]
    calendar = CalendarAdapter([FixtureCalendar(cal_dates)])
    build_snapshot(source="fixture", symbols=list(closes), start="2024-01-01",
                   end=str(dates[-1].date()), data_root=tmp_path, from_fixture=True,
                   provider=provider, calendar_adapter=calendar, name=name)
    return DatasetView.load(name, tmp_path)


def run_gate_demo(
    sandbox: str | Path | None = None,
    *,
    print_steps: bool = True,
    demo_to_live: bool = False,
) -> dict[str, Any]:
    """Run the full sandwich gate demo to PAPER in an isolated sandbox. Returns
    a results dict with one entry per step (state before/after + result)."""
    if sandbox is None:
        sandbox = Path(tempfile.mkdtemp(prefix="pql-gate-demo-"))
    sandbox = Path(sandbox)
    root, data_root, reg = _build_sandbox(sandbox)
    results: dict[str, Any] = {"sandbox": str(sandbox)}

    def step(name, fn):
        before = _state(reg)
        try:
            out = fn()
        except GateError as exc:
            results[name] = {"result": "REJECT", "reason": str(exc),
                             "state_before": before, "state_after": _state(reg)}
            if print_steps:
                print(f"STEP {name}: REJECT ({exc})")
            return None
        after = _state(reg)
        results[name] = {"result": "PASS", "state_before": before, "state_after": after}
        if print_steps:
            print(f"STEP {name}: PASS  ({before} -> {after})")
        return out

    # 0 register -> IDEA
    register_strategy(reg, "demo_v1", approver="zhangjl", reason="demo init")
    results["IDEA"] = {"result": "PASS", "state_after": "IDEA"}

    step("IDEA->SPECIFIED", lambda: promote(root, "demo_v1", "SPECIFIED",
                                            "zhangjl", "spec", registry_path=reg,
                                            report_root=root / "reports",
                                            experiments_root=root / "experiments",
                                            data_root=data_root))
    step("SPECIFIED->RESEARCH", lambda: promote(root, "demo_v1", "RESEARCH",
                                                "zhangjl", "research",
                                                registry_path=reg,
                                                report_root=root / "reports",
                                                experiments_root=root / "experiments",
                                                data_root=data_root))

    from pql.validation.pipeline import validate_candidate

    cand = validate_candidate(root, "demo_v1", data_root=data_root,
                              report_root=root / "reports",
                              experiments_root=root / "experiments", persist=True)
    results["RESEARCH->CANDIDATE"] = {"result": "PASS" if cand["overall"] == "PASS" else "FAIL",
                                      "candidate_overall": cand["overall"]}
    if cand["overall"] != "PASS":
        raise GateDemoError(f"candidate validation failed: {cand['overall']}")
    if print_steps:
        print(f"STEP RESEARCH->CANDIDATE: candidate overall={cand['overall']}")

    step("RESEARCH->CANDIDATE", lambda: promote(root, "demo_v1", "CANDIDATE",
                                                "zhangjl", "freeze",
                                                registry_path=reg,
                                                report_root=root / "reports",
                                                experiments_root=root / "experiments",
                                                data_root=data_root))

    from pql.validation.final import validate_final

    final = validate_final(root, "demo_v1", data_root=data_root,
                           report_root=root / "reports",
                           experiments_root=root / "experiments",
                           registry_path=reg)
    results["CANDIDATE->VALIDATED"] = {"result": "PASS" if final["overall"] == "PASS" else "FAIL",
                                       "final_overall": final["overall"]}
    if final["overall"] != "PASS":
        raise GateDemoError(f"final validation failed: {final['overall']}")
    if print_steps:
        print(f"STEP CANDIDATE->VALIDATED: final overall={final['overall']}")

    step("CANDIDATE->VALIDATED", lambda: promote(root, "demo_v1", "VALIDATED",
                                                 "zhangjl", "validated",
                                                 registry_path=reg,
                                                 report_root=root / "reports",
                                                 experiments_root=root / "experiments",
                                                 data_root=data_root))

    # paper replay on the IS window (never consumes any holdout)
    from pql.execution.paper import paper_replay
    from pql.execution.report import load_paper_report
    from pql.schemas import load_spec

    spec = load_spec(root / "strategies" / "demo_v1.yaml")
    is_start, is_end = spec.windows["in_sample"]
    replay = paper_replay(root, "demo_v1", is_start, is_end,
                          data_root=data_root, paper_root=data_root / "paper",
                          init_cash=100_000)
    report = load_paper_report(root, "demo_v1", data_root=data_root,
                               paper_root=data_root / "paper",
                               report_root=root / "reports", persist=True)
    results["paper_replay"] = replay
    results["paper_report"] = {
        "overall": report["overall"],
        "trading_days": report["trading_days"],
        "rebalance_cycles": report["rebalance_cycles"],
        "sim_orders": report["sim_orders"],
        "unreconciled": report["unreconciled"],
        "silent_failures": report["silent_failures"],
    }
    if report["overall"] != "PASS":
        raise GateDemoError(f"paper gate failed: {report['overall']}")
    if print_steps:
        print(f"STEP VALIDATED->PAPER: paper overall={report['overall']} "
              f"(days={report['trading_days']}, cycles={report['rebalance_cycles']}, "
              f"orders={report['sim_orders']}, unrec={report['unreconciled']}, "
              f"silent={report['silent_failures']})")

    step("VALIDATED->PAPER", lambda: promote(root, "demo_v1", "PAPER",
                                             "zhangjl", "paper",
                                             registry_path=reg,
                                             report_root=root / "reports",
                                             experiments_root=root / "experiments",
                                             data_root=data_root))
    results["DEMO_RESULT"] = "PASS"

    if demo_to_live:
        # PAPER -> LIVE: AI rejected, human accepted
        step("PAPER->LIVE(ai)", lambda: promote(root, "demo_v1", "LIVE",
                                                "ai", "try ai",
                                                registry_path=reg,
                                                report_root=root / "reports",
                                                experiments_root=root / "experiments",
                                                data_root=data_root))
        step("PAPER->LIVE(human)", lambda: promote(root, "demo_v1", "LIVE",
                                                   "zhangjl", "human live",
                                                   registry_path=reg,
                                                   report_root=root / "reports",
                                                   experiments_root=root / "experiments",
                                                   data_root=data_root))
    return results


def _state(registry_path) -> str:
    import yaml

    reg = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8")) or {}
    for s in reg.get("strategies", []):
        if s.get("id") == "demo_v1":
            return s.get("state", "?")
    return "UNREGISTERED"


def gate_demo_main() -> int:
    results = run_gate_demo(print_steps=True)
    print(f"\nDEMO_RESULT={results.get('DEMO_RESULT', 'FAIL')}")
    print(f"sandbox={results['sandbox']}")
    print(f"final state={results.get('VALIDATED->PAPER', {}).get('state_after', '?')}")
    return 0 if results.get("DEMO_RESULT") == "PASS" else 1


__all__ = ["GateDemoError", "gate_demo_main", "run_gate_demo"]