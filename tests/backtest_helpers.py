"""Shared helpers for M3 backtest tests: build a small immutable snapshot from
hand-crafted price arrays (via the M2 fixture snapshot path) and load it as a
DatasetView."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pql.data.adapters import FixtureProvider
from pql.data.calendar import CalendarAdapter, FixtureCalendar
from pql.data.dataset import DatasetView
from pql.data.snapshot import build_snapshot

_START = "2024-01-01"


def make_snapshot(
    tmp_path,
    closes: dict[str, np.ndarray],
    *,
    name: str = "snap",
    research: dict[str, np.ndarray] | None = None,
    drop_days: dict[str, list[int]] | None = None,
) -> DatasetView:
    """Build a snapshot where each symbol's close is the given array. Optionally
    override research (close_adj) and drop specific day indices (missing days)."""
    n = len(next(iter(closes.values())))
    dates = pd.date_range(_START, periods=n, freq="D")
    data: dict[str, dict] = {}
    for sym, close in closes.items():
        close = np.asarray(close, dtype=float)
        mask = np.ones(n, dtype=bool)
        for idx in (drop_days or {}).get(sym, []):
            mask[idx] = False
        keep_dates = dates[mask]
        keep_close = close[mask]
        raw = pd.DataFrame(
            {
                "date": keep_dates,
                "open": keep_close - 0.1,
                "high": keep_close + 0.2,
                "low": keep_close - 0.2,
                "close": keep_close,
                "volume": np.full(len(keep_close), 1_000_000),
                "amount": keep_close * 1_000_000,
            }
        )
        rc = research.get(sym) if research else None
        adj = np.asarray(rc if rc is not None else close, dtype=float)[mask]
        data[sym] = {
            "raw": raw,
            "research": pd.Series(adj, index=keep_dates, name=sym),
        }
    provider = FixtureProvider(data)
    cal_dates = [d.strftime("%Y-%m-%d") for d in dates]
    calendar = CalendarAdapter([FixtureCalendar(cal_dates)])
    build_snapshot(
        source="fixture",
        symbols=list(closes),
        start=_START,
        end=str(dates[-1].date()),
        data_root=tmp_path,
        from_fixture=True,
        provider=provider,
        calendar_adapter=calendar,
        name=name,
    )
    return DatasetView.load(name, tmp_path)