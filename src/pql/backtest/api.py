"""M3 backtest public API (D10). `run_backtest` is the single domain entry point;
strategies never import vectorbt directly. Production cost policy (fee_rate > 0)
is enforced here; the raw engine (engine.run_backtest_impl) is what the ZeroCost
golden unit tests exercise.
"""
from __future__ import annotations

from pql.schemas import BacktestResult, CostModel, PortfolioConfig
from pql.timing import TimingContract

from ..data.dataset import DatasetView
from .costs import assert_production_costs
from .engine import SignalIntent, TargetWeightIntent, TradingIntent, run_backtest_impl

__all__ = [
    "BacktestResult",
    "SignalIntent",
    "TargetWeightIntent",
    "TradingIntent",
    "run_backtest",
]


def run_backtest(
    intent: TradingIntent,
    universe: list[str],
    execution_model: TimingContract,
    cost_model: CostModel,
    portfolio_config: PortfolioConfig,
    dataset: DatasetView,
) -> BacktestResult:
    """Run a backtest through the vectorbt engine; production cost must be > 0."""
    assert_production_costs(cost_model)
    return run_backtest_impl(
        intent=intent,
        universe=universe,
        execution_model=execution_model,
        cost_model=cost_model,
        portfolio_config=portfolio_config,
        dataset=dataset,
    )

