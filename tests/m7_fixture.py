"""M7 test fixtures: a momentum repo whose validation_gates.yaml includes the
M7 `risk:` policy, plus helpers to build controlled snapshots for paper-replay
tests (T+1 execution, missing price, etc.)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from tests.backtest_helpers import make_snapshot

A, B, C, D = "510300.SH", "510500.SH", "518880.SH", "511010.SH"

_GATES = (
    "version: gates-2026-v1\n"
    "candidate:\n"
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
    "  max_order_value: 100000\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, check=True)


def make_momentum_repo(tmp_path: Path, n_days: int = 300) -> tuple[Path, Path, Path]:
    """A momentum repo with the M7 risk policy. IS window = the whole snapshot
    (so paper replay can run on IS). Returns (repo_root, data_root, registry).
    Small n_days keeps paper tests fast; the momentum spec is monthly-rebalance
    so a 300-day window still gives >3 rebalance cycles and >10 sim orders at
    small init_cash."""
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
    (root / "config" / "validation_gates.yaml").write_text(_GATES, encoding="utf-8")
    for s in (A, B, C, D):
        (root / "config" / "instruments" / f"{s.split('.')[0]}.yaml").write_text(
            f"symbol: \"{s}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
            "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
            "listed_date: \"2020-01-01\"\n", encoding="utf-8")

    drifts = [0.0018, 0.0014, 0.0010, 0.0004]
    closes = {
        s: 100.0 * (1 + g) ** np.arange(n_days) * (1 + 0.002 * np.sin(np.arange(n_days) / 30))
        for s, g in zip((A, B, C, D), drifts)
    }
    ds = make_snapshot(root / "data", closes, name="market-m7-v1")
    start = str(pd.to_datetime(ds.execution_frame()["date"].min()).date())
    end = str(pd.to_datetime(ds.execution_frame()["date"].max()).date())

    spec_yaml = (
        f"name: test_momentum_v1\nhypothesis: \"h\"\n"
        f"universe: [{', '.join(repr(s) for s in (A, B, C, D))}]\n"
        f"benchmark: \"{A}\"\n"
        "signal: {kind: momentum_rotation, momentum_days: 10, ma_filter: 0, top_k: 2}\n"
        "rebalance: monthly\nrisk: {max_positions: 3}\n"
        "dataset_version: market-m7-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        f"windows:\n  in_sample: [\"{start}\", \"{end}\"]\n"
        "  holdout: [\"2026-01-01\", \"2026-12-31\"]\n"
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
    return root, root / "data", root / "strategy_registry.yaml"


def make_single_repo(tmp_path: Path, closes: dict[str, np.ndarray],
                     *, spec_name: str = "test_v1",
                     signal: str = "buy_hold",
                     n: int | None = None) -> tuple[Path, Path, Path]:
    """A minimal repo with a single-symbol snapshot and a configurable signal
    (buy_hold or trend_ma) for controlled paper tests. Returns
    (repo_root, data_root, registry)."""
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
    (root / "config" / "validation_gates.yaml").write_text(_GATES, encoding="utf-8")
    sym = next(iter(closes))
    code = sym.split(".")[0]
    (root / "config" / "instruments" / f"{code}.yaml").write_text(
        f"symbol: \"{sym}\"\nexchange: SSE\nasset_type: ETF\nunderlying_type: INDEX\n"
        "currency: CNY\nlot_size: 100\ntick_size: 0.001\nsame_day_sell: true\n"
        "listed_date: \"2020-01-01\"\n", encoding="utf-8")

    ds = make_snapshot(root / "data", closes, name="market-single-v1")
    dates = pd.to_datetime(ds.execution_frame()["date"].unique())
    start = str(dates.min().date())
    end = str(dates.max().date())

    if signal == "buy_hold":
        sig = f"{{kind: buy_hold, symbol: \"{sym}\"}}"
        grid = "{}\n"
    else:
        sig = "{kind: trend_ma, ma_period: 5}"
        grid = "{ma_period: [5]}\n"
    spec_yaml = (
        f"name: {spec_name}\nhypothesis: \"h\"\n"
        f"universe: [\"{sym}\"]\nbenchmark: \"{sym}\"\n"
        f"signal: {sig}\nrebalance: daily\nrisk: {{max_positions: 1}}\n"
        "dataset_version: market-single-v1\nmarket_rule_version: cn-etf-2026-v1\n"
        "cost_model_version: cn-etf-cost-2026-v1\n"
        "timing: {execution_bar: 1, execution_price: close}\n"
        f"windows:\n  in_sample: [\"{start}\", \"{end}\"]\n"
        "  holdout: [\"2026-01-01\", \"2026-12-31\"]\n"
        f"param_grid: {grid}"
        "research_budget:\n  max_total_selection_runs: 50\n"
        "  max_variants_per_param: {}\n  holdout_access: {allowed: false}\nseed: 42\n"
    )
    (root / "strategies" / f"{spec_name}.yaml").write_text(spec_yaml, encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root, root / "data", root / "strategy_registry.yaml"