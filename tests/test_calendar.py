"""M2 CalendarAdapter: multi-source resolution + coverage gate."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.data.calendar import (
    CalendarAdapter,
    CalendarCoverageError,
    CalendarError,
    FixtureCalendar,
    ensure_coverage,
)
from tests.fixtures.make_fixture import make_calendar

START, END = "2020-01-01", "2020-12-31"


def _dates(end=END):
    return pd.to_datetime(pd.Series(make_calendar(START, end))).dt.normalize()


def test_adapter_returns_first_working_source():
    adapter = CalendarAdapter([FixtureCalendar(_dates())])
    dates, source = adapter.fetch(START, END)
    assert source == "fixture"
    assert not dates.empty


def test_adapter_all_sources_fail():
    adapter = CalendarAdapter()  # no sources configured
    with pytest.raises(CalendarError, match="no calendar source"):
        adapter.fetch(START, END)


def test_coverage_ok():
    ensure_coverage(_dates(END).to_frame(name="trade_date"), END, allow_gap=False)


def test_coverage_insufficient_rejected():
    short = _dates("2020-06-30").to_frame(name="trade_date")
    with pytest.raises(CalendarCoverageError, match="calendar_end"):
        ensure_coverage(short, END, allow_gap=False)


def test_coverage_insufficient_allowed_with_flag():
    short = _dates("2020-06-30").to_frame(name="trade_date")
    ensure_coverage(short, END, allow_gap=True)  # no raise when gap allowed