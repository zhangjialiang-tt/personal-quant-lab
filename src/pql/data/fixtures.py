"""Deterministic offline fixtures (fixed seed). Used by the CLI `--from-fixture`
and by tests; real network is never required. `tests/fixtures/make_fixture.py`
re-exports these for the plan-prescribed path.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .adapters import CANONICAL_BAR_COLUMNS, FixtureProvider
from .symbols import resolve_symbol

_DEFAULT_SYMBOLS = ["510300.SH", "510500.SH", "518880.SH", "511010.SH"]


def make_calendar(start: str, end: str, seed: int = 42) -> list[str]:
    """Deterministic business-day trading calendar (mimics trading days)."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start, end)
    n = len(dates)
    keep = np.sort(rng.choice(n, size=max(1, int(n * 0.985)), replace=False))
    return [dates[i].strftime("%Y-%m-%d") for i in keep]


def _gen_symbol(symbol: str, dates: list[str], seed: int) -> dict:
    rng = np.random.RandomState(seed + sum(symbol.encode()))
    n = len(dates)
    start_price = 1.0 + abs(rng.normal(3.0, 1.5))
    drift = rng.normal(0.0002, 0.001)
    rets = rng.normal(drift, 0.012, n)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * (1 + rng.uniform(0.0, 0.006, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.0, 0.006, n))
    volume = rng.randint(200_000, 5_000_000, n)  # shares (canonical)
    amount = volume * close

    raw = pd.DataFrame(
        {
            "date": pd.to_datetime(pd.Series(dates)).dt.normalize(),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    )[CANONICAL_BAR_COLUMNS]
    research = pd.Series(
        close, index=pd.to_datetime(pd.Series(dates)).dt.normalize(), name=symbol
    )
    return {"raw": raw.reset_index(drop=True), "research": research.sort_index()}


def make_provider_data(
    symbols: list[str] | None = None,
    start: str = "2020-01-01",
    end: str = "2024-12-31",
    seed: int = 42,
) -> dict:
    symbols = [resolve_symbol(s) for s in (symbols or _DEFAULT_SYMBOLS)]
    dates = make_calendar(start, end, seed=seed)
    return {sym: _gen_symbol(sym, dates, seed) for sym in symbols}


def make_fixture_provider(
    symbols: list[str] | None = None,
    start: str = "2020-01-01",
    end: str = "2024-12-31",
    seed: int = 42,
) -> FixtureProvider:
    return FixtureProvider(make_provider_data(symbols, start, end, seed))
