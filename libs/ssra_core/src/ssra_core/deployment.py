"""Deployment mode selection for fail-closed reference implementations."""

from __future__ import annotations

import os
from enum import StrEnum


class RuntimeMode(StrEnum):
    """Supported service modes; production is the safe default."""

    PRODUCTION = "production"
    REFERENCE = "reference"


def get_runtime_mode() -> RuntimeMode | None:
    """Return the configured runtime mode, defaulting to production and rejecting unknown values."""
    raw_mode = os.environ.get("SSRA_RUNTIME_MODE", RuntimeMode.PRODUCTION.value)
    try:
        return RuntimeMode(raw_mode.strip().lower())
    except ValueError:
        return None


def is_reference_mode() -> bool:
    """Return true only when synthetic, process-local reference behavior is explicitly enabled."""
    return get_runtime_mode() == RuntimeMode.REFERENCE
