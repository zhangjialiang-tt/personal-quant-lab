"""M6.7 candidate-freeze tests: FAIL/dirty/stale rejected, payload complete,
candidate_hash deterministic, and every frozen item mismatch fails verification."""
from __future__ import annotations

import json

import pytest
import yaml

from pql.validation.freeze import (
    FreezeError,
    compute_freeze_payload,
    promote_to_candidate,
    verify_freeze,
)
from tests.final_fixture import make_final_momentum_repo, run_candidate_pass


def _frozen(root):
    reg = yaml.safe_load((root / "strategy_registry.yaml").read_text(encoding="utf-8"))
    return reg["strategies"][0]["candidate_freeze"]


def test_candidate_fail_freezing_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    # write a FAILING candidate report (overall FAIL) without freezing
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    report_path = root / "reports" / "validation" / "ftest_v1" / "candidate_report.json"
    import json

    r = json.loads(report_path.read_text(encoding="utf-8"))
    r["overall"] = "FAIL"
    r["ready_for_candidate_freeze"] = False
    report_path.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FreezeError, match="not PASS"):
        promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="r",
                             registry_path=reg, report_root=root / "reports",
                             experiments_root=root / "experiments", data_root=data_root)


def test_dirty_code_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    # dirty the worktree AFTER validation with a tests/ file (inside the dirty
    # scope but OUTSIDE the code-tree binding), so only the current clean-state
    # check can catch it (D9 require_code_clean, review P1-3).
    dirty = root / "tests" / "_dirty_probe.py"
    dirty.parent.mkdir(parents=True, exist_ok=True)
    dirty.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="dirty"):
        promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="r",
                             registry_path=reg, report_root=root / "reports",
                             experiments_root=root / "experiments", data_root=data_root)


def test_stale_candidate_report_rejected(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    # run candidate but with a stale/dirty code_commit in the report
    from pql.validation.pipeline import validate_candidate

    report = validate_candidate(root, "ftest_v1", data_root=data_root,
                                report_root=root / "reports",
                                experiments_root=root / "experiments", persist=True)
    assert report["overall"] == "PASS"
    report_path = root / "reports" / "validation" / "ftest_v1" / "candidate_report.json"
    r = json.loads(report_path.read_text(encoding="utf-8"))
    r["validation_fingerprint"] = {**r.get("validation_fingerprint", {}), "spec_sha256": "0" * 64}
    report_path.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FreezeError, match="validation_fingerprint"):
        promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="r",
                             registry_path=reg, report_root=root / "reports",
                             experiments_root=root / "experiments", data_root=data_root)


def test_freeze_payload_complete(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    frozen = _frozen(root)
    for key in ("candidate_hash", "spec_sha256", "code_commit", "parameters",
                "gate_version", "gate_config_sha256", "cost_config_sha256",
                "market_rule_sha256", "instrument_sha256", "uv_lock_sha256",
                "dataset_version", "created"):
        assert key in frozen
    assert len(frozen["candidate_hash"]) == 64
    assert frozen["code_commit"]
    assert frozen["parameters"]  # non-empty
    assert yaml.safe_load((root / "strategy_registry.yaml").read_text(encoding="utf-8"))["strategies"][0]["state"] == "CANDIDATE"


def test_candidate_hash_deterministic(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    from pql.schemas import load_spec

    spec = load_spec(root / "strategies" / "ftest_v1.yaml")
    p1 = compute_freeze_payload(root, root / "experiments", spec)
    p2 = compute_freeze_payload(root, root / "experiments", spec)
    assert p1["candidate_hash"] == p2["candidate_hash"]
    assert _frozen(root)["candidate_hash"] == p1["candidate_hash"]


def _git(root, *args):
    import subprocess

    subprocess.run(["git", *args], cwd=str(root), capture_output=True, check=True)


def test_evidence_only_commit_does_not_invalidate_freeze(tmp_path):
    """An evidence-only commit (reports/ …) must NOT change the freeze's code
    binding or candidate_hash — the reviewed self-invalidation concern."""
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    frozen = _frozen(root)
    from pql.schemas import load_spec

    spec = load_spec(root / "strategies" / "ftest_v1.yaml")
    before = compute_freeze_payload(root, root / "experiments", spec)
    verify_freeze(frozen, before)  # consistent pre-commit

    # commit an evidence-only file (reports/ is not part of the code tree)
    ev = root / "reports" / "evidence_only.txt"
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text("evidence", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "evidence-only commit")

    after = compute_freeze_payload(root, root / "experiments", spec)
    assert before["code_tree_sha256"] == after["code_tree_sha256"]
    assert before["candidate_hash"] == after["candidate_hash"]
    verify_freeze(frozen, after)  # evidence commit did NOT invalidate the freeze


def test_freeze_after_evidence_commit_is_allowed(tmp_path):
    """The reviewer's exact concern: validate candidate -> commit report ->
    freeze must NOT fail. The freeze binds the code-tree fingerprint, which an
    evidence-only commit does not change."""
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    # commit the report (evidence) BEFORE freezing
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "commit report before freeze")
    # freeze must still succeed (code unchanged by the evidence commit)
    promoted = promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="r",
                                    registry_path=reg, report_root=root / "reports",
                                    experiments_root=root / "experiments", data_root=data_root)
    assert promoted["candidate_freeze"]["code_tree_sha256"]


