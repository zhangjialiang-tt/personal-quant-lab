"""M6.9 AI Review Bundles (D1 / proposal §20).

`pql review bundle --exp EXP-NNNN --role reviewer|challenger` assembles the
evidence a reviewer/challenger needs and writes a markdown bundle under
`reports/review_bundles/<exp>_<role>.md`.

Hard isolation contract:
- Reviewer sees StrategySpec, hypothesis, experiment/run manifests, relevant
  source code, dataset metadata, cost/timing metadata, candidate validation
  results, gates, provenance.
- Challenger sees FACTS + the `StrategySpec.hypothesis` (it must be able to
  attack the economic logic), but MUST NOT see the researcher prompt, `research/`
  exploration, researcher reasoning, or any prior reviewer conclusion. The
  bundle generator enforces this filter.
- The generator never runs the actual AI review; that happens in a fresh
  isolated session. Reviewer output is never injected into a challenger bundle.
"""
from __future__ import annotations

import json
from pathlib import Path

from pql.registry.experiments import iter_experiments, iter_runs
from pql.schemas import load_spec

# Challenger MUST NOT see these (hard filter).
_CHALLENGER_BANNED_MARKERS = [
    "researcher_prompt",
    "research/",
    "SECRET_RESEARCHER_REASONING",
    "researcher reasoning",
    "reviewer_recommendation",
    "review:",
]

_REVIEWER_ROLES = {"reviewer", "challenger"}


class BundleError(RuntimeError):
    """Raised when a review bundle cannot be assembled."""


def _find_experiment(experiments_root, exp_id) -> dict:
    for exp in iter_experiments(experiments_root):
        if exp.get("experiment_id") == exp_id:
            return exp
    raise BundleError(f"experiment not found: {exp_id}")


def _source_of_strategy(strategy: str, repo_root: Path) -> dict[str, str]:
    """The strategy's source files (spec + signal modules) as text."""
    out: dict[str, str] = {}
    spec_path = repo_root / "strategies" / f"{strategy}.yaml"
    if spec_path.exists():
        out[str(spec_path)] = spec_path.read_text(encoding="utf-8")
    # include signal/validation source referenced by the strategy
    for sub in ("src/pql/signals", "src/pql/validation", "src/pql/backtest"):
        d = repo_root / sub
        if d.exists():
            for p in sorted(d.glob("*.py")):
                out[str(p)] = p.read_text(encoding="utf-8")
    return out


def _dataset_metadata(spec, data_root: Path) -> dict:
    manifest_path = data_root / "snapshots" / spec.dataset_version / "manifest.json"
    if not manifest_path.exists():
        return {"dataset_version": spec.dataset_version, "manifest": None}
    return {
        "dataset_version": spec.dataset_version,
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
    }


def _candidate_report(repo_root: Path, strategy: str) -> dict | None:
    p = repo_root / "reports" / "validation" / strategy / "candidate_report.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _filter_banned(text: str) -> str:
    """Remove / mask any banned content from a challenger bundle (fail-closed:
    if a banned marker is found, drop the whole section it belongs to)."""
    for marker in _CHALLENGER_BANNED_MARKERS:
        if marker.lower() in text.lower():
            return "[filtered: content matching a challenger-banned marker]"
    return text


def build_bundle(
    repo_root: str | Path,
    exp_id: str,
    role: str,
    *,
    experiments_root: str | Path = "experiments",
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    out_root: str | Path = "reports",
) -> str:
    """Assemble and persist a review bundle markdown. Returns the bundle path."""
    role = role.lower()
    if role not in _REVIEWER_ROLES:
        raise BundleError(f"role must be reviewer|challenger, got {role!r}")
    repo = Path(repo_root)
    exp = _find_experiment(experiments_root, exp_id)
    strategy = exp.get("strategy", "")
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")

    lines: list[str] = []
    lines.append(f"# Review Bundle — {exp_id} ({role})")
    lines.append("")
    lines.append(f"strategy: `{strategy}`")
    lines.append(f"experiment: `{exp_id}`")
    lines.append("")

    # -- StrategySpec + hypothesis (REQUIRED for both roles) ------------------
    lines.append("## StrategySpec")
    lines.append("")
    lines.append(f"hypothesis: {spec.hypothesis}")
    lines.append("")
    lines.append("```yaml")
    lines.append((repo / "strategies" / f"{strategy}.yaml").read_text(encoding="utf-8"))
    lines.append("```")
    lines.append("")

    # -- experiment + run manifests -------------------------------------------
    lines.append("## Experiment Manifest")
    lines.append("")
    lines.append("```yaml")
    lines.append(
        json.dumps(
            {k: exp[k] for k in ("experiment_id", "strategy", "research_question",
                                 "decision", "reason") if k in exp},
            ensure_ascii=False, indent=2,
        )
    )
    lines.append("```")
    lines.append("")
    lines.append("## Runs")
    lines.append("")
    for run in iter_runs(experiments_root, exp_id):
        lines.append("```yaml")
        lines.append(json.dumps({
            "run_id": run["run_id"], "run_kind": run["run_kind"],
            "selection_key": run["selection_key"], "parameters": run.get("parameters"),
            "metrics": run.get("metrics"), "code_commit": run.get("code_commit"),
            "config_sha256": run.get("config_sha256"),
        }, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

    # -- dataset metadata ------------------------------------------------------
    lines.append("## Dataset Metadata")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(_dataset_metadata(spec, data_root), ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")

    # -- cost / timing metadata ------------------------------------------------
    lines.append("## Cost / Timing Metadata")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({
        "cost_model_version": spec.cost_model_version,
        "timing": spec.timing,
        "windows": spec.windows,
    }, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")

    # -- candidate validation results + gates ----------------------------------
    cand = _candidate_report(repo, strategy)
    if cand:
        lines.append("## Candidate Validation")
        lines.append("")
        for key in ("overall", "ready_for_candidate_freeze", "gate_results",
                    "code_clean", "effective_trial_count", "dataset_source",
                    "market_evidence", "deflated_sharpe", "bootstrap",
                    "cost_stress", "execution_stress", "kill_tests"):
            if key in cand:
                lines.append(f"### {key}")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(cand[key], ensure_ascii=False, indent=2, default=str))
                lines.append("```")
                lines.append("")

    # -- source code -----------------------------------------------------------
    lines.append("## Source Code")
    lines.append("")
    for path, text in _source_of_strategy(strategy, repo).items():
        lines.append(f"### `{path}`")
        lines.append("")
        lines.append("```python")
        lines.append(text)
        lines.append("```")
        lines.append("")

    body = "\n".join(lines)

    if role == "challenger":
        # Hard filter: challenger gets FACTS only, never researcher reasoning.
        banned = [m for m in _CHALLENGER_BANNED_MARKERS if m.lower() in body.lower()]
        if banned:
            raise BundleError(
                f"challenger bundle contains banned content: {banned}; "
                "refusing to write a leaky bundle"
            )

    out_dir = Path(out_root) / "review_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{exp_id}_{role}.md"
    out_path.write_text(body, encoding="utf-8")
    return str(out_path)


__all__ = ["BundleError", "build_bundle"]