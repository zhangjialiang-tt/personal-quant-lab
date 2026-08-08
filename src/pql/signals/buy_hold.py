"""M3 Buy & Hold Control signal (system self-check, NOT an alpha strategy): a
single symbol, 100% exposure, no active rebalancing, long-only. Entry fires on
the first available bar; the engine fills at T+1 per the TimingContract."""
from __future__ import annotations

import pandas as pd

from ..backtest.api import SignalIntent


def buy_hold_signal(dates, symbol: str) -> SignalIntent:
    """Entry at the first bar, never exit. `dates` is an index of trading days."""
    dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates)).dt.normalize())
    entries = pd.DataFrame(False, index=dates, columns=[symbol])
    exits = pd.DataFrame(False, index=dates, columns=[symbol])
    entries.iloc[0] = True
    return SignalIntent(entries=entries, exits=exits)
