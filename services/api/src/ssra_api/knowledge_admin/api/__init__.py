"""API router for knowledge_admin bounded context (6-Step Knowledge Release Workflow)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ssra_api.knowledge_admin.application import (
    get_active_snapshot_use_case,
    get_workflow_engine,
)
from ssra_api.knowledge_admin.domain import KnowledgeSnapshotEntity

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


def _to_res(snap: KnowledgeSnapshotEntity) -> SnapshotResponse:
    return SnapshotResponse(
        version=snap.version,
        status=snap.status,
        approved_by=snap.approved_by,
        checksum=snap.checksum,
    )


@router.get("/active-snapshot", response_model=SnapshotResponse)
async def get_active_snapshot() -> SnapshotResponse:
    return _to_res(get_active_snapshot_use_case())


@router.post("/snapshots", response_model=SnapshotResponse)
async def create_draft_snapshot(body: CreateDraftSnapshotRequest) -> SnapshotResponse:
    return _to_res(
        get_workflow_engine().create_draft(
            version=body.version, content_digest_input=body.content_digest_input
        )
    )


@router.post("/snapshots/{version}/submit-review", response_model=SnapshotResponse)
async def submit_for_review(version: str) -> SnapshotResponse:
    return _to_res(get_workflow_engine().submit_for_legal_review(version))


@router.post("/snapshots/{version}/approve", response_model=SnapshotResponse)
async def approve_snapshot(version: str, body: ApproveSnapshotRequest) -> SnapshotResponse:
    return _to_res(
        get_workflow_engine().approve_snapshot(version, legal_approver=body.legal_approver)
    )


@router.post("/snapshots/{version}/publish", response_model=SnapshotResponse)
async def publish_snapshot(version: str, body: PublishSnapshotRequest) -> SnapshotResponse:
    return _to_res(
        get_workflow_engine().publish_snapshot(
            version, eval_regression_passed=body.eval_regression_passed
        )
    )


@router.post("/snapshots/rollback", response_model=SnapshotResponse)
async def rollback_snapshot() -> SnapshotResponse:
    return _to_res(get_workflow_engine().rollback_to_previous())
