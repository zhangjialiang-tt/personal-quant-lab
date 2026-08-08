"""M7.63 TargetPortfolio tests: equal weight, max_positions, risk-off cash,
sum<=1, no negative weights, monthly schedule reuses the calendar. Does NOT
duplicate the momentum signal logic."""
from __future__ import annotations

import pandas as pd
import pytest

from pql.portfolio.target import (
    TargetPortfolio,
    TargetPortfolioError,
    build_target_portfolio_series,
    target_for_series_row,
    target_portfolio_for_day,
)
from pql.schemas import load_spec
from tests.m7_fixture import make_momentum_repo


def _repo(tmp_path, n_days=300):
    root, data_root, reg = make_momentum_repo(tmp_path, n_days=n_days)
    spec = load_spec(root / "strategies" / "test_momentum_v1.yaml")
    from pql.data.dataset import DatasetView

    ds = DatasetView.load(spec.dataset_version, data_root, universe=spec.universe,
                          start=spec.windows["in_sample"][0],
                          end=spec.windows["in_sample"][1])
    return root, data_root, reg, spec, ds


def test_validate_weights_invariants():
    ok = TargetPortfolio(date="2026-01-06", weights={"A": 0.5, "B": 0.5},
                         cash_weight=0.0)
    ok.validate(max_positions=3)  # no error
    with pytest.raises(TargetPortfolioError):
        TargetPortfolio(date="d", weights={"A": -0.1}).validate()
    with pytest.raises(TargetPortfolioError):
        TargetPortfolio(date="d", weights={"A": 0.6, "B": 0.6}).validate()
    with pytest.raises(TargetPortfolioError):
        TargetPortfolio(date="d", weights={"A": 0.5, "B": 0.5}).validate(max_positions=1)


def test_build_series_invariants(tmp_path):
    _root, _data_root, _reg, spec, ds = _repo(tmp_path)
    series = build_target_portfolio_series(spec, ds.research_frame(), None,
                                           ds.calendar_dates())
    assert set(series.columns) == set(spec.universe)
    # rebalance rows are non-negative and sum to <= 1
    for d in series.index:
        row = series.loc[d]
        if row.isna().all():
            continue
        assert (row.fillna(0.0) >= -1e-9).all()
        assert row.fillna(0.0).sum() <= 1 + 1e-9


def test_rebalance_schedule_uses_calendar(tmp_path):
    _root, _data_root, _reg, spec, ds = _repo(tmp_path)
    series = build_target_portfolio_series(spec, ds.research_frame(), None,
                                           ds.calendar_dates())
    rebal_days = [d for d in series.index if not series.loc[d].isna().all()]
    assert len(rebal_days) > 0
    # each rebalance day is the FIRST actual trading day of its calendar month
    from pql.signals.momentum_rotation import first_trading_day_of_month

    firsts = set(first_trading_day_of_month(ds.calendar_dates()))
    for d in rebal_days:
        assert d in firsts


def test_equal_weight_and_max_positions(tmp_path):
    _root, _data_root, _reg, spec, ds = _repo(tmp_path)
    series = build_target_portfolio_series(spec, ds.research_frame(), None,
                                           ds.calendar_dates())
    for d in series.index:
        row = series.loc[d]
        if row.isna().all():
            continue
        nz = row[row > 1e-9]
        assert len(nz) <= spec.risk["max_positions"]
        if len(nz) > 0:
            # equal weight: every active symbol ~1/N
            for v in nz.values:
                assert abs(v - 1.0 / len(nz)) < 1e-9


def test_risk_off_cash_when_no_eligible(tmp_path):
    # a day with all weights zero -> cash_weight == 1
    _root, _data_root, _reg, spec, ds = _repo(tmp_path)
    series = build_target_portfolio_series(spec, ds.research_frame(), None,
                                           ds.calendar_dates())
    any_risk_off = False
    for d in series.index:
        row = series.loc[d]
        if not row.isna().all() and (row.fillna(0.0) == 0).all():
            any_risk_off = True
            tp = target_for_series_row(series, d, spec)
            assert tp is not None
            assert tp.weights == {}
            assert abs(tp.cash_weight - 1.0) < 1e-9
    # the fixture has an early window where momentum is not yet positive
    assert any_risk_off


def test_target_portfolio_for_day_none_on_hold(tmp_path):
    _root, _data_root, _reg, spec, ds = _repo(tmp_path)
    tp = target_portfolio_for_day(spec, ds.research_frame(), None,
                                  ds.calendar_dates(), pd.Timestamp("2099-01-01"))
    assert tp is None  # not a rebalance day