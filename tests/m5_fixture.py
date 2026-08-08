"""M5 test fixture: a self-contained temp repo with a momentum strategy spec
(small grid for speed) and an offline synthetic snapshot with enough trading
days for walk-forward (>= 1008)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from tests.backtest_helpers import make_snapshot

A, B, C, D = "510300.SH", "510500.SH", "518880.SH", "511010.SH"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, check=True)


def make_momentum_repo(tmp_path: Path, n_days: int = 1100) -> tuple[Path, Path]:
    """Build a temp repo: git + config + momentum spec + synthetic snapshot.
    Returns (repo_root, data_root)."""
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
        "final: {}\n", encoding="utf-8")
    for s in (A, B, C, D):
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n", encoding="utf-8")

    # Strongly trending prices (geometric) with distinct drifts -> momentum
    # rotation is profitable in-sample, so the happy-path pipeline passes.
    drifts = [0.0018, 0.0014, 0.0010, 0.0004]
    closes = {
        s: 100.0 * (1 + g) ** np.arange(n_days) * (1 + 0.002 * np.sin(np.arange(n_days) / 30))
        for s, g in zip((A, B, C, D), drifts)
    }
    ds = make_snapshot(root / "data", closes, name="market-test-v1")
    start = str(pd.to_datetime(ds.execution_frame()["date"].min()).date())
    end = str(pd.to_datetime(ds.execution_frame()["date"].max()).date())

    spec_yaml = (
        f"name: test_momentum_v1\nhypothesis: \"h\"\n"
        f"universe: [{', '.join(repr(s) for s in (A, B, C, D))}]\n"
        f"benchmark: \"{A}\"\n"
        "signal: {kind: momentum_rotation, momentum_days: 10, ma_filter: 0, top_k: 2}\n"
        "rebalance: monthly\nrisk: {max_positions: 3}\n"
        "dataset_version: market-test-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        f"windows:\n  in_sample: [\"{start}\", \"{end}\"]\n"
        "  holdout: [\"2025-01-01\", \"2026-08-07\"]\n"
        "param_grid: {momentum_days: [5, 10], ma_filter: [0], top_k: [1, 2]}\n"
        "research_budget:\n  max_total_selection_runs: 50\n"
        "  max_variants_per_param: {momentum_days: 2, ma_filter: 1, top_k: 2}\n"
        "  holdout_access: {allowed: false}\nseed: 42\n"
    )
    (root / "strategies" / "test_momentum_v1.yaml").write_text(spec_yaml, encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root, root / "data"