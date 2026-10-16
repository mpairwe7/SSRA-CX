"""Domain layer for admin bounded context (Kill switches & audit verification)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KillSwitchState:
    degradation_level: int
    disabled_tools: tuple[str, ...]
    disabled_channels: tuple[str, ...]
