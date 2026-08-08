"""D1 CLI entry point. M2 implements `pql data snapshot`; other groups remain
--help placeholders until their milestones."""
from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime

from .data.snapshot import (
    DataQualityError,
    SnapshotBuildError,
    SnapshotExistsError,
    build_snapshot,
)
from .data.symbols import resolve_symbol

_GROUPS = [
    "data",
    "experiment",
    "registry",
    "validate",
    "risk",
    "paper",
    "gate",
    "review",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pql", description="Personal Quant Lab CLI")
    sub = parser.add_subparsers(dest="group", metavar="<group>")

    data = sub.add_parser("data", help="data commands")
    dsub = data.add_subparsers(dest="command", metavar="<command>")
    snap = dsub.add_parser("snapshot", help="build an immutable dataset snapshot")
    snap.add_argument("--source", default="akshare", choices=["akshare", "tushare", "fixture"])
    snap.add_argument("--symbols", required=True,
                      help="comma-separated symbols, e.g. 510300,510500,518880,511010")
    snap.add_argument("--start", required=True, help="YYYY-MM-DD")
    snap.add_argument("--end", default=None, help="YYYY-MM-DD (default: today)")
    snap.add_argument("--name", default=None, help="explicit snapshot version (no overwrite)")
    snap.add_argument("--allow-calendar-gap", action="store_true",
                      help="proceed if calendar does not cover the end date (recorded in manifest)")
    snap.add_argument("--from-fixture", action="store_true",
                      help="build from deterministic synthetic fixture (manifest source=synthetic)")
    snap.add_argument("--data-root", default="data", help="data root directory")

    # --- experiment ---------------------------------------------------------
    experiment = sub.add_parser("experiment", help="experiment commands (M4)")
    xsub = experiment.add_subparsers(dest="command", metavar="<command>")
    xcreate = xsub.add_parser("create", help="create an Experiment (no backtest)")
    xcreate.add_argument("--strategy", required=True, help="strategy name (spec yaml)")
    xcreate.add_argument("--params", default=None,
                         help="k=v,k=v JSON-able scalars (research question config)")
    xcreate.add_argument("--question", default="", help="research question")
    xrun = xsub.add_parser("run", help="run one Run in an Experiment")
    xrun.add_argument("--exp", default=None, help="experiment id EXP-NNNN")
    xrun.add_argument("--strategy", default=None, help="strategy (first-run auto-create)")
    xrun.add_argument("--params", default=None, help="k=v,k=v overrides (must be in param_grid)")
    xrun.add_argument("--run-kind", default="SELECT",
                      choices=["SELECT", "EVALUATE", "STRESS", "DIAGNOSTIC", "FINAL_HOLDOUT"])
    xdecide = xsub.add_parser("decide", help="record an experiment decision")
    xdecide.add_argument("--exp", required=True)
    xdecide.add_argument("--decision", required=True, choices=["ACCEPTED", "REJECTED"])
    xdecide.add_argument("--reason", required=True)

    # --- registry -----------------------------------------------------------
    registry = sub.add_parser("registry", help="derived experiment registry (M4)")
    rsub = registry.add_subparsers(dest="command", metavar="<command>")
    rrebuild = rsub.add_parser("rebuild", help="rebuild the derived parquet index from source of truth")
    rrebuild.add_argument("--out", default="experiment_registry.parquet")
    rlist = rsub.add_parser("list", help="list experiments/runs")
    rlist.add_argument("--strategy", default=None)
    rlist.add_argument("--out", default="experiment_registry.parquet")

    # --- validate -----------------------------------------------------------
    validate = sub.add_parser("validate", help="validation commands (M4)")
    vsub = validate.add_subparsers(dest="command", metavar="<command>")
    vrun = vsub.add_parser("run", help="deterministic run validation")
    vrun.add_argument("--exp", required=True)
    vrun.add_argument("--run", default=None, help="run id RUN-XXXXX (required if >1 run)")

    for name in [g for g in _GROUPS if g not in ("data", "experiment", "registry", "validate")]:
        sub.add_parser(name, help=f"{name} commands").add_subparsers(dest="command")
    return parser


def _cmd_data_snapshot(args) -> int:
    symbols = [resolve_symbol(s) for s in (args.symbols.split(",") if args.symbols else [])]
    end = args.end or datetime.now().astimezone().date().isoformat()
    provider = None
    calendar_adapter = None
    if args.from_fixture:
        from .data.calendar import CalendarAdapter, FixtureCalendar
        from .data.fixtures import make_calendar, make_fixture_provider

        provider = make_fixture_provider(symbols, args.start, end)
        calendar_adapter = CalendarAdapter(
            [FixtureCalendar(make_calendar(args.start, end))]
        )
        source = "fixture"
    else:
        source = args.source
    try:
        result = build_snapshot(
            source=source,
            symbols=symbols,
            start=args.start,
            end=end,
            data_root=args.data_root,
            allow_calendar_gap=args.allow_calendar_gap,
            name=args.name,
            from_fixture=args.from_fixture,
            provider=provider,
            calendar_adapter=calendar_adapter,
        )
    except (SnapshotExistsError, SnapshotBuildError, DataQualityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"snapshot {result.version} -> {result.path}")
    print(f"  source={result.source} symbols={result.manifest['symbols']}")
    print(f"  calendar_source={result.manifest['calendar_source']} "
          f"calendar_end={result.manifest['calendar_end']} "
          f"coverage_gap={result.manifest['coverage_gap']}")
    print(f"  files={result.manifest['files']}")
    return 0


def _parse_params(spec: str | None) -> dict:
    """Parse 'k=v,k=v'. Values are parsed as JSON scalars when possible."""
    if not spec or not spec.strip():
        return {}
    out: dict = {}
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "=" not in tok:
            raise ValueError(f"param must be k=v, got {tok!r}")
        k, v = tok.split("=", 1)
        k = k.strip()
        v = v.strip()
        try:
            import json

            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def _first_experiment_for_strategy(exp_root, strategy: str):
    from .registry.experiments import iter_experiments

    return [e["experiment_id"] for e in iter_experiments(exp_root) if e.get("strategy") == strategy]


def _cmd_experiment_create(args) -> int:
    from .registry.experiments import (
        ExperimentError,
        next_experiment_id,
        write_manifest,
    )

    exp_root = "experiments"
    exp_id = next_experiment_id(exp_root)
    try:
        cfg = _parse_params(args.params)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        write_manifest(
            exp_root,
            experiment_id=exp_id,
            strategy=args.strategy,
            research_question=args.question or f"research on {args.strategy}",
            experiment_config=cfg,
        )
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"created experiment {exp_id} (strategy={args.strategy})")
    return 0


