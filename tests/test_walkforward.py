"""M5.2 walk-forward tests: 756/252/252 segmentation, no overlap, train-only
selection, deterministic tie-break, insufficient-data skip, future-data
invariance of train selection."""
from __future__ import annotations

from pql.data.dataset import DatasetView
from pql.validation.base import grid_configs, load_context
from pql.validation.walkforward import (
    STEP,
    TEST,
    TRAIN,
    _select_on_train,
    segment_folds,
    walkforward,
)

MIN_DAYS = TRAIN + TEST


def test_segment_folds_756_252_252():
    assert (TRAIN, TEST, STEP) == (756, 252, 252)
    folds = segment_folds(1008)
    assert folds == [(0, 756, 756, 1008)]


def test_segment_folds_multiple_non_overlapping():
    folds = segment_folds(1260)
    assert folds == [(0, 756, 756, 1008), (252, 1008, 1008, 1260)]
    # test segments disjoint
    assert folds[0][2:] == (756, 1008)
    assert folds[1][2:] == (1008, 1260)
    assert folds[0][2] < folds[1][2]  # test_start of fold0 < test_start of fold1


def test_segment_folds_train_before_test_no_overlap():
    prev_test_end = None
    for (ts, te, us, ue) in segment_folds(2000):
        assert te <= us  # train_end < test_start (no overlap)
        assert (te - ts) == TRAIN
        assert (ue - us) == TEST
        if prev_test_end is not None:
            assert us >= prev_test_end  # test segments do not overlap
        prev_test_end = ue


def test_insufficient_data_skipped(tmp_path):
    root, data_root = _make_short_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    wf = walkforward(spec, grid_configs(spec), ds, cost, data_root)
    assert wf["status"] == "skipped"
    assert "insufficient_data" in wf["reason"]


def test_walkforward_runs_and_selects(tmp_path):
    root, data_root = _make_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    wf = walkforward(spec, grid_configs(spec), ds, cost, data_root)
    assert wf["status"] == "ok"
    assert wf["fold_count"] >= 1
    for fold in wf["folds"]:
        assert fold["test_start"] > fold["train_end"]
        assert fold["selected_params"] in grid_configs(spec)
        assert "train_sharpe" in fold and "test_metrics" in fold
        assert "cagr" in fold["test_metrics"]


def test_walkforward_deterministic_selection(tmp_path):
    root, data_root = _make_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    w1 = walkforward(spec, grid_configs(spec), ds, cost, data_root)
    w2 = walkforward(spec, grid_configs(spec), ds, cost, data_root)
    assert [f["selected_params"] for f in w1["folds"]] == \
        [f["selected_params"] for f in w2["folds"]]


def test_selection_uses_only_train_not_future(tmp_path):
    """Truncating the dataset at a fold's train_end must not change the selected
    params (the signal is PIT; the selection backtest runs only on the train
    window, so future test data cannot influence it)."""
    root, data_root = _make_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    grid = grid_configs(spec)
    full = walkforward(spec, grid, ds, cost, data_root)
    fold = full["folds"][0]
    train_end = fold["train_end"]

    # rebuild the selection with a dataset truncated exactly at train_end
    truncated = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=spec.windows["in_sample"][0], end=train_end,
    )
    _best_sharpe, best_key, best_params = _select_on_train(
        grid, spec, truncated, cost, data_root,
        fold["train_start"], train_end,
    )
    assert best_params == fold["selected_params"]
    assert best_key == fold["selection_key"]


def test_walkforward_records_combined_oos(tmp_path):
    root, data_root = _make_repo(tmp_path)
    spec, cost, ds = load_context(root, "test_momentum_v1", data_root)
    wf = walkforward(spec, grid_configs(spec), ds, cost, data_root)
    assert "combined_oos_metrics" in wf
    assert "sharpe" in wf["combined_oos_metrics"]
    assert 0.0 <= wf["positive_sharpe_segment_fraction"] <= 1.0


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _make_repo(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    return make_momentum_repo(tmp_path, n_days=1100)


def _make_short_repo(tmp_path):
    from tests.m5_fixture import make_momentum_repo
    return make_momentum_repo(tmp_path, n_days=500)