"""M1 tests: schema YAML round-trip + strict unknown-key rejection."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pql.schemas import (
    SchemaError,
    StrategySpec,
    dump_spec,
    load_cost_model,
    load_spec,
)

REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def _spec_dict() -> dict:
    return {
        "name": "etf_trend_v1",
        "hypothesis": "中期表现较强的资产存在一定趋势延续性。",
        "universe": ["510300", "510500", "518880", "511010"],
        "benchmark": "510300",
        "signal": {"kind": "trend_ma", "ma_period": 200},
        "rebalance": "daily",
        "risk": {"max_positions": 2},
        "dataset_version": "market-20260808-v1",
        "market_rule_version": "cn-etf-2026-v1",
        "cost_model_version": "cn-etf-cost-2026-v1",
        "timing": {"execution_bar": 1, "execution_price": "close"},
        "windows": {"in_sample": ["2013-07-29", "2024-12-31"],
                    "holdout": ["2025-01-01", "2026-08-07"]},
        "param_grid": {"ma_period": [150, 180, 200, 220, 250]},
        "research_budget": {
            "max_total_selection_runs": 50,
            "max_variants_per_param": {"ma_period": 20},
            "holdout_access": {"allowed": False},
        },
        "seed": 42,
    }


def test_spec_roundtrip(tmp_path):
    target = tmp_path / "spec.yaml"
    dump_spec(StrategySpec(**_spec_dict()), target)
    loaded = load_spec(target)
    assert loaded == StrategySpec(**_spec_dict())


def test_unknown_top_level_key_rejected(tmp_path):
    data = _spec_dict()
    data["bogus_field"] = 1
    target = tmp_path / "spec.yaml"
    target.write_text(
        "name: etf_trend_v1\n"
        "hypothesis: h\n"
        "universe: [510300]\n"
        "benchmark: 510300\n"
        "signal: {kind: trend_ma}\n"
        "rebalance: daily\n"
        "risk: {max_positions: 2}\n"
        "dataset_version: v\n"
        "market_rule_version: v\n"
        "cost_model_version: v\n"
        "param_grid: {ma_period: [200]}\n"
        "seed: 42\n"
        "bogus_field: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="bogus_field"):
        load_spec(target)


def test_unknown_timing_key_rejected(tmp_path):
    data = _spec_dict()
    data["timing"]["bogus"] = 1
    target = tmp_path / "spec.yaml"
    dump_spec(StrategySpec(**data), target)
    with pytest.raises(SchemaError, match="timing"):
        load_spec(target)


def test_unknown_budget_key_rejected(tmp_path):
    data = _spec_dict()
    data["research_budget"]["bogus"] = 1
    target = tmp_path / "spec.yaml"
    dump_spec(StrategySpec(**data), target)
    with pytest.raises(SchemaError, match="research_budget"):
        load_spec(target)


def test_missing_required_field_rejected(tmp_path):
    data = _spec_dict()
    del data["seed"]
    target = tmp_path / "spec.yaml"
    target.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(SchemaError, match="seed"):
        load_spec(target)


def test_signal_risk_free_form_accepted(tmp_path):
    # signal/risk are strategy extension points: inner keys must be allowed.
    data = _spec_dict()
    data["signal"] = {"kind": "momentum_rotation", "momentum_days": 120,
                      "ma_filter": 200, "top_k": 2}
    data["risk"] = {"max_positions": 2, "custom_halt": True}
    target = tmp_path / "spec.yaml"
    dump_spec(StrategySpec(**data), target)
    loaded = load_spec(target)
    assert loaded.signal["momentum_days"] == 120
    assert loaded.risk["custom_halt"] is True


def test_load_real_cost_model():
    cost = load_cost_model(f"{REPO_ROOT}/config/costs/cn_etf_2026.yaml")
    assert cost.version == "cn-etf-cost-2026-v1"
    assert cost.fee_rate == 0.0003
    assert cost.stamp_duty == 0.0
    assert cost.slippage == 0.001


def test_cost_model_unknown_key_rejected(tmp_path):
    target = tmp_path / "cost.yaml"
    target.write_text(
        "version: v\nfee_rate: 0.01\nstamp_duty: 0.0\nslippage: 0.0\nbogus: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(SchemaError, match="bogus"):
        load_cost_model(target)