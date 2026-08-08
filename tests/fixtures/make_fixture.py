"""Deterministic offline fixtures for M2 (fixed seed). Re-exports the canonical
fixture generation from `pql.data.fixtures` so the same code backs tests and the
CLI `--from-fixture` path.
"""
from pql.data.fixtures import (  # noqa: F401
    make_calendar,
    make_fixture_provider,
    make_provider_data,
)
