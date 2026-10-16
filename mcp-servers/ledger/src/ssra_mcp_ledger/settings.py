"""Settings for ssra_mcp_ledger."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LedgerServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SSRA_MCP_LEDGER_", extra="ignore")

    server_name: str = "ledger"
