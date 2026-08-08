"""M6.10 trial-ledger regression tests: effective_trial_count = COUNT(DISTINCT
selection_key across the strategy lineage) where run_kind == SELECT. Bootstrap /
stress / kill / folds / final holdout NEVER add to N."""
from __future__ import annotations

import json
import pathlib
import tempfile

from pql.registry.experiments import effective_trial_count, selection_key


def _write_run(exp_root, exp, run, strategy, run_kind, params):
    d = exp_root / exp / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    (d / "run.yaml").write_text(json.dumps({
        "run_id": run, "experiment_id": exp, "strategy": strategy,
        "parameters": params, "selection_key": selection_key(params),
        "run_kind": run_kind, "visible_to_researcher": True,
        "dataset_version": "v", "dataset_checksums": {}, "market_rule_version": "m",
        "cost_model_version": "c", "cost_config": {}, "gate_version": "g",
        "code_commit": "c", "code_dirty": False, "git_diff_sha256": "",
        "config_sha256": "", "dependencies": {}, "seed": 42, "timing": {},
        "metrics": {}, "created": "2026-01-01T00:00:00",
    }), encoding="utf-8")
    (d / "equity.parquet").write_bytes(b"")
    (exp_root / exp / "manifest.yaml")


def _write_manifest(exp_root, exp, strategy):
    d = exp_root / exp
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yaml").write_text(json.dumps({
        "experiment_id": exp, "strategy": strategy, "research_question": "q",
        "experiment_config": {}, "decision": "PENDING", "reason": "",
        "decision_time": None, "created": "2026-01-01T00:00:00",
    }), encoding="utf-8")


def test_full_m6_pipeline_still_five_trials():
    """5 SELECT configs + 1000 bootstrap + 3 cost stress + 5 exec stress +
    8 kill families/subvariants + walk-forward folds + final holdout -> N=5."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "etf_momentum_v1")
    # 5 DISTINCT SELECT configs
    configs = [
        {"momentum_days": 60, "top_k": 1},
        {"momentum_days": 60, "top_k": 2},
        {"momentum_days": 120, "top_k": 1},
        {"momentum_days": 120, "top_k": 2},
        {"momentum_days": 180, "top_k": 2},
    ]
    for i, cfg in enumerate(configs):
        _write_run(tmp, "EXP-0001", f"RUN-{i + 1:05d}", "etf_momentum_v1", "SELECT", cfg)
    # 1000 bootstrap samples (DIAGNOSTIC)
    for i in range(1000):
        _write_run(tmp, "EXP-0001", f"RUN-{10000 + i:05d}", "etf_momentum_v1", "DIAGNOSTIC",
                   {"momentum_days": 120, "top_k": 2})
    # 3 cost stress + 5 exec stress (STRESS)
    for i in range(8):
        _write_run(tmp, "EXP-0001", f"RUN-{20000 + i:05d}", "etf_momentum_v1", "STRESS",
                   {"momentum_days": 120, "top_k": 2})
    # 8+ kill family subvariants (DIAGNOSTIC)
    for i in range(20):
        _write_run(tmp, "EXP-0001", f"RUN-{30000 + i:05d}", "etf_momentum_v1", "DIAGNOSTIC",
                   {"momentum_days": 120, "top_k": 2, "_kill": "K0" + str(i % 8 + 1)})
    # walk-forward folds (EVALUATE)
    for i in range(5):
        _write_run(tmp, "EXP-0001", f"RUN-{40000 + i:05d}", "etf_momentum_v1", "EVALUATE",
                   {"momentum_days": 120, "top_k": 2})
    # final holdout
    _write_run(tmp, "EXP-0001", "RUN-50001", "etf_momentum_v1", "FINAL_HOLDOUT",
               {"momentum_days": 120, "top_k": 2})
    assert effective_trial_count(tmp, "etf_momentum_v1") == 5


def test_lineage_union_effective_trial_count():
    """v1 SELECT = {A,B,C}; v2 SELECT = {B,C,D}; stress/bootstrap/kill/many ->
    N(v2) = {A,B,C,D} = 4 (NOT 6, NOT 3)."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "etf_trend_v1")
    _write_manifest(tmp, "EXP-0002", "etf_trend_v2")
    for i, p in enumerate([{"ma_period": 150}, {"ma_period": 180}, {"ma_period": 200}]):
        _write_run(tmp, "EXP-0001", f"RUN-{i + 1:05d}", "etf_trend_v1", "SELECT", p)
    for i, p in enumerate([{"ma_period": 180}, {"ma_period": 200}, {"ma_period": 220}]):
        _write_run(tmp, "EXP-0002", f"RUN-{i + 1:05d}", "etf_trend_v2", "SELECT", p)
    # noise: stress x20, bootstrap x1000, kill x many
    for i in range(20):
        _write_run(tmp, "EXP-0002", f"RUN-{10000 + i:05d}", "etf_trend_v2", "STRESS", {"ma_period": 999})
    for i in range(1000):
        _write_run(tmp, "EXP-0002", f"RUN-{20000 + i:05d}", "etf_trend_v2", "DIAGNOSTIC", {"ma_period": 999})
    for i in range(50):
        _write_run(tmp, "EXP-0002", f"RUN-{30000 + i:05d}", "etf_trend_v2", "DIAGNOSTIC", {"ma_period": 999})
    _write_run(tmp, "EXP-0002", "RUN-40001", "etf_trend_v2", "FINAL_HOLDOUT", {"ma_period": 220})
    assert effective_trial_count(tmp, "etf_trend_v2") == 4


def test_duplicate_select_does_not_double_count():
    tmp = pathlib.Path(tempfile.mkdtemp())
    _write_manifest(tmp, "EXP-0001", "s_v1")
    for _ in range(3):
        _write_run(tmp, "EXP-0001", next_run(tmp), "s_v1", "SELECT", {"p": 1})
    _write_run(tmp, "EXP-0001", next_run(tmp), "s_v1", "SELECT", {"p": 2})
    assert effective_trial_count(tmp, "s_v1") == 2


def next_run(tmp):
    import re

    run_dir = tmp / "EXP-0001" / "runs"
    mx = 0
    if run_dir.exists():
        for d in run_dir.iterdir():
            m = re.match(r"RUN-(\d+)", d.name)
            if m:
                mx = max(mx, int(m.group(1)))
    return f"RUN-{mx + 1:05d}"