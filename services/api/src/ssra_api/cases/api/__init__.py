"""API router for cases bounded context (including Tier T3 Two-Officer Maker-Checker Approval — Section 4)."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError

from ssra_api.cases.application import open_case_use_case

router = APIRouter(prefix="/v1/cases", tags=["cases"])


def _raise_staff_session_required() -> NoReturn:
    """Fail closed until an approved server-side staff identity and role provider exists."""
    raise SSRAError(
        McpErrorCode.NOT_AUTHORIZED,
        "Staff case approvals are unavailable until an approved server-verified session and role policy are configured (OQ-014).",
        status_code=403,
    )


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


class MakerCheckerApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maker_staff_id: str = Field(min_length=3)
    checker_staff_id: str = Field(min_length=3)
    action_type: str = Field(min_length=3)
    rationale: str = Field(min_length=5)


class MakerCheckerApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    maker_staff_id: str
    checker_staff_id: str
    action_type: str
    status: str


@router.post("", response_model=CaseResponse)
async def create_case(body: CreateCaseRequest) -> CaseResponse:
    """Open a new taxpayer support or inquiry case."""
    c = open_case_use_case(case_type=body.case_type, priority=body.priority)
    return CaseResponse(id=c.id, case_type=c.case_type, status=c.status, priority=c.priority)


@router.post(
    "/{case_id}/maker-checker",
    response_model=MakerCheckerApprovalResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def approve_maker_checker(
    case_id: str, body: MakerCheckerApprovalRequest
) -> MakerCheckerApprovalResponse:
    """Approve a Tier T3 case only after server-side staff authentication and authorization."""
    del case_id, body
    _raise_staff_session_required()
