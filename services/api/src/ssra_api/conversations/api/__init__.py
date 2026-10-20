"""API router for conversations & Phase 3 Staff Copilot inbox, takeover, hand-back, and QA scoring."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import IntentName, McpErrorCode, SSRAError

from ssra_api.conversations.application import (
    create_conversation_use_case,
    generate_copilot_draft_use_case,
    score_conversation_qa_use_case,
    staff_handback_to_ai_use_case,
    staff_takeover_use_case,
)
from ssra_api.conversations.infrastructure import InMemoryConversationRepository
from ssra_api.repositories import PostgresRlsSessionContext

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])
_repo = InMemoryConversationRepository()


class CreateConversationRequest(BaseModel):
    """Request payload for creating a new taxpayer conversation thread."""

    model_config = ConfigDict(extra="forbid")

    channel: str = "web"
    locale: str = "en"
    office_code: str = "JUBA_HQ"


class OfficerResolutionResponse(BaseModel):
    """Serialized officer resolution artifact attached on warm hand-back to AI."""

    model_config = ConfigDict(extra="forbid")

    officer_id: str
    resolution_summary: str
    approved_next_intent: str
    return_to_ai_step: int


class ConversationResponse(BaseModel):
    """Response payload representing a conversation thread and its current assignment state."""

    model_config = ConfigDict(extra="forbid")

    id: str
    channel: str
    locale: str
    auth_level: str
    office_code: str
    status: str
    assigned_staff_id: str | None = None
    qa_score: float | None = None
    officer_resolution: OfficerResolutionResponse | None = None


class TakeoverRequest(BaseModel):
    """Request payload for an SSRA officer taking over a conversation."""

    model_config = ConfigDict(extra="forbid")

    staff_id: str


class HandbackResolutionRequest(BaseModel):
    """Optional structured resolution payload when an officer hands a conversation back to AI."""

    model_config = ConfigDict(extra="forbid")

    officer_id: str = Field(min_length=2)
    resolution_summary: str = Field(min_length=3, max_length=240)
    approved_next_intent: str = "guided_filing_and_payment"
    return_to_ai_step: int = Field(ge=1, le=10, default=1)


class CopilotDraftRequest(BaseModel):
    """Request payload for generating an AI copilot reply draft."""

    model_config = ConfigDict(extra="forbid")

    taxpayer_question: str


class CopilotDraftResponse(BaseModel):
    """Response payload containing a cited reply draft and next-best action for staff."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    summary: str
    cited_reply_draft: str
    citations: list[str]
    next_best_action: str
    snapshot_version: str


class QaScoreRequest(BaseModel):
    """Request payload for scoring a conversation against the 4-dimension QA rubric."""

    model_config = ConfigDict(extra="forbid")

    accuracy: float = Field(ge=0.0, le=1.0)
    citations_complete: float = Field(ge=0.0, le=1.0)
    neutrality: float = Field(ge=0.0, le=1.0)
    language_quality: float = Field(ge=0.0, le=1.0)


def _to_response(entity: object) -> ConversationResponse:
    """Convert a domain `ConversationEntity` into a `ConversationResponse` DTO."""
    from ssra_api.conversations.domain import ConversationEntity

    assert isinstance(entity, ConversationEntity)
    res_dto = (
        OfficerResolutionResponse(
            officer_id=entity.officer_resolution.officer_id,
            resolution_summary=entity.officer_resolution.resolution_summary,
            approved_next_intent=entity.officer_resolution.approved_next_intent,
            return_to_ai_step=entity.officer_resolution.return_to_ai_step,
        )
        if entity.officer_resolution is not None
        else None
    )
    return ConversationResponse(
        id=entity.id,
        channel=entity.channel,
        locale=entity.locale,
        auth_level=entity.auth_level,
        office_code=entity.office_code,
        status=entity.status,
        assigned_staff_id=entity.assigned_staff_id,
        qa_score=entity.qa_score,
        officer_resolution=res_dto,
    )


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    body: CreateConversationRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ConversationResponse:
    """Create a new taxpayer conversation thread scoped to an SSRA office."""
    _ = idempotency_key
    entity = create_conversation_use_case(
        channel=body.channel, locale=body.locale, office_code=body.office_code
    )
    _repo.save(entity)
    return _to_response(entity)


