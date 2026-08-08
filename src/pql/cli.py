"""D1 CLI entry point. M2 implements `pql data snapshot`; other groups remain
--help placeholders until their milestones."""
from __future__ import annotations

import argparse
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

    for name in [g for g in _GROUPS if g != "data"]:
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.group is None:
        parser.print_help()
        return 0
    if args.group == "data" and getattr(args, "command", None) == "snapshot":
        return _cmd_data_snapshot(args)
    # M1 groups are --help placeholders only; real dispatch lands in later milestones.
    parser.parse_args([args.group, "--help"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
