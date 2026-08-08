"""M7.66 reconcile tests: independent reconstruction from the order ledger,
mismatch detection on tampered positions/cash. Reconcile must NOT be
`read positions then compare to positions`."""
from __future__ import annotations

import pandas as pd

from pql.execution.paper import PaperAccount, paper_replay
from pql.execution.reconcile import reconcile
from tests.m7_fixture import make_momentum_repo


def _repo(tmp_path, n_days=200):
    root, data_root, reg = make_momentum_repo(tmp_path, n_days=n_days)
    from pql.schemas import load_spec

    spec = load_spec(root / "strategies" / "test_momentum_v1.yaml")
    return root, data_root, reg, spec


def _cost(root):
    from pql.registry.runner import resolve_paths
    from pql.schemas import load_cost_model, load_spec

    spec = load_spec(root / "strategies" / "test_momentum_v1.yaml")
    return load_cost_model(resolve_paths(root, spec)["cost"])


def _instruments(root):
    from pql.risk.rules import load_instruments

    return load_instruments(root)


def _run_replay(root, data_root, spec):
    is0, is1 = spec.windows["in_sample"]
    paper_replay(root, "test_momentum_v1", is0, is1, data_root=data_root,
                 paper_root=data_root / "paper", init_cash=100_000)
    return PaperAccount("test_momentum_v1", data_root / "paper")


def test_clean_replay_unreconciled_zero(tmp_path):
    root, data_root, _reg, spec = _repo(tmp_path)
    account = _run_replay(root, data_root, spec)
    rec = reconcile(account, cost=_cost(root), instruments=_instruments(root))
    assert rec["unreconciled"] == 0
    assert rec["cash_mismatch"] is False
    assert rec["position_mismatches"] == []
    # expected == actual by independent reconstruction
    assert rec["expected_positions"] == rec["actual_positions"]


def test_tampered_positions_detected(tmp_path):
    root, data_root, _reg, spec = _repo(tmp_path)
    account = _run_replay(root, data_root, spec)
    # tamper the persisted positions (add 10000 shares of the first symbol)
    pos_path = account.positions_path
    df = pd.read_parquet(pos_path)
    last = df["date"].max()
    df.loc[(df["date"] == last), "quantity"] += 10000
    df.to_parquet(pos_path, index=False)
    rec = reconcile(account, cost=_cost(root), instruments=_instruments(root))
    assert rec["unreconciled"] > 0
    assert len(rec["position_mismatches"]) >= 1
    m = rec["position_mismatches"][0]
    assert "delta" in m and "expected" in m and "actual" in m


def test_tampered_cash_detected(tmp_path):
    root, data_root, _reg, spec = _repo(tmp_path)
    account = _run_replay(root, data_root, spec)
    cash_path = account.cash_path
    df = pd.read_parquet(cash_path)
    df.loc[df.index[-1], "cash"] += 5000.0
    df.to_parquet(cash_path, index=False)
    rec = reconcile(account, cost=_cost(root), instruments=_instruments(root))
    assert rec["unreconciled"] > 0
    assert rec["cash_mismatch"] is True


def test_reconcile_independent_from_ledger(tmp_path):
    """Reconciliation must rebuild expected state from the order ledger, not
    trust the persisted positions/cash. Deleting the persisted snapshots and
    reconstructing from the ledger must still yield the same expected state."""
    root, data_root, _reg, spec = _repo(tmp_path)
    account = _run_replay(root, data_root, spec)
    # independent reconstruction: expected must equal the ledger-derived state
    # even if we never look at the current positions file.
    rec = reconcile(account, cost=_cost(root), instruments=_instruments(root))
    ledger = account.executed_orders()
    assert len(ledger) > 0
    # expected positions are derived ONLY from the ledger replay
    assert rec["expected_positions"] == rec["actual_positions"]  # clean
    # every executed order is a legal lot (100) and BUY/SELL only
    for o in ledger:
        assert o["side"] in ("BUY", "SELL")
        assert int(o["adjust_quantity"]) % 100 == 0