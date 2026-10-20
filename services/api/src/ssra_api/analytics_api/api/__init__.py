"""API router for analytics_api bounded context (Insights, User Feedback, Drift Monitors & Synthetic CX Scorecard)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ssra_api.analytics_api.application import (
    evaluate_online_drift_monitors_use_case,
    get_agentic_cx_scorecard_use_case,
    get_funnel_summary_use_case,
    get_regional_language_insights_use_case,
    record_user_feedback_use_case,
)

router = APIRouter(prefix="/v1/analytics", tags=["analytics_api"])


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
    """Synthetic baseline response model for the October 2026 SSRA Agentic CX Scorecard (`OQ-013`)."""

    model_config = ConfigDict(extra="forbid")

    quality_adjusted_autonomous_resolution_rate: float
    cross_session_goal_completion_rate: float
    customer_effort_repetition_rate: float
    eq_deescalation_save_rate: float
    clean_handoff_rate: float
    officer_high_eq_hours_saved_30d: float
    vernacular_parity_gap_pct: float
    zero_unverified_numeric_claims: bool
    is_synthetic_baseline: bool = True
    source_note: str = "SYNTHETIC_PHASE4_BASELINE_OQ013"


@router.get("/summary", response_model=FunnelSummaryResponse)
async def get_summary() -> FunnelSummaryResponse:
    """Return the quality-adjusted containment and safety funnel summary."""
    s = get_funnel_summary_use_case()
    return FunnelSummaryResponse(
        quality_adjusted_containment_rate=s.quality_adjusted_containment_rate,
        zero_fabricated_figures=s.zero_fabricated_figures,
        zero_cross_taxpayer_leakage=s.zero_cross_taxpayer_leakage,
    )


@router.get("/insights", response_model=list[RegionalLanguageInsightResponse])
async def get_insights() -> list[RegionalLanguageInsightResponse]:
    """Return regional and language containment insights across SSRA offices."""
    return [
        RegionalLanguageInsightResponse(
            locale=i.locale,
            region=i.region,
            top_intent=i.top_intent,
            containment_rate=i.containment_rate,
            top_abstention_reason=i.top_abstention_reason,
            average_csat=i.average_csat,
        )
        for i in get_regional_language_insights_use_case()
    ]


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


@router.get("/drift-monitors", response_model=DriftMonitorResponse)
async def get_drift_monitors(
    intent_kl: float = 0.03,
    abstention_rate: float = 0.08,
    guardrail_rate: float = 0.01,
) -> DriftMonitorResponse:
    """Evaluate 24-hour online drift monitors for intent KL divergence and abstention spikes."""
    snap = evaluate_online_drift_monitors_use_case(
        intent_mix_kl_divergence=intent_kl,
        abstention_rate_24h=abstention_rate,
        guardrail_trigger_rate_24h=guardrail_rate,
    )
    return DriftMonitorResponse(
        intent_mix_kl_divergence=snap.intent_mix_kl_divergence,
        abstention_rate_24h=snap.abstention_rate_24h,
        guardrail_trigger_rate_24h=snap.guardrail_trigger_rate_24h,
        slo_burn_rate_alert=snap.slo_burn_rate_alert,
        status=snap.status,
    )


@router.get("/cx-scorecard", response_model=AgenticCxScorecardResponse)
async def get_cx_scorecard() -> AgenticCxScorecardResponse:
    """Return the synthetic baseline October 2026 SSRA Agentic CX & Human-AI Workforce Scorecard (`OQ-013`)."""
    sc = get_agentic_cx_scorecard_use_case()
    return AgenticCxScorecardResponse(
        quality_adjusted_autonomous_resolution_rate=sc.quality_adjusted_autonomous_resolution_rate,
        cross_session_goal_completion_rate=sc.cross_session_goal_completion_rate,
        customer_effort_repetition_rate=sc.customer_effort_repetition_rate,
        eq_deescalation_save_rate=sc.eq_deescalation_save_rate,
        clean_handoff_rate=sc.clean_handoff_rate,
        officer_high_eq_hours_saved_30d=sc.officer_high_eq_hours_saved_30d,
        vernacular_parity_gap_pct=sc.vernacular_parity_gap_pct,
        zero_unverified_numeric_claims=sc.zero_unverified_numeric_claims,
        is_synthetic_baseline=sc.is_synthetic_baseline,
        source_note=sc.source_note,
    )
