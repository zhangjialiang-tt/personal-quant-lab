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

from pql.lifecycle import find_strategy
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


# Reproducible strategy implementation scope: the `src/` package that produces
# the strategy's signals/backtests. Config/spec files (config/, strategies/)
# are individually bound by their own hashes (spec_sha256, gate/cost/market/
# instrument hashes), so they are NOT re-hashed here. Evidence outputs
# (reports/, experiments/) are not part of the code tree, so an evidence-only
# commit never changes code_tree_sha256 (a whole-HEAD code_commit would — that
# is the self-invalidation the reviewer flagged).
_CODE_SCOPE = ("src",)


def code_tree_sha256(repo_root: str | Path) -> str:
    """SHA256 over the strategy implementation code tree (`src/`, .py files),
    stable across evidence-only commits. Any change to the strategy code
    (engine/signals/validation/…) changes it."""
    repo = Path(repo_root)
    files: dict[str, str] = {}
    for scope in _CODE_SCOPE:
        base = repo / scope
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix == ".py" and "__pycache__" not in p.parts:
                files[p.relative_to(repo).as_posix()] = _file_sha256(p)
    return _sha256_bytes(_canonical_json(files).encode("utf-8"))


def _binding_payload(repo_root: str | Path, spec) -> dict[str, Any]:
    """The STABLE freeze binding payload (everything that must not change between
    candidate validation and freeze, and must not change after freeze). Evidence
    outputs are excluded. The SAME payload is recorded in the candidate report
    as `validation_fingerprint`, so a freeze can never silently bind an
    environment the candidate was never validated against (review P1-3)."""
    repo = Path(repo_root)
    paths = resolve_paths(repo, spec)
    cfg = config_hashes(
        paths["spec"], paths["gates"], paths["cost"], paths["market"],
        paths["instruments"],
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
    uv_lock = repo / "uv.lock"
    uv_lock_sha = _file_sha256(uv_lock) if uv_lock.exists() else ""

    return {
        "spec_sha256": spec_sha,
        "code_tree_sha256": code_tree_sha256(repo),
        "parameters": dict(effective_params(spec, None)),
        "gate_version": _gate_version(repo),
        "gate_config_sha256": gate_sha,
        "cost_config_sha256": cost_sha,
        "market_rule_sha256": market_sha,
        "instrument_sha256": inst_sha,
        "uv_lock_sha256": uv_lock_sha,
        "dataset_version": spec.dataset_version,
    }


def validation_fingerprint(repo_root: str | Path, spec) -> dict[str, Any]:
    """The stable binding payload the candidate report records at validation
    time and the freeze re-verifies at promotion. Because both sides use the
    identical payload, the freeze can never bind an environment the candidate
    was never validated against."""
    return _binding_payload(Path(repo_root), spec)


def compute_freeze_payload(
    repo_root: str | Path, experiments_root: str | Path, spec
) -> dict[str, Any]:
    """Compute the full freeze fingerprint + candidate_hash for a spec."""
    repo = Path(repo_root)
    binding = _binding_payload(repo, spec)
    code = git_state(experiments_root)
    payload = dict(binding)
    # code_commit is informational provenance (the HEAD at freeze time); it is
    # NOT part of the stability binding, because evidence-only commits bump HEAD
    # without changing the code tree.
    payload["code_commit"] = code.commit
    # candidate_hash binds the STABLE binding payload (which includes the code
    # tree), not the whole-HEAD code_commit, so committing evidence afterwards
    # does not invalidate the freeze.
    candidate_hash = _sha256_bytes(_canonical_json(binding).encode("utf-8"))
    payload["candidate_hash"] = candidate_hash
    payload["created"] = _now()
    return payload


_BIND_KEYS = (
    "spec_sha256", "code_tree_sha256", "parameters", "gate_version",
    "gate_config_sha256", "cost_config_sha256", "market_rule_sha256",
    "instrument_sha256", "uv_lock_sha256", "dataset_version",
)


def verify_report_provenance(report: dict, payload: dict) -> None:
    """The candidate report's `validation_fingerprint` (recorded at validation
    time from the SAME binding payload the freeze uses) must match the current
    environment. Because both sides use the identical binding payload, every
    field (spec, code tree, params, gate, cost, market, instrument, uv.lock,
    dataset) is covered — no per-field checklist to forget (review P1-3)."""
    vf = report.get("validation_fingerprint")
    if not isinstance(vf, dict):
        raise FreezeError(
            "candidate report missing validation_fingerprint; "
            "regenerate the report before freezing"
        )
    for k in _BIND_KEYS:
        if vf.get(k) != payload.get(k):
            raise FreezeError(
                f"candidate report validation_fingerprint.{k} does not match the "
                "current environment; regenerate the report before freezing"
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

    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    payload = compute_freeze_payload(repo, experiments_root, spec)
    verify_report_provenance(report, payload)

    # Re-check the CURRENT clean state (not the stale report flag): a worktree
    # that became dirty after validation must refuse the freeze (D9
    # require_code_clean). Evidence-only reports//experiments/ are outside the
    # dirty scope, so this does not reintroduce evidence self-invalidation.
    current_code = git_state(experiments_root)
    if current_code.code_dirty:
        raise FreezeError("current code is dirty; candidate freeze refused")

    # Single atomic registry mutation: RESEARCH -> CANDIDATE + history +
    # candidate_freeze in ONE write (review P2-5), so a crash cannot leave
    # state=CANDIDATE without a candidate_freeze block.
    from pql import lifecycle as _lc

    reg_path = Path(registry_path)
    registry = _lc._load_registry(reg_path)
    entry = next((e for e in registry["strategies"] if e.get("id") == strategy), None)
    if entry is None:
        raise FreezeError(f"strategy not registered: {strategy}")
    if entry.get("state") != "RESEARCH":
        raise FreezeError(
            f"candidate freeze requires state RESEARCH, got {entry.get('state')}"
        )
    if not _lc.is_legal_transition(_lc.State("RESEARCH"), _lc.State("CANDIDATE")):
        raise FreezeError("illegal transition RESEARCH -> CANDIDATE")
    hist_entry = {
        "from": "RESEARCH",
        "to": "CANDIDATE",
        "time": _lc._now(),
        "reason": reason,
        "evidence": str(report_path),
        "approver": approver,
    }
    entry["history"] = list(entry["history"]) + [hist_entry]
    entry["state"] = "CANDIDATE"
    entry["candidate_freeze"] = {k: v for k, v in payload.items()}
    _lc._write_registry(reg_path, registry)
    _lc._append_audit(reg_path, {"strategy_id": strategy, **hist_entry})
    return {"strategy": strategy, "candidate_freeze": payload}


def verify_freeze(freeze: dict, actual: dict) -> None:
    """Verify a stored freeze against the current fingerprint. ANY mismatch on
    a frozen item raises FreezeError ('Frozen candidate changed'). Component
    keys are checked first for a precise message, then the aggregate
    candidate_hash last. `code_commit` (whole HEAD) is intentionally NOT a
    binding key: evidence-only commits bump HEAD without changing the code."""
    for key in (
        "spec_sha256", "code_tree_sha256", "parameters", "gate_config_sha256",
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
    "code_tree_sha256",
    "compute_freeze_payload",
    "promote_to_candidate",
    "validation_fingerprint",
    "verify_freeze",
]