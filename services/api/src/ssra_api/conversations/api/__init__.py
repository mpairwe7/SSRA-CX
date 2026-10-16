"""API router for conversations & Phase 3 Staff Copilot inbox, takeover, hand-back, and QA scoring."""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError

from ssra_api.conversations.application import (
    create_conversation_use_case,
    generate_copilot_draft_use_case,
    score_conversation_qa_use_case,
    staff_handback_to_ai_use_case,
    staff_takeover_use_case,
)
from ssra_api.conversations.infrastructure import InMemoryConversationRepository

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])
_repo = InMemoryConversationRepository()


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = "web"
    locale: str = "en"
    office_code: str = "JUBA_HQ"


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    channel: str
    locale: str
    auth_level: str
    office_code: str
    status: str
    assigned_staff_id: str | None = None
    qa_score: float | None = None


class TakeoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: str


class CopilotDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxpayer_question: str


class CopilotDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    summary: str
    cited_reply_draft: str
    citations: list[str]
    next_best_action: str
    snapshot_version: str


class QaScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accuracy: float = Field(ge=0.0, le=1.0)
    citations_complete: float = Field(ge=0.0, le=1.0)
    neutrality: float = Field(ge=0.0, le=1.0)
    language_quality: float = Field(ge=0.0, le=1.0)


def _to_response(entity: object) -> ConversationResponse:
    from ssra_api.conversations.domain import ConversationEntity

    assert isinstance(entity, ConversationEntity)
    return ConversationResponse(
        id=entity.id,
        channel=entity.channel,
        locale=entity.locale,
        auth_level=entity.auth_level,
        office_code=entity.office_code,
        status=entity.status,
        assigned_staff_id=entity.assigned_staff_id,
        qa_score=entity.qa_score,
    )


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    body: CreateConversationRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ConversationResponse:
    _ = idempotency_key
    entity = create_conversation_use_case(
        channel=body.channel, locale=body.locale, office_code=body.office_code
    )
    _repo.save(entity)
    return _to_response(entity)


@router.get("/inbox", response_model=list[ConversationResponse])
async def list_inbox(office_code: str = "JUBA_HQ") -> list[ConversationResponse]:
    return [_to_response(c) for c in _repo.list_by_office(office_code)]


@router.post("/{conversation_id}/takeover", response_model=ConversationResponse)
async def takeover_conversation(
    conversation_id: str, body: TakeoverRequest
) -> ConversationResponse:
    entity = _repo.get(conversation_id)
    if entity is None:
        raise SSRAError(McpErrorCode.NOT_FOUND, "Conversation not found", status_code=404)
    updated = staff_takeover_use_case(entity, staff_id=body.staff_id)
    _repo.save(updated)
    return _to_response(updated)


@router.post("/{conversation_id}/handback", response_model=ConversationResponse)
async def handback_conversation(conversation_id: str) -> ConversationResponse:
    entity = _repo.get(conversation_id)
    if entity is None:
        raise SSRAError(McpErrorCode.NOT_FOUND, "Conversation not found", status_code=404)
    updated = staff_handback_to_ai_use_case(entity)
    _repo.save(updated)
    return _to_response(updated)


@router.post("/{conversation_id}/copilot-draft", response_model=CopilotDraftResponse)
async def generate_copilot_draft(
    conversation_id: str, body: CopilotDraftRequest
) -> CopilotDraftResponse:
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
