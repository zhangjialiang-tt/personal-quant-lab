"""M4 run pipeline (M4.15 / M4.16). Orchestrates a single Run:

    load Experiment -> load StrategySpec -> validate params in frozen
    param_grid -> check Research Budget -> load pinned Dataset -> build signal
    -> run_backtest() -> capture provenance -> write RUN-NNNNN -> update ledger.

The same functions are used by the deterministic validator to RE-RUN a Run for
reproducibility, so the executed and validated results come from one code path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pql.backtest.api import run_backtest
from pql.backtest.engine import TradingIntent
from pql.data.dataset import DatasetView
from pql.schemas import (
    PortfolioConfig,
    StrategySpec,
    load_cost_model,
    load_spec,
)
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract

from .budget import check_would_exceed
from .experiments import next_run_id, selection_key, write_run
from .provenance import (
    config_hashes,
    dependency_versions,
    git_state,
)


class ParamError(ValueError):
    """Raised when a run parameter is outside the frozen param_grid."""


def _match_config(repo: Path, subdir: str, version: str) -> Path:
    """Find the config file under repo/config/<subdir> whose `version` id
    matches. Scans actual file contents so a version id never maps to a stale
    path by name alone."""
    cfg_dir = repo / "config" / subdir
    for p in sorted(cfg_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if data.get("version") == version:
            return p
    raise FileNotFoundError(f"no config under config/{subdir} with version {version!r}")


def resolve_paths(repo: Path, spec: StrategySpec) -> dict[str, Path]:
    """Resolve the config file paths referenced by a spec."""
    return {
        "spec": repo / "strategies" / f"{spec.name}.yaml",
        "gates": repo / "config" / "validation_gates.yaml",
        "cost": _match_config(repo, "costs", spec.cost_model_version),
        "market": _match_config(repo, "markets", spec.market_rule_version),
        "instruments": list((repo / "config" / "instruments").glob("*.yaml")),
    }


def validate_params(spec: StrategySpec, params: dict[str, Any]) -> dict[str, Any]:
    """Every parameter must fall inside the frozen param_grid (M4.17)."""
    for key, value in params.items():
        grid = spec.param_grid.get(key)
        if grid is None:
            raise ParamError(f"parameter {key!r} is not in the frozen param_grid")
        if value not in grid:
            raise ParamError(
                f"parameter {key}={value} is outside the frozen param_grid "
                f"{spec.name}.param_grid[{key}]={grid}; every researcher-visible "
                "selection belongs to the research space"
            )
    return dict(params)


def execute_run(
    *,
    repo_root_path: str | Path,
    strategy: str,
    params: dict[str, Any] | None = None,
    data_root: str | Path = "data",
    seed: int = 42,
) -> dict[str, Any]:
    """Compute a run's backtest WITHOUT persisting it (used by the experiment
    runner and by the deterministic validator's reproducibility re-run)."""
    repo = Path(repo_root_path)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    effective = effective_params(spec, params)
    validate_params(spec, effective)

    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])

    in_sample = spec.windows["in_sample"]
    ds = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=in_sample[0], end=in_sample[1],
    )
    research = ds.research_frame()
    intent: TradingIntent = build_signal(spec, research, effective)

    timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    portfolio = PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )
    result = run_backtest(
        intent=intent,
        universe=spec.universe,
        execution_model=timing,
        cost_model=cost,
        portfolio_config=portfolio,
        dataset=ds,
    )
    return {
        "spec": spec,
        "effective": effective,
        "timing": timing,
        "cost": cost,
        "dataset": ds,
        "result": result,
        "paths": paths,
        "intent": intent,
    }


def run_pipeline(
    *,
    repo_root_path: str | Path,
    experiments_root: str | Path,
    strategy: str,
    params: dict[str, Any] | None = None,
    experiment_id: str,
    run_kind: str = "SELECT",
    visible_to_researcher: bool = True,
    data_root: str | Path = "data",
    seed: int = 42,
) -> dict[str, Any]:
    """Execute one Run and persist it. If run_kind == SELECT the research budget
    is enforced BEFORE any backtest runs (a budget-exceed SELECT is rejected
    without executing the engine)."""
    exp_root = Path(experiments_root)
    repo = Path(repo_root_path)
    # Resolve the effective params + enforce the SELECT budget gate FIRST, so a
    # budget-exceed run never reaches the backtest engine (research governance).
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    effective = effective_params(spec, params)
    validate_params(spec, effective)
    if run_kind == "SELECT":
        check_would_exceed(spec, exp_root, effective)

    col = execute_run(
        repo_root_path=repo, strategy=strategy, params=effective,
        data_root=data_root, seed=seed,
    )
    spec = col["spec"]
    effective = col["effective"]
    result = col["result"]
    timing = col["timing"]
    cost = col["cost"]
    ds = col["dataset"]
    paths = col["paths"]

    gate = git_state(exp_root)
    deps = dependency_versions()
    cfg = config_hashes(
        paths["spec"], paths["gates"], paths["cost"], paths["market"], paths["instruments"]
    )
    sk = selection_key(effective)
    run_dir = write_run(
        experiments_root=exp_root,
        experiment_id=experiment_id,
        strategy=strategy,
        parameters=effective,
        selection_key=sk,
        run_kind=run_kind,
        visible_to_researcher=visible_to_researcher,
        dataset_version=spec.dataset_version,
        dataset_checksums=ds.manifest().get("files", {}),
        market_rule_version=spec.market_rule_version,
        cost_model_version=spec.cost_model_version,
        cost_config={
            "version": cost.version,
            "fee_rate": cost.fee_rate,
            "slippage": cost.slippage,
        },
        gate_version=_gate_version(repo_root_path),
        gate=gate,
        config_sha256=cfg["config_sha256"],
        dependencies=deps,
        seed=seed,
        timing={
            "signal_time": timing.signal_time,
            "decision_time": timing.decision_time,
            "execution_bar": timing.execution_bar,
            "execution_price": timing.execution_price,
        },
        metrics=result.metrics,
        equity=result.equity,
        orders=result.orders,
    )
    run_id = run_dir.name
    return {
        "run_id": run_id,
        "experiment_id": experiment_id,
        "selection_key": sk,
        "run_kind": run_kind,
        "metrics": result.metrics,
        "run_dir": run_dir,
        "code_commit": gate.commit,
        "code_dirty": gate.code_dirty,
        "config_sha256": cfg["config_sha256"],
        "dataset_version": spec.dataset_version,
    }


def _gate_version(repo: Path) -> str:
    gates = Path(repo) / "config" / "validation_gates.yaml"
    data = yaml.safe_load(gates.read_text(encoding="utf-8")) or {}
    return str(data.get("version", ""))


__all__ = [
    "ParamError",
    "execute_run",
    "next_run_id",
    "resolve_paths",
    "run_pipeline",
    "selection_key",
    "validate_params",
]