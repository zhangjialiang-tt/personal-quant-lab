"""M2 snapshot: build, manifest sha256, no-overwrite, auto version, verify-on-read,
calendar coverage gate."""
from __future__ import annotations

import json
import os
import stat

import pytest

from pql.data.calendar import CalendarAdapter, FixtureCalendar
from pql.data.dataset import DatasetVersionNotFound, DatasetView, SnapshotIntegrityError
from pql.data.snapshot import SnapshotBuildError, SnapshotExistsError, build_snapshot
from tests.fixtures.make_fixture import make_calendar, make_fixture_provider

START, END = "2020-01-01", "2020-12-31"
SYMBOLS = ["510300.SH", "510500.SH", "518880.SH", "511010.SH"]


def _build(tmp_path, *, symbols=None, end=END, name=None, allow_calendar_gap=False,
           calendar_end=None):
    symbols = symbols or SYMBOLS
    cend = calendar_end or end
    provider = make_fixture_provider(symbols, START, end)
    cal = CalendarAdapter([FixtureCalendar(make_calendar(START, cend))])
    return build_snapshot(
        source="fixture", symbols=symbols, start=START, end=end,
        data_root=tmp_path, from_fixture=True, provider=provider,
        calendar_adapter=cal, name=name, allow_calendar_gap=allow_calendar_gap,
    )


def test_build_creates_snapshot_with_manifest(tmp_path):
    result = _build(tmp_path, name="market-test-v1")
    assert result.source == "synthetic"
    mf = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))
    assert mf["dataset_version"] == "market-test-v1"
    assert mf["source"] == "synthetic"
    assert set(mf["files"]) == {"prices.parquet", "calendar.parquet"}
    assert len(mf["files"]["prices.parquet"]) == 64  # sha256 hex
    assert (result.path / "prices.parquet").exists()
    assert (result.path / "calendar.parquet").exists()
    assert mf["units"]["volume"] == "shares"
    assert mf["symbols"] == SYMBOLS


def test_explicit_name_no_overwrite(tmp_path):
    _build(tmp_path, name="market-x")
    with pytest.raises(SnapshotExistsError):
        _build(tmp_path, name="market-x")


def test_auto_version_increments(tmp_path):
    r1 = _build(tmp_path)
    r2 = _build(tmp_path)
    assert r1.version != r2.version
    assert r1.version.endswith("-v1")
    assert r2.version.endswith("-v2")


def test_verify_on_read_rejects_tampered_file(tmp_path):
    r = _build(tmp_path, name="market-tamper")
    prices = r.path / "prices.parquet"
    os.chmod(prices, stat.S_IWRITE)
    with prices.open("ab") as fh:
        fh.write(b"corrupt")
    os.chmod(prices, stat.S_IREAD)
    with pytest.raises(SnapshotIntegrityError, match="checksum mismatch"):
        DatasetView.load(r.version, tmp_path)


def test_reload_ok_before_tamper(tmp_path):
    r = _build(tmp_path, name="market-ok")
    view = DatasetView.load(r.version, tmp_path)
    df = view.research_frame()
    assert "close_adj" in df.columns


def test_missing_version_raises(tmp_path):
    with pytest.raises(DatasetVersionNotFound):
        DatasetView.load("market-does-not-exist", tmp_path)


def test_calendar_gap_rejected(tmp_path):
    # calendar covers only to 2020-12-31 but snapshot end is 2021-06-30 -> reject
    with pytest.raises(SnapshotBuildError):
        _build(tmp_path, end="2021-06-30", calendar_end="2020-12-31")


def test_calendar_gap_allowed_recorded(tmp_path):
    r = _build(tmp_path, end="2021-06-30", calendar_end="2020-12-31", allow_calendar_gap=True)
    assert r.manifest["coverage_gap"] is True
    assert r.manifest["allow_calendar_gap"] is True