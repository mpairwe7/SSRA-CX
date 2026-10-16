"""Settings for ssra_mcp_official_channels."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class OfficialChannelsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SSRA_MCP_OFFICIAL_CHANNELS_", extra="ignore")

    server_name: str = "official-channels"
