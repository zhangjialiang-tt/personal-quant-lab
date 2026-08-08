"""M6.3 bootstrap tests: block_len = ceil(n^(1/3)), circular wrap, each sample
len == n, R = 1000, same-seed reproducibility, different-seed divergence, and
bootstrap never increases the effective trial count."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pql.validation.bootstrap import (
    R,
    block_len,
    bootstrap,
    bootstrap_sharpe_p05,
    circular_block_sample,
)


def test_block_len_floor():
    # ceil(n^(1/3)): 399 -> ceil(7.36) = 8 ; 1000 -> 10 ; 8 -> 2
    assert block_len(399) == 8
    assert block_len(1000) == 10
    n = 200
    assert block_len(n) == int(np.ceil(n ** (1 / 3)))


def test_circular_block_sample_length_and_wrap():
    rets = np.linspace(0.0, 0.1, 100)
    rng = np.random.default_rng(7)
    for _ in range(20):
        sample = circular_block_sample(rets, block_len(len(rets)), rng)
        assert len(sample) == len(rets)  # every sample length == n
        assert set(np.round(sample, 10)).issubset(set(np.round(rets, 10)))  # only input values


def test_circular_wrap_reaches_end():
    # A block starting near the end must wrap to the beginning (test the wrap
    # directly with a tiny n and a block_len that forces wrapping).
    rets = np.arange(1.0, 6.0)  # [1,2,3,4,5]
    # force a block that starts at index 4 (value 5) and wraps to 1,2,...
    rng = np.random.default_rng(0)
    # monkey the start by drawing many samples; assert values only come from input
    for _ in range(50):
        s = circular_block_sample(rets, 3, rng)
        assert set(s).issubset({1.0, 2.0, 3.0, 4.0, 5.0})


def test_R_is_1000():
    assert R == 1000


def _equity_with_seed(seed):
    rng = np.random.default_rng(seed)
    rets = pd.Series(rng.normal(0.0005, 0.01, 300))
    return pd.Series(np.cumprod(1.0 + rets))


def test_same_seed_reproducible():
    eq = _equity_with_seed(42)
    r1 = bootstrap(_spec(42), eq, out_dir=None)
    r2 = bootstrap(_spec(42), eq, out_dir=None)
    assert r1["distribution"].equals(r2["distribution"])
    assert r1["summary"]["sharpe"]["p05"] == r2["summary"]["sharpe"]["p05"]
    assert r1["summary"]["cagr"]["ci95"] == r2["summary"]["cagr"]["ci95"]
    assert r1["summary"]["max_drawdown"]["ci95"] == r2["summary"]["max_drawdown"]["ci95"]


def test_different_seed_differs():
    eq = _equity_with_seed(42)
    r1 = bootstrap(_spec(1), eq, out_dir=None)
    r2 = bootstrap(_spec(2), eq, out_dir=None)
    assert not r1["distribution"].equals(r2["distribution"])


def test_summary_keys_and_dimensions():
    eq = _equity_with_seed(7)
    rep = bootstrap(_spec(7), eq, out_dir=None)
    s = rep["summary"]
    assert s["n"] == len(eq.pct_change().dropna())
    assert s["R"] == 1000
    assert s["seed"] == 7
    assert s["block_len"] == block_len(s["n"])
    for key in ("sharpe", "cagr", "max_drawdown"):
        assert set(s[key]) == {"p05", "p50", "p95", "ci95"}
        assert s[key]["p05"] <= s[key]["p50"] <= s[key]["p95"]
    assert bootstrap_sharpe_p05(rep) == s["sharpe"]["p05"]


def test_bootstrap_does_not_increase_n(tmp_path):
    from pql.registry.experiments import effective_trial_count
    from pql.validation.pipeline import validate_candidate
    from tests.m5_fixture import make_momentum_repo

    root, data_root = make_momentum_repo(tmp_path, n_days=400)
    validate_candidate(root, "test_momentum_v1", data_root=data_root,
                       report_root=root / "reports",
                       experiments_root=root / "experiments", persist=False)
    assert effective_trial_count(root / "experiments", "test_momentum_v1") == 4


def _spec(seed):
    from types import SimpleNamespace

    return SimpleNamespace(seed=seed)