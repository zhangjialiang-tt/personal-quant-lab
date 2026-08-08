"""M4.2 Research Budget (D6 / A6 / M4.12-14).

`check_budget(spec, ledger)` enforces the frozen search space from the SAME fact
source as effective_trial_count (the selection_key ledger): exceeding
`max_total_selection_runs` or a `max_variants_per_param` cap rejects the run
with exit 2 and a directive to create a new hypothesis/strategy version. The AI
never silently extends the research search space.

Counting is lineage-aware (etf_trend_v1/v2 share the search budget) and only
SELECT runs consume trials; EVALUATE/STRESS/DIAGNOSTIC/FINAL_HOLDOUT never add
to N. Duplicate selection_keys do not consume additional budget.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pql.schemas import StrategySpec

from .experiments import (
    param_variant_counts,
    select_run_keys,
    selection_key,
)


class BudgetError(RuntimeError):
    """Raised when a run would exceed the frozen research budget."""


def _budget_total(spec: StrategySpec) -> int:
    return int(spec.research_budget.get("max_total_selection_runs", 0))


def _budget_variants(spec: StrategySpec) -> dict[str, int]:
    raw = spec.research_budget.get("max_variants_per_param", {})
    return {str(k): int(v) for k, v in (raw or {}).items()}


def check_budget(spec: StrategySpec, experiments_root: str | Path) -> None:
    """Raise BudgetError if the next SELECT would exceed a frozen budget cap.

    The check is stateless over the *existing* ledger: the caller has already
    merged the new params into the selection set by the time budget is enforced
    (the run is written to the ledger regardless of budget, but a budget-exceed
    SELECT is rejected before it is executed). See `check_would_exceed`.
    """
    total = _budget_total(spec)
    existing = select_run_keys(experiments_root, spec.name)
    if total > 0 and len(existing) >= total:
        raise BudgetError(
            f"Research Budget exceeded (max_total_selection_runs={total}). "
            "Create a new hypothesis/strategy version instead of silently "
            "extending search."
        )
    variants = _budget_variants(spec)
    counts = param_variant_counts(experiments_root, spec.name)
    for key, cap in variants.items():
        if cap <= 0:
            continue
        n = len(counts.get(key, set()))
        if n >= cap:
            raise BudgetError(
                f"Research Budget exceeded (max_variants_per_param[{key}]={cap}, "
                f"already {n} distinct variants). Create a new hypothesis/strategy "
                "version instead of silently extending search."
            )


def check_would_exceed(spec: StrategySpec, experiments_root: str | Path,
                       params: dict[str, Any]) -> None:
    """Enforce budget for a PROPOSED SELECT before it runs: the candidate's
    selection_key is merged into the ledger counts, then the caps are checked.
    A duplicate key (already seen) does not consume budget, but the run itself
    is still executed and written to the ledger (Run count up, trial count
    unchanged)."""
    from .experiments import selection_key

    cand_key = selection_key(params)
    existing = select_run_keys(experiments_root, spec.name)
    select_count_after = len(existing) + (0 if cand_key in existing else 1)

    total = _budget_total(spec)
    if total > 0 and select_count_after > total:
        raise BudgetError(
            f"Research Budget exceeded (max_total_selection_runs={total}); "
            f"this SELECT would make {select_count_after} distinct trials. "
            "Create a new hypothesis/strategy version instead of silently "
            "extending search."
        )

    variants = _budget_variants(spec)
    counts = param_variant_counts(experiments_root, spec.name)
    for key, cap in variants.items():
        if cap <= 0:
            continue
        proposed = set(counts.get(key, set()))
        if key in params:
            proposed.add(str(params[key]))
        if len(proposed) > cap:
            raise BudgetError(
                f"Research Budget exceeded (max_variants_per_param[{key}]={cap}); "
                f"this SELECT would make {len(proposed)} distinct values. Create a "
                "new hypothesis/strategy version instead of silently extending search."
            )


def check_grid_budget(spec: StrategySpec, experiments_root: str | Path,
                      grid: list[dict[str, Any]]) -> None:
    """Preflight the ENTIRE proposed SELECT grid against the research budget
    BEFORE any backtest runs. This is the candidate-pipeline gate: if the union
    of existing SELECT keys and the grid's keys exceeds max_total_selection_runs,
    or any param would exceed its variant cap, the whole evaluation is rejected
    with zero backtests executed (M5 review P0)."""
    cand_keys = {selection_key(cfg) for cfg in grid}
    existing = select_run_keys(experiments_root, spec.name)
    total_after = len(existing | cand_keys)

    total = _budget_total(spec)
    if total > 0 and total_after > total:
        raise BudgetError(
            f"Research Budget exceeded (max_total_selection_runs={total}); the "
            f"proposed grid would make {total_after} distinct trials "
            f"({len(existing)} existing + {len(cand_keys)} proposed). Create a "
            "new hypothesis/strategy version instead of silently extending search."
        )

    variants = _budget_variants(spec)
    counts = param_variant_counts(experiments_root, spec.name)
    for key, cap in variants.items():
        if cap <= 0:
            continue
        proposed = set(counts.get(key, set()))
        for cfg in grid:
            if key in cfg:
                proposed.add(str(cfg[key]))
        if len(proposed) > cap:
            raise BudgetError(
                f"Research Budget exceeded (max_variants_per_param[{key}]={cap}); "
                f"the proposed grid would make {len(proposed)} distinct values. "
                "Create a new hypothesis/strategy version instead of silently "
                "extending search."
            )


__all__ = ["BudgetError", "check_budget", "check_grid_budget", "check_would_exceed"]