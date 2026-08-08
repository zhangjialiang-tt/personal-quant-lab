"""Shared M6 fixture: a momentum repo whose snapshot spans BOTH the in-sample
window and the Final Holdout window (so freeze -> final-holdout E2E works), with
the strategy registered and promoted to RESEARCH. Used by the candidate-freeze,
final-validation and bundle tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from pql.lifecycle import register_strategy, transition
from tests.backtest_helpers import make_snapshot

A, B, C, D = "510300.SH", "510500.SH", "518880.SH", "511010.SH"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, check=True)


def make_final_momentum_repo(tmp_path: Path, n_days: int = 1095) -> tuple[Path, Path, Path]:
    """Build a git repo + config + momentum spec + snapshot spanning
    IS (2023 -> 2024-12-31) and holdout (2025 -> end). Registers the strategy
    and promotes it to RESEARCH. Returns (repo_root, data_root, registry_path)."""
    root = Path(tmp_path)
    for sub in ("config/costs", "config/markets", "config/instruments",
                "strategies", "experiments", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
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
        "final:\n  holdout_min_sharpe: 0.0\n", encoding="utf-8")
    for s in (A, B, C, D):
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    drifts = [0.0018, 0.0014, 0.0010, 0.0004]
    closes = {
        s: 100.0 * (1 + g) ** np.arange(n_days) * (1 + 0.002 * np.sin(np.arange(n_days) / 30))
        for s, g in zip((A, B, C, D), drifts)
    }
    ds = make_snapshot(root / "data", closes, name="market-test-v1")
    dates = pd.to_datetime(ds.execution_frame()["date"].unique())
    start = str(dates.min().date())
    hol_end = str(dates.max().date())

    spec_yaml = (
        f"name: ftest_v1\nhypothesis: \"h\"\n"
        f"universe: [{', '.join(repr(s) for s in (A, B, C, D))}]\n"
        f"benchmark: \"{A}\"\n"
        "signal: {kind: momentum_rotation, momentum_days: 10, ma_filter: 0, top_k: 2}\n"
        "rebalance: monthly\nrisk: {max_positions: 3}\n"
        "dataset_version: market-test-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        f"windows:\n  in_sample: [\"{start}\", \"2024-12-31\"]\n"
        f"  holdout: [\"2025-01-01\", \"{hol_end}\"]\n"
        "param_grid: {momentum_days: [5, 10], ma_filter: [0], top_k: [1, 2]}\n"
        "research_budget:\n  max_total_selection_runs: 50\n"
        "  max_variants_per_param: {momentum_days: 2, ma_filter: 1, top_k: 2}\n"
        "  holdout_access: {allowed: false}\nseed: 42\n"
    )
    (root / "strategies" / "ftest_v1.yaml").write_text(spec_yaml, encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")

    reg = root / "strategy_registry.yaml"
    register_strategy(reg, "ftest_v1", "zhangjl", "init")
    transition(reg, "ftest_v1", "SPECIFIED", "spec", "strategies/ftest_v1.yaml", "zhangjl")
    transition(reg, "ftest_v1", "RESEARCH", "research", "strategies/ftest_v1.yaml", "zhangjl")
    return root, root / "data", reg


def run_candidate_pass(root, data_root, reg) -> None:
    """Run candidate validation + freeze so the strategy is CANDIDATE + frozen."""
    from pql.validation.freeze import promote_to_candidate
    from pql.validation.pipeline import validate_candidate

    report = validate_candidate(root, "ftest_v1", data_root=data_root,
                                report_root=root / "reports",
                                experiments_root=root / "experiments", persist=True)
    assert report["overall"] == "PASS", report["overall"]
    promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="freeze for test",
                         registry_path=reg, report_root=root / "reports",
                         experiments_root=root / "experiments", data_root=data_root)