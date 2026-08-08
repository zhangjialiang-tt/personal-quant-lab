"""M7.7 Promotion Gate (plan §M7.7 / M7.48-57).

Full lifecycle gate: IDEA→SPECIFIED→RESEARCH→CANDIDATE→VALIDATED→PAPER→LIVE,
plus LIVE⇄SUSPENDED and any→RETIRED.

Structure (M7.49):
  resolve current state
  → validate target-specific preconditions
  → validate current provenance / code-clean where required
  → lifecycle legality
  → single state transition
  → registry history
  → audit.log

Transition NEVER happens before evidence validation (M7.49): a precondition
failure raises GateError with ZERO mutation (state/history/freeze/audit
unchanged — asserted by regression tests).

RESEARCH→CANDIDATE REUSES the accepted M6 `pql.validation.freeze
.promote_to_candidate` (no duplicate Candidate Freeze). CANDIDATE→VALIDATED
requires a PASS final_report with a CONSUMED holdout bound to the same
candidate_hash. LIVE requires a HUMAN approver (AI has no live-approval
authority, M7.55).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from pql.lifecycle import State, find_strategy, is_legal_transition, transition
from pql.registry.provenance import git_state
from pql.registry.runner import resolve_paths
from pql.schemas import load_cost_model, load_spec
from pql.timing import TimingContract
from pql.validation.freeze import (
    FreezeError,
    compute_freeze_payload,
    promote_to_candidate,
    verify_freeze,
)

# Exact-match blocklist of AI/agent identifiers (M7.55). A human name like "Ali"
# or "Aidan" is NOT matched (no substring rule), so it is never wrongly rejected.
_AI_APPROVERS = frozenset({
    "ai", "a.i.", "agent", "ai agent", "ai-agent", "ai_agent", "agentic",
    "assistant", "bot", "auto", "automation", "claude", "chatgpt", "gpt",
    "llm", "copilot", "codex", "model", "artificial intelligence", "ai system",
    "system ai", "machine learning", "ml",
})


class GateError(RuntimeError):
    """Raised when a promotion precondition fails (state unchanged)."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def is_ai_approver(name: str) -> bool:
    """True when the approver identifier is an obvious AI/agent form (after
    normalization). Exact-match on the whole normalized identifier so ordinary
    human names containing 'ai'/'agent' as substrings are never rejected."""
    if not name or not name.strip():
        return True
    norm = " ".join(name.strip().lower().split())
    return norm in _AI_APPROVERS


def require_human_approver(name: str) -> None:
    if is_ai_approver(name):
        raise GateError(
            f"approver {name!r} is not a recognized human; AI/agent has no "
            "promotion approval authority (M7.55)"
        )


def _gates_data(repo: Path) -> dict[str, Any]:
    return yaml.safe_load((repo / "config" / "validation_gates.yaml").read_text(encoding="utf-8")) or {}


def _code_clean(experiments_root) -> bool:
    return not git_state(experiments_root).code_dirty


def _load_report(report_root: Path, strategy: str, name: str) -> dict | None:
    p = report_root / "validation" / strategy / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def specified_preconditions(repo: Path, spec) -> dict[str, Any]:
    """IDEA -> SPECIFIED: the six frozen requirements (M7.50). StrategySpec has
    no separate `validation_plan` field; the validation plan is the existing
    config/validation_gates.yaml candidate/final policy (per the plan)."""
    checks: dict[str, Any] = {}

    # 1 execution timing
    try:
        TimingContract(
            execution_bar=int(spec.timing.get("execution_bar", 1)),
            execution_price=spec.timing.get("execution_price", "close"),
        ).validate()
        checks["execution_timing"] = True
    except (ValueError, TypeError):
        checks["execution_timing"] = False

    # 2 cost model resolves
    try:
        paths = resolve_paths(repo, spec)
        load_cost_model(paths["cost"])
        checks["cost_model"] = True
    except (OSError, ValueError):
        checks["cost_model"] = False

    # 3 validation plan (gates config exists, candidate/final policies valid)
    try:
        gates = _gates_data(repo)
        cand = gates.get("candidate")
        fin = gates.get("final")
        checks["validation_plan"] = bool(gates.get("version")) and isinstance(cand, dict) \
            and "min_is_sharpe" in cand and isinstance(fin, dict) \
            and "holdout_min_sharpe" in fin
    except (OSError, yaml.YAMLError, ValueError):
        checks["validation_plan"] = False

    # 4 parameter range
    checks["parameter_range"] = bool(spec.param_grid) and any(
        isinstance(v, (list, tuple)) and len(v) > 0 for v in spec.param_grid.values())

    # 5 research budget
    budget = spec.research_budget
    checks["research_budget"] = bool(budget) and budget.get("max_total_selection_runs",
                                                             0) is not None

    # 6 hypothesis
    checks["hypothesis"] = bool(spec.hypothesis and spec.hypothesis.strip())

    checks["overall"] = all(isinstance(v, bool) and v for v in checks.values())
    return checks


def _check_specified(repo: Path, spec) -> dict[str, Any]:
    checks = specified_preconditions(repo, spec)
    if not checks["overall"]:
        failed = [k for k, v in checks.items() if not v]
        raise GateError(f"SPECIFIED preconditions not met: {failed}")
    return checks


def _freeze_block(registry_path, strategy) -> dict | None:
    entry = find_strategy(registry_path, strategy)
    if entry is None:
        return None
    return entry.get("candidate_freeze")


def _check_validated(repo, registry_path, experiments_root, report_root, strategy, spec) -> dict:
    entry = find_strategy(registry_path, strategy)
    if entry is None or entry.get("state") != State.CANDIDATE.value:
        raise GateError("CANDIDATE->VALIDATED requires state CANDIDATE")
    freeze = entry.get("candidate_freeze")
    if not freeze or not isinstance(freeze, dict):
        raise GateError("CANDIDATE->VALIDATED requires a candidate_freeze")
    actual = compute_freeze_payload(repo, experiments_root, spec)
    try:
        verify_freeze(dict(freeze), actual)
    except FreezeError as exc:
        raise GateError(f"CANDIDATE->VALIDATED freeze mismatch: {exc}") from exc
    report = _load_report(report_root, strategy, "final_report")
    if report is None:
        raise GateError("CANDIDATE->VALIDATED requires a final_report")
    if report.get("overall") != "PASS":
        raise GateError(f"CANDIDATE->VALIDATED final_report overall is "
                        f"{report.get('overall')!r}; not PASS")
    if str(report.get("candidate_hash", "")) != str(freeze.get("candidate_hash", "")):
        raise GateError("CANDIDATE->VALIDATED final_report candidate_hash != freeze "
                        "candidate_hash")
    hs = entry.get("holdout_status") or {}
    if not hs.get("consumed"):
        raise GateError("CANDIDATE->VALIDATED requires holdout consumed=true")
    if str(hs.get("candidate_hash", "")) != str(freeze.get("candidate_hash", "")):
        raise GateError("CANDIDATE->VALIDATED holdout_status.candidate_hash != freeze "
                        "candidate_hash")
    if not _code_clean(experiments_root):
        raise GateError("CANDIDATE->VALIDATED requires clean code")
    return {"candidate_freeze": freeze, "final_report": report, "holdout_status": hs}


def _paper_report(report_root: Path, strategy: str) -> dict | None:
    p = report_root / "paper" / strategy / "paper_report.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return None


def _check_paper(repo, registry_path, experiments_root, report_root, strategy, spec, freeze,
                 paper_dir: Path | None = None) -> None:
    if freeze is None:
        raise GateError("VALIDATED->PAPER requires a valid candidate freeze")
    actual = compute_freeze_payload(repo, experiments_root, spec)
    try:
        verify_freeze(dict(freeze), actual)
    except FreezeError as exc:
        raise GateError(f"VALIDATED->PAPER freeze mismatch: {exc}") from exc
    if not _code_clean(experiments_root):
        raise GateError("VALIDATED->PAPER requires clean code")
    report = _paper_report(report_root, strategy)
    if report is None:
        raise GateError("VALIDATED->PAPER requires a paper_report")
    if report.get("overall") != "PASS":
        raise GateError(f"VALIDATED->PAPER paper gate overall is {report.get('overall')!r}; not PASS")
    # provenance must match the strategy/freeze/risk policy
    prov = report.get("provenance") or {}
    if str(prov.get("candidate_hash", "")) != str(freeze.get("candidate_hash", "")):
        raise GateError("VALIDATED->PAPER paper_report candidate_hash != freeze candidate_hash")
    if prov.get("market_rule_version") != spec.market_rule_version:
        raise GateError("VALIDATED->PAPER paper_report market_rule_version mismatch")
    # the report must not be stale relative to the CURRENT PaperAccount state
    # (review P1-2): recompute the fingerprint from the live account and compare.
    if paper_dir is not None:
        from pql.execution.paper import PaperAccount
        from pql.execution.report import paper_state_fingerprint

        account = PaperAccount(strategy, paper_dir)
        current = paper_state_fingerprint(account)
        recorded = report.get("paper_state_fingerprint", "")
        if not recorded or current != recorded:
            raise GateError(
                "VALIDATED->PAPER paper_report is stale: PaperAccount state does not "
                "match the report's paper_state_fingerprint; regenerate the report"
            )


def promote(
    repo_root: str | Path,
    strategy: str,
    to_state: str,
    approver: str,
    reason: str,
    *,
    registry_path: str | Path = "strategy_registry.yaml",
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    data_root: str | Path = "data",
) -> dict[str, Any]:
    """Run the promotion gate for a single state transition. All preconditions
    are validated BEFORE any mutation; a failure raises GateError with state and
    history unchanged."""
    repo = Path(repo_root)
    entry = find_strategy(registry_path, strategy)
    if entry is None:
        raise GateError(f"strategy not registered: {strategy}")
    current = State(entry["state"])
    target = State(to_state)
    if not is_legal_transition(current, target):
        raise GateError(f"illegal transition {strategy}: {current.value} -> {target.value}")

    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    evidence = f"strategies/{strategy}.yaml"

    if target == State.SPECIFIED:
        _check_specified(repo, spec)
    elif target == State.RESEARCH:
        _check_specified(repo, spec)  # spec + six requirements still valid (M7.51)
    elif target == State.CANDIDATE:
        # reuses the accepted M6 candidate freeze promotion (zero-holdout reads)
        try:
            return promote_to_candidate(
                repo_root, strategy, approver=approver, reason=reason,
                registry_path=registry_path, report_root=report_root,
                experiments_root=experiments_root, data_root=data_root)
        except FreezeError as exc:
            raise GateError(str(exc)) from exc
    elif target == State.VALIDATED:
        _check_validated(repo, registry_path, experiments_root, report_root, strategy, spec)
    elif target == State.PAPER:
        freeze = _freeze_block(registry_path, strategy)
        _check_paper(repo, registry_path, experiments_root, report_root, strategy, spec,
                     freeze, paper_dir=Path(data_root) / "paper")
    elif target == State.LIVE:
        require_human_approver(approver)
        freeze = _freeze_block(registry_path, strategy)
        _check_paper(repo, registry_path, experiments_root, report_root, strategy, spec,
                     freeze, paper_dir=Path(data_root) / "paper")
    elif target in (State.RETIRED,) or target == State.SUSPENDED:
        require_human_approver(approver)
    else:
        raise GateError(f"unsupported target state: {to_state}")

    # single transition (registry history + audit.log)
    return transition(registry_path, strategy, target, reason=reason,
                      evidence=evidence, approver=approver)


__all__ = [
    "GateError",
    "is_ai_approver",
    "promote",
    "require_human_approver",
    "specified_preconditions",
]