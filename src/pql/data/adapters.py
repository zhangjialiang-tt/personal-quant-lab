"""M2 Provider abstraction (D4 / M2.1).

Canonical contract: `fetch_raw_bars` returns a DataFrame with columns
`date, open, high, low, close, volume, amount` in canonical units
(price CNY/share, volume shares, amount CNY); `fetch_research_prices` returns a
Series indexed by date of the adjusted research close (`close_adj`).

Providers convert source-specific units to canonical at the adapter boundary;
the conversion is also recorded in the snapshot manifest. There is NO forced
`fetch_adjust_factor()` API — providers differ internally (Tushare synthesises
qfq from `fund_daily` + `fund_adj`; AKShare returns `adjust=""/"qfq"` directly).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd

from .symbols import bare_symbol, resolve_symbol


class DataAdapterError(RuntimeError):
    """Raised when a provider cannot fetch or normalize data."""


# Canonical column set and units (also reused by the manifest).
CANONICAL_BAR_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]
CANONICAL_UNITS = {"price": "CNY/share", "volume": "shares", "amount": "CNY"}


def _identity_unit_conversion() -> dict[str, Any]:
    return {
        "volume": {"source": "shares", "factor": 1.0},
        "amount": {"source": "CNY", "factor": 1.0},
    }


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_raw_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Canonical raw bars for one symbol in [start, end]."""

    @abstractmethod
    def fetch_research_prices(self, symbol: str, start: str, end: str) -> pd.Series:
        """Adjusted research close (qfq) indexed by date for one symbol."""

    def source_units(self) -> dict[str, Any]:
        """Source units as fetched, before normalization (for the manifest)."""
        return _identity_unit_conversion()


# --------------------------------------------------------------------------- #
# AKShare provider (verified against akshare 1.18.83 at runtime)
# --------------------------------------------------------------------------- #


