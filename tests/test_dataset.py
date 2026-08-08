"""M2 DatasetView: research/execution frame separation + verify-on-read."""
from __future__ import annotations

import os
import stat

import pandas as pd
import pytest

from pql.data.calendar import CalendarAdapter, FixtureCalendar
from pql.data.dataset import DatasetView, SnapshotIntegrityError
from pql.data.snapshot import build_snapshot
from tests.fixtures.make_fixture import make_calendar, make_fixture_provider

START, END = "2020-01-01", "2020-12-31"


def _build(tmp_path, name="market-ds"):
    provider = make_fixture_provider(["510300.SH", "510500.SH"], START, END)
    cal = CalendarAdapter([FixtureCalendar(make_calendar(START, END))])
    return build_snapshot(
        source="fixture", symbols=["510300.SH", "510500.SH"], start=START, end=END,
        data_root=tmp_path, from_fixture=True, provider=provider,
        calendar_adapter=cal, name=name,
    )


def test_research_and_execution_frames_separate(tmp_path):
    r = _build(tmp_path)
    view = DatasetView.load(r.version, tmp_path)
    research = view.research_frame()
    execution = view.execution_frame()
    assert set(research.columns) == {"date", "symbol", "close_adj"}
    assert set(execution.columns) == {"date", "symbol", "open", "close"}
    # research close_adj values must differ from raw close_adj == close baseline
    assert not research.empty and not execution.empty


def test_universe_filter(tmp_path):
    r = _build(tmp_path)
    view = DatasetView.load(r.version, tmp_path, universe=["510300.SH"])
    assert set(view.research_frame()["symbol"].unique()) == {"510300.SH"}


def test_start_end_filter(tmp_path):
    r = _build(tmp_path)
    view = DatasetView.load(r.version, tmp_path, start="2020-06-01", end="2020-06-30")
    dates = view.research_frame()["date"]
    assert dates.min() >= pd.Timestamp("2020-06-01").normalize()
    assert dates.max() <= pd.Timestamp("2020-06-30").normalize()


def test_verify_on_read_detects_calendar_tamper(tmp_path):
    r = _build(tmp_path)
    cal_file = r.path / "calendar.parquet"
    os.chmod(cal_file, stat.S_IWRITE)
    with cal_file.open("ab") as fh:
        fh.write(b"x")
    os.chmod(cal_file, stat.S_IREAD)
    with pytest.raises(SnapshotIntegrityError):
        DatasetView.load(r.version, tmp_path)