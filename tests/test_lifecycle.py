"""M1 tests: lifecycle state machine, legal/illegal transitions, history + audit."""
from __future__ import annotations

import json

import pytest

from pql.lifecycle import (
    LifecycleError,
    RegistryError,
    State,
    find_strategy,
    is_legal_transition,
    register_strategy,
    transition,
)


@pytest.fixture
def registry_path(tmp_path):
    return tmp_path / "strategy_registry.yaml"


def _audit_path(registry_path):
    return registry_path.parent / "reports" / "audit.log"


def test_register_creates_idle_entry(registry_path):
    entry = register_strategy(registry_path, "etf_trend_v1", approver="zhangjl")
    assert entry["state"] == State.IDEA.value
    assert len(entry["history"]) == 1
    assert entry["history"][0]["to"] == "IDEA"
    assert entry["history"][0]["from"] is None
    assert entry["history"][0]["approver"] == "zhangjl"


def test_register_duplicate_rejected(registry_path):
    register_strategy(registry_path, "s", approver="a")
    with pytest.raises(RegistryError):
        register_strategy(registry_path, "s", approver="a")


def test_full_chain_legal(registry_path):
    register_strategy(registry_path, "s", approver="a")
    chain = [
        State.SPECIFIED, State.RESEARCH, State.CANDIDATE,
        State.VALIDATED, State.PAPER, State.LIVE, State.SUSPENDED, State.LIVE,
    ]
    for to in chain:
        transition(registry_path, "s", to, reason="r", evidence="e", approver="a")
    assert find_strategy(registry_path, "s")["state"] == State.LIVE.value


def test_illegal_transition_rejected(registry_path):
    register_strategy(registry_path, "s", approver="a")
    with pytest.raises(LifecycleError):
        transition(registry_path, "s", State.RESEARCH, reason="r", evidence="e", approver="a")


def test_retired_from_any_state(registry_path):
    register_strategy(registry_path, "s", approver="a")
    # walk IDEA -> SPECIFIED -> RESEARCH legally, then RETIRED from RESEARCH
    transition(registry_path, "s", State.SPECIFIED, reason="r", evidence="e", approver="a")
    transition(registry_path, "s", State.RESEARCH, reason="r", evidence="e", approver="a")
    transition(registry_path, "s", State.RETIRED, reason="r", evidence="e", approver="a")
    assert find_strategy(registry_path, "s")["state"] == State.RETIRED.value
    # RETIRED is terminal: no further transitions inc. back to LIVE
    with pytest.raises(LifecycleError):
        transition(registry_path, "s", State.LIVE, reason="r", evidence="e", approver="a")


def test_history_appended_with_fields(registry_path):
    register_strategy(registry_path, "s", approver="a")
    transition(registry_path, "s", State.SPECIFIED, reason="spec complete",
               evidence="strategies/s.yaml", approver="zhangjl")
    entry = find_strategy(registry_path, "s")
    assert len(entry["history"]) == 2
    last = entry["history"][-1]
    assert last["from"] == "IDEA"
    assert last["to"] == "SPECIFIED"
    assert last["reason"] == "spec complete"
    assert last["evidence"] == "strategies/s.yaml"
    assert last["approver"] == "zhangjl"
    assert "time" in last


def test_audit_log_appended(registry_path):
    register_strategy(registry_path, "s", approver="a")
    transition(registry_path, "s", State.SPECIFIED, reason="r", evidence="e", approver="a")
    lines = _audit_path(registry_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # registration + transition
    rec = json.loads(lines[-1])
    assert rec["strategy_id"] == "s"
    assert rec["from"] == "IDEA"
    assert rec["to"] == "SPECIFIED"


def test_transition_unregistered_rejected(registry_path):
    with pytest.raises(RegistryError):
        transition(registry_path, "ghost", State.SPECIFIED, reason="r", evidence="e", approver="a")


def test_is_legal_transition_table():
    # spot-check the hard-coded legal table + any->RETIRED
    assert is_legal_transition(State.IDEA, State.SPECIFIED)
    assert is_legal_transition(State.LIVE, State.SUSPENDED)
    assert is_legal_transition(State.CANDIDATE, State.RETIRED)
    assert not is_legal_transition(State.IDEA, State.RESEARCH)
    assert not is_legal_transition(State.RETIRED, State.LIVE)