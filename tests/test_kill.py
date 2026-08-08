"""M6.5 kill-test family tests."""
from __future__ import annotations

import pandas as pd

from pql.validation.kill import (
    drop_best_year,
    kill_tests,
    killed_family_count,
    top_winning_trades,
)


def _momentum_context(tmp_path, n_days=400):
    from pql.data.dataset import DatasetView
    from pql.registry.runner import resolve_paths
    from pql.schemas import load_cost_model, load_spec
    from tests.m5_fixture import make_momentum_repo

    root, data_root = make_momentum_repo(tmp_path, n_days=n_days)
    spec = load_spec(root / "strategies" / "test_momentum_v1.yaml")
    paths = resolve_paths(root, spec)
    cost = load_cost_model(paths["cost"])
    ds = DatasetView.load(spec.dataset_version, data_root, universe=spec.universe,
                          start=spec.windows["in_sample"][0], end=spec.windows["in_sample"][1])
    return spec, cost, ds, data_root


# --------------------------------------------------------------------------- #
# K01 drop_best_year
# --------------------------------------------------------------------------- #
def test_k01_removes_actual_best_natural_year():
    # 3 natural years; year2 has the clearly highest annual return.
    dates = pd.to_datetime([
        "2020-01-15", "2020-06-30", "2020-12-15",
        "2021-01-15", "2021-06-30", "2021-12-15",
        "2022-01-15", "2022-06-30", "2022-12-15",
    ])
    # equity: year1 +10%, year2 +60%, year3 +5%
    eq = pd.Series([100, 110, 110, 176, 176, 176, 184.8, 184.8, 184.8], index=dates)
    rets = eq.pct_change().dropna()
    best_year, remaining = drop_best_year(rets)
    assert best_year == 2021  # the year with the highest annual return
    assert remaining.index.year.unique().tolist() == [2020, 2022]


def test_k01_family_present(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    assert set(fam) == {"K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08"}
    assert fam["K01"]["family_name"] == "drop_best_year"
    assert len(fam["K01"]["variants"]) == 1


# --------------------------------------------------------------------------- #
# K02 drop_best_trades (rounding + two modes)
# --------------------------------------------------------------------------- #
def test_k02_top_trades_rounding():
    # 15 closed trades -> k = min(10, max(1, ceil(1.5))) = 2
    trades = [{"net_pnl": i} for i in range(15)]
    top = top_winning_trades(trades, 15)
    assert len(top) == 2
    # 5 trades -> k = ceil(0.5) = 1
    top5 = top_winning_trades([{"net_pnl": i} for i in range(5)], 5)
    assert len(top5) == 1
    # 150 trades -> k = min(10, 15) = 10
    top150 = top_winning_trades([{"net_pnl": i} for i in range(150)], 150)
    assert len(top150) == 10
    # no closed trades -> empty (NOT_APPLICABLE path)
    assert top_winning_trades([], 0) == []


def test_k02_two_modes_recorded_separately(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k02 = fam["K02"]
    modes = {v["variant_id"] for v in k02["variants"]}
    assert "K02_ATTRIBUTION" in modes and "K02_COUNTERFACTUAL" in modes
    att = next(v for v in k02["variants"] if v["variant_id"] == "K02_ATTRIBUTION")
    cf = next(v for v in k02["variants"] if v["variant_id"] == "K02_COUNTERFACTUAL")
    assert att["gate_relevant"] is False  # attribution is diagnostic only
    assert cf["gate_relevant"] is True
    assert att["parameters"]["mode"] == "ATTRIBUTION_TEST"
    assert cf["parameters"]["mode"] == "COUNTERFACTUAL_TEST"


# --------------------------------------------------------------------------- #
# K03 universe_loo
# --------------------------------------------------------------------------- #
def test_k03_loo_count(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k03 = fam["K03"]
    assert len(k03["variants"]) == len(spec.universe)  # one variant per symbol
    assert k03["gate_relevant_variant_count"] == len(spec.universe)


# --------------------------------------------------------------------------- #
# K04 / K05 / K08
# --------------------------------------------------------------------------- #
def test_k04_delay_execution_bar_plus_one(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k04 = fam["K04"]
    base_bar = int(spec.timing.get("execution_bar", 1))
    assert k04["variants"][0]["parameters"]["execution_bar"] == base_bar + 1


def test_k05_cost_x2(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k05 = fam["K05"]
    assert k05["variants"][0]["parameters"]["multiplier"] == 2


def test_k08_shift_start_60_trading_days(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k08 = fam["K08"]
    assert k08["variants"][0]["parameters"]["shift_trading_days"] == 60


# --------------------------------------------------------------------------- #
# K06 shift_rebalance (schedule shift, NOT execution delay)
# --------------------------------------------------------------------------- #
def test_k06_shift_rebalance_is_schedule_shift(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k06 = fam["K06"]
    assert k06["family_name"] == "shift_rebalance"
    assert k06["variants"][0]["parameters"]["rebalance_shift_days"] == 1
    # K06 must NOT be equivalent to K04 (execution delay): the decision
    # schedule itself moved, not just the fill delay.
    assert k06["variants"][0]["parameters"] != {
        "execution_bar": int(spec.timing.get("execution_bar", 1)) + 1
    }


# --------------------------------------------------------------------------- #
# K07 perturb_params
# --------------------------------------------------------------------------- #
def test_k07_perturb_params_outside_grid_no_budget(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    k07 = fam["K07"]
    # momentum_days base is 10 -> -10% = 9, +10% = 11 (distinct variants)
    assert len(k07["variants"]) >= 2
    values = {next(iter(v["parameters"].values())) for v in k07["variants"]}
    assert 9 in values and 11 in values
    # kill/perturb runs are diagnostic stress, never SELECT: they never consume
    # research budget or add trial N (verified by the ledger test suite).
    assert all(v["gate_relevant"] for v in k07["variants"])


# --------------------------------------------------------------------------- #
# Family aggregation
# --------------------------------------------------------------------------- #
def test_killed_family_count_counts_families_not_variants():
    # 1 family KILLED with 3 killed children still counts as 1 family.
    fam = {
        "K01": {"family_result": "KILLED", "variants": []},
        "K02": {"family_result": "PASSED", "variants": []},
        "K03": {"family_result": "KILLED", "variants": [
            {"result": "KILLED"}, {"result": "KILLED"}, {"result": "KILLED"},
        ]},
    }
    assert killed_family_count(fam) == 2  # K01 + K03, NOT 3+1 children


def test_killed_fraction_over_gate_relevant_variants(tmp_path):
    spec, cost, ds, data_root = _momentum_context(tmp_path)
    fam = kill_tests(spec, cost, ds, data_root)
    for f in fam.values():
        rel = [v for v in f["variants"] if v["gate_relevant"]]
        if rel:
            killed = sum(1 for v in rel if v["result"] == "KILLED")
            assert f["killed_fraction"] == killed / len(rel)