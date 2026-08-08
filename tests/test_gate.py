"""M7.69 promotion gate tests: per-state precondition failures all reject with
ZERO mutation (state/history/freeze/audit unchanged), plus LIVE human-approver
enforcement."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pql.gate import GateError, is_ai_approver, promote
from pql.lifecycle import find_strategy, register_strategy
from tests.final_fixture import make_final_momentum_repo, run_candidate_pass


def _audit(registry_path) -> list[dict]:
    p = Path(registry_path).parent / "reports" / "audit.log"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _state(registry_path, strategy) -> str:
    return find_strategy(registry_path, strategy)["state"]


def _history_len(registry_path, strategy) -> int:
    return len(find_strategy(registry_path, strategy)["history"])


def _snapshot(registry_path, strategy):
    return (_state(registry_path, strategy), _history_len(registry_path, strategy),
            len(_audit(registry_path)))


def _rewrite_spec(root, strategy, old, new):
    p = root / "strategies" / f"{strategy}.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


# --------------------------------------------------------------------------- #
# IDEA -> SPECIFIED
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def idea_repo(tmp_path_factory):
    # build spec + configs, but register ftest_v1 at IDEA in a fresh registry
    root = tmp_path_factory.mktemp("idea")
    root, data_root, _ = make_final_momentum_repo(root)
    reg = root / "idea_registry.yaml"
    register_strategy(reg, "ftest_v1", "zhangjl", "init")
    return root, data_root, reg


@pytest.mark.parametrize("bad,good", [
    ("hypothesis: \"h\"", "hypothesis: \"\""),          # no hypothesis
    ("timing: {execution_bar: 1, execution_price: close}",
     "timing: {execution_bar: 0, execution_price: close}"),  # look-ahead timing
    ("param_grid: {momentum_days: [5, 10], ma_filter: [0], top_k: [1, 2]}",
     "param_grid: {}"),                                  # no parameter range
])
def test_idea_to_specified_missing_element_rejected(idea_repo, bad, good):
    root, data_root, reg = idea_repo
    _rewrite_spec(root, "ftest_v1", bad, good)
    before = _snapshot(reg, "ftest_v1")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "SPECIFIED", "zhangjl", "spec",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)
    assert _snapshot(reg, "ftest_v1") == before  # zero mutation
    _rewrite_spec(root, "ftest_v1", good, bad)  # restore


def test_idea_to_specified_valid(tmp_path):
    root, data_root, _reg = make_final_momentum_repo(tmp_path)
    # strategy starts at IDEA? make_final promotes to RESEARCH; re-register a
    # fresh one at IDEA
    from pql.lifecycle import register_strategy as _reg

    reg2 = tmp_path / "reg2.yaml"
    _reg(reg2, "ftest_v1", "zhangjl", "init")
    before = len(_audit(reg2))
    promote(root, "ftest_v1", "SPECIFIED", "zhangjl", "spec",
            registry_path=reg2, report_root=root / "reports",
            experiments_root=root / "experiments", data_root=data_root)
    assert _state(reg2, "ftest_v1") == "SPECIFIED"
    assert len(_audit(reg2)) == before + 1


# --------------------------------------------------------------------------- #
# SPECIFIED -> RESEARCH
# --------------------------------------------------------------------------- #
def test_specified_to_research_invalid_spec_rejected(tmp_path):
    root, data_root, _reg = make_final_momentum_repo(tmp_path)  # RESEARCH state
    # move back is illegal; instead register fresh and walk to SPECIFIED
    reg2 = tmp_path / "reg2.yaml"
    register_strategy(reg2, "ftest_v1", "zhangjl", "init")
    promote(root, "ftest_v1", "SPECIFIED", "zhangjl", "spec",
            registry_path=reg2, report_root=root / "reports",
            experiments_root=root / "experiments", data_root=data_root)
    _rewrite_spec(root, "ftest_v1", "timing: {execution_bar: 1, execution_price: close}",
                  "timing: {execution_bar: 0, execution_price: close}")
    before = _snapshot(reg2, "ftest_v1")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "RESEARCH", "zhangjl", "research",
                registry_path=reg2, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)
    assert _snapshot(reg2, "ftest_v1") == before


# --------------------------------------------------------------------------- #
# RESEARCH -> CANDIDATE
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def research_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("research")
    return make_final_momentum_repo(root)


def test_research_to_candidate_no_report_rejected(research_repo, tmp_path):
    root, data_root, reg = research_repo
    before = _snapshot(reg, "ftest_v1")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "CANDIDATE", "zhangjl", "freeze",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)
    assert _snapshot(reg, "ftest_v1") == before


def test_research_to_candidate_dirty_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    # dirty the code tree (src/ scope) -> freeze refused
    code = root / "src" / "pql" / "_fixture" / "code.py"
    code.write_text("FIXTURE_CODE_VERSION = 2\n", encoding="utf-8")
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "CANDIDATE", "zhangjl", "freeze",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)


def test_research_to_candidate_stale_report_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    # stale: change the gates config (validation_fingerprint no longer matches)
    gates = root / "config" / "validation_gates.yaml"
    gates.write_text(gates.read_text(encoding="utf-8").replace(
        "min_is_sharpe: 0.5", "min_is_sharpe: 0.6"), encoding="utf-8")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "CANDIDATE", "zhangjl", "freeze",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)


# --------------------------------------------------------------------------- #
# CANDIDATE -> VALIDATED
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def candidate_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("candidate")
    root, data_root, reg = make_final_momentum_repo(root)
    run_candidate_pass(root, data_root, reg)
    return root, data_root, reg


def test_candidate_to_validated_no_final_report_rejected(candidate_repo):
    root, data_root, reg = candidate_repo
    before = _snapshot(reg, "ftest_v1")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "VALIDATED", "zhangjl", "validated",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)
    assert _snapshot(reg, "ftest_v1") == before


def test_candidate_to_validated_final_fail_rejected(candidate_repo):
    root, data_root, reg = candidate_repo
    report = root / "reports" / "validation" / "ftest_v1" / "final_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    freeze = find_strategy(reg, "ftest_v1")["candidate_freeze"]
    report.write_text(json.dumps({"overall": "FAIL", "candidate_hash":
                                  freeze["candidate_hash"]}), encoding="utf-8")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "VALIDATED", "zhangjl", "validated",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)


def test_candidate_to_validated_hash_mismatch_rejected(candidate_repo):
    root, data_root, reg = candidate_repo
    report = root / "reports" / "validation" / "ftest_v1" / "final_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"overall": "PASS", "candidate_hash": "deadbeef"}),
                      encoding="utf-8")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "VALIDATED", "zhangjl", "validated",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)


def test_candidate_to_validated_holdout_not_consumed_rejected(candidate_repo):
    root, data_root, reg = candidate_repo
    report = root / "reports" / "validation" / "ftest_v1" / "final_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    freeze = find_strategy(reg, "ftest_v1")["candidate_freeze"]
    report.write_text(json.dumps({"overall": "PASS",
                                  "candidate_hash": freeze["candidate_hash"]}),
                      encoding="utf-8")
    # ensure holdout_status is NOT consumed (fresh registry entry has none)
    entry = find_strategy(reg, "ftest_v1")
    assert not (entry.get("holdout_status") or {}).get("consumed")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "VALIDATED", "zhangjl", "validated",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)


def test_candidate_to_validated_dirty_rejected(candidate_repo):
    root, data_root, reg = candidate_repo
    code = root / "src" / "pql" / "_fixture" / "code.py"
    code.write_text("FIXTURE_CODE_VERSION = 3\n", encoding="utf-8")
    with pytest.raises(GateError):
        promote(root, "ftest_v1", "VALIDATED", "zhangjl", "validated",
                registry_path=reg, report_root=root / "reports",
                experiments_root=root / "experiments", data_root=data_root)


# --------------------------------------------------------------------------- #
# VALIDATED -> PAPER and PAPER -> LIVE
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def paper_repo(tmp_path_factory):
    """A strategy walked through the FULL real chain to PAPER in an isolated
    sandbox (gate demo machinery; production state untouched)."""
    from pql.gate_demo import run_gate_demo

    sandbox = tmp_path_factory.mktemp("paperrepo")
    res = run_gate_demo(sandbox=sandbox, print_steps=False)
    assert res.get("DEMO_RESULT") == "PASS"
    root = Path(sandbox)
    return root, root / "data", root / "strategy_registry.yaml", "demo_v1"


def _paper_report_path(root, strategy):
    return root / "reports" / "paper" / strategy / "paper_report.json"


def _mutate_paper_report(root, strategy, **changes):
    """Temporarily force the persisted paper_report to FAIL (mutations must not
    leak into later tests), then restore the original PASS report."""
    report = _paper_report_path(root, strategy)
    orig = report.read_text(encoding="utf-8")
    data = json.loads(orig)
    data.update(changes)
    data["overall"] = "FAIL"
    report.write_text(json.dumps(data), encoding="utf-8")
    return orig


def _restore_paper_report(report, orig):
    report.write_text(orig, encoding="utf-8")


def test_validated_to_paper_metrics_below_threshold_rejected(paper_repo):
    root, data_root, reg, strategy = paper_repo
    report = _paper_report_path(root, strategy)
    orig = _mutate_paper_report(root, strategy, paper_gate={"trading_days": {"actual": 5, "threshold": 40, "pass": False},
                       "rebalance_cycles": {"actual": 3, "threshold": 3, "pass": True},
                       "sim_orders": {"actual": 10, "threshold": 10, "pass": True},
                       "unreconciled": {"actual": 0, "threshold": 0, "pass": True},
                       "silent_failures": {"actual": 0, "threshold": 0, "pass": True}})
    try:
        before = _snapshot(reg, strategy)
        with pytest.raises(GateError):
            promote(root, strategy, "PAPER", "zhangjl", "paper",
                    registry_path=reg, report_root=root / "reports",
                    experiments_root=root / "experiments", data_root=data_root)
        assert _snapshot(reg, strategy) == before
    finally:
        _restore_paper_report(report, orig)


def test_validated_to_paper_unreconciled_rejected(paper_repo):
    root, data_root, reg, strategy = paper_repo
    report = _paper_report_path(root, strategy)
    orig = _mutate_paper_report(root, strategy, unreconciled=1)
    try:
        with pytest.raises(GateError):
            promote(root, strategy, "PAPER", "zhangjl", "paper",
                    registry_path=reg, report_root=root / "reports",
                    experiments_root=root / "experiments", data_root=data_root)
    finally:
        _restore_paper_report(report, orig)


def test_validated_to_paper_silent_failures_rejected(paper_repo):
    root, data_root, reg, strategy = paper_repo
    report = _paper_report_path(root, strategy)
    orig = _mutate_paper_report(root, strategy, silent_failures=1)
    try:
        with pytest.raises(GateError):
            promote(root, strategy, "PAPER", "zhangjl", "paper",
                    registry_path=reg, report_root=root / "reports",
                    experiments_root=root / "experiments", data_root=data_root)
    finally:
        _restore_paper_report(report, orig)


def test_paper_to_live_ai_rejected(paper_repo):
    root, data_root, reg, strategy = paper_repo
    before = _snapshot(reg, strategy)
    for approver in ("ai", "AI", "agent", "AGENT", "claude"):
        with pytest.raises(GateError):
            promote(root, strategy, "LIVE", approver, "live",
                    registry_path=reg, report_root=root / "reports",
                    experiments_root=root / "experiments", data_root=data_root)
        assert _snapshot(reg, strategy) == before  # zero mutation on each reject


def test_paper_to_live_human_pass(paper_repo):
    root, data_root, reg, strategy = paper_repo
    promote(root, strategy, "LIVE", "zhangjl", "human live approval",
            registry_path=reg, report_root=root / "reports",
            experiments_root=root / "experiments", data_root=data_root)
    assert _state(reg, strategy) == "LIVE"
    entry = find_strategy(reg, strategy)
    assert entry["history"][-1]["approver"] == "zhangjl"
    assert entry["history"][-1]["to"] == "LIVE"


def test_human_name_with_ai_substring_not_rejected():
    # "Ali" / "Aidan" contain "ai" as characters but are human names
    assert is_ai_approver("Ali") is False
    assert is_ai_approver("Aidan Zhang") is False
    assert is_ai_approver("ai") is True
    assert is_ai_approver(" AI ") is True
    assert is_ai_approver("agent") is True
    assert is_ai_approver("zhangjl") is False