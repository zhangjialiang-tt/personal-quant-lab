"""M6.7 Candidate Freeze (D6). The narrow RESEARCH -> CANDIDATE promotion path.

Candidate Freeze locks spec hash, code commit, parameter set, gate version +
versioned-config hashes, uv.lock and dataset version into the registry's
`candidate_freeze` block. `candidate_hash` binds ALL of them (a canonical,
key-sorted, UTF-8 serialization hashed with SHA256) — it is NOT just spec_sha256.

Freeze is EXPLICIT only (`pql gate promote --to CANDIDATE`), never automatic
after `pql validate candidate`. A candidate that fails any gate, has dirty code,
or a stale report is refused (FreezeError). Once frozen, any change to the
frozen payload requires a NEW strategy version; the freeze is never auto-updated.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pql.lifecycle import LifecycleError, find_strategy, transition
from pql.registry.provenance import config_hashes, git_state
from pql.registry.runner import resolve_paths
from pql.schemas import load_spec
from pql.signals.registry import effective_params


class FreezeError(RuntimeError):
    """Raised when candidate freeze preconditions are not met."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _canonical_json(data: Any) -> str:
    """Stable canonical serialization: sort keys, compact separators, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _gate_version(repo_root: Path) -> str:
    import yaml

    data = yaml.safe_load((repo_root / "config" / "validation_gates.yaml").read_text(encoding="utf-8")) or {}
    return str(data.get("version", ""))


def compute_freeze_payload(
    repo_root: str | Path, experiments_root: str | Path, spec
) -> dict[str, Any]:
    """Compute the full freeze fingerprint + candidate_hash for a spec."""
    repo = Path(repo_root)
    paths = resolve_paths(repo, spec)
    cfg = config_hashes(
        paths["spec"], paths["gates"], paths["cost"], paths["market"], paths["instruments"]
    )
    per_file = cfg["per_file"]
    spec_sha = per_file.get(str(paths["spec"]), "")
    gate_sha = per_file.get(str(paths["gates"]), "")
    cost_sha = per_file.get(str(paths["cost"]), "")
    market_sha = per_file.get(str(paths["market"]), "")

    inst_map = {
        p.split("instruments")[-1].lstrip("/\\"): sha
        for p, sha in per_file.items()
        if "instruments" in p
    }
    inst_sha = _sha256_bytes(_canonical_json(inst_map).encode("utf-8"))

    code = git_state(experiments_root)
    uv_lock = repo / "uv.lock"
    uv_lock_sha = _file_sha256(uv_lock) if uv_lock.exists() else ""

    payload = {
        "spec_sha256": spec_sha,
        "code_commit": code.commit,
        "parameters": dict(effective_params(spec, None)),
        "gate_version": _gate_version(repo),
        "gate_config_sha256": gate_sha,
        "cost_config_sha256": cost_sha,
        "market_rule_sha256": market_sha,
        "instrument_sha256": inst_sha,
        "uv_lock_sha256": uv_lock_sha,
        "dataset_version": spec.dataset_version,
    }
    candidate_hash = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
    payload["candidate_hash"] = candidate_hash
    payload["created"] = _now()
    return payload


def verify_report_provenance(report: dict, payload: dict) -> None:
    """The candidate report's recorded config hashes must match the CURRENT
    frozen files (a stale report is refused)."""
    if report.get("code_commit") != payload.get("code_commit"):
        raise FreezeError(
            "candidate report code_commit does not match current HEAD; "
            "regenerate the candidate report before freezing"
        )
    cfg = report.get("config_hashes") or {}
    spec_path = next((p for p in cfg if "strategies" in p), None)
    if spec_path and cfg.get(spec_path) != payload.get("spec_sha256"):
        raise FreezeError("candidate report spec hash does not match current spec")
    for label, key in (
        ("gate", "gate_config_sha256"),
        ("cost", "cost_config_sha256"),
        ("market", "market_rule_sha256"),
    ):
        match = [
            p for p in cfg if label in p.lower()
        ]
        if match:
            current = cfg.get(match[0])
            if current != payload.get(key):
                raise FreezeError(
                    f"candidate report {label} config hash does not match current files"
                )


def promote_to_candidate(
    repo_root: str | Path,
    strategy: str,
    *,
    approver: str,
    reason: str,
    registry_path: str | Path,
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    data_root: str | Path = "data",
) -> dict[str, Any]:
    """Explicit RESEARCH -> CANDIDATE promotion with Candidate Freeze.

    Preconditions (all must hold, else FreezeError):
        - strategy registered and in state RESEARCH
        - latest candidate_report overall == PASS
        - ready_for_candidate_freeze == true
        - code_dirty == false
        - report provenance still matches the current frozen files
    """
    repo = Path(repo_root)
    entry = find_strategy(registry_path, strategy)
    if entry is None:
        raise FreezeError(f"strategy not registered: {strategy}")
    if entry.get("state") != "RESEARCH":
        raise FreezeError(
            f"candidate freeze requires state RESEARCH, got {entry.get('state')}"
        )
    if not approver or approver in ("ai", "agent"):
        raise FreezeError("candidate freeze requires a human approver")

    report_path = Path(report_root) / "validation" / strategy / "candidate_report.json"
    if not report_path.exists():
        raise FreezeError(f"candidate report not found: {report_path}")
    import json as _json

    report = _json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("overall") != "PASS":
        raise FreezeError(f"candidate overall is {report.get('overall')!r}; not PASS")
    if not report.get("ready_for_candidate_freeze"):
        raise FreezeError("ready_for_candidate_freeze is false; freeze refused")
    if report.get("code_dirty"):
        raise FreezeError("code is dirty; candidate freeze refused")

    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    payload = compute_freeze_payload(repo, experiments_root, spec)
    verify_report_provenance(report, payload)

    # perform the lifecycle transition (RESEARCH -> CANDIDATE)
    try:
        transition(
            registry_path, strategy, "CANDIDATE",
            reason=reason, evidence=str(report_path), approver=approver,
        )
    except LifecycleError as exc:
        raise FreezeError(str(exc)) from exc

    # write the candidate_freeze block into the registry entry
    import yaml

    reg_path = Path(registry_path)
    registry = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {"strategies": []}
    freeze_payload = {k: v for k, v in payload.items()}
    for item in registry.get("strategies", []):
        if item.get("id") == strategy:
            item["candidate_freeze"] = freeze_payload
            break
    reg_path.write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return {"strategy": strategy, "candidate_freeze": freeze_payload}


def verify_freeze(freeze: dict, actual: dict) -> None:
    """Verify a stored freeze against the current fingerprint. ANY mismatch on
    a frozen item raises FreezeError ('Frozen candidate changed'). Component
    keys are checked first for a precise message, then the aggregate
    candidate_hash last."""
    for key in (
        "spec_sha256", "code_commit", "parameters", "gate_config_sha256",
        "cost_config_sha256", "market_rule_sha256", "instrument_sha256",
        "uv_lock_sha256", "dataset_version",
    ):
        if freeze.get(key) != actual.get(key):
            raise FreezeError(
                f"Frozen candidate changed ({key}). Create a new strategy version."
            )
    if freeze.get("candidate_hash") != actual.get("candidate_hash"):
        raise FreezeError(
            "Frozen candidate changed (candidate_hash). Create a new strategy version."
        )


__all__ = [
    "FreezeError",
    "compute_freeze_payload",
    "promote_to_candidate",
    "verify_freeze",
]