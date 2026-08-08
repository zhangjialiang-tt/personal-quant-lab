"""M3 TimingContract (D2). Encodes the data-availability invariant:
data_available_time <= signal_time <= decision_time < execution_time.

Default: signal/decision at T close, execution at T+1 (execution_bar=1).
Production backtests must reject execution_bar < 1 (look-ahead).
"""
from __future__ import annotations

from dataclasses import dataclass


class TimingError(ValueError):
    """Raised when a TimingContract admits look-ahead or is internally invalid."""


@dataclass(frozen=True)
class TimingContract:
    signal_time: str = "T_close"        # signal uses only data <= T close
    decision_time: str = "T_close"      # decision made at T close
    execution_bar: int = 1              # execute on bar T+N
    execution_price: str = "close"      # "close" | "open"

    def validate(self) -> None:
        assert_no_lookahead(self)
        if self.execution_price not in ("close", "open"):
            raise TimingError(
                f"execution_price must be 'close' or 'open', got {self.execution_price!r}"
            )


def assert_no_lookahead(contract: TimingContract) -> None:
    """execution_bar < 1 means the signal and the fill share a bar (look-ahead)."""
    if contract.execution_bar < 1:
        raise TimingError(
            f"execution_bar={contract.execution_bar} admits look-ahead; "
            "signal at T must fill no earlier than T+1"
        )
