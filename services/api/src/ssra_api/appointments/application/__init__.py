"""Application layer for appointments bounded context."""

from __future__ import annotations

from ssra_api.appointments.domain import AppointmentSlot


def list_slots_use_case(office_code: str = "JUBA_HQ") -> list[AppointmentSlot]:
    return [
        AppointmentSlot(
            slot_id="slot_2026_10_20_0900",
            office_code=office_code,
            start_eat="2026-10-20T09:00:00+02:00",
        ),
        AppointmentSlot(
            slot_id="slot_2026_10_20_1100",
            office_code=office_code,
            start_eat="2026-10-20T11:00:00+02:00",
        ),
    ]
