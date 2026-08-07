"""D1 CLI entry point. Subcommand groups are registered as placeholders in M1;
dispatch is implemented in later milestones."""
from __future__ import annotations

import argparse

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
    parser = argparse.ArgumentParser(
        prog="pql", description="Personal Quant Lab CLI"
    )
    sub = parser.add_subparsers(dest="group", metavar="<group>")
    for name in _GROUPS:
        group_parser = sub.add_parser(name, help=f"{name} commands")
        group_parser.add_subparsers(dest="command", metavar="<command>")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.group is None:
        parser.print_help()
        return 0
    # M1: groups are --help placeholders only; real dispatch lands in M2+.
    parser.parse_args([args.group, "--help"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())