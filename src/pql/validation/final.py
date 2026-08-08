"""M6.8 Final Holdout validation (`pql validate final`).

The ONLY post-freeze validation. It verifies the Candidate Freeze fingerprint
against the current files, then consumes the Final Holdout exactly once (via
HoldoutGuard, fail-closed), runs the FROZEN candidate, computes holdout-only
metrics, and applies the D9 `final` gate (holdout_min_sharpe).

Absent by design: stress, bootstrap, DSR, kill, parameter search, re-training.
Final reports holdout-only sections; the IS / walk-forward / stress / bootstrap
/ DSR / kill content from the candidate report is NOT copied here.

Boundary state: the frozen strategy is run over the full [IS_start, holdout_end]
range (signal built PIT over IS+released-holdout research so MA/momentum warmup
uses legal pre-holdout history), then ONLY the holdout window's equity is
scored. This preserves the real portfolio state at the holdout boundary instead
of cold-starting at cash (PLAN_CLARIFICATION M6-005: no cold start).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from pql.backtest.api import run_backtest
from pql.data.dataset import DatasetView
from pql.registry.experiments import (
    next_experiment_id,
    selection_key,
    write_manifest,
    write_run,
)
from pql.registry.holdout import HoldoutError, HoldoutGuard
from pql.registry.provenance import dependency_versions, git_state
from pql.registry.runner import resolve_paths
from pql.schemas import PortfolioConfig, load_cost_model, load_spec
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract

from .freeze import compute_freeze_payload, verify_freeze


class FinalValidationError(RuntimeError):
    """Raised for final-validation failures (not frozen, freeze mismatch, ...)."""


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


class _CombinedView:
    """Read-only DatasetView-like wrapper spanning IS (freely accessible) plus
    the guard-RELEASED holdout window. The engine reads execution_frame() only;
    the signal reads research_frame(). Holdout data was released by HoldoutGuard
    (consumed once) before this view is built — the final validator never loads
    holdout data directly."""

    def __init__(self, is_view: DatasetView, holdout_view: DatasetView) -> None:
        self.is_view = is_view
        self.holdout_view = holdout_view
        self.version = is_view.version
        self.data_root = is_view.data_root

    def manifest(self) -> dict:
        return self.is_view.manifest()

    def calendar_dates(self):
        return self.is_view.calendar_dates() | self.holdout_view.calendar_dates()

    def research_frame(self) -> pd.DataFrame:
        return pd.concat([self.is_view.research_frame(), self.holdout_view.research_frame()],
                         ignore_index=True).reset_index(drop=True)

    def execution_frame(self) -> pd.DataFrame:
        return pd.concat([self.is_view.execution_frame(), self.holdout_view.execution_frame()],
                         ignore_index=True).reset_index(drop=True)

    def amount_frame(self) -> pd.DataFrame:
        return pd.concat([self.is_view.amount_frame(), self.holdout_view.amount_frame()],
                         ignore_index=True).reset_index(drop=True)


def _final_gate(repo_root, holdout_sharpe):
    import yaml

    gates = yaml.safe_load(
        (Path(repo_root) / "config" / "validation_gates.yaml").read_text(encoding="utf-8")
    ) or {}
    final = gates.get("final") or {}
    thr = _num(final.get("holdout_min_sharpe"))
    return {
        "threshold": thr,
        "holdout_sharpe": holdout_sharpe,
        "pass": holdout_sharpe is not None and (thr is None or holdout_sharpe >= thr),
    }


def validate_final(
    repo_root: str | Path,
    strategy: str,
    *,
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    registry_path: str | Path = "strategy_registry.yaml",
    caller: str = "validate_final",
) -> dict[str, Any]:
    """Run the Final Holdout validation. Returns the final report (persisted to
    reports/validation/<strategy>/final_report.json)."""
    repo = Path(repo_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    params = effective_params(spec, None)
    holdout_start, holdout_end = spec.windows["holdout"]
    is_start = spec.windows["in_sample"][0]

    guard = HoldoutGuard(registry_path, data_root)

    # 1) verify the candidate is frozen and the fingerprint still matches the
    #    current files BEFORE consuming the holdout (a mismatch must NOT consume
    #    the holdout, per D5/M6).
    try:
        frozen = guard.frozen_freeze(strategy)
    except HoldoutError as exc:
        raise FinalValidationError(str(exc)) from exc
    actual = compute_freeze_payload(repo, experiments_root, spec)
    try:
        verify_freeze(frozen, actual)
    except Exception as exc:
        raise FinalValidationError(f"freeze mismatch: {exc}") from exc
    candidate_hash = str(frozen.get("candidate_hash") or "")

    # 2) fail-closed consumption: consumed=true is persisted BEFORE data release.
    try:
        holdout_view = guard.holdout_slice(
            strategy, spec.dataset_version, holdout_start, holdout_end,
            caller=caller, purpose="final_holdout", as_view=True,
        )
    except HoldoutError as exc:
        raise FinalValidationError(str(exc)) from exc

    # 3) run the FROZEN candidate over [IS_start, holdout_end]; boundary state
    #    preserved, holdout scored only from holdout_start.
    is_view = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=is_start, end=spec.windows["in_sample"][1],
    )
    combined = _CombinedView(is_view, holdout_view)
    intent = build_signal(spec, combined.research_frame(), params,
                          calendar_dates=combined.calendar_dates())
    timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    portfolio = PortfolioConfig(
        init_cash=1_000_000, max_positions=spec.risk.get("max_positions"), weighting="equal",
    )
    res = run_backtest(
        intent=intent, universe=spec.universe, execution_model=timing,
        cost_model=cost, portfolio_config=portfolio, dataset=combined,
    )
    equity = pd.Series(res.equity).sort_index()
    hol_equity = equity.loc[pd.Timestamp(holdout_start):pd.Timestamp(holdout_end)]
    from pql.backtest.metrics import compute_metrics

    hol_metrics = compute_metrics(hol_equity)

    gate = _final_gate(repo, _num(hol_metrics.get("sharpe")))
    overall = "PASS" if gate["pass"] else "FAIL"

    # 4) write a FINAL_HOLDOUT run to the ledger (never adds to N).
    exp_id = next_experiment_id(experiments_root)
    write_manifest(
        experiments_root, experiment_id=exp_id, strategy=strategy,
        research_question=f"final holdout validation: {strategy}",
        experiment_config={"purpose": "final_holdout", "candidate_hash": candidate_hash},
    )
    gate_state = git_state(experiments_root)
    import yaml as _yaml

    _gates = _yaml.safe_load((repo / "config" / "validation_gates.yaml").read_text(encoding="utf-8")) or {}
    gate_version = str(_gates.get("version", ""))
    run_dir = write_run(
        experiments_root=experiments_root,
        experiment_id=exp_id,
        strategy=strategy,
        parameters=dict(params),
        selection_key=selection_key(params),
        run_kind="FINAL_HOLDOUT",
        visible_to_researcher=True,
        dataset_version=spec.dataset_version,
        dataset_checksums=is_view.manifest().get("files", {}),
        market_rule_version=spec.market_rule_version,
        cost_model_version=spec.cost_model_version,
        cost_config={"version": cost.version, "fee_rate": cost.fee_rate,
                     "slippage": cost.slippage},
        gate_version=gate_version,
        gate=gate_state,
        config_sha256="",
        dependencies=dependency_versions(),
        seed=spec.seed,
        timing={"execution_bar": timing.execution_bar, "execution_price": timing.execution_price},
        metrics=dict(hol_metrics),
        equity=hol_equity,
        orders=res.orders,
    )

    from datetime import datetime

    report = {
        "strategy": strategy,
        "candidate_hash": candidate_hash,
        "freeze_fingerprint": {k: frozen.get(k) for k in (
            "candidate_hash", "spec_sha256", "code_commit", "parameters",
            "gate_version", "gate_config_sha256", "cost_config_sha256",
            "market_rule_sha256", "instrument_sha256", "uv_lock_sha256",
            "dataset_version", "created",
        )},
        "dataset_version": spec.dataset_version,
        "dataset_source": is_view.manifest().get("source", ""),
        "market_evidence": is_view.manifest().get("source", "") != "synthetic",
        "holdout_start": holdout_start,
        "holdout_end": holdout_end,
        "holdout_metrics": {k: v for k, v in hol_metrics.items()},
        "holdout_gate": gate,
        "overall": overall,
        "final_run_ref": f"{exp_id}/{run_dir.name}",
        "holdout_access": {
            "consumed": True,
            "candidate_hash": candidate_hash,
        },
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    out = Path(report_root) / "validation" / strategy / "final_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report_path"] = str(out)
    return report


__all__ = ["FinalValidationError", "validate_final"]