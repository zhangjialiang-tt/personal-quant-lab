"""Canonical security symbol resolution (D4).

Internal symbols use the canonical form `510300.SH`. Bare codes accepted at the
CLI/config boundary are resolved here explicitly; core data structures never mix
`510300` / `"510300"` / `"510300.SH"`.
"""
from __future__ import annotations

import re

_CANONICAL_RE = re.compile(r"^\d{6}\.(SH|SZ)$")

# v0.1 universe is all SSE-listed ETFs (5xxxxx). Bare-code -> exchange mapping
# covers the common cases so the system is not hard-wired to one exchange.
_SH_PREFIXES = ("5", "6")
_SZ_PREFIXES = ("0", "1", "3")


class SymbolError(ValueError):
    """Raised for an unresolvable or malformed security symbol."""


def resolve_symbol(symbol: str) -> str:
    """Resolve a user-supplied symbol (bare or canonical) to canonical form."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise SymbolError(f"empty symbol: {symbol!r}")
    s = symbol.strip().upper()
    if "." in s:
        if not _CANONICAL_RE.match(s):
            raise SymbolError(f"malformed canonical symbol: {symbol!r} (want 6 digits + .SH/.SZ)")
        return s
    if not s.isdigit() or len(s) < 5:
        raise SymbolError(f"unresolvable bare symbol: {symbol!r}")
    if s.startswith(_SH_PREFIXES):
        return f"{s}.SH"
    if s.startswith(_SZ_PREFIXES):
        return f"{s}.SZ"
    raise SymbolError(f"cannot infer exchange for bare symbol: {symbol!r}")


def bare_symbol(symbol: str) -> str:
    """Return the bare 6-digit code (for provider APIs that take bare codes)."""
    return resolve_symbol(symbol).split(".")[0]
