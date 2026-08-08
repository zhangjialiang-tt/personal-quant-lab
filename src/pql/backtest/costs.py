"""M3 cost model helpers (D3). `apply_stress` scales fee_rate and slippage by a
multiplier (1x/2x/3x). Production cost must be positive; the engine unit tests
use an explicit ZeroCostFixture instead of weakening the production policy.
"""
from __future__ import annotations

from dataclasses import replace

from pql.schemas import CostModel, load_cost_model


class CostModelError(ValueError):
    """Raised when a cost model violates the production non-zero cost policy."""


def apply_stress(model: CostModel, multiplier: float) -> CostModel:
    """Scale fee_rate and slippage by `multiplier` (plan M6: 1x/2x/3x)."""
    if multiplier <= 0:
        raise CostModelError(f"stress multiplier must be > 0, got {multiplier}")
    return replace(
        model,
        fee_rate=model.fee_rate * multiplier,
        slippage=model.slippage * multiplier,
    )


def assert_production_costs(model: CostModel) -> None:
    """Production backtests must have positive fee_rate (D3)."""
    if model.fee_rate <= 0:
        raise CostModelError(
            f"production cost model must have fee_rate > 0, got {model.fee_rate}; "
            "use ZeroCostFixture only in engine unit tests"
        )


__all__ = [
    "CostModel",
    "CostModelError",
    "apply_stress",
    "assert_production_costs",
    "load_cost_model",
]
