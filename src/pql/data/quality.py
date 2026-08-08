"""M2 data quality checks (M2.4). Run on the normalized long frame BEFORE a
snapshot is written. Reject-level failures abort the build; warning-level items
are recorded in the manifest / report. Rules are not weakened to pass real data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Columns the quality check requires on the normalized long frame.
REQUIRED_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume", "amount"]

# adj/raw ratio: a >15% day-over-day jump is flagged as an anomaly (warning).
_ADJ_RATIO_JUMP = 0.15


class DataQualityError(RuntimeError):
    """Raised when a reject-level quality check fails (aborts snapshot build)."""


@dataclass
class QualityReport:
    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    missing_ratio_by_symbol: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def run_quality_checks(
    frame: pd.DataFrame,
    calendar_dates: set[pd.Timestamp],
    *,
    allow_calendar_gap: bool = False,
    warn_missing_ratio: float = 0.05,
    reject_missing_ratio: float = 0.20,
) -> QualityReport:
    """Validate the normalized long frame. Returns a QualityReport; callers must
    raise DataQualityError when `report.passed` is False."""
    report = QualityReport()
    if frame.empty:
        report.errors.append("empty frame")
        return _finalize(report)

    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        report.errors.append(f"missing columns: {sorted(missing)}")
        return _finalize(report)

    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)

    # --- cross-symbol checks -------------------------------------------------
    dup = frame.duplicated(subset=["symbol", "date"]).sum()
    if dup:
        report.errors.append(f"duplicate (symbol, date) rows: {dup}")

    for symbol, sub in frame.groupby("symbol", sort=True):
        where = f"{symbol}"
        # monotonic dates
        if not sub["date"].is_monotonic_increasing:
            report.errors.append(f"{where}: dates not monotonically increasing")
        # calendar membership
        free_dates = set(sub["date"]) - calendar_dates
        if free_dates:
            if allow_calendar_gap:
                report.warnings.append(
                    f"{where}: {len(free_dates)} dates outside trading calendar (gap allowed)"
                )
            else:
                bad = sorted(str(d.date()) for d in list(free_dates)[:5])
                report.errors.append(f"{where}: dates outside trading calendar: {bad}")
        # OHLC relation
        bad_ohlc = sub[
            ~(
                (sub["low"] <= sub["open"])
                & (sub["open"] <= sub["high"])
                & (sub["low"] <= sub["close"])
                & (sub["close"] <= sub["high"])
            )
        ]
        for _, row in bad_ohlc.iterrows():
            report.errors.append(
                f"{where} {row['date'].date()}: bad OHLC O={row['open']} H={row['high']} "
                f"L={row['low']} C={row['close']}"
            )
        # price > 0
        neg = sub[(sub[["open", "high", "low", "close"]] <= 0).any(axis=1)]
        for _, row in neg.iterrows():
            report.errors.append(f"{where} {row['date'].date()}: non-positive price")
        # volume >= 0
        neg_vol = sub[sub["volume"] < 0]
        for idx in neg_vol.index:
            report.errors.append(
                f"{where} {sub.loc[idx, 'date'].date()}: negative volume {sub.loc[idx, 'volume']}"
            )
        # missing trading days
        if calendar_dates and not sub.empty:
            lo, hi = sub["date"].min(), sub["date"].max()
            expected = pd.DatetimeIndex(sorted(d for d in calendar_dates if lo <= d <= hi))
            actual = set(sub["date"])
            miss = len(set(expected) - actual)
            ratio = miss / len(expected) if len(expected) else 0.0
            report.missing_ratio_by_symbol[symbol] = round(ratio, 4)
            if ratio > reject_missing_ratio:
                report.errors.append(
                    f"{where}: {miss}/{len(expected)} trading days missing "
                    f"({ratio:.1%} > {reject_missing_ratio:.0%})"
                )
            elif ratio > warn_missing_ratio:
                report.warnings.append(
                    f"{where}: {miss}/{len(expected)} trading days missing ({ratio:.1%})"
                )
        # adj/raw ratio jump (anomaly marker, warning only)
        if "close_adj" in frame.columns:
            ratio_series = sub["close_adj"] / sub["close"]
            jump = ratio_series.pct_change().abs() > _ADJ_RATIO_JUMP
            for idx in sub.index[jump]:
                report.anomalies.append(
                    f"{where} {sub.loc[idx, 'date'].date()}: adj/raw ratio jump > "
                    f"{_ADJ_RATIO_JUMP:.0%} (possible ex-dividend or data error)"
                )

    return _finalize(report)


def _finalize(report: QualityReport) -> QualityReport:
    report.passed = not report.errors
    return report
