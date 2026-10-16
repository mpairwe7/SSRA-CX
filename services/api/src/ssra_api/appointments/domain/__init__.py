"""Domain layer for appointments bounded context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppointmentSlot:
    slot_id: str
    office_code: str
    start_eat: str
