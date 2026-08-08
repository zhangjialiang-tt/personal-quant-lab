"""M4.9 selection_key + M4.11 lineage tests (deterministic, canonical)."""
from __future__ import annotations

from pql.registry.experiments import lineage_root, selection_key


def test_same_params_same_key():
    assert selection_key({"ma_period": 200}) == selection_key({"ma_period": 200})


def test_dict_key_order_does_not_change_key():
    a = selection_key({"ma_period": 200, "top_k": 2})
    b = selection_key({"top_k": 2, "ma_period": 200})
    assert a == b


def test_different_params_different_key():
    assert selection_key({"ma_period": 200}) != selection_key({"ma_period": 220})


def test_key_is_readable_and_stable():
    assert selection_key({"ma_period": 200}) == "ma_period=200"


def test_nested_values_canonical():
    a = selection_key({"x": {"b": 1, "a": 2}})
    b = selection_key({"x": {"a": 2, "b": 1}})
    assert a == b


def test_lineage_root_strips_vN_suffix():
    assert lineage_root("etf_trend_v1") == "etf_trend"
    assert lineage_root("etf_trend_v2") == "etf_trend"
    assert lineage_root("etf_trend_v3") == "etf_trend"


def test_lineage_root_identity_without_suffix():
    assert lineage_root("etf_trend_v1") == lineage_root("etf_trend_v1")
    assert lineage_root("buy_hold_control") == "buy_hold_control"


def test_lineage_groups_editions_but_not_siblings():
    assert lineage_root("etf_trend_v1") == lineage_root("etf_trend_v2")
    assert lineage_root("etf_trend_v1") != lineage_root("etf_momentum_v1")