class AkShareProvider(Provider):
    name = "akshare"

    # Verified at runtime: fund_etf_hist_em columns are
    # 日期/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率
    # 成交量 unit = 手 (hands, x100 -> shares); 成交额 unit = CNY (x1).
    _COLUMN_MAP: ClassVar[dict[str, str]] = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    _VOLUME_FACTOR = 100  # 手 -> shares
    _AMOUNT_FACTOR = 1.0  # CNY

    def __init__(self) -> None:
        try:
            import akshare as ak
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise DataAdapterError(
                "akshare not installed; add the 'data' extra: uv sync --all-extras"
            ) from exc
        self._ak = ak

    def fetch_raw_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        try:
            raw = self._ak.fund_etf_hist_em(
                symbol=bare_symbol(symbol),
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust="",
            )
        except Exception as exc:
            raise DataAdapterError(f"akshare fetch failed for {symbol}: {exc}") from exc
        return self._normalize_raw(raw, symbol)

    def fetch_research_prices(self, symbol: str, start: str, end: str) -> pd.Series:
        try:
            raw = self._ak.fund_etf_hist_em(
                symbol=bare_symbol(symbol),
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust="qfq",
            )
        except Exception as exc:
            raise DataAdapterError(f"akshare qfq fetch failed for {symbol}: {exc}") from exc
        return self._normalize_research(raw, symbol)

    def _normalize_raw(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame(columns=CANONICAL_BAR_COLUMNS)
        missing = set(self._COLUMN_MAP) - set(raw.columns)
        if missing:
            raise DataAdapterError(
                f"akshare returned unexpected columns for {symbol}: missing {missing}"
            )
        out = raw.rename(columns=self._COLUMN_MAP)[list(self._COLUMN_MAP.values())].copy()
        out["date"] = pd.to_datetime(out["date"]).dt.normalize()
        out["volume"] = (out["volume"].astype("float64") * self._VOLUME_FACTOR).astype("int64")
        out["amount"] = out["amount"].astype("float64") * self._AMOUNT_FACTOR
        for col in ("open", "high", "low", "close"):
            out[col] = out[col].astype("float64")
        return out[CANONICAL_BAR_COLUMNS].reset_index(drop=True)

    def _normalize_research(self, raw: pd.DataFrame, symbol: str) -> pd.Series:
        if raw.empty:
            return pd.Series(dtype="float64", name=symbol)
        if "日期" not in raw.columns or "收盘" not in raw.columns:
            raise DataAdapterError(f"akshare qfq missing columns for {symbol}")
        dates = pd.to_datetime(raw["日期"]).dt.normalize()
        close_adj = raw["收盘"].astype("float64")
        return close_adj.set_axis(dates, axis=0).sort_index()

    def source_units(self) -> dict[str, Any]:
        return {
            "volume": {"source": "hands", "factor": self._VOLUME_FACTOR},
            "amount": {"source": "CNY", "factor": self._AMOUNT_FACTOR},
        }


# --------------------------------------------------------------------------- #
# Tushare provider (optional; token from env TUSHARE_TOKEN)
# --------------------------------------------------------------------------- #


class TushareProvider(Provider):
    name = "tushare"

    # fund_daily: vol unit = 手 (lots), amount unit = 千元 (thousand CNY).
    # fund_adj: provides adj_factor; qfq close = close * factor / latest_factor.
    _VOLUME_FACTOR = 100
    _AMOUNT_FACTOR = 1000

    def __init__(self) -> None:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            raise DataAdapterError(
                "TUSHARE_TOKEN not set (use placeholder <YOUR_TUSHARE_TOKEN>)"
            )
        try:
            import tushare as ts
        except ImportError as exc:  # pragma: no cover - optional
            raise DataAdapterError(
                "tushare not installed; add the 'data' extra: uv sync --all-extras"
            ) from exc
        try:
            self._pro = ts.pro_api(token)
        except Exception as exc:
            raise DataAdapterError(f"tushare init failed: {exc}") from exc

    def fetch_raw_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        ts_code = resolve_symbol(symbol)
        try:
            raw = self._pro.fund_daily(
                ts_code=ts_code,
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )
        except Exception as exc:
            raise DataAdapterError(f"tushare fund_daily failed for {symbol}: {exc}") from exc
        if raw is None or raw.empty:
            return pd.DataFrame(columns=CANONICAL_BAR_COLUMNS)
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(raw["trade_date"]).dt.normalize(),
                "open": raw["open"].astype("float64"),
                "high": raw["high"].astype("float64"),
                "low": raw["low"].astype("float64"),
                "close": raw["close"].astype("float64"),
                "volume": (raw["vol"].astype("float64") * self._VOLUME_FACTOR).astype("int64"),
                "amount": raw["amount"].astype("float64") * self._AMOUNT_FACTOR,
            }
        )
        return out[CANONICAL_BAR_COLUMNS].sort_values("date").reset_index(drop=True)

    def fetch_research_prices(self, symbol: str, start: str, end: str) -> pd.Series:
        ts_code = resolve_symbol(symbol)
        try:
            daily = self._pro.fund_daily(
                ts_code=ts_code,
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )
            adj = self._pro.fund_adj(
                ts_code=ts_code,
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )
        except Exception as exc:
            raise DataAdapterError(f"tushare research failed for {symbol}: {exc}") from exc
        if daily is None or daily.empty or adj is None or adj.empty:
            return pd.Series(dtype="float64", name=ts_code)
        merged = daily.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
        merged = merged.sort_values("trade_date")
        latest = merged["adj_factor"].iloc[-1]
        close_adj = merged["close"].astype("float64") * merged["adj_factor"] / latest
        dates = pd.to_datetime(merged["trade_date"]).dt.normalize()
        return close_adj.set_axis(dates, axis=0).sort_index()

    def source_units(self) -> dict[str, Any]:
        return {
            "volume": {"source": "lots", "factor": self._VOLUME_FACTOR},
            "amount": {"source": "thousand CNY", "factor": self._AMOUNT_FACTOR},
        }


# --------------------------------------------------------------------------- #
# Fixture provider (offline, deterministic)
# --------------------------------------------------------------------------- #


class FixtureProvider(Provider):
    name = "fixture"

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        """data[canonical_symbol] = {"raw": DataFrame, "research": Series}."""
        self._data = data

    def fetch_raw_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        symbol = resolve_symbol(symbol)
        if symbol not in self._data:
            raise DataAdapterError(f"fixture has no data for {symbol}")
        return self._data[symbol]["raw"].copy()

    def fetch_research_prices(self, symbol: str, start: str, end: str) -> pd.Series:
        symbol = resolve_symbol(symbol)
        if symbol not in self._data:
            raise DataAdapterError(f"fixture has no data for {symbol}")
        return self._data[symbol]["research"].copy()
