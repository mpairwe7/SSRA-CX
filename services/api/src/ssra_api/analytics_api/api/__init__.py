"""API router for reference feedback and fail-closed operational analytics endpoints."""

from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError

from ssra_api.analytics_api.application import (
    record_user_feedback_use_case,
)

router = APIRouter(prefix="/v1/analytics", tags=["analytics_api"])


def _raise_analytics_source_unavailable() -> NoReturn:
    """Prevent synthetic counters and caller-supplied values from appearing as operational analytics."""
    raise SSRAError(
        McpErrorCode.UPSTREAM_UNAVAILABLE,
        "Operational analytics are unavailable until the approved warehouse, freshness controls, and provenance are configured (OQ-013).",
        status_code=503,
    )


class FunnelSummaryResponse(BaseModel):
    """Response model for quality-adjusted containment and safety summary."""

    model_config = ConfigDict(extra="forbid")

    quality_adjusted_containment_rate: float
    zero_fabricated_figures: bool
    zero_cross_taxpayer_leakage: bool


class RegionalLanguageInsightResponse(BaseModel):
    """Response model for regional and language-level CX insights."""

    model_config = ConfigDict(extra="forbid")

    locale: str
    region: str
    top_intent: str
    containment_rate: float
    top_abstention_reason: str
    average_csat: float


class SubmitFeedbackRequest(BaseModel):
    """Request payload for submitting taxpayer CSAT feedback."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    csat: int = Field(ge=1, le=5)
    reason: Literal[
        "ACCURATE",
        "CLEAR_CITATIONS",
        "MISSING_INFO",
        "SLOW_NETWORK",
        "NEEDED_HUMAN",
    ]
    locale: str = "en"


class SubmitFeedbackResponse(BaseModel):
    """Response payload confirming recorded taxpayer feedback."""

    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    conversation_id: str
    csat: int
    reason: str
    locale: str


class DriftMonitorResponse(BaseModel):
    """Response model for 24-hour online drift monitor evaluation."""

    model_config = ConfigDict(extra="forbid")

    intent_mix_kl_divergence: float
    abstention_rate_24h: float
    guardrail_trigger_rate_24h: float
    slo_burn_rate_alert: bool
    status: str


class AgenticCxScorecardResponse(BaseModel):
    """Planned scorecard payload; the endpoint returns 503 until governed data is configured (`OQ-013`)."""

    model_config = ConfigDict(extra="forbid")

    quality_adjusted_autonomous_resolution_rate: float
    cross_session_goal_completion_rate: float
    customer_effort_repetition_rate: float
    eq_deescalation_save_rate: float
    clean_handoff_rate: float
    officer_high_eq_hours_saved_30d: float
    vernacular_parity_gap_pct: float
    zero_unverified_numeric_claims: bool
    is_synthetic_baseline: bool
    source_note: str


@router.get(
    "/summary",
    response_model=FunnelSummaryResponse,
    responses={503: {"description": "Approved analytics source is not configured."}},
)
async def get_summary() -> FunnelSummaryResponse:
    """Return operational funnel metrics only when their governed data source exists."""
    _raise_analytics_source_unavailable()


@router.get(
    "/insights",
    response_model=list[RegionalLanguageInsightResponse],
    responses={503: {"description": "Approved analytics source is not configured."}},
)
async def get_insights() -> list[RegionalLanguageInsightResponse]:
    """Return regional metrics only when their governed data source exists."""
    _raise_analytics_source_unavailable()


@router.post("/feedback", response_model=SubmitFeedbackResponse)
async def submit_feedback(body: SubmitFeedbackRequest) -> SubmitFeedbackResponse:
    """Submit a taxpayer CSAT rating and reason for a conversation."""
    item = record_user_feedback_use_case(
        conversation_id=body.conversation_id,
        csat=body.csat,
        reason=body.reason,
        locale=body.locale,
    )
    return SubmitFeedbackResponse(
        feedback_id=item.feedback_id,
        conversation_id=item.conversation_id,
        csat=item.csat,
        reason=item.reason,
        locale=item.locale,
    )


@router.get(
    "/drift-monitors",
    response_model=DriftMonitorResponse,
    responses={503: {"description": "Approved analytics source is not configured."}},
)
async def get_drift_monitors(
    intent_kl: float = 0.03,
    abstention_rate: float = 0.08,
    guardrail_rate: float = 0.01,
) -> DriftMonitorResponse:
    """Do not evaluate caller-provided values as SSRA's live drift telemetry."""
    del intent_kl, abstention_rate, guardrail_rate
    _raise_analytics_source_unavailable()


@router.get(
    "/cx-scorecard",
    response_model=AgenticCxScorecardResponse,
    responses={503: {"description": "Approved analytics source is not configured."}},
)
async def get_cx_scorecard() -> AgenticCxScorecardResponse:
    """Return a scorecard only when its warehouse provenance and freshness can be established."""
    _raise_analytics_source_unavailable()
