"""Settings for ssra_mcp_knowledge."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SSRA_MCP_KNOWLEDGE_", extra="ignore")

    server_name: str = "knowledge"
    snapshot_version: str = "2026.10.1"
