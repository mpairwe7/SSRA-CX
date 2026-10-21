"""API router for conversations & Phase 3 Staff Copilot inbox, takeover, hand-back, and QA scoring."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError

from ssra_api.conversations.application import create_conversation_use_case
from ssra_api.conversations.infrastructure import InMemoryConversationRepository

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])
_repo = InMemoryConversationRepository()


def _raise_staff_session_required() -> NoReturn:
    """Fail closed until an approved server-side staff identity and role provider exists."""
    raise SSRAError(
        McpErrorCode.NOT_AUTHORIZED,
        "Staff inbox data and actions are unavailable until an approved server-verified session and role policy are configured (OQ-014).",
        status_code=403,
    )


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


@router.get(
    "/inbox",
    response_model=list[ConversationResponse],
    responses={403: {"description": "Verified staff session is required."}},
)
async def list_inbox(office_code: str = "JUBA_HQ") -> list[ConversationResponse]:
    """List staff inbox data only to a server-verified, authorized staff session."""
    del office_code
    _raise_staff_session_required()


@router.get(
    "/inbox/stream", responses={403: {"description": "Verified staff session is required."}}
)
async def stream_inbox_events(office_code: str = "JUBA_HQ") -> StreamingResponse:
    """Stream staff inbox data only to a server-verified, authorized staff session."""
    del office_code
    _raise_staff_session_required()


@router.post(
    "/{conversation_id}/takeover",
    response_model=ConversationResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def takeover_conversation(
    conversation_id: str, body: TakeoverRequest
) -> ConversationResponse:
    """Assign a conversation only after server-side staff authentication and authorization."""
    del conversation_id, body
    _raise_staff_session_required()


@router.post(
    "/{conversation_id}/handback",
    response_model=ConversationResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def handback_conversation(
    conversation_id: str,
    body: HandbackResolutionRequest | None = None,
) -> ConversationResponse:
    """Hand a conversation back only after server-side staff authentication and authorization."""
    del conversation_id, body
    _raise_staff_session_required()


@router.post(
    "/{conversation_id}/copilot-draft",
    response_model=CopilotDraftResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def generate_copilot_draft(
    conversation_id: str, body: CopilotDraftRequest
) -> CopilotDraftResponse:
    """Generate staff reply drafts only for a server-verified, authorized session."""
    del conversation_id, body
    _raise_staff_session_required()


@router.post(
    "/{conversation_id}/qa-score",
    response_model=ConversationResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def score_conversation_qa(conversation_id: str, body: QaScoreRequest) -> ConversationResponse:
    """Record staff QA scores only for a server-verified supervisor session."""
    del conversation_id, body
    _raise_staff_session_required()
