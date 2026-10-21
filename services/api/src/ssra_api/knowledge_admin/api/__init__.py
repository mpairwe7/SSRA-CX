"""Staff-only knowledge-release route contracts; handlers remain gated pending trusted authorization."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from ssra_core import McpErrorCode, SSRAError

router = APIRouter(prefix="/v1/knowledge-admin", tags=["knowledge_admin"])


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    status: str
    approved_by: str
    checksum: str


class CreateDraftSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    content_digest_input: str


class ApproveSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_approver: str


class PublishSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eval_regression_passed: bool = True


def _raise_staff_session_required() -> NoReturn:
    """Block reference workflow state until trusted staff authorization and durable storage exist."""
    raise SSRAError(
        McpErrorCode.NOT_AUTHORIZED,
        "Knowledge snapshot data and actions are unavailable until server-verified staff roles and durable state are configured (OQ-014, OQ-015).",
        status_code=403,
    )


@router.get(
    "/active-snapshot",
    response_model=SnapshotResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def get_active_snapshot() -> SnapshotResponse:
    """Return snapshot state only to a server-verified, authorized knowledge operator."""
    _raise_staff_session_required()


@router.post(
    "/snapshots",
    response_model=SnapshotResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def create_draft_snapshot(body: CreateDraftSnapshotRequest) -> SnapshotResponse:
    """Create drafts only after staff identity, role, and durable workflow state are verified."""
    del body
    _raise_staff_session_required()


@router.post(
    "/snapshots/{version}/submit-review",
    response_model=SnapshotResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def submit_for_review(version: str) -> SnapshotResponse:
    """Submit drafts only through a verified knowledge-release workflow."""
    del version
    _raise_staff_session_required()


@router.post(
    "/snapshots/{version}/approve",
    response_model=SnapshotResponse,
    responses={
        403: {"description": "Verified staff session and maker-checker policy are required."}
    },
)
async def approve_snapshot(version: str, body: ApproveSnapshotRequest) -> SnapshotResponse:
    """Never accept approver identity from request data as evidence of legal authorization."""
    del version, body
    _raise_staff_session_required()


@router.post(
    "/snapshots/{version}/publish",
    response_model=SnapshotResponse,
    responses={403: {"description": "Verified staff session and release policy are required."}},
)
async def publish_snapshot(version: str, body: PublishSnapshotRequest) -> SnapshotResponse:
    """Never trust a caller-supplied regression flag to authorize snapshot publication."""
    del version, body
    _raise_staff_session_required()


@router.post(
    "/snapshots/rollback",
    response_model=SnapshotResponse,
    responses={403: {"description": "Verified staff session and release policy are required."}},
)
async def rollback_snapshot() -> SnapshotResponse:
    """Allow rollback only through an approved, authenticated operations workflow."""
    _raise_staff_session_required()