def _cmd_experiment_run(args) -> int:
    from .registry.budget import BudgetError
    from .registry.experiments import (
        ExperimentError,
        load_manifest,
    )
    from .registry.runner import ParamError, run_pipeline

    exp_root = "experiments"
    try:
        params = _parse_params(args.params)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.exp is None:
        if args.strategy is None:
            print("error: must provide --exp or --strategy", file=sys.stderr)
            return 1
        existing = _first_experiment_for_strategy(exp_root, args.strategy)
        if existing:
            print(
                f"error: experiment already exists for {args.strategy}; "
                f"must explicitly pass --exp (existing: {', '.join(existing)})",
                file=sys.stderr,
            )
            return 1
        # first-run shortcut: auto-create the first Experiment (M4.16)
        from .registry.experiments import next_experiment_id, write_manifest

        args.exp = next_experiment_id(exp_root)
        try:
            write_manifest(
                exp_root, experiment_id=args.exp, strategy=args.strategy,
                research_question=f"research on {args.strategy}",
                experiment_config={},
            )
        except ExperimentError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"auto-created experiment {args.exp} for {args.strategy}")
    else:
        try:
            manifest = load_manifest(exp_root, args.exp)
        except ExperimentError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if args.strategy and args.strategy != manifest["strategy"]:
            print(
                f"error: {args.exp} belongs to {manifest['strategy']}, not {args.strategy}",
                file=sys.stderr,
            )
            return 1
        args.strategy = manifest["strategy"]

    try:
        result = run_pipeline(
            repo_root_path=".",
            experiments_root=exp_root,
            strategy=args.strategy,
            params=params,
            experiment_id=args.exp,
            run_kind=args.run_kind,
            data_root="data",
            seed=42,
        )
    except BudgetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ParamError, ExperimentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{args.exp}/{result['run_id']} strategy={args.strategy}")
    print(f"  selection_key={result['selection_key']} run_kind={result['run_kind']}")
    print(f"  dataset_version={result['dataset_version']}")
    print(f"  code_commit={result['code_commit']} code_dirty={result['code_dirty']}")
    print(f"  config_sha256={result['config_sha256']}")
    m = result["metrics"]
    for k in ("cagr", "sharpe", "max_drawdown", "n_trades", "turnover", "exposure"):
        v = m.get(k)
        if isinstance(v, float) and math.isnan(v):
            print(f"  {k}=nan")
        else:
            print(f"  {k}={v if v is None else round(v, 6)}")
    return 0


