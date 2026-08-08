"""M3 TimingContract (D2). Encodes the data-availability invariant:
data_available_time <= signal_time <= decision_time < execution_time.

Default: signal/decision at T close, execution at T+1 (execution_bar=1).
Production backtests must reject execution_bar < 1 (look-ahead).

M7: `latest_expected_completed_bar` computes the most recent COMPLETED daily bar
for the CN ETF market (daily-bar completion boundary Asia/Shanghai 15:00,
PLAN_CLARIFICATION M7-004). A price dated before that bar is STALE; a price on
the expected completed bar is not. This is NOT "today": on a trading morning the
previous trading day's bar is the latest completed one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

import pandas as pd


class TimingError(ValueError):
    """Raised when a TimingContract admits look-ahead or is internally invalid."""


@dataclass(frozen=True)
class TimingContract:
    signal_time: str = "T_close"        # signal uses only data <= T close
    decision_time: str = "T_close"      # decision made at T close
    execution_bar: int = 1              # execute on bar T+N
    execution_price: str = "close"      # "close" | "open"

    def validate(self) -> None:
        assert_no_lookahead(self)
        if self.execution_price not in ("close", "open"):
            raise TimingError(
                f"execution_price must be 'close' or 'open', got {self.execution_price!r}"
            )


def assert_no_lookahead(contract: TimingContract) -> None:
    """execution_bar < 1 means the signal and the fill share a bar (look-ahead)."""
    if contract.execution_bar < 1:
        raise TimingError(
            f"execution_bar={contract.execution_bar} admits look-ahead; "
            "signal at T must fill no earlier than T+1"
        )


_CN_TZ = ZoneInfo("Asia/Shanghai")
_MARKET_CLOSE = dtime(15, 0)


def latest_expected_completed_bar(
    calendar_dates,
    as_of,
    *,
    market_close: str = "15:00",
    timezone: str = "Asia/Shanghai",
) -> pd.Timestamp:
    """The most recent COMPLETED daily bar as of `as_of` (PLAN_CLARIFICATION
    M7-004).

    `calendar_dates` is the authoritative Snapshot trading calendar (normalized
    Timestamps). `as_of` may be a date, a naive datetime (interpreted in the
    given market timezone) or an aware datetime.

    Rules (all based on the trading calendar, never weekday heuristics):
      - on a trading day BEFORE the daily-bar completion boundary
        (Asia/Shanghai 15:00): the PREVIOUS trading day's bar is the latest
        completed one (today's daily bar is still forming);
      - on a trading day AT/AFTER the boundary: today's bar is complete;
      - on a weekend / holiday (not a trading day): the MOST RECENT trading day
        <= `as_of` is the latest completed bar.
    """
    tz = ZoneInfo(timezone)
    hh, mm = (int(p) for p in market_close.split(":"))
    boundary = dtime(hh, mm)

    if isinstance(as_of, pd.Timestamp):
        dt = as_of.to_pydatetime()
    elif isinstance(as_of, datetime):
        dt = as_of
    else:
        dt = pd.Timestamp(as_of).to_pydatetime()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)

    cal = pd.Index(sorted(pd.Timestamp(d).normalize() for d in calendar_dates))
    if len(cal) == 0:
        raise TimingError("empty trading calendar for latest_expected_completed_bar")

    today = pd.Timestamp(dt.date()).normalize()
    # trading days strictly after `as_of` (its date) — exclude if today is a
    # trading day and we only know its bar is complete after the boundary.
    if today in cal:
        if dt.timetz() < boundary:
            # today's bar not complete yet -> strictly previous trading day
            prior = cal[cal < today]
            if len(prior) == 0:
                raise TimingError(
                    f"as_of {dt.isoformat()} has no prior completed trading bar"
                )
            return prior[-1]
        return today
    # not a trading day -> most recent trading day <= today
    le = cal[cal <= today]
    if len(le) == 0:
        raise TimingError(
            f"as_of {dt.isoformat()} has no completed trading bar in calendar"
        )
    return le[-1]
