"""Adapter wrapping TaxFactsRegistry for ssra_mcp_tax_facts."""

from __future__ import annotations

from ssra_rules import TaxFactsRegistry


def get_tax_facts_adapter() -> TaxFactsRegistry:
    return TaxFactsRegistry.from_yaml_file()