def test_validate_then_modify_instrument_then_freeze_rejected(tmp_path):
    """Modifying an instrument config (or uv.lock) between candidate validation
    and freeze must be caught by the report->freeze provenance check (the
    report's validation_fingerprint binds instrument + uv.lock)."""
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    # modify an instrument config AFTER validation
    ip = root / "config" / "instruments" / "510300.yaml"
    ip.write_text(ip.read_text(encoding="utf-8").replace("tick_size: 0.001", "tick_size: 0.01"), encoding="utf-8")
    with pytest.raises(FreezeError, match="instrument_sha256"):
        promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="r",
                             registry_path=reg, report_root=root / "reports",
                             experiments_root=root / "experiments", data_root=data_root)
    ip.write_text(ip.read_text(encoding="utf-8").replace("tick_size: 0.01", "tick_size: 0.001"), encoding="utf-8")

    # and uv.lock
    ul = root / "uv.lock"
    ul.write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="uv_lock_sha256"):
        promote_to_candidate(root, "ftest_v1", approver="zhangjl", reason="r",
                             registry_path=reg, report_root=root / "reports",
                             experiments_root=root / "experiments", data_root=data_root)


def test_freeze_mismatch_on_file_change(tmp_path):
    root, data_root, reg = make_final_momentum_repo(tmp_path)
    run_candidate_pass(root, data_root, reg)
    frozen = _frozen(root)
    from pql.schemas import load_spec

    spec = load_spec(root / "strategies" / "ftest_v1.yaml")

    def _actual():
        actual = compute_freeze_payload(root, root / "experiments", spec)
        verify_freeze(frozen, actual)

    _actual()  # unchanged -> passes

    # modify spec
    sp = root / "strategies" / "ftest_v1.yaml"
    sp.write_text(sp.read_text(encoding="utf-8").replace("momentum_days: 10", "momentum_days: 180"), encoding="utf-8")
    with pytest.raises(FreezeError, match="spec_sha256"):
        _actual()
    sp.write_text(sp.read_text(encoding="utf-8").replace("momentum_days: 180", "momentum_days: 10"), encoding="utf-8")

    # modify gate config
    gp = root / "config" / "validation_gates.yaml"
    gp.write_text(gp.read_text(encoding="utf-8").replace("min_is_sharpe: 0.5", "min_is_sharpe: 0.7"), encoding="utf-8")
    with pytest.raises(FreezeError, match="gate_config_sha256"):
        _actual()
    gp.write_text(gp.read_text(encoding="utf-8").replace("min_is_sharpe: 0.7", "min_is_sharpe: 0.5"), encoding="utf-8")

    # modify cost
    cp = root / "config" / "costs" / "test.yaml"
    cp.write_text(cp.read_text(encoding="utf-8").replace("fee_rate: 0.0003", "fee_rate: 0.0005"), encoding="utf-8")
    with pytest.raises(FreezeError, match="cost_config_sha256"):
        _actual()
    cp.write_text(cp.read_text(encoding="utf-8").replace("fee_rate: 0.0005", "fee_rate: 0.0003"), encoding="utf-8")

    # modify market
    mp = root / "config" / "markets" / "test.yaml"
    mp.write_text(mp.read_text(encoding="utf-8").replace("lot_size: 100", "lot_size: 200"), encoding="utf-8")
    with pytest.raises(FreezeError, match="market_rule_sha256"):
        _actual()
    mp.write_text(mp.read_text(encoding="utf-8").replace("lot_size: 200", "lot_size: 100"), encoding="utf-8")

    # modify instrument
    ip = root / "config" / "instruments" / "510300.yaml"
    ip.write_text(ip.read_text(encoding="utf-8").replace("tick_size: 0.001", "tick_size: 0.01"), encoding="utf-8")
    with pytest.raises(FreezeError, match="instrument_sha256"):
        _actual()
    ip.write_text(ip.read_text(encoding="utf-8").replace("tick_size: 0.01", "tick_size: 0.001"), encoding="utf-8")

    # modify uv.lock
    ul = root / "uv.lock"
    ul.write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="uv_lock_sha256"):
        _actual()
    ul.write_text("version = 1\n", encoding="utf-8")

    # modify params (via spec signal defaults)
    sp2 = root / "strategies" / "ftest_v1.yaml"
    sp2.write_text(sp2.read_text(encoding="utf-8").replace("top_k: 2", "top_k: 3"), encoding="utf-8")
    with pytest.raises(FreezeError):
        _actual()
    sp2.write_text(sp2.read_text(encoding="utf-8").replace("top_k: 3", "top_k: 2"), encoding="utf-8")

    # modify the strategy implementation code (fixture src/) -> code_tree_sha256
    _src = root / "src" / "pql" / "_fixture" / "code.py"
    with open(_src, "a", encoding="utf-8") as fh:
        fh.write("\n# freeze-mismatch test\n")
    try:
        with pytest.raises(FreezeError, match="code_tree_sha256"):
            _actual()
    finally:
        with open(_src, "w", encoding="utf-8") as fh:
            fh.write("FIXTURE_CODE_VERSION = 1\n")