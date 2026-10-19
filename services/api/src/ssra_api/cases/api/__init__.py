"""API router for cases bounded context (including Tier T3 Two-Officer Maker-Checker Approval — Section 4)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError

from ssra_api.cases.application import (
    open_case_use_case,
    record_maker_checker_approval_use_case,
)

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


@router.post("/{case_id}/maker-checker", response_model=MakerCheckerApprovalResponse)
async def approve_maker_checker(
    case_id: str, body: MakerCheckerApprovalRequest
) -> MakerCheckerApprovalResponse:
    """Approve a Tier T3 case action under two-officer maker-checker control."""
    if body.maker_staff_id == body.checker_staff_id:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "Tier T3 maker-checker control requires checker_staff_id != maker_staff_id",
            status_code=403,
        )
    record_maker_checker_approval_use_case(
        case_id=case_id,
        maker_staff_id=body.maker_staff_id,
        checker_staff_id=body.checker_staff_id,
        action_type=body.action_type,
        rationale=body.rationale,
    )
    return MakerCheckerApprovalResponse(
        case_id=case_id,
        maker_staff_id=body.maker_staff_id,
        checker_staff_id=body.checker_staff_id,
        action_type=body.action_type,
        status="MAKER_CHECKER_APPROVED",
    )
