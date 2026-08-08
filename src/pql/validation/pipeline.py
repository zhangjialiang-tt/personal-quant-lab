"""M5.6 candidate development validation pipeline (D9).

Orchestrates the M5 portion of `pql validate candidate`: IS baseline, walk-
forward, parameter robustness, time robustness, regime diagnostics. M6 gates
(cost/exec stress, bootstrap, DSR, kill) are recorded as PENDING_M6 — never
PASS. Overall is INCOMPLETE_PENDING_M6 when every M5 gate passes, FAIL
otherwise; it can never be PASS until M6 completes all candidate gates.

Holdout is a hard exclusion: the pipeline never calls HoldoutGuard.holdout_slice
and records the holdout_access.log before/after (must be identical). No
Candidate Freeze / promotion is performed (strategy stays RESEARCH).

Research runs are written to the Experiment->Run ledger: grid params as SELECT
runs (deduped by selection_key), walk-forward OOS / year / regime slices as
EVALUATE / DIAGNOSTIC runs (never adding to effective_trial_count).
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from pql.data.dataset import DatasetView
from pql.registry.experiments import (
    next_experiment_id,
    selection_key,
    write_manifest,
    write_run,
)
from pql.registry.provenance import (
    config_hashes,
    dependency_versions,
    git_state,
)
from pql.registry.runner import resolve_paths
from pql.schemas import load_cost_model, load_spec
from pql.signals.registry import effective_params

from .base import grid_configs, run_window
from .regimes import regime_analysis
from .robustness import parameter_robustness, time_robustness
from .walkforward import walkforward

M6_KEYS = ["cost_stress", "exec_stress", "bootstrap", "deflated_sharpe", "kill_tests"]


class PipelineError(RuntimeError):
    """Raised for pipeline orchestration failures."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_gates(repo_root: str | Path) -> tuple[dict, str]:
    """Return (candidate-gate thresholds, gate_version) from validation_gates.yaml."""
    path = Path(repo_root) / "config" / "validation_gates.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("candidate", {})), str(data.get("version", ""))


