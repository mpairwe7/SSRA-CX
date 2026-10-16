"""API router for cases bounded context."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ssra_api.cases.application import open_case_use_case

router = APIRouter(prefix="/v1/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_type: str = "INQUIRY"
    summary: str
    priority: str = "NORMAL"


class CaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    case_type: str
    status: str
    priority: str


@router.post("", response_model=CaseResponse)
async def create_case(body: CreateCaseRequest) -> CaseResponse:
    c = open_case_use_case(case_type=body.case_type, priority=body.priority)
    return CaseResponse(id=c.id, case_type=c.case_type, status=c.status, priority=c.priority)
