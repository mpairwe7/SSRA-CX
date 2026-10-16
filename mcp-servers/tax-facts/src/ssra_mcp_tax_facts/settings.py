"""Settings for ssra_mcp_tax_facts."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TaxFactsServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SSRA_MCP_TAX_FACTS_", extra="ignore")

    server_name: str = "tax-facts"
