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

from pql.backtest.costs import apply_stress
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
from pql.validation.freeze import code_tree_sha256

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
    cost_model=None,
):
    """Write a window backtest result as a Run in the ledger."""
    cost_model = cost_model or cost
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
        cost_config={"version": cost_model.version, "fee_rate": cost_model.fee_rate,
                     "slippage": cost_model.slippage},
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

    # M5 review P0: preflight the ENTIRE proposed SELECT grid against the
    # research budget BEFORE any backtest runs. A budget-exceed grid aborts here
    # with zero backtests executed and no SELECT runs written.
    from pql.registry.budget import check_grid_budget

    check_grid_budget(spec, exp_root, grid)

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

    # -- parameter robustness (full grid as SELECT runs, with real artifacts) --
    pr = parameter_robustness(spec, ds, cost, data_root)
    for row in pr["rows"]:
        _write_eval(exp_id, strategy, row["params"], "SELECT", spec, cost, ds,
                    gate, cfg["config_sha256"], gate_version, row["metrics"],
                    row.get("result").equity if row.get("result") else None,
                    row.get("result").orders if row.get("result") else None,
                    exp_root)

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

    # -- M6: cost stress (STRESS runs, full rerun, real costs) ---------------
    from .stress import cost_stress, execution_stress, worst_exec_max_drawdown

    cost_variants = cost_stress(spec, cost, ds, data_root)
    for v in cost_variants:
        _write_eval(exp_id, strategy, default_params, "STRESS", spec, cost, ds,
                    gate, cfg["config_sha256"], gate_version, v["metrics"],
                    v["equity"], v["orders"], exp_root)
    _cost_2x = next(v for v in cost_variants if v["parameters"].get("multiplier") == 2)
    cost_2x_sharpe = _num(_cost_2x["sharpe"])

    # -- M6: execution stress (STRESS runs, frozen E01-E05) ------------------
    exec_variants = execution_stress(spec, cost, ds, data_root)
    for v in exec_variants:
        _write_eval(exp_id, strategy, {**default_params, "_exec": v["variant_id"]},
                    "STRESS", spec, cost, ds, gate, cfg["config_sha256"],
                    gate_version, v["metrics"], v["equity"], v["orders"], exp_root)
    worst_mdd = worst_exec_max_drawdown(exec_variants)

    # -- M6: circular block bootstrap (IS returns, never holdout) ------------
    from .bootstrap import bootstrap, bootstrap_sharpe_p05

    boot_out = Path(report_root) / "validation" / strategy / "bootstrap"
    bs = bootstrap(spec, is_res.equity, out_dir=boot_out if persist else None)
    bs_p05 = bootstrap_sharpe_p05(bs)

    # -- M6: Deflated Sharpe Ratio (N = effective_trial_count) ---------------
    from .overfitting import deflated_sharpe_report

    dsr = deflated_sharpe_report(spec, is_res.equity, exp_root, strategy)

    # -- M6: kill test families (DIAGNOSTIC runs) ----------------------------
    from .kill import kill_tests, killed_family_count

    families = kill_tests(spec, cost, ds, data_root)
    for fid, fam in families.items():
        for v in fam["variants"]:
            if v.get("equity") is None:
                continue
            cost_model = apply_stress(cost, 2) if fid == "K05" else cost
            _write_eval(exp_id, strategy,
                        {**default_params, "_kill": fid, "_variant": v["variant_id"]},
                        "DIAGNOSTIC", spec, cost, ds, gate, cfg["config_sha256"],
                        gate_version, v["metrics"], v["equity"], v["orders"],
                        exp_root, cost_model=cost_model)
    n_killed_families = killed_family_count(families)

    # -- gate evaluation (M5 + M6, all from validation_gates.yaml) -----------
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
        "cost_2x_min_sharpe": cost_2x_sharpe is not None and cost_2x_sharpe >= _num(gates.get("cost_2x_min_sharpe")),
        "exec_stress_max_drawdown_floor": worst_mdd is not None and worst_mdd >= _num(gates.get("exec_stress_max_drawdown_floor")),
        "bootstrap_sharpe_p05_min": bs_p05 >= _num(gates.get("bootstrap_sharpe_p05_min")),
        "deflated_sharpe_min": dsr["dsr_probability"] is not None and not (
            isinstance(dsr["dsr_probability"], float) and math.isnan(dsr["dsr_probability"])
        ) and float(dsr["dsr_probability"]) >= _num(gates.get("deflated_sharpe_min")),
        "max_kill_families_killed": n_killed_families <= _num(gates.get("max_kill_families_killed")),
        "require_code_clean": not bool(gate.code_dirty),
    }
    code_clean = not bool(gate.code_dirty)
    overall = "FAIL" if any(v is False for v in gate_results.values()) else "PASS"
    ready_for_candidate_freeze = overall == "PASS"

    holdout_after = _holdout_snapshot(data_root)
    report = {
        "strategy": strategy,
        "strategy_state": "RESEARCH",  # never promoted
        "dataset_version": spec.dataset_version,
        "dataset_source": ds.manifest().get("source", ""),
        "market_evidence": ds.manifest().get("source", "") != "synthetic",
        "candidate_params": default_params,
        "gate_version": gate_version,
        "gate_content_sha256": cfg["per_file"].get(str(paths["gates"]), ""),
        "code_commit": gate.commit,
        "code_dirty": gate.code_dirty,
        "code_tree_sha256": code_tree_sha256(repo),
        "config_hashes": cfg["per_file"],
        "selected_params": default_params,
        "effective_trial_count": _effective_trial_count(exp_root, strategy),
        "provenance": {
            "dataset_version": spec.dataset_version,
            "dataset_source": ds.manifest().get("source", ""),
            "code_commit": gate.commit,
            "code_dirty": gate.code_dirty,
            "gate_version": gate_version,
            "config_sha256": cfg["config_sha256"],
        },
        "holdout_access_before": holdout_before,
        "holdout_access_after": holdout_after,
        "holdout_untouched": holdout_before == holdout_after,
        "experiment_id": exp_id,
        "is_baseline": is_metrics,
        "walkforward": {k: v for k, v in wf.items() if k != "combined_oos_equity"},
        "parameter_robustness": {k: v for k, v in pr.items() if k != "rows"},
        "time_robustness": tr,
        "regime": rg,
        "cost_stress": {
            "variants": [
                {"multiplier": v["parameters"].get("multiplier"), "sharpe": v["sharpe"],
                 "max_drawdown": v["max_drawdown"], "cagr": v["cagr"],
                 "fee_rate": v.get("fee_rate"), "slippage": v.get("slippage")}
                for v in cost_variants
            ],
            "cost_2x_sharpe": cost_2x_sharpe,
        },
        "execution_stress": {
            "variants": [
                {"variant_id": v["variant_id"], "variant_name": v["variant_name"],
                 "parameters": v["parameters"], "sharpe": v["sharpe"],
                 "max_drawdown": v["max_drawdown"], "cagr": v["cagr"],
                 "valuation_mode": v.get("valuation_mode")}
                for v in exec_variants
            ],
            "worst_exec_max_drawdown": worst_mdd,
            "gate_input_variant": "worst across required E01-E05 variants (M6-002)",
        },
        "bootstrap": bs["summary"],
        "deflated_sharpe": dsr,
        "kill_tests": {
            "families": [
                {
                    "family_id": f["family_id"],
                    "family_name": f["family_name"],
                    "family_result": f["family_result"],
                    "killed_fraction": f["killed_fraction"],
                    "gate_relevant_variant_count": f["gate_relevant_variant_count"],
                    "killed_variant_count": f["killed_variant_count"],
                    "variants": [
                        {"variant_id": v["variant_id"], "variant_name": v["variant_name"],
                         "parameters": v["parameters"], "result": v["result"],
                         "gate_relevant": v["gate_relevant"], "metrics": v["metrics"]}
                        for v in f["variants"]
                    ],
                }
                for f in families.values()
            ],
            "killed_family_count": n_killed_families,
        },
        "code_clean": {"code_dirty": bool(gate.code_dirty), "pass": code_clean},
        "gate_results": gate_results,
        "overall": overall,
        "ready_for_candidate_freeze": ready_for_candidate_freeze,
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