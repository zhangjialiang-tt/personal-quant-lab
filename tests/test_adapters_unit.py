"""M2 unit-normalization and canonical-symbol contracts at the adapter boundary."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.data.adapters import AkShareProvider
from pql.data.symbols import SymbolError, resolve_symbol


def test_canonical_symbol_resolution():
    assert resolve_symbol("510300") == "510300.SH"
    assert resolve_symbol("159915") == "159915.SZ"
    assert resolve_symbol("510300.SH") == "510300.SH"
    assert resolve_symbol(" 510300 ") == "510300.SH"
    with pytest.raises(SymbolError):
        resolve_symbol("")
    with pytest.raises(SymbolError):
        resolve_symbol("510300.XY")


class _FakeAk:
    """Fake akshare returning 成交量 in 手 (hands) and 成交额 in CNY."""

    def fund_etf_hist_em(self, symbol, period, start_date, end_date, adjust):
        if adjust == "":
            return pd.DataFrame(
                {
                    "日期": ["2024-01-02"],
                    "开盘": [10.0],
                    "收盘": [10.5],
                    "最高": [10.6],
                    "最低": [9.9],
                    "成交量": [100],  # hands
                    "成交额": [1500.0],  # CNY
                }
            )
        return pd.DataFrame({"日期": ["2024-01-02"], "收盘": [10.5]})


def test_akshare_unit_conversion_happens_in_adapter_boundary():
    prov = AkShareProvider()
    prov._ak = _FakeAk()
    raw = prov.fetch_raw_bars("510300.SH", "2024-01-01", "2024-01-31")
    # 100 hands -> 10000 shares; amount stays CNY
    assert raw.iloc[0]["volume"] == 10000
    assert raw.iloc[0]["amount"] == 1500.0
    assert set(raw.columns) == {"date", "open", "high", "low", "close", "volume", "amount"}
    # research close_adj is the qfq close
    research = prov.fetch_research_prices("510300.SH", "2024-01-01", "2024-01-31")
    assert research.iloc[0] == 10.5


def test_akshare_source_units_recorded():
    prov = AkShareProvider()
    units = prov.source_units()
    assert units["volume"]["source"] == "hands"
    assert units["volume"]["factor"] == 100
    assert units["amount"]["factor"] == 1.0