def _holdout_snapshot(data_root: str | Path) -> dict:
    path = Path(data_root) / "metadata" / "holdout_access.log"
    if not path.exists():
        return {"exists": False, "lines": 0, "sha256": None}
    content = path.read_bytes()
    return {
        "exists": True,
        "lines": content.count(b"\n"),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_eval(
    exp_id: str, strategy: str, params: dict, run_kind: str,
    spec, cost, ds: DatasetView, gate, config_sha256: str, gate_version: str,
    metrics: dict, equity, orders, exp_root: str | Path,
):
    """Write a window backtest result as a Run in the ledger."""
    return write_run(
        experiments_root=exp_root,
        experiment_id=exp_id,
        strategy=strategy,
        parameters=dict(params),
        selection_key=selection_key(params),
        run_kind=run_kind,
        visible_to_researcher=True,
        dataset_version=spec.dataset_version,
        dataset_checksums=ds.manifest().get("files", {}),
        market_rule_version=spec.market_rule_version,
        cost_model_version=spec.cost_model_version,
        cost_config={"version": cost.version, "fee_rate": cost.fee_rate,
                     "slippage": cost.slippage},
        gate_version=gate_version,
        gate=gate,
        config_sha256=config_sha256,
        dependencies=dependency_versions(),
        seed=spec.seed,
        timing={"execution_bar": int(spec.timing.get("execution_bar", 1)),
                "execution_price": spec.timing.get("execution_price", "close")},
        metrics=dict(metrics),
        equity=equity,
        orders=orders,
    )


def validate_candidate(
    repo_root: str | Path,
    strategy: str,
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    persist: bool = True,
) -> dict[str, Any]:
    """Run the M5 candidate development validation for a strategy. Returns the
    candidate report (persisted to reports/validation/<strategy>/candidate_report.json
    when persist). Never consumes holdout and never promotes the strategy."""
    repo = Path(repo_root)
    exp_root = Path(experiments_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    ds = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=spec.windows["in_sample"][0], end=spec.windows["in_sample"][1],
    )
    gates, gate_version = load_gates(repo)
    default_params = effective_params(spec, None)
    grid = grid_configs(spec)

    gate = git_state(exp_root)
    cfg = config_hashes(paths["spec"], paths["gates"], paths["cost"],
                        paths["market"], paths["instruments"])
    holdout_before = _holdout_snapshot(data_root)

    # -- Experiment -> Run ledger container for this candidate validation -----
    exp_id = next_experiment_id(exp_root)
    write_manifest(
        exp_root, experiment_id=exp_id, strategy=strategy,
        research_question=f"candidate development validation: {strategy}",
        experiment_config={"gate_version": gate_version},
    )

    # -- IS baseline ----------------------------------------------------------
    is_res = run_window(spec, default_params, ds, cost, data_root,
                        spec.windows["in_sample"][0], spec.windows["in_sample"][1])
    is_metrics = dict(is_res.metrics)
    _write_eval(exp_id, strategy, default_params, "SELECT", spec, cost, ds,
                gate, cfg["config_sha256"], gate_version, is_metrics,
                is_res.equity, is_res.orders, exp_root)

    # -- parameter robustness (full grid as SELECT runs) ----------------------
    pr = parameter_robustness(spec, ds, cost, data_root)
    for row in pr["rows"]:
        _write_eval(exp_id, strategy, row["params"], "SELECT", spec, cost, ds,
                    gate, cfg["config_sha256"], gate_version, row["metrics"],
                    None, None, exp_root)

    # -- walk-forward (OOS test folds as EVALUATE runs) -----------------------
    wf = walkforward(spec, grid, ds, cost, data_root)
    if wf.get("status") == "ok":
        for fold in wf["folds"]:
            # re-run the selected config's test fold to persist its equity/orders
            f_res = run_window(spec, fold["selected_params"], ds, cost, data_root,
                               fold["test_start"], fold["test_end"])
            _write_eval(exp_id, strategy, fold["selected_params"], "EVALUATE",
                        spec, cost, ds, gate, cfg["config_sha256"], gate_version,
                        f_res.metrics, f_res.equity, f_res.orders, exp_root)

    # -- time robustness (year slices as EVALUATE runs) -----------------------
    tr = time_robustness(spec, ds, cost, data_root)
    for yr in tr["years"]:
        if yr["status"] == "ok":
            _write_eval(exp_id, strategy, default_params, "EVALUATE", spec, cost, ds,
                        gate, cfg["config_sha256"], gate_version, yr["metrics"],
                        None, None, exp_root)

    # -- regime diagnostics (DIAGNOSTIC runs) ---------------------------------
    rg = regime_analysis(spec, ds, cost, data_root)
    for combo in rg["combos"]:
        _write_eval(exp_id, strategy, {**default_params, "_regime": combo["regime_combo"]},
                    "DIAGNOSTIC", spec, cost, ds, gate, cfg["config_sha256"],
                    gate_version, combo, None, None, exp_root)

    # -- gate evaluation -------------------------------------------------------
    is_sharpe = _num(is_metrics.get("sharpe"))
    is_maxdd = _num(is_metrics.get("max_drawdown"))
    gate_results = {
        "min_is_sharpe": is_sharpe is not None and is_sharpe >= _num(gates.get("min_is_sharpe")),
        "max_drawdown_floor": is_maxdd is not None and is_maxdd >= _num(gates.get("max_drawdown_floor")),
        "walkforward": _wf_gate(wf, gates),
        "param_stability": pr["param_stability"] >= _num(gates.get("param_stability_min_frac")),
        "time_windows_min_pos_cagr_frac": (
            tr["positive_cagr_fraction"] >= _num(gates.get("time_windows_min_pos_cagr_frac"))
        ),
    }
    m6_sections = {k: "PENDING_M6" for k in M6_KEYS}
    m5_fail = any(v is False for v in gate_results.values())
    overall = "FAIL" if m5_fail else "INCOMPLETE_PENDING_M6"

    holdout_after = _holdout_snapshot(data_root)
    report = {
        "strategy": strategy,
        "strategy_state": "RESEARCH",  # never promoted
        "dataset_version": spec.dataset_version,
        "dataset_source": ds.manifest().get("source", ""),
        "market_evidence": ds.manifest().get("source", "") != "synthetic",
        "gate_version": gate_version,
        "gate_content_sha256": cfg["per_file"].get(str(paths["gates"]), ""),
        "code_commit": gate.commit,
        "code_dirty": gate.code_dirty,
        "config_hashes": cfg["per_file"],
        "selected_params": default_params,
        "effective_trial_count": _effective_trial_count(exp_root, strategy),
        "holdout_access_before": holdout_before,
        "holdout_access_after": holdout_after,
        "holdout_untouched": holdout_before == holdout_after,
        "experiment_id": exp_id,
        "is_baseline": is_metrics,
        "walkforward": {k: v for k, v in wf.items() if k != "combined_oos_equity"},
        "parameter_robustness": {k: v for k, v in pr.items() if k != "rows"},
        "time_robustness": tr,
        "regime": rg,
        "m6_pending": m6_sections,
        "gate_results": gate_results,
        "overall": overall,
        "created": _now(),
    }
    if persist:
        out = Path(report_root) / "validation" / strategy / "candidate_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")
        report["report_path"] = str(out)
    return report


def _wf_gate(wf: dict, gates: dict) -> bool:
    """Positive test-segment Sharpe fraction >= threshold. Walk-forward skipped
    (insufficient data) is treated as not-failing (task M5.26: skipped, not
    FAIL) but recorded as 'skipped'."""
    if wf.get("status") == "skipped":
        return True
    frac = wf.get("positive_sharpe_segment_fraction", 0.0)
    thr = _num(gates.get("walkforward_min_segment_sharpe_frac"))
    return frac >= thr if thr is not None else True


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _effective_trial_count(exp_root: Path, strategy: str) -> int:
    from pql.registry.experiments import effective_trial_count as _etc

    return _etc(exp_root, strategy)


__all__ = ["M6_KEYS", "PipelineError", "load_gates", "validate_candidate"]