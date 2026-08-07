"""Frozen schema dataclasses + strict YAML loaders for research contracts.

Global decisions D3 / D6 / D8 / D10 from the execution plan. Unknown YAML keys
are rejected (SchemaError) to prevent spec/config drift.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


class SchemaError(ValueError):
    """Raised when a spec/config YAML has unknown keys or invalid structure."""


# --------------------------------------------------------------------------- #
# Model dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CostModel:
    """D3 cost model: proportional commission + slippage, no min_fee in v0.1."""

    version: str
    fee_rate: float
    stamp_duty: float
    slippage: float

    _ALLOWED_KEYS = frozenset({"version", "fee_rate", "stamp_duty", "slippage"})


@dataclass(frozen=True)
class PortfolioConfig:
    """D10 portfolio knobs passed to run_backtest."""

    init_cash: float = 1_000_000
    max_positions: int | None = None
    weighting: str = "equal"  # equal-weighted by default


@dataclass(frozen=True)
class StrategySpec:
    """D6 strategy specification. `signal`/`risk`/`param_grid` are strategy
    extension points (inner keys vary per signal kind), so their inner keys are
    NOT restricted; `timing`/`windows`/`research_budget` have fixed structure.
    """

    name: str
    hypothesis: str
    universe: list[str]
    benchmark: str
    signal: dict[str, Any]
    rebalance: str
    risk: dict[str, Any]
    dataset_version: str
    market_rule_version: str
    cost_model_version: str
    timing: dict[str, Any]
    windows: dict[str, list[str]]
    param_grid: dict[str, list[Any]]
    research_budget: dict[str, Any]
    seed: int

    _ALLOWED_KEYS = frozenset(
        {
            "name",
            "hypothesis",
            "universe",
            "benchmark",
            "signal",
            "rebalance",
            "risk",
            "dataset_version",
            "market_rule_version",
            "cost_model_version",
            "timing",
            "windows",
            "param_grid",
            "research_budget",
            "seed",
        }
    )
    _TIMING_KEYS = frozenset({"execution_bar", "execution_price"})
    _WINDOWS_KEYS = frozenset({"in_sample", "holdout"})
    _BUDGET_KEYS = frozenset(
        {"max_total_selection_runs", "max_variants_per_param", "holdout_access"}
    )
    _BUDGET_HOLDOUT_KEYS = frozenset({"allowed"})


@dataclass(frozen=True)
class BacktestResult:
    """D8/D10 backtest output. equity/orders/metrics filled by M3 engine;
    run_meta carries engine/dependency provenance."""

    equity: Any = None  # pd.DataFrame (date x strategy nav)
    orders: Any = None  # order records
    metrics: dict[str, float] = field(default_factory=dict)  # D8 metric set
    run_meta: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# YAML helpers
# --------------------------------------------------------------------------- #


def _load_yaml(path: Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise SchemaError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: expected a YAML mapping, got {type(data).__name__}")
    return data


def _reject_unknown_keys(mapping: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise SchemaError(f"{where}: unknown key(s): {sorted(unknown)}")


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{where}: expected a mapping, got {type(value).__name__}")
    return value


# --------------------------------------------------------------------------- #
# Cost model
# --------------------------------------------------------------------------- #


def load_cost_model(path: str | Path) -> CostModel:
    data = _load_yaml(Path(path))
    _reject_unknown_keys(data, CostModel._ALLOWED_KEYS, str(path))
    try:
        return CostModel(
            version=data["version"],
            fee_rate=float(data["fee_rate"]),
            stamp_duty=float(data["stamp_duty"]),
            slippage=float(data["slippage"]),
        )
    except KeyError as exc:
        raise SchemaError(f"{path}: missing required field {exc.args[0]}") from exc


# --------------------------------------------------------------------------- #
# Strategy spec
# --------------------------------------------------------------------------- #


def load_spec(path: str | Path) -> StrategySpec:
    data = _load_yaml(Path(path))
    _reject_unknown_keys(data, StrategySpec._ALLOWED_KEYS, str(path))

    timing = _require_mapping(data.get("timing", {}), f"{path}.timing")
    _reject_unknown_keys(timing, StrategySpec._TIMING_KEYS, f"{path}.timing")

    windows = _require_mapping(data.get("windows", {}), f"{path}.windows")
    _reject_unknown_keys(windows, StrategySpec._WINDOWS_KEYS, f"{path}.windows")
    for key in ("in_sample", "holdout"):
        if key in windows and not (
            isinstance(windows[key], (list, tuple)) and len(windows[key]) == 2
        ):
            raise SchemaError(f"{path}.windows.{key}: expected [start, end] date pair")

    budget = _require_mapping(data.get("research_budget", {}), f"{path}.research_budget")
    _reject_unknown_keys(budget, StrategySpec._BUDGET_KEYS, f"{path}.research_budget")
    holdout_access = _require_mapping(
        budget.get("holdout_access", {}), f"{path}.research_budget.holdout_access"
    )
    _reject_unknown_keys(
        holdout_access, StrategySpec._BUDGET_HOLDOUT_KEYS, f"{path}.research_budget.holdout_access"
    )

    required = {
        "name",
        "hypothesis",
        "universe",
        "benchmark",
        "signal",
        "rebalance",
        "risk",
        "dataset_version",
        "market_rule_version",
        "cost_model_version",
        "param_grid",
        "seed",
    }
    missing = required - set(data)
    if missing:
        raise SchemaError(f"{path}: missing required field(s): {sorted(missing)}")

    return StrategySpec(
        name=data["name"],
        hypothesis=data["hypothesis"],
        universe=list(data["universe"]),
        benchmark=data["benchmark"],
        signal=dict(data["signal"]),
        rebalance=data["rebalance"],
        risk=dict(data["risk"]),
        dataset_version=data["dataset_version"],
        market_rule_version=data["market_rule_version"],
        cost_model_version=data["cost_model_version"],
        timing=dict(timing),
        windows=dict(windows),
        param_grid=dict(data["param_grid"]),
        research_budget=dict(budget),
        seed=int(data["seed"]),
    )


def dump_spec(spec: StrategySpec, path: str | Path) -> None:
    Path(path).write_text(
        yaml.safe_dump(asdict(spec), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )