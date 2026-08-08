"""M2 CalendarAdapter (M2.2). Multi-source trading calendar; coverage is checked
by the snapshot builder (`calendar_end >= snapshot_end`) unless `--allow-calendar-gap`.
No single source is hard-wired as the only truth.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class CalendarError(RuntimeError):
    """Raised when no calendar source can be fetched."""


class CalendarCoverageError(CalendarError):
    """Raised when calendar coverage does not reach the snapshot end date."""


class CalendarSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """Return a DataFrame with a single datetime column `trade_date`."""


class AkShareCalendar(CalendarSource):
    name = "akshare"

    def __init__(self) -> None:
        try:
            import akshare as ak
        except ImportError as exc:  # pragma: no cover - optional
            raise CalendarError("akshare not installed (add 'data' extra)") from exc
        self._ak = ak

    def fetch(self) -> pd.DataFrame:
        try:
            raw = self._ak.tool_trade_date_hist_sina()
        except Exception as exc:
            raise CalendarError(f"akshare calendar fetch failed: {exc}") from exc
        if raw is None or raw.empty or "trade_date" not in raw.columns:
            raise CalendarError("akshare calendar returned no usable trade_date column")
        out = raw.copy()
        out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.normalize()
        return out[["trade_date"]].drop_duplicates().sort_values("trade_date").reset_index(drop=True)


class TushareTradeCalendar(CalendarSource):
    name = "tushare"

    def __init__(self, token: str) -> None:
        import tushare as ts

        self._pro = ts.pro_api(token)

    def fetch(self) -> pd.DataFrame:
        try:
            raw = self._pro.trade_cal(exchange="SSE", is_open="1")
        except Exception as exc:
            raise CalendarError(f"tushare calendar fetch failed: {exc}") from exc
        if raw is None or raw.empty or "cal_date" not in raw.columns:
            raise CalendarError("tushare calendar returned no usable cal_date column")
        out = raw.copy()
        out["trade_date"] = pd.to_datetime(out["cal_date"]).dt.normalize()
        return out[["trade_date"]].drop_duplicates().sort_values("trade_date").reset_index(drop=True)


class FixtureCalendar(CalendarSource):
    name = "fixture"

    def __init__(self, dates: list[str]) -> None:
        self._dates = pd.to_datetime(pd.Series(dates)).dt.normalize().sort_values()

    def fetch(self) -> pd.DataFrame:
        return pd.DataFrame({"trade_date": self._dates}).reset_index(drop=True)


class CalendarAdapter:
    """Try candidate sources in order; return the first that yields a non-empty
    calendar. Coverage (>= end) is enforced by the snapshot builder."""

    def __init__(self, sources: list[CalendarSource] | None = None) -> None:
        self._sources = sources or []

    def add_source(self, source: CalendarSource) -> None:
        self._sources.append(source)

    def fetch(self, start: str, end: str) -> tuple[pd.DataFrame, str]:
        if not self._sources:
            raise CalendarError("no calendar sources configured")
        errors: list[str] = []
        for source in self._sources:
            try:
                dates = source.fetch()
            except CalendarError as exc:
                errors.append(f"{source.name}: {exc}")
                continue
            if dates is None or dates.empty:
                errors.append(f"{source.name}: empty")
                continue
            return dates, source.name
        raise CalendarError("no calendar source available: " + "; ".join(errors))


def ensure_coverage(dates: pd.DataFrame, end: str, allow_gap: bool) -> None:
    """Require calendar last_date >= snapshot end, unless a gap is allowed."""
    if dates is None or dates.empty:
        raise CalendarCoverageError("calendar is empty")
    last = pd.Timestamp(dates["trade_date"].max()).normalize()
    target = pd.Timestamp(end).normalize()
    if last < target:
        if not allow_gap:
            raise CalendarCoverageError(
                f"calendar_end ({last.date()}) < snapshot_end ({target.date()}); "
                "use --allow-calendar-gap to proceed with an explicit gap record"
            )
        return
