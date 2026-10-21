"""Application layer for appointments bounded context."""

from __future__ import annotations

from ssra_core import McpErrorCode, SSRAError

from ssra_api.appointments.domain import AppointmentSlot


def list_slots_use_case(office_code: str = "JUBA_HQ") -> list[AppointmentSlot]:
    """Return live office inventory only; no approved appointment provider is configured."""
    del office_code
    raise SSRAError(
        McpErrorCode.UPSTREAM_UNAVAILABLE,
        "Appointment availability is unavailable until SSRA approves and configures an office inventory provider (OQ-016).",
        status_code=503,
    )
