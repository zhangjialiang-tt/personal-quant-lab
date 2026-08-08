"""M5.3 / M5.4 robustness tests: full grid, frozen param_stability formula,
calendar-year slicing, positive-CAGR fraction, insufficient-year handling."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pql.schemas import load_spec
from pql.validation.base import grid_configs, load_context
from pql.validation.robustness import (
    MIN_YEAR_DAYS,
    parameter_robustness,
    time_robustness,
)


def test_momentum_grid_is_full_18():
    spec = load_spec("strategies/etf_momentum_v1.yaml")
    grid = grid_configs(spec)
    assert len(grid) == 18  # 3 x 2 x 3 = 18 unique configurations
    keys = {tuple(sorted(c.items())) for c in grid}
    assert len(keys) == 18  # all unique


def test_parameter_robustness_full_grid(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    pr = parameter_robustness(spec, ds, cost, data_root)
    assert pr["grid_size"] == len(grid_configs(spec))
    assert len(pr["rows"]) == pr["grid_size"]
    assert pr["best_params"] is not None
    assert "param_stability" in pr


def test_param_stability_frozen_formula(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    pr = parameter_robustness(spec, ds, cost, data_root)
    best = pr["best_sharpe"]
    stable = [1.0 if r["metrics"]["sharpe"] >= 0.5 * best else 0.0 for r in pr["rows"]]
    assert pr["param_stability"] == pytest.approx(sum(stable) / len(stable))


def test_param_stability_negative_best_uses_frozen_formula(monkeypatch, tmp_path):
    """Even when best_sharpe < 0 the frozen formula (sharpe >= 0.5*best) is used
    verbatim, not a 'more sensible' alternative."""
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    sharpes = [-0.4, -0.2, -0.3, -0.1]  # all negative; best = -0.1

    calls = {"n": 0}

    def fake_run_window(spec, cfg, ds, cost, data_root, start, end):
        calls["n"] += 1
        return SimpleNamespace(metrics={"sharpe": sharpes[calls["n"] - 1]})

    monkeypatch.setattr("pql.validation.robustness.run_window", fake_run_window)
    from pql.validation.robustness import parameter_robustness

    pr = parameter_robustness(spec, ds, cost, data_root)
    best = max(sharpes)
    assert pr["best_sharpe"] == best
    assert all(best < 0 for best in sharpes)  # negative-best case
    expected = sum(1.0 for s in sharpes if s >= 0.5 * best) / len(sharpes)
    assert pr["param_stability"] == pytest.approx(expected)


def test_time_robustness_calendar_years(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path, n_days=1100)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    tr = time_robustness(spec, ds, cost, data_root)
    years = [y["year"] for y in tr["years"]]
    assert years == sorted(years)  # ascending calendar years
    assert len(years) >= 2
    assert all(y.isdigit() and len(y) == 4 for y in years)


def test_time_robustness_positive_cagr_fraction(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path, n_days=1100)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    tr = time_robustness(spec, ds, cost, data_root)
    valid = [y for y in tr["years"] if y["status"] == "ok"]
    assert tr["valid_year_count"] == len(valid)
    expected = sum(1 for y in valid if y["metrics"].get("cagr", 0) > 0) / len(valid)
    assert tr["positive_cagr_fraction"] == pytest.approx(expected)


def test_time_robustness_insufficient_year_excluded(tmp_path):
    """A year with fewer than MIN_YEAR_DAYS trading days is marked
    insufficient_data and excluded from the positive-CAGR denominator."""
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path, n_days=1100)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    tr = time_robustness(spec, ds, cost, data_root)
    for y in tr["years"]:
        if y["trading_days"] < MIN_YEAR_DAYS:
            assert y["status"] == "insufficient_data"
    # valid years all have >= MIN_YEAR_DAYS
    assert all(y["trading_days"] >= MIN_YEAR_DAYS for y in tr["years"] if y["status"] == "ok")


def test_trading_days_counts_unique_dates_not_rows(tmp_path):
    """A year's trading_days is the number of UNIQUE dates, never inflated by
    the universe size (M5 review P1)."""
    import pandas as pd

    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path, n_days=1100)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    dates = pd.to_datetime(ds.research_frame()["date"]).dt.normalize()
    n_sym = ds.research_frame()["symbol"].nunique()
    assert n_sym > 1
    tr = time_robustness(spec, ds, cost, data_root)
    for y in tr["years"]:
        n_unique = int(dates[dates.dt.year == int(y["year"])].nunique())
        assert y["trading_days"] == n_unique
        assert y["trading_days"] < n_unique * n_sym  # not inflated x universe


def test_nan_first_config_does_not_poison_best(monkeypatch, tmp_path):
    """Sharpe=NaN must be treated as -inf for best-selection: a NaN first config
    must not lock best_sharpe into NaN (M5 review P1)."""
    import math

    from pql.registry.experiments import selection_key
    from tests.m5_fixture import make_momentum_repo
    root, data_root = make_momentum_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    grid = grid_configs(spec)
    assert len(grid) == 4
    sharpes = [float("nan"), 1.0, 2.0, 0.5]  # first config is NaN
    calls = {"n": 0}

    def fake_run_window(_spec, cfg, _ds, _cost, _data_root, _start, _end):
        calls["n"] += 1
        return SimpleNamespace(metrics={"sharpe": sharpes[calls["n"] - 1]})

    monkeypatch.setattr("pql.validation.robustness.run_window", fake_run_window)
    pr = parameter_robustness(spec, ds, cost, data_root)
    assert pr["best_sharpe"] == 2.0
    assert pr["best_selection_key"] == selection_key(grid[2])  # cfg with sharpe 2.0
    assert not math.isnan(pr["best_sharpe"])