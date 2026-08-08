"""M6.9 review-bundle tests: reviewer + challenger bundles generated, challenger
contains the hypothesis but NEVER researcher_prompt / research/ / prior reviewer
conclusions / SECRET_RESEARCHER_REASONING markers."""
from __future__ import annotations

import json

import pytest

from pql.review.bundle import BundleError, build_bundle
from tests.final_fixture import make_final_momentum_repo


def _repo_with_candidate(tmp_path):
    root, data_root, _reg = make_final_momentum_repo(tmp_path)
    from pql.validation.pipeline import validate_candidate

    validate_candidate(root, "ftest_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=True)
    return root, data_root


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_reviewer_bundle_generated(tmp_path):
    root, data_root = _repo_with_candidate(tmp_path)
    path = build_bundle(root, "EXP-0001", "reviewer", experiments_root=root / "experiments",
                        data_root=data_root, report_root=root / "reports",
                        out_root=root / "reports")
    text = _read(path)
    assert "reviewer" in text
    assert "StrategySpec" in text
    assert "hypothesis" in text


def test_challenger_bundle_generated_with_hypothesis(tmp_path):
    root, data_root = _repo_with_candidate(tmp_path)
    path = build_bundle(root, "EXP-0001", "challenger", experiments_root=root / "experiments",
                        data_root=data_root, report_root=root / "reports",
                        out_root=root / "reports")
    text = _read(path)
    # Hard contract: challenger MUST see the hypothesis (to attack economic logic)
    assert "hypothesis" in text
    # and candidate metrics + code/provenance
    assert "Candidate Validation" in text
    assert "Source Code" in text


def test_challenger_bundle_excludes_researcher_content(tmp_path):
    root, data_root = _repo_with_candidate(tmp_path)
    path = build_bundle(root, "EXP-0001", "challenger", experiments_root=root / "experiments",
                        data_root=data_root, report_root=root / "reports",
                        out_root=root / "reports")
    text = _read(path)
    assert "researcher_prompt" not in text
    assert "research/" not in text
    assert "researcher reasoning" not in text
    assert "reviewer_recommendation" not in text


def test_challenger_bundle_rejects_secret_marker(tmp_path):
    """A SECRET_RESEARCHER_REASONING marker inside a bundled field must cause
    the challenger bundle to be refused (fail-closed), never written."""
    root, data_root = _repo_with_candidate(tmp_path)
    report_path = root / "reports" / "validation" / "ftest_v1" / "candidate_report.json"
    r = json.loads(report_path.read_text(encoding="utf-8"))
    r["bootstrap"] = {"_leak": "SECRET_RESEARCHER_REASONING"}
    report_path.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(BundleError, match="SECRET_RESEARCHER_REASONING"):
        build_bundle(root, "EXP-0001", "challenger", experiments_root=root / "experiments",
                     data_root=data_root, report_root=root / "reports",
                     out_root=root / "reports")


def test_reviewer_and_challenger_bundles_differ(tmp_path):
    root, data_root = _repo_with_candidate(tmp_path)
    rev = build_bundle(root, "EXP-0001", "reviewer", experiments_root=root / "experiments",
                       data_root=data_root, report_root=root / "reports",
                       out_root=root / "reports")
    ch = build_bundle(root, "EXP-0001", "challenger", experiments_root=root / "experiments",
                      data_root=data_root, report_root=root / "reports",
                      out_root=root / "reports")
    assert rev != ch  # separate bundles for separate roles