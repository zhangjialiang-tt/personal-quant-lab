"""M7.70 gate demo tests: demo reaches PAPER in an isolated sandbox; production
strategy registry / holdout log / paper state are untouched; the fixture's own
holdout is consumed exactly once; the fixture lifecycle history is complete."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from pql.gate_demo import run_gate_demo


def _sha(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _link(path: Path) -> Path:
    return Path(__file__).resolve().parent.parent / path


def test_demo_reaches_paper(tmp_path):
    res = run_gate_demo(sandbox=tmp_path, print_steps=False)
    assert res.get("DEMO_RESULT") == "PASS"
    assert res.get("VALIDATED->PAPER", {}).get("state_after") == "PAPER"
    # each transition PASSED
    for step in ("IDEA->SPECIFIED", "SPECIFIED->RESEARCH", "RESEARCH->CANDIDATE",
                 "CANDIDATE->VALIDATED", "VALIDATED->PAPER"):
        assert res[step]["result"] == "PASS", step
    assert res["paper_report"]["overall"] == "PASS"


def test_production_untouched(tmp_path):
    reg = _link("strategy_registry.yaml")
    holdout = _link("data/metadata/holdout_access.log")
    paper_dir = _link("data/paper")
    reg_before = _sha(reg)
    holdout_before = _sha(holdout)
    paper_before = sorted(str(p.relative_to(paper_dir)) for p in paper_dir.rglob("*")
                          if p.is_file()) if paper_dir.exists() else []
    run_gate_demo(sandbox=tmp_path, print_steps=False)
    assert _sha(reg) == reg_before
    assert _sha(holdout) == holdout_before
    paper_after = sorted(str(p.relative_to(paper_dir)) for p in paper_dir.rglob("*")
                         if p.is_file()) if paper_dir.exists() else []
    assert paper_after == paper_before


def test_fixture_holdout_consumed_once(tmp_path):
    run_gate_demo(sandbox=tmp_path, print_steps=False)
    reg = yaml.safe_load((tmp_path / "strategy_registry.yaml").read_text(encoding="utf-8"))
    entry = next(s for s in reg["strategies"] if s["id"] == "demo_v1")
    hs = entry.get("holdout_status") or {}
    assert hs.get("consumed") is True
    assert "consumed_at" in hs
    # exactly one holdout access line for the fixture strategy
    if (tmp_path / "data" / "metadata" / "holdout_access.log").exists():
        lines = (tmp_path / "data" / "metadata" / "holdout_access.log") \
            .read_text(encoding="utf-8").splitlines()
        demo_lines = [l for l in lines if json.loads(l).get("strategy") == "demo_v1"]
        assert len(demo_lines) == 1


def test_fixture_lifecycle_history_complete(tmp_path):
    run_gate_demo(sandbox=tmp_path, print_steps=False)
    reg = yaml.safe_load((tmp_path / "strategy_registry.yaml").read_text(encoding="utf-8"))
    entry = next(s for s in reg["strategies"] if s["id"] == "demo_v1")
    states = [h["to"] for h in entry["history"]]
    assert states[0] == "IDEA"
    for expected in ("SPECIFIED", "RESEARCH", "CANDIDATE", "VALIDATED", "PAPER"):
        assert expected in states, f"missing {expected} in history {states}"
    assert entry["state"] == "PAPER"
    # each history entry carries from/to/time/reason/evidence/approver
    for h in entry["history"]:
        for k in ("from", "to", "time", "reason", "evidence", "approver"):
            assert k in h
    # every transition has a corresponding audit.log record
    audit = (tmp_path / "reports" / "audit.log").read_text(encoding="utf-8").splitlines()
    assert len(audit) >= len(entry["history"])