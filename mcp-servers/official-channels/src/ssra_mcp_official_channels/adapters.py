"""Adapters for ssra_mcp_official_channels."""

from __future__ import annotations

from ssra_adapters import MockOfficialChannelsAdapter


def get_official_channels_adapter() -> MockOfficialChannelsAdapter:
    return MockOfficialChannelsAdapter()
