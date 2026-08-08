"""M2 immutable snapshot builder (M2.3 / D5).

Pipeline: fetch raw + research per symbol -> canonical normalization (in the
Provider) -> merge to long frame -> trading calendar + coverage gate ->
quality validation -> write immutable snapshot (prices.parquet, calendar.parquet,
manifest.json with sha256) with no-overwrite semantics and verify-on-read.
`data/raw/` is a deletable download cache; `data/snapshots/` is research evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .adapters import (
    CANONICAL_UNITS,
    AkShareProvider,
    Provider,
    TushareProvider,
)
from .calendar import CalendarAdapter, CalendarError, ensure_coverage
from .quality import DataQualityError, run_quality_checks
from .symbols import resolve_symbol

SCHEMA_VERSION = 1


class SnapshotExistsError(RuntimeError):
    """Raised when an explicit snapshot version already exists (no overwrite)."""


class SnapshotBuildError(RuntimeError):
    """Raised for any snapshot build failure."""


@dataclass
class SnapshotResult:
    version: str
    path: Path
    manifest: dict = field(default_factory=dict)
    source: str = ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_read_only(path: Path) -> None:
    """Remove write bits (best-effort guard against accidental edits; not the
    security boundary — checksums are)."""
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:  # pragma: no cover - platform differences
        pass


def default_version_base(today: date | None = None) -> str:
    today = today or datetime.now().astimezone().date()
    return f"market-{today:%Y%m%d}"


def next_version(data_root: Path, base: str) -> str:
    """market-YYYYMMDD-vN with N incremented until the directory is free."""
    n = 1
    while (data_root / snapshots_dir() / f"{base}-v{n}").exists():
        n += 1
    return f"{base}-v{n}"


def snapshots_dir() -> str:
    return "snapshots"


def build_snapshot(
    *,
    source: str,
    symbols: list[str],
    start: str,
    end: str,
    data_root: str | Path,
    allow_calendar_gap: bool = False,
    name: str | None = None,
    from_fixture: bool = False,
    provider: Provider | None = None,
    calendar_adapter: CalendarAdapter | None = None,
) -> SnapshotResult:
    """Build an immutable dataset snapshot. `provider`/`calendar_adapter` may be
    injected (fixture) for offline tests; otherwise resolved from `source`."""
    root = Path(data_root)
    snapshots = root / snapshots_dir()
    raw_dir = root / "raw"
    snapshots.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    canonical_symbols = [resolve_symbol(s) for s in symbols]

    # --- provider ------------------------------------------------------------
    if from_fixture:
        if provider is None:
            raise SnapshotBuildError("--from-fixture requires a FixtureProvider")
        prov = provider
        manifest_source = "synthetic"
    else:
        prov = provider or _resolve_provider(source)
        manifest_source = prov.name

    # --- fetch + merge to canonical long frame -------------------------------
    frames: list[pd.DataFrame] = []
    for sym in canonical_symbols:
        raw = prov.fetch_raw_bars(sym, start, end)
        research = prov.fetch_research_prices(sym, start, end)
        if raw.empty:
            continue
        raw = raw.copy()
        raw["symbol"] = sym
        if research is not None and not research.empty:
            raw = raw.merge(
                research.rename("close_adj").reset_index().rename(columns={"index": "date"}),
                on="date",
                how="left",
            )
        else:
            raw["close_adj"] = pd.NA
        frames.append(raw)
    if not frames:
        raise SnapshotBuildError("no data fetched for any symbol")
    long_frame = pd.concat(frames, ignore_index=True)
    long_frame["date"] = pd.to_datetime(long_frame["date"]).dt.normalize()
    long_frame = long_frame.sort_values(["symbol", "date"]).reset_index(drop=True)

    # --- calendar + coverage gate --------------------------------------------
    if calendar_adapter is None:
        calendar_adapter = _default_calendar_adapter()
    try:
        calendar, calendar_source = calendar_adapter.fetch(start, end)
    except CalendarError as exc:
        raise SnapshotBuildError(f"calendar unavailable: {exc}") from exc
    calendar_dates = set(pd.to_datetime(calendar["trade_date"]).dt.normalize())
    # Coverage is checked against the LAST TRADING DAY actually present in the
    # data, not the requested `end` boundary (which may fall on a non-trading
    # day). This preserves the contract's intent: a stale calendar must not
    # silently accept newer data.
    data_end = pd.Timestamp(long_frame["date"].max()).normalize()
    try:
        ensure_coverage(calendar, data_end.strftime("%Y-%m-%d"), allow_gap=allow_calendar_gap)
    except CalendarError as exc:
        raise SnapshotBuildError(str(exc)) from exc
    coverage_gap = pd.Timestamp(calendar["trade_date"].max()).normalize() < data_end

    # --- data quality gate ----------------------------------------------------
    report = run_quality_checks(
        long_frame, calendar_dates, allow_calendar_gap=allow_calendar_gap
    )
    if not report.passed:
        raise DataQualityError(
            "snapshot rejected by quality gate:\n  " + "\n  ".join(report.errors)
        )

    # --- version resolution (no-overwrite) -------------------------------------
    if name:
        version = name
        target = snapshots / version
        if target.exists():
            raise SnapshotExistsError(f"snapshot already exists: {version}")
    else:
        version = next_version(root, default_version_base())
        target = snapshots / version

    # --- write raw cache (deletable) then immutable snapshot -------------------
    raw_cache = raw_dir / f"{version}_{manifest_source}_raw.parquet"
    long_frame.drop(columns=["close_adj"], errors="ignore").to_parquet(raw_cache, index=False)

    target.mkdir(parents=True, exist_ok=True)
    prices_path = target / "prices.parquet"
    calendar_path = target / "calendar.parquet"
    long_frame.to_parquet(prices_path, index=False)
    calendar.to_parquet(calendar_path, index=False)

    source_units = prov.source_units()
    manifest = {
        "dataset_version": version,
        "source": manifest_source,
        "provider": prov.name,
        "download_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "adjustment": "qfq",
        "units": dict(CANONICAL_UNITS),
        "source_units": source_units,
        "normalized_units": {"volume": "shares", "amount": "CNY"},
        "conversion": {
            k: f"x{v['factor']} ({v['source']} -> {CANONICAL_UNITS[k]})"
            for k, v in source_units.items()
        },
        "symbols": canonical_symbols,
        "start": start,
        "end": end,
        "calendar_source": calendar_source,
        "calendar_end": str(pd.Timestamp(calendar["trade_date"].max()).date()),
        "allow_calendar_gap": allow_calendar_gap,
        "coverage_gap": coverage_gap,
        "warnings": report.warnings,
        "anomalies": report.anomalies,
        "missing_ratio_by_symbol": report.missing_ratio_by_symbol,
        "files": {
            "prices.parquet": _sha256(prices_path),
            "calendar.parquet": _sha256(calendar_path),
        },
    }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    for fname in ("prices.parquet", "calendar.parquet", "manifest.json"):
        _make_read_only(target / fname)

    return SnapshotResult(version=version, path=target, manifest=manifest, source=manifest_source)


def _resolve_provider(source: str) -> Provider:
    if source == "akshare":
        return AkShareProvider()
    if source == "tushare":
        return TushareProvider()
    raise SnapshotBuildError(f"unknown source: {source!r}")


def _default_calendar_adapter() -> CalendarAdapter:
    from .calendar import AkShareCalendar, CalendarError, TushareTradeCalendar

    adapter = CalendarAdapter()
    try:
        adapter.add_source(AkShareCalendar())
    except (CalendarError, ImportError):
        pass  # akshare unavailable; fall through to other sources
    token = os.environ.get("TUSHARE_TOKEN", "")
    if token:
        try:
            adapter.add_source(TushareTradeCalendar(token))
        except (CalendarError, ImportError):
            pass  # tushare unavailable; fall through to other sources
    return adapter