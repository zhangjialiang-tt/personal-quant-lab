"""M4 Experiment Registry (D7 / M4.1). Frozen data model:

    Strategy -> Experiment -> Run

An Experiment is a research question / hypothesis-validation task (NOT one
backtest). It holds multiple Runs. The manifest + run.yaml files under
`experiments/EXP-NNNN/` are the SOURCE OF TRUTH; `experiment_registry.parquet`
is a DERIVED index rebuilt by `pql registry rebuild`.

RunKind and selection_key are hard contracts (M4.8/M4.9). effective_trial_count
= COUNT(DISTINCT selection_key across the strategy lineage) where run_kind==
SELECT — the SAME fact source used by the research budget.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .provenance import GitState

_EXP_RE = re.compile(r"^EXP-(\d{4})$")
_RUN_RE = re.compile(r"^RUN-(\d{5})$")
_LINEAGE_RE = re.compile(r"^(.*?)(?:_v\d+)?$")
_RUN_KINDS = frozenset({"SELECT", "EVALUATE", "STRESS", "DIAGNOSTIC", "FINAL_HOLDOUT"})
_DECISIONS = frozenset({"PENDING", "ACCEPTED", "REJECTED"})


class ExperimentError(RuntimeError):
    """Raised for any registry / experiment / run inconsistency."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _yaml_write(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _yaml_read(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ExperimentError(f"{path}: expected a YAML mapping")
    return data


# --------------------------------------------------------------------------- #
# selection_key + lineage (M4.9 / M4.11)
# --------------------------------------------------------------------------- #


