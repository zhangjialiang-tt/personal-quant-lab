"""M2 DatasetView (M2.5 / D5). The single dataset entry point for run_backtest().
`load()` verifies snapshot checksums on every read (verify-on-read); a changed
file raises SnapshotIntegrityError. research_frame() exposes adjusted research
prices (close_adj) for signals; execution_frame() exposes raw open/close.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .snapshot import snapshots_dir


class SnapshotIntegrityError(RuntimeError):
    """Raised when a snapshot file fails checksum verification on read."""


class DatasetVersionNotFound(RuntimeError):
    """Raised when the requested snapshot version does not exist."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class DatasetView:
    def __init__(
        self,
        version: str,
        data_root: str | Path,
        universe: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        self.version = version
        self.data_root = Path(data_root)
        self.path = self.data_root / snapshots_dir() / version
        self.universe = universe
        self.start = start
        self.end = end
        self._manifest: dict = {}
        self._prices: pd.DataFrame | None = None
        self._calendar: pd.DataFrame | None = None

    # -- loading --------------------------------------------------------------
    @classmethod
    def load(
        cls,
        version: str,
        data_root: str | Path,
        universe: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> DatasetView:
        view = cls(version, data_root, universe=universe, start=start, end=end)
        view._verify()
        return view

    def _verify(self) -> None:
        if not self.path.exists():
            raise DatasetVersionNotFound(f"snapshot not found: {self.version}")
        manifest_path = self.path / "manifest.json"
        if not manifest_path.exists():
            raise SnapshotIntegrityError(f"missing manifest for {self.version}")
        self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for fname, expected in self._manifest.get("files", {}).items():
            fp = self.path / fname
            if not fp.exists():
                raise SnapshotIntegrityError(f"missing snapshot file: {fname}")
            actual = _sha256(fp)
            if actual != expected:
                raise SnapshotIntegrityError(
                    f"checksum mismatch for {self.version}/{fname}: "
                    f"expected {expected}, got {actual}"
                )

    # -- data access ------------------------------------------------------------
    def manifest(self) -> dict:
        if not self._manifest:
            self._verify()
        return dict(self._manifest)

    def _prices_frame(self) -> pd.DataFrame:
        if self._prices is None:
            self._prices = pd.read_parquet(self.path / "prices.parquet")
            self._prices["date"] = pd.to_datetime(self._prices["date"]).dt.normalize()
        return self._prices

    def calendar_dates(self) -> set[pd.Timestamp]:
        if self._calendar is None:
            self._calendar = pd.read_parquet(self.path / "calendar.parquet")
        return set(pd.to_datetime(self._calendar["trade_date"]).dt.normalize())

    def research_frame(self) -> pd.DataFrame:
        """Adjusted research prices (close_adj) for signals, in [start, end]."""
        df = self._prices_frame()[["date", "symbol", "close_adj"]]
        return self._filter(df)

    def execution_frame(self) -> pd.DataFrame:
        """Raw open/close for historical execution simulation."""
        df = self._prices_frame()[["date", "symbol", "open", "close"]]
        return self._filter(df)

    def amount_frame(self) -> pd.DataFrame:
        """Canonical amount (CNY) for liquidity analysis (M5 regimes)."""
        df = self._prices_frame()[["date", "symbol", "amount"]]
        return self._filter(df)

    def _filter(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df
        if self.universe:
            out = out[out["symbol"].isin(self.universe)]
        if self.start:
            out = out[out["date"] >= pd.Timestamp(self.start).normalize()]
        if self.end:
            out = out[out["date"] <= pd.Timestamp(self.end).normalize()]
        return out.sort_values(["symbol", "date"]).reset_index(drop=True)