@router.get("/inbox", response_model=list[ConversationResponse])
async def list_inbox(office_code: str = "JUBA_HQ") -> list[ConversationResponse]:
    """List conversations in the staff inbox scoped by PostgreSQL RLS `office_code`."""
    PostgresRlsSessionContext(
        staff_id="stf_inbox", office_code=office_code, staff_role="agent"
    ).to_set_local_sql()
    return [_to_response(c) for c in _repo.list_by_office(office_code)]


@router.get("/inbox/stream")
async def stream_inbox_events(office_code: str = "JUBA_HQ") -> StreamingResponse:
    """Real-time SSE inbox feed for Phase 3 Staff Console (`apps/console` — Section 11)."""
    items = [_to_response(c).model_dump(mode="json") for c in _repo.list_by_office(office_code)]

    async def _gen() -> AsyncIterator[str]:
        payload = json.dumps(
            {
                "type": "INBOX_SNAPSHOT",
                "office_code": office_code,
                "conversations": items,
            }
        )
        yield f"event: inbox\ndata: {payload}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.post("/{conversation_id}/takeover", response_model=ConversationResponse)
async def takeover_conversation(
    conversation_id: str, body: TakeoverRequest
) -> ConversationResponse:
    """Assign a conversation to an SSRA staff officer for human takeover."""
    entity = _repo.get(conversation_id)
    if entity is None:
        raise SSRAError(McpErrorCode.NOT_FOUND, "Conversation not found", status_code=404)
    updated = staff_takeover_use_case(entity, staff_id=body.staff_id)
    _repo.save(updated)
    return _to_response(updated)


@router.post("/{conversation_id}/handback", response_model=ConversationResponse)
async def handback_conversation(
    conversation_id: str,
    body: HandbackResolutionRequest | None = None,
) -> ConversationResponse:
    """Hand a conversation back to the AI assistant, optionally attaching a verified officer resolution."""
    from ssra_api.conversations.domain import OfficerResolutionArtifact

    entity = _repo.get(conversation_id)
    if entity is None:
        raise SSRAError(McpErrorCode.NOT_FOUND, "Conversation not found", status_code=404)
    if body is not None:
        if entity.status != "STAFF_TAKEOVER" or body.officer_id != entity.assigned_staff_id:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Only the assigned officer on a STAFF_TAKEOVER conversation can submit a hand-back resolution",
                status_code=403,
            )
        if body.approved_next_intent not in IntentName._value2member_map_:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Unsupported approved_next_intent '{body.approved_next_intent}'",
                status_code=422,
            )
    resolution = (
        OfficerResolutionArtifact(
            officer_id=body.officer_id,
            resolution_summary=body.resolution_summary,
            approved_next_intent=body.approved_next_intent,
            return_to_ai_step=body.return_to_ai_step,
        )
        if body is not None
        else None
    )
    updated = staff_handback_to_ai_use_case(entity, officer_resolution=resolution)
    _repo.save(updated)
    return _to_response(updated)


@router.post("/{conversation_id}/copilot-draft", response_model=CopilotDraftResponse)
async def generate_copilot_draft(
    conversation_id: str, body: CopilotDraftRequest
) -> CopilotDraftResponse:
    """Generate a cited reply draft and next-best action for an SSRA officer."""
    draft = generate_copilot_draft_use_case(
        conversation_id=conversation_id,
        taxpayer_question=body.taxpayer_question,
    )
    return CopilotDraftResponse(
        conversation_id=draft.conversation_id,
        summary=draft.summary,
        cited_reply_draft=draft.cited_reply_draft,
        citations=list(draft.citations),
        next_best_action=draft.next_best_action,
        snapshot_version=draft.snapshot_version,
    )


@router.post("/{conversation_id}/qa-score", response_model=ConversationResponse)
async def score_conversation_qa(conversation_id: str, body: QaScoreRequest) -> ConversationResponse:
    """Record a supervisor QA rubric score for a conversation."""
    entity = _repo.get(conversation_id)
    if entity is None:
        raise SSRAError(McpErrorCode.NOT_FOUND, "Conversation not found", status_code=404)
    updated = score_conversation_qa_use_case(
        entity,
        accuracy=body.accuracy,
        citations_complete=body.citations_complete,
        neutrality=body.neutrality,
        language_quality=body.language_quality,
    )
    _repo.save(updated)
    return _to_response(updated)