def _cmd_experiment_decide(args) -> int:
    from .registry.experiments import ExperimentError, decide_experiment

    try:
        manifest = decide_experiment("experiments", args.exp, args.decision, args.reason)
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{args.exp} decision={manifest['decision']} reason={manifest['reason']!r}")
    return 0


def _cmd_registry_rebuild(args) -> int:
    from .registry.experiments import rebuild_registry

    df = rebuild_registry("experiments", args.out)
    print(f"registry rebuilt: {len(df)} runs -> {args.out}")
    return 0


def _cmd_registry_list(args) -> int:

    from .registry.experiments import (
        effective_trial_count,
        iter_all_runs,
        lineage_root,
    )

    rows = iter_all_runs("experiments")
    if args.strategy:
        root = lineage_root(args.strategy)
        rows = [(e, r) for e, r in rows if lineage_root(r.get("strategy", "")) == root]
    if not rows:
        print("(no runs)")
        if args.strategy:
            print(f"effective_trial_count={effective_trial_count('experiments', args.strategy)}")
        return 0
    header = (
        f"{'EXP':<10}{'RUN':<10}{'STRATEGY':<16}{'RUNKIND':<10}{'sel_key':<16}"
        f"{'decision':<10} metrics"
    )
    print(header)
    print("-" * len(header))
    for exp, run in rows:
        m = run.get("metrics") or {}
        summary = (
            f"cagr={m.get('cagr'):.4f} sharpe={m.get('sharpe'):.4f} "
            f"n={m.get('n_trades')}"
        )
        print(
            f"{exp['experiment_id']:<10}{run['run_id']:<10}{run['strategy']:<16}"
            f"{run['run_kind']:<10}{run['selection_key']:<16}"
            f"{exp.get('decision','PENDING'):<10} {summary}"
        )
    if args.strategy:
        print(f"effective_trial_count({args.strategy}) = "
              f"{effective_trial_count('experiments', args.strategy)}")
    return 0


def _cmd_validate_run(args) -> int:
    from .registry.experiments import ExperimentError, iter_runs
    from .validation.deterministic import validate_run

    exp_root = "experiments"
    run_id = args.run
    if run_id is None:
        try:
            runs = iter_runs(exp_root, args.exp)
        except ExperimentError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if len(runs) != 1:
            run_ids = ", ".join(r["run_id"] for r in runs)
            print(
                f"error: {args.exp} has {len(runs)} runs; "
                f"specify --run (runs: {run_ids})",
                file=sys.stderr,
            )
            return 1
        run_id = runs[0]["run_id"]
    try:
        report = validate_run(".", exp_root, args.exp, run_id, data_root="data")
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"validate {args.exp}/{run_id} -> overall={report['overall']}")
    for name, res in report["checks"].items():
        print(f"  {name}: {res['status']}")
    print(f"  report: {report.get('report_path')}")
    return 0 if report["overall"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.group is None:
        parser.print_help()
        return 0
    if args.group == "data" and getattr(args, "command", None) == "snapshot":
        return _cmd_data_snapshot(args)
    if args.group == "experiment" and getattr(args, "command", None) == "create":
        return _cmd_experiment_create(args)
    if args.group == "experiment" and getattr(args, "command", None) == "run":
        return _cmd_experiment_run(args)
    if args.group == "experiment" and getattr(args, "command", None) == "decide":
        return _cmd_experiment_decide(args)
    if args.group == "registry" and getattr(args, "command", None) == "rebuild":
        return _cmd_registry_rebuild(args)
    if args.group == "registry" and getattr(args, "command", None) == "list":
        return _cmd_registry_list(args)
    if args.group == "validate" and getattr(args, "command", None) == "run":
        return _cmd_validate_run(args)
    parser.parse_args([args.group, "--help"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