def _canon_val(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps({k: _canon_val(v) for k, v in sorted(value.items())},
                          sort_keys=True, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return json.dumps([_canon_val(v) for v in value], sort_keys=True, separators=(",", ":"))
    return str(value)


def selection_key(params: dict[str, Any]) -> str:
    """Canonical, dict-order-independent key for a SELECT candidate config.

    Same params -> same key; dict key order changes -> same key; different
    params -> different key. Readable form: `ma_period=200` (D7 example).
    """
    items = sorted((str(k), _canon_val(v)) for k, v in params.items())
    return ";".join(f"{k}={v}" for k, v in items)


def lineage_root(strategy_id: str) -> str:
    """Lineage = strategy family ignoring the `_vN` edition suffix.

    etf_trend_v1 / etf_trend_v2 / etf_trend_v3 share the `etf_trend` lineage, so
    Research Budget and DSR de-dup across versions (D7/A6). A strategy with no
    `_vN` suffix is its own lineage.
    """
    m = _LINEAGE_RE.match(strategy_id)
    return m.group(1) if m else strategy_id


# --------------------------------------------------------------------------- #
# Experiment manifest
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    strategy: str
    research_question: str
    experiment_config: dict[str, Any] = field(default_factory=dict)
    decision: str = "PENDING"
    reason: str = ""
    decision_time: str | None = None
    created: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def next_experiment_id(experiments_root: str | Path) -> str:
    """Next EXP-NNNN = max existing + 1, zero-padded to 4 digits."""
    root = Path(experiments_root)
    mx = 0
    if root.exists():
        for p in root.iterdir():
            m = _EXP_RE.match(p.name)
            if m and p.is_dir():
                mx = max(mx, int(m.group(1)))
    return f"EXP-{mx + 1:04d}"


def write_manifest(
    experiments_root: str | Path,
    *,
    experiment_id: str,
    strategy: str,
    research_question: str = "",
    experiment_config: dict[str, Any] | None = None,
) -> Path:
    """Create an Experiment manifest (does NOT run a backtest)."""
    if not _EXP_RE.match(experiment_id):
        raise ExperimentError(f"invalid experiment id: {experiment_id}")
    exp_dir = Path(experiments_root) / experiment_id
    manifest_path = exp_dir / "manifest.yaml"
    if manifest_path.exists():
        raise ExperimentError(f"experiment already exists: {experiment_id}")
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        strategy=strategy,
        research_question=research_question,
        experiment_config=dict(experiment_config or {}),
        decision="PENDING",
        reason="",
        decision_time=None,
        created=_now(),
    )
    _yaml_write(manifest_path, manifest.as_dict())
    return manifest_path


def load_manifest(experiments_root: str | Path, experiment_id: str) -> dict:
    path = Path(experiments_root) / experiment_id / "manifest.yaml"
    if not path.exists():
        raise ExperimentError(f"experiment not found: {experiment_id}")
    return _yaml_read(path)


def decide_experiment(
    experiments_root: str | Path,
    experiment_id: str,
    decision: str,
    reason: str,
) -> dict:
    """Record ACCEPTED/REJECTED (+ reason + decision_time). Never deletes."""
    decision = decision.upper()
    if decision not in _DECISIONS:
        raise ExperimentError(f"decision must be one of {sorted(_DECISIONS)}, got {decision}")
    manifest = load_manifest(experiments_root, experiment_id)
    if decision == "PENDING" and not reason:
        reason = manifest.get("reason", "")
    manifest.update(
        {
            "decision": decision,
            "reason": reason,
            "decision_time": _now(),
        }
    )
    path = Path(experiments_root) / experiment_id / "manifest.yaml"
    _yaml_write(path, manifest)
    return manifest


# --------------------------------------------------------------------------- #
# Run record
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    experiment_id: str
    strategy: str
    parameters: dict[str, Any]
    selection_key: str
    run_kind: str
    visible_to_researcher: bool
    dataset_version: str
    dataset_checksums: dict[str, str]
    market_rule_version: str
    cost_model_version: str
    cost_config: dict[str, Any]
    gate_version: str
    code_commit: str
    code_dirty: bool
    git_diff_sha256: str
    config_sha256: str
    dependencies: dict[str, str]
    seed: int
    timing: dict[str, Any]
    metrics: dict[str, float]
    created: str = ""

    @property
    def run_dir(self) -> Path:
        raise NotImplementedError

    def as_dict(self) -> dict:
        return asdict(self)


def next_run_id(experiments_root: str | Path, experiment_id: str) -> str:
    """Next RUN-NNNNN within an experiment = max existing + 1, padded to 5."""
    runs_dir = Path(experiments_root) / experiment_id / "runs"
    mx = 0
    if runs_dir.exists():
        for p in runs_dir.iterdir():
            m = _RUN_RE.match(p.name)
            if m and p.is_dir():
                mx = max(mx, int(m.group(1)))
    return f"RUN-{mx + 1:05d}"


def write_run(
    experiments_root: str | Path,
    *,
    experiment_id: str,
    strategy: str,
    parameters: dict[str, Any],
    selection_key: str,
    run_kind: str,
    visible_to_researcher: bool,
    dataset_version: str,
    dataset_checksums: dict[str, str],
    market_rule_version: str,
    cost_model_version: str,
    cost_config: dict[str, Any],
    gate_version: str,
    gate: GitState,
    config_sha256: str,
    dependencies: dict[str, str],
    seed: int,
    timing: dict[str, Any],
    metrics: dict[str, float],
    equity: Any,
    orders: Any,
) -> Path:
    """Write a full Run: run.yaml + equity.parquet + orders.parquet +
    metrics.json + (if dirty) git_diff.patch. Returns the run directory."""
    run_kind = run_kind.upper()
    if run_kind not in _RUN_KINDS:
        raise ExperimentError(f"run_kind must be one of {sorted(_RUN_KINDS)}, got {run_kind}")
    if gate.code_dirty:
        if not gate.patch:
            raise ExperimentError(
                "code_dirty cannot be recorded without a reproducible patch; "
                "refusing to write a non-reproducible run"
            )
        if not gate.patch_sha256:
            raise ExperimentError("dirty run missing git_diff_sha256")

    exp_dir = Path(experiments_root) / experiment_id
    if not (exp_dir / "manifest.yaml").exists():
        raise ExperimentError(f"experiment not found: {experiment_id}")
    run_id = next_run_id(experiments_root, experiment_id)
    run_dir = exp_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    record = RunRecord(
        run_id=run_id,
        experiment_id=experiment_id,
        strategy=strategy,
        parameters=dict(parameters),
        selection_key=selection_key,
        run_kind=run_kind,
        visible_to_researcher=visible_to_researcher,
        dataset_version=dataset_version,
        dataset_checksums=dict(dataset_checksums),
        market_rule_version=market_rule_version,
        cost_model_version=cost_model_version,
        cost_config=dict(cost_config),
        gate_version=gate_version,
        code_commit=gate.commit,
        code_dirty=gate.code_dirty,
        git_diff_sha256=gate.patch_sha256,
        config_sha256=config_sha256,
        dependencies=dict(dependencies),
        seed=seed,
        timing=dict(timing),
        metrics=dict(metrics),
        created=_now(),
    )
    _yaml_write(run_dir / "run.yaml", record.as_dict())

    eq = equity
    if isinstance(eq, pd.DataFrame) and "date" in eq.columns and eq.columns.tolist() != ["date"]:
        eq = eq.set_index("date").iloc[:, 0]
    eq = pd.Series(eq)
    eq = eq.rename("nav").rename_axis("date")
    eq.reset_index().to_parquet(run_dir / "equity.parquet", index=False)
    if orders is not None and len(orders):
        orders.reset_index(drop=True).to_parquet(run_dir / "orders.parquet", index=False)
    else:
        pd.DataFrame().to_parquet(run_dir / "orders.parquet", index=False)
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if gate.code_dirty:
        (run_dir / "git_diff.patch").write_text(gate.patch, encoding="utf-8")
    return run_dir


def load_run(experiments_root: str | Path, experiment_id: str, run_id: str) -> dict:
    path = Path(experiments_root) / experiment_id / "runs" / run_id / "run.yaml"
    if not path.exists():
        raise ExperimentError(f"run not found: {experiment_id}/{run_id}")
    return _yaml_read(path)


def iter_experiments(experiments_root: str | Path) -> list[dict]:
    """All experiment manifests, sorted by id."""
    root = Path(experiments_root)
    out: list[dict] = []
    if not root.exists():
        return out
    for p in sorted(root.iterdir()):
        if _EXP_RE.match(p.name) and p.is_dir():
            mp = p / "manifest.yaml"
            if mp.exists():
                out.append(_yaml_read(mp))
    return out


def iter_runs(experiments_root: str | Path, experiment_id: str) -> list[dict]:
    exp_dir = Path(experiments_root) / experiment_id
    runs_dir = exp_dir / "runs"
    out: list[dict] = []
    if not runs_dir.exists():
        return out
    for p in sorted(runs_dir.iterdir()):
        if _RUN_RE.match(p.name) and p.is_dir():
            rp = p / "run.yaml"
            if rp.exists():
                out.append(_yaml_read(rp))
    return out


def iter_all_runs(experiments_root: str | Path) -> list[tuple[dict, dict]]:
    """[(experiment_manifest, run_record)] across every experiment."""
    out: list[tuple[dict, dict]] = []
    for exp in iter_experiments(experiments_root):
        for run in iter_runs(experiments_root, exp["experiment_id"]):
            out.append((exp, run))
    return out


# --------------------------------------------------------------------------- #
# effective_trial_count / ledger (M4.10)
# --------------------------------------------------------------------------- #


def effective_trial_count(experiments_root: str | Path, strategy_id: str) -> int:
    """N = COUNT(DISTINCT selection_key across the strategy lineage) where
    run_kind == SELECT. Non-SELECT runs and duplicate keys never add to N."""
    root = lineage_root(strategy_id)
    keys: set[str] = set()
    for _exp, run in iter_all_runs(experiments_root):
        if run.get("run_kind") != "SELECT":
            continue
        if lineage_root(run.get("strategy", "")) != root:
            continue
        sk = run.get("selection_key")
        if sk:
            keys.add(sk)
    return len(keys)


def select_run_keys(experiments_root: str | Path, strategy_id: str) -> set[str]:
    """All SELECT selection_keys across the lineage (budget's fact source)."""
    root = lineage_root(strategy_id)
    keys: set[str] = set()
    for _exp, run in iter_all_runs(experiments_root):
        if run.get("run_kind") != "SELECT":
            continue
        if lineage_root(run.get("strategy", "")) != root:
            continue
        sk = run.get("selection_key")
        if sk:
            keys.add(sk)
    return keys


def param_variant_counts(experiments_root: str | Path, strategy_id: str) -> dict[str, set[str]]:
    """Per param key, the set of distinct values seen across SELECT runs."""
    root = lineage_root(strategy_id)
    counts: dict[str, set[str]] = {}
    for _exp, run in iter_all_runs(experiments_root):
        if run.get("run_kind") != "SELECT":
            continue
        if lineage_root(run.get("strategy", "")) != root:
            continue
        for k, v in (run.get("parameters") or {}).items():
            counts.setdefault(str(k), set()).add(_canon_val(v))
    return counts


# --------------------------------------------------------------------------- #
# Derived registry parquet (M4.22)
# --------------------------------------------------------------------------- #


def rebuild_registry(experiments_root: str | Path, out_path: str | Path) -> pd.DataFrame:
    """Scan the source of truth (manifest.yaml + run.yaml) and regenerate the
    derived parquet index. Deleting the parquet and rebuilding must yield an
    equivalent index — the parquet is never needed to rebuild itself."""
    rows: list[dict[str, Any]] = []
    for exp, run in iter_all_runs(experiments_root):
        rows.append(
            {
                "experiment_id": exp["experiment_id"],
                "strategy": exp["strategy"],
                "research_question": exp.get("research_question", ""),
                "decision": exp.get("decision", "PENDING"),
                "reason": exp.get("reason", ""),
                "decision_time": exp.get("decision_time"),
                "run_id": run["run_id"],
                "run_kind": run["run_kind"],
                "selection_key": run["selection_key"],
                "parameters": json.dumps(run.get("parameters", {}), sort_keys=True),
                "visible_to_researcher": run["visible_to_researcher"],
                "dataset_version": run["dataset_version"],
                "code_commit": run["code_commit"],
                "code_dirty": run["code_dirty"],
                "config_sha256": run.get("config_sha256", ""),
                "metrics_json": json.dumps(run.get("metrics", {}), sort_keys=True),
                "created": run["created"],
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["experiment_id", "run_id"]).reset_index(drop=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


def load_registry(out_path: str | Path) -> pd.DataFrame:
    """Load the derived parquet index (optimized read; not a fact source)."""
    path = Path(out_path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)