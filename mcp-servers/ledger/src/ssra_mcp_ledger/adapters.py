"""LedgerPort adapter wiring for ssra_mcp_ledger."""

from __future__ import annotations

from ssra_adapters import MockETaxAdapter


def get_ledger_adapter() -> MockETaxAdapter:
    return MockETaxAdapter()
