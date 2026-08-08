"""M5 shared validation helpers.

A validation run builds the strategy's PIT signal ONCE over the full in-sample
research frame (momentum/MA warmup is preserved), then executes the backtest on
an arbitrary [start, end] window via the frozen run_backtest() public API. The
signal is point-in-time (every decision at T uses only data <= T), so slicing
the execution window never leaks future data.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

from pql.backtest.api import run_backtest
from pql.data.dataset import DatasetView
from pql.registry.runner import resolve_paths
from pql.schemas import PortfolioConfig, load_cost_model, load_spec
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract


def grid_configs(spec) -> list[dict[str, Any]]:
    """Full Cartesian product of the frozen param_grid, as a list of param
    dicts (deterministic key order)."""
    keys = list(spec.param_grid.keys())
    if not keys:
        return [{}]
    return [dict(zip(keys, combo)) for combo in product(*[spec.param_grid[k] for k in keys])]


def load_context(repo_root: str | Path, strategy: str, data_root: str | Path = "data"):
    """Load the strategy spec, its referenced cost model, and the in-sample
    DatasetView."""
    repo = Path(repo_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    in_sample = spec.windows["in_sample"]
    ds = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=in_sample[0], end=in_sample[1],
    )
    return spec, cost, ds


def build_intent(spec, params: dict[str, Any], ds: DatasetView):
    """Build the PIT signal over the full in-sample research frame."""
    return build_signal(spec, ds.research_frame(), params)


def run_window(
    spec, params: dict[str, Any], ds: DatasetView, cost, data_root: str | Path,
    start: str, end: str,
):
    """Run the strategy on [start, end] fresh-portfolio backtest, returning the
    BacktestResult (metrics computed on that window's equity)."""
    intent = build_intent(spec, effective_params(spec, params), ds)
    win = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe, start=start, end=end,
    )
    timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    portfolio = PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )
    return run_backtest(
        intent=intent, universe=spec.universe, execution_model=timing,
        cost_model=cost, portfolio_config=portfolio, dataset=win,
    )


__all__ = ["build_intent", "load_context", "run_window"]