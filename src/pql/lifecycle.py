"""D6 strategy lifecycle state machine + registry + audit log.

States: IDEA → SPECIFIED → RESEARCH → CANDIDATE → VALIDATED → PAPER → LIVE,
plus LIVE ⇄ SUSPENDED and any → RETIRED. Illegal transitions raise LifecycleError.
Every transition appends to strategy_registry.yaml history and reports/audit.log.
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path

import yaml


class LifecycleError(ValueError):
    """Raised for an illegal state transition."""


class RegistryError(ValueError):
    """Raised when a strategy is missing or the registry is malformed."""


class State(str, Enum):
    IDEA = "IDEA"
    SPECIFIED = "SPECIFIED"
    RESEARCH = "RESEARCH"
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    PAPER = "PAPER"
    LIVE = "LIVE"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


# D6 legal transition table (hard-coded). `any -> RETIRED` is applied via the
# generic clause below; specific edges are enumerated here.
_EDGES: dict[State, frozenset[State]] = {
    State.IDEA: frozenset({State.SPECIFIED}),
    State.SPECIFIED: frozenset({State.RESEARCH}),
    State.RESEARCH: frozenset({State.CANDIDATE}),
    State.CANDIDATE: frozenset({State.VALIDATED}),
    State.VALIDATED: frozenset({State.PAPER}),
    State.PAPER: frozenset({State.LIVE}),
    State.LIVE: frozenset({State.SUSPENDED}),
    State.SUSPENDED: frozenset({State.LIVE}),
    State.RETIRED: frozenset(),
}

_RETIRED = frozenset({State.RETIRED})


def _targets(state: State) -> frozenset[State]:
    return _EDGES[state] | _RETIRED


def is_legal_transition(_from: State, to: State) -> bool:
    return to in _targets(_from)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _audit_path(registry_path: str | Path) -> Path:
    return Path(registry_path).parent / "reports" / "audit.log"


def _load_registry(registry_path: str | Path) -> dict:
    path = Path(registry_path)
    if not path.exists():
        return {"strategies": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "strategies" not in data:
        raise RegistryError(f"{registry_path}: malformed registry (missing `strategies`)")
    return data


def _write_registry(registry_path: str | Path, registry: dict) -> None:
    Path(registry_path).write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _append_audit(registry_path: str | Path, record: dict) -> None:
    dest = _audit_path(registry_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def find_strategy(registry_path: str | Path, strategy_id: str) -> dict | None:
    registry = _load_registry(registry_path)
    for entry in registry["strategies"]:
        if entry.get("id") == strategy_id:
            return entry
    return None


def register_strategy(
    registry_path: str | Path,
    strategy_id: str,
    approver: str,
    reason: str = "registered",
    evidence: str = "",
) -> dict:
    """Create a strategy entry at state IDEA. Raises RegistryError if it exists."""
    if find_strategy(registry_path, strategy_id) is not None:
        raise RegistryError(f"strategy already registered: {strategy_id}")
    registry = _load_registry(registry_path)
    hist_entry = {
        "from": None,
        "to": State.IDEA.value,
        "time": _now(),
        "reason": reason,
        "evidence": evidence,
        "approver": approver,
    }
    entry = {
        "id": strategy_id,
        "state": State.IDEA.value,
        "created": _now(),
        "history": [hist_entry],
    }
    registry["strategies"].append(entry)
    _write_registry(registry_path, registry)
    _append_audit(registry_path, {"strategy_id": strategy_id, **hist_entry})
    return entry


def transition(
    registry_path: str | Path,
    strategy_id: str,
    to: str | State,
    reason: str,
    evidence: str,
    approver: str,
) -> dict:
    """Validate and apply a state transition, appending to registry history and
    reports/audit.log. `_from` is derived from the strategy's current state."""
    target = State(to)
    entry = find_strategy(registry_path, strategy_id)
    if entry is None:
        raise RegistryError(f"strategy not registered: {strategy_id}")
    current = State(entry["state"])
    if not is_legal_transition(current, target):
        raise LifecycleError(
            f"illegal transition {strategy_id}: {current.value} -> {target.value}"
        )

    hist_entry = {
        "from": current.value,
        "to": target.value,
        "time": _now(),
        "reason": reason,
        "evidence": evidence,
        "approver": approver,
    }
    entry["history"] = list(entry["history"]) + [hist_entry]
    entry["state"] = target.value

    registry = _load_registry(registry_path)
    for i, item in enumerate(registry["strategies"]):
        if item.get("id") == strategy_id:
            registry["strategies"][i] = entry
            break
    _write_registry(registry_path, registry)
    _append_audit(registry_path, {"strategy_id": strategy_id, **hist_entry})
    return entry