"""M2 HoldoutGuard base contract (D5). Guarded one-time consumption of the Final
Holdout, fail-closed: `consumed=true` is persisted (and fsynced) BEFORE any
holdout data leaves the guard. Access requires the strategy to be Candidate
Freeze-locked (candidate_freeze present in the registry, set in M6)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import yaml

from ..data.dataset import DatasetView


class HoldoutError(RuntimeError):
    """Raised when holdout access is denied (not frozen, already consumed, ...)."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_registry(registry_path: Path) -> dict:
    if not registry_path.exists():
        return {"strategies": []}
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {"strategies": []}


def _write_registry(registry_path: Path, registry: dict) -> None:
    with registry_path.open("w", encoding="utf-8") as fh:
        fh.write(yaml.safe_dump(registry, sort_keys=False, allow_unicode=True))
        fh.flush()
        os.fsync(fh.fileno())


class HoldoutGuard:
    def __init__(self, registry_path: str | Path, data_root: str | Path) -> None:
        self.registry_path = Path(registry_path)
        self.data_root = Path(data_root)

    def holdout_slice(
        self,
        strategy_id: str,
        version: str,
        start: str,
        end: str,
        caller: str = "",
        purpose: str = "final_holdout",
    ):
        """Consume the Final Holdout once and return the dataset window.

        Order (fail-closed): (1) reject unless UNUSED and candidate frozen;
        (2) persist consumed=true + fsync; (3) append audit log; (4) only then
        load and return the data. A crash between (2) and (4) wastes the holdout
        rather than silently permitting a second access.
        """
        registry = _load_registry(self.registry_path)
        entry = next((e for e in registry.get("strategies", []) if e.get("id") == strategy_id), None)
        if entry is None:
            raise HoldoutError(f"strategy not registered: {strategy_id}")

        # Candidate must be freeze-locked (D5/D6; set by M6 promotion logic).
        freeze = entry.get("candidate_freeze")
        if not freeze or not isinstance(freeze, dict):
            raise HoldoutError(f"candidate not frozen for {strategy_id}; access denied")

        status = entry.get("holdout_status") or {}
        if status.get("consumed"):
            raise HoldoutError(f"holdout already consumed for {strategy_id}")

        candidate_hash = str(freeze.get("spec_sha256") or freeze.get("code_commit") or "")
        # --- fail-closed: persist consumed BEFORE releasing data --------------
        entry["holdout_status"] = {
            "consumed": True,
            "consumed_at": _now(),
            "candidate_hash": candidate_hash,
        }
        _write_registry(self.registry_path, registry)

        access_log = self.data_root / "metadata" / "holdout_access.log"
        access_log.parent.mkdir(parents=True, exist_ok=True)
        with access_log.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "time": _now(),
                        "caller": caller,
                        "strategy": strategy_id,
                        "purpose": purpose,
                        "dataset_version": version,
                        "start": start,
                        "end": end,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            fh.flush()
            os.fsync(fh.fileno())

        # --- release data last -------------------------------------------------
        view = DatasetView.load(version, self.data_root, start=start, end=end)
        return view.research_frame()
