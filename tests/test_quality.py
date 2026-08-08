"""M2 quality checks: one counterexample per dirty-data class must be rejected."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.data.calendar import CalendarAdapter, FixtureCalendar
from pql.data.quality import DataQualityError, run_quality_checks
from pql.data.snapshot import build_snapshot
from tests.fixtures.make_fixture import make_calendar, make_fixture_provider

START, END = "2020-01-01", "2020-12-31"
CAL = set(pd.to_datetime(pd.Series(make_calendar(START, END))).dt.normalize())


def _frame(changes=None):
    data = make_fixture_provider(["510300.SH"], START, END)
    raw = data._data["510300.SH"]["raw"].copy()
    raw["close_adj"] = raw["close"]
    raw["symbol"] = "510300.SH"
    if changes:
        changes(raw)
    return raw.reset_index(drop=True)


def _check(frame, allow_calendar_gap=False):
    return run_quality_checks(frame, CAL, allow_calendar_gap=allow_calendar_gap)


def test_valid_frame_passes():
    report = _check(_frame())
    assert report.passed is True
    assert report.errors == []


def test_bad_ohlc_rejected():
    def chg(df):
        df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] - 1  # high < low
    report = _check(_frame(chg))
    assert report.passed is False
    assert any("bad OHLC" in e for e in report.errors)


def test_duplicate_rows_rejected():
    def chg(df):
        df.loc[0] = df.iloc[1]
    report = _check(_frame(chg))
    assert report.passed is False
    assert any("duplicate" in e for e in report.errors)


def test_negative_price_rejected():
    def chg(df):
        df.iloc[5, df.columns.get_loc("close")] = -1.0
    report = _check(_frame(chg))
    assert report.passed is False
    assert any("non-positive price" in e for e in report.errors)


def test_negative_volume_rejected():
    def chg(df):
        df.iloc[5, df.columns.get_loc("volume")] = -10
    report = _check(_frame(chg))
    assert report.passed is False
    assert any("negative volume" in e for e in report.errors)


def test_date_outside_calendar_rejected():
    def chg(df):
        df.iloc[0, df.columns.get_loc("date")] = pd.Timestamp("2020-01-01") + pd.Timedelta(days=400)
    report = _check(_frame(chg))
    assert report.passed is False
    assert any("outside trading calendar" in e for e in report.errors)


def test_date_outside_calendar_allowed_with_gap():
    def chg(df):
        df.iloc[0, df.columns.get_loc("date")] = pd.Timestamp("2020-01-01") + pd.Timedelta(days=400)
    report = _check(_frame(chg), allow_calendar_gap=True)
    assert report.passed is True
    assert any("gap allowed" in w for w in report.warnings)


def test_missing_days_warn_then_reject():
    def drop_ratio(r):
        def chg(df):
            n = len(df)
            start_idx = int(n * 0.3)
            end_idx = start_idx + int(n * r)
            df.drop(index=df.index[start_idx:end_idx], inplace=True)
        return chg
    # ~10% interior rows missing -> warning, still passes
    report = _check(_frame(drop_ratio(0.10)))
    assert report.passed is True
    assert any("missing" in w for w in report.warnings)
    # ~50% interior rows missing -> reject
    report = _check(_frame(drop_ratio(0.50)))
    assert report.passed is False
    assert any("missing" in e for e in report.errors)


def test_adj_ratio_jump_flagged_as_anomaly():
    def chg(df):
        df.loc[20, "close_adj"] = df.loc[20, "close"] * 1.5  # 50% jump vs prior ratio
    report = _check(_frame(chg))
    assert report.passed is True  # anomaly is a warning, not a reject
    assert any("adj/raw ratio jump" in a for a in report.anomalies)


def test_quality_gate_blocks_dirty_snapshot(tmp_path):
    # A dirty frame fed through the snapshot path must abort the build.
    def chg(df):
        df.iloc[3, df.columns.get_loc("close")] = 0.0
    bad = _frame(chg)
    provider = make_fixture_provider(["510300.SH"], START, END)
    provider._data["510300.SH"]["raw"] = bad[["date", "open", "high", "low", "close",
                                              "volume", "amount"]]
    with pytest.raises(DataQualityError):
        build_snapshot(
            source="fixture", symbols=["510300.SH"], start=START, end=END,
            data_root=tmp_path, from_fixture=True, provider=provider,
            calendar_adapter=CalendarAdapter([FixtureCalendar(make_calendar(START, END))]),
        )