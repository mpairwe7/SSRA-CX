"""API router for appointments bounded context."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ssra_api.appointments.application import list_slots_use_case

router = APIRouter(prefix="/v1/appointments", tags=["appointments"])


class SlotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    office_code: str
    start_eat: str


@router.get(
    "/slots",
    response_model=list[SlotModel],
    responses={503: {"description": "Live office inventory is not configured."}},
)
async def get_slots(office_code: str = "JUBA_HQ") -> list[SlotModel]:
    """Return current appointment inventory or fail closed when no provider is configured."""
    slots = list_slots_use_case(office_code)
    return [
        SlotModel(
            slot_id=s.slot_id,
            office_code=s.office_code,
            start_eat=s.start_eat,
        )
        for s in slots
    ]
