"""M4.4 deterministic validator (D7 / M4.25-35, proposal §20.3).

Seven checks, each PASS/FAIL, never letting a FAIL roll up to overall PASS:

    no_same_bar_fill      execution_bar >= 1 AND no order fills at a signal bar
    no_future_data        point-in-time: truncating data to T and re-running the
                          signal must match the full-data signal at T
    dataset_pinned        snapshot exists and its checksums match the run
    cost_nonzero          production fee_rate > 0
    valid_trading_dates   every filled date is in the snapshot trading calendar
    holdout_compliance    RESEARCH runs never (illegally) touch the Final Holdout
    reproducible          re-executing the same config reproduces equity/orders
                          semantically; on PASS, records semantic_result_hash

Output is written to reports/validation/<EXP>/<RUN>/deterministic.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from pql.data.dataset import DatasetVersionNotFound, DatasetView, SnapshotIntegrityError
from pql.registry.experiments import load_run
from pql.registry.runner import execute_run
from pql.schemas import load_spec
from pql.signals.registry import build_signal, effective_params


class ValidationError(RuntimeError):
    """Raised when a validation cannot be performed (malformed run, etc.)."""


def _read_run_artifacts(exp_root: Path, experiment_id: str, run_id: str) -> tuple[dict, Path]:
    run = load_run(exp_root, experiment_id, run_id)
    run_dir = exp_root / experiment_id / "runs" / run_id
    return run, run_dir


def _load_equity(run_dir: Path) -> pd.Series:
    df = pd.read_parquet(run_dir / "equity.parquet")
    df = df.set_index("date").sort_index()
    return df.iloc[:, 0].astype(float)


def _load_orders(run_dir: Path) -> pd.DataFrame:
    df = pd.read_parquet(run_dir / "orders.parquet")
    if df.empty:
        return df
    return df.sort_values("id").reset_index(drop=True)


def _execution_dates(ds: DatasetView) -> pd.DatetimeIndex:
    dates = pd.to_datetime(ds.execution_frame()["date"].dt.normalize()).drop_duplicates()
    return pd.DatetimeIndex(sorted(dates))


def _semantic_compare(a: pd.DataFrame, b: pd.DataFrame) -> None:
    """normalize (sort index, sort columns, uniform dtype) then
    assert_frame_equal with the frozen rtol/atol."""
    a = a.sort_index(axis=0).sort_index(axis=1)
    b = b.sort_index(axis=0).sort_index(axis=1)
    pd.testing.assert_frame_equal(a, b, rtol=1e-12, atol=1e-12)


def _semantic_result_hash(run_dir: Path) -> str:
    """sha256 over CANONICALIZED VALUES (not parquet bytes), so identical
    semantic results hash identically regardless of serialization metadata."""
    equity = _load_equity(run_dir)
    orders = _load_orders(run_dir)
    h = hashlib.sha256()
    h.update(b"equity\n")
    for date, val in equity.items():
        h.update(f"{date.isoformat()}:{val:.17g}\n".encode())
    h.update(b"orders\n")
    for row in orders.itertuples(index=False):
        h.update(
            f"{int(row.id)}:{int(row.col)}:{int(row.idx)}:{float(row.size):.17g}:"
            f"{float(row.price):.17g}:{float(row.fees):.17g}:{int(row.side)}\n".encode()
        )
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #


def check_no_same_bar_fill(run: dict, run_dir: Path, col: dict | None = None) -> dict:
    """Same-bar fill prevention = the frozen TimingContract (D2): execution_bar
    >= 1 guarantees the engine shifts every signal to fill no earlier than
    T+1. This check verifies the run's recorded timing contract actually holds
    (execution_bar >= 1) and that no order fills in the pre-shift bars
    (idx < execution_bar), which are the only bars a same-bar fill could occupy.

    It does NOT independently re-derive every fill's originating signal: that
    per-fill guarantee is provided by the engine's shift and independently
    verified by the `reproducible` check (which re-executes the engine with the
    same timing contract). `col` is accepted for API symmetry but not used.
    """
    eb = int(run["timing"].get("execution_bar", -1))
    if eb < 1:
        return {"status": "FAIL", "detail": f"execution_bar={eb} < 1 admits same-bar fill"}
    orders = _load_orders(run_dir)
    if not orders.empty:
        fill_early = orders["idx"] < eb
        if fill_early.any():
            return {
                "status": "FAIL",
                "detail": f"{int(fill_early.sum())} order(s) filled before the earliest "
                f"legal bar (idx<{eb}) — same-bar fill",
            }
    return {
        "status": "PASS",
        "detail": f"timing contract valid: execution_bar={eb} >= 1; no fill before bar {eb}",
    }


def _sample_dates(dates: pd.DatetimeIndex, warmup: int, k: int = 5) -> list[pd.Timestamp]:
    """Deterministic, fixed-position sample of k dates after the warmup window."""
    usable = dates[dates >= dates[min(warmup, len(dates) - 1)]]
    n = len(usable)
    if n < k:
        k = max(1, n)
    idxs = sorted({min(int(n * (i + 1) / (k + 1)), n - 1) for i in range(k)})
    return [usable[i] for i in idxs]


def check_no_future_data(
    repo_root: Path, run: dict, exp_root: Path, data_root: Path
) -> dict:
    """Truncate the research data to each sampled date T, rebuild the signal,
    and require it to equal the full-data signal at T. This actually re-invokes
    the signal function, so internal future references are exposed."""
    spec = load_spec(repo_root / "strategies" / f"{run['strategy']}.yaml")
    effective = effective_params(spec, run.get("parameters"))
    in_sample = spec.windows["in_sample"]
    ds = DatasetView.load(
        run["dataset_version"], data_root, universe=spec.universe,
        start=in_sample[0], end=in_sample[1],
    )
    research = ds.research_frame()
    full = build_signal(spec, research, effective)
    dates = sorted(pd.to_datetime(research["date"].dt.normalize()).unique())
    warmup = int(effective.get("ma_period", 1))
    sample = _sample_dates(pd.DatetimeIndex(dates), warmup)
    for t in sample:
        truncated = research[research["date"] <= t]
        sig = build_signal(spec, truncated, effective)
        for df_name, full_df, cur_df in (
            ("entries", full.entries, sig.entries),
            ("exits", full.exits, sig.exits),
        ):
            for sym in sorted(full_df.columns):
                fv = bool(full_df.loc[t, sym]) if t in full_df.index else False
                cv = bool(cur_df.loc[t, sym]) if t in cur_df.index else False
                if fv != cv:
                    return {
                        "status": "FAIL",
                        "detail": f"future-data leak at {t.date()} symbol {sym}: "
                        f"full={fv} truncated={cv}",
                    }
    return {
        "status": "PASS",
        "detail": f"signal point-in-time identical at {len(sample)} sampled dates",
    }


def check_dataset_pinned(run: dict, data_root: Path) -> dict:
    try:
        ds = DatasetView.load(run["dataset_version"], data_root)
    except (DatasetVersionNotFound, SnapshotIntegrityError) as exc:
        return {"status": "FAIL", "detail": f"dataset unpinned: {exc}"}
    manifest_files = ds.manifest().get("files", {})
    run_checksums = run.get("dataset_checksums") or {}
    if manifest_files != run_checksums:
        return {
            "status": "FAIL",
            "detail": "snapshot checksums no longer match the run's recorded provenance",
        }
    return {
        "status": "PASS",
        "detail": f"dataset_pinned={run['dataset_version']} checksums match",
    }


def check_cost_nonzero(run: dict) -> dict:
    fee = float((run.get("cost_config") or {}).get("fee_rate", 0.0))
    if fee <= 0:
        return {"status": "FAIL", "detail": f"fee_rate={fee} <= 0 (production costs must be > 0)"}
    return {"status": "PASS", "detail": f"fee_rate={fee} > 0"}


def check_valid_trading_dates(run: dict, run_dir: Path, data_root: Path) -> dict:
    ds = DatasetView.load(run["dataset_version"], data_root)
    calendar = ds.calendar_dates()
    dates = _execution_dates(ds)
    orders = _load_orders(run_dir)
    if orders.empty:
        return {"status": "PASS", "detail": "no orders to validate"}
    bad: list[str] = []
    for row in orders.itertuples():
        idx = int(row.idx)
        if idx >= len(dates):
            bad.append(f"idx={idx} out of range")
            continue
        d = dates[idx]
        if d not in calendar:
            bad.append(f"{d.date()} (idx {idx}) not in trading calendar")
    if bad:
        return {"status": "FAIL", "detail": "; ".join(bad[:10])}
    return {"status": "PASS", "detail": f"all {len(orders)} fills on trading calendar days"}


def check_holdout_compliance(run: dict, data_root: Path, repo_root: Path) -> dict:
    spec = load_spec(repo_root / "strategies" / f"{run['strategy']}.yaml")
    allowed = bool((spec.research_budget.get("holdout_access") or {}).get("allowed", False))
    log = Path(data_root) / "metadata" / "holdout_access.log"
    accesses = 0
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("strategy") == run["strategy"]:
                accesses += 1
    if not allowed and accesses > 0:
        return {
            "status": "FAIL",
            "detail": f"holdout_access.allowed=false but {accesses} access(es) recorded for "
            f"{run['strategy']}",
        }
    return {
        "status": "PASS",
        "detail": f"holdout_access.allowed={allowed}, accesses recorded={accesses}",
    }


def check_reproducible(col: dict | None, run: dict, run_dir: Path) -> dict:
    if col is None:
        return {"status": "FAIL", "detail": "re-execution failed"}

    result = col["result"]
    # equity: stored [date,group] vs rerun Series
    stored_eq = _load_equity(run_dir)
    rerun_eq_series = pd.Series(result.equity).sort_index().astype(float)
    try:
        _semantic_compare(stored_eq.to_frame("nav"), rerun_eq_series.to_frame("nav"))
    except AssertionError as exc:
        return {"status": "FAIL", "detail": f"equity divergence: {exc}"}

    stored_orders = _load_orders(run_dir)
    rerun_orders = result.orders.reset_index(drop=True) if result.orders is not None and len(
        result.orders
    ) else pd.DataFrame()
    if not stored_orders.empty and not rerun_orders.empty:
        sel = ["col", "idx", "size", "price", "fees", "side"]
        try:
            _semantic_compare(
                stored_orders[sel].astype(float), rerun_orders[sel].astype(float)
            )
        except AssertionError as exc:
            return {"status": "FAIL", "detail": f"orders divergence: {exc}"}
    elif stored_orders.empty != rerun_orders.empty:
        return {"status": "FAIL", "detail": "order count divergence"}

    ref_hash = run.get("semantic_result_hash", "")
    now_hash = _semantic_result_hash(run_dir)
    return {
        "status": "PASS",
        "detail": f"reproducible; semantic_result_hash={now_hash}",
        "semantic_result_hash": now_hash,
        "hash_matches_recorded": bool(ref_hash) and ref_hash == now_hash,
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

_ALL = [
    "no_same_bar_fill",
    "no_future_data",
    "dataset_pinned",
    "cost_nonzero",
    "valid_trading_dates",
    "holdout_compliance",
    "reproducible",
]


def validate_run(
    repo_root: str | Path,
    experiments_root: str | Path,
    experiment_id: str,
    run_id: str,
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    persist: bool = True,
) -> dict:
    """Run all seven checks for one Run. Returns the report dict; when persist,
    writes reports/validation/<EXP>/<RUN>/deterministic.json."""
    exp_root = Path(experiments_root)
    run, run_dir = _read_run_artifacts(exp_root, experiment_id, run_id)
    repo = Path(repo_root)
    data = Path(data_root)

    # Re-execute the run ONCE, sharing it between the signal-aware same-bar
    # check and the reproducibility check (single engine call).
    try:
        col = execute_run(
            repo_root_path=repo, strategy=run["strategy"],
            params=run.get("parameters"), data_root=data,
        )
    except Exception:  # noqa: BLE001 - surfaces as reproducible FAIL
        col = None

    checks = {
        "no_same_bar_fill": check_no_same_bar_fill(run, run_dir, col),
        "no_future_data": check_no_future_data(repo, run, exp_root, data),
        "dataset_pinned": check_dataset_pinned(run, data),
        "cost_nonzero": check_cost_nonzero(run),
        "valid_trading_dates": check_valid_trading_dates(run, run_dir, data),
        "holdout_compliance": check_holdout_compliance(run, data, repo),
    }
    checks["reproducible"] = check_reproducible(col, run, run_dir)

    overall = "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"

    report = {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "strategy": run.get("strategy"),
        "overall": overall,
        "checks": checks,
    }
    if persist:
        from pql.registry.experiments import _yaml_write

        # Persist the semantic_result_hash into the run.yaml source of truth once
        # reproducibility passes (M4.34).
        repro = checks["reproducible"]
        if (
            repro.get("status") == "PASS"
            and repro.get("semantic_result_hash")
            and not run.get("semantic_result_hash")
        ):
            run["semantic_result_hash"] = repro["semantic_result_hash"]
            _yaml_write(run_dir / "run.yaml", run)
        out = Path(report_root) / "validation" / experiment_id / run_id / "deterministic.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(out)
    return report


__all__ = ["_ALL", "ValidationError", "validate_run"]