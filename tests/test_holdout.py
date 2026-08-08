"""M2 HoldoutGuard base contract: not-frozen rejection, one-time consumption,
fail-closed ordering, audit log."""
from __future__ import annotations

import json

import pytest
import yaml

from pql.data.calendar import CalendarAdapter, FixtureCalendar
from pql.data.snapshot import build_snapshot
from pql.registry.holdout import HoldoutError, HoldoutGuard
from tests.fixtures.make_fixture import make_calendar, make_fixture_provider

START, END = "2020-01-01", "2020-12-31"


def _registry(path, frozen=True):
    entry = {
        "id": "s1",
        "state": "CANDIDATE" if frozen else "RESEARCH",
        "created": "2026-01-01T00:00:00",
        "history": [],
    }
    if frozen:
        entry["candidate_freeze"] = {"spec_sha256": "abc123", "code_commit": "deadbeef"}
    path.write_text(yaml.safe_dump({"strategies": [entry]}, sort_keys=False), encoding="utf-8")


def _snapshot(tmp_path):
    provider = make_fixture_provider(["510300.SH"], START, END)
    cal = CalendarAdapter([FixtureCalendar(make_calendar(START, END))])
    return build_snapshot(
        source="fixture", symbols=["510300.SH"], start=START, end=END,
        data_root=tmp_path, from_fixture=True, provider=provider,
        calendar_adapter=cal, name="market-holdout",
    )


def test_not_frozen_rejected(tmp_path):
    _registry(tmp_path / "registry.yaml", frozen=False)
    _snapshot(tmp_path)
    guard = HoldoutGuard(tmp_path / "registry.yaml", tmp_path)
    with pytest.raises(HoldoutError, match="not frozen"):
        guard.holdout_slice("s1", "market-holdout", START, END, caller="test")


def test_consume_once_success(tmp_path):
    _registry(tmp_path / "registry.yaml", frozen=True)
    _snapshot(tmp_path)
    guard = HoldoutGuard(tmp_path / "registry.yaml", tmp_path)
    slice_df = guard.holdout_slice("s1", "market-holdout", START, END, caller="test")
    assert "close_adj" in slice_df.columns and not slice_df.empty
    # registry records consumed
    reg = yaml.safe_load((tmp_path / "registry.yaml").read_text(encoding="utf-8"))
    status = reg["strategies"][0]["holdout_status"]
    assert status["consumed"] is True
    assert status["candidate_hash"] == "abc123"
    # audit log has exactly one access line
    log = tmp_path / "metadata" / "holdout_access.log"
    lines = [json.loads(l) for l in log.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 1
    assert lines[0]["strategy"] == "s1"


def test_consume_twice_rejected(tmp_path):
    _registry(tmp_path / "registry.yaml", frozen=True)
    _snapshot(tmp_path)
    guard = HoldoutGuard(tmp_path / "registry.yaml", tmp_path)
    guard.holdout_slice("s1", "market-holdout", START, END, caller="test")
    with pytest.raises(HoldoutError, match="already consumed"):
        guard.holdout_slice("s1", "market-holdout", START, END, caller="test")


def test_unregistered_rejected(tmp_path):
    _registry(tmp_path / "registry.yaml", frozen=True)
    _snapshot(tmp_path)
    guard = HoldoutGuard(tmp_path / "registry.yaml", tmp_path)
    with pytest.raises(HoldoutError, match="not registered"):
        guard.holdout_slice("ghost", "market-holdout", START, END, caller="test")