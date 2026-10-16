"""API router for analytics_api bounded context (Insights, User Feedback & Online Drift Monitors)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ssra_api.analytics_api.application import (
    evaluate_online_drift_monitors_use_case,
    get_funnel_summary_use_case,
    get_regional_language_insights_use_case,
    record_user_feedback_use_case,
)

router = APIRouter(prefix="/v1/analytics", tags=["analytics_api"])


class FunnelSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quality_adjusted_containment_rate: float
    zero_fabricated_figures: bool
    zero_cross_taxpayer_leakage: bool


class RegionalLanguageInsightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: str
    region: str
    top_intent: str
    containment_rate: float
    top_abstention_reason: str
    average_csat: float


class SubmitFeedbackRequest(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    conversation_id: str
    csat: int
    reason: str
    locale: str


class DriftMonitorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_mix_kl_divergence: float
    abstention_rate_24h: float
    guardrail_trigger_rate_24h: float
    slo_burn_rate_alert: bool
    status: str


@router.get("/summary", response_model=FunnelSummaryResponse)
async def get_summary() -> FunnelSummaryResponse:
    s = get_funnel_summary_use_case()
    return FunnelSummaryResponse(
        quality_adjusted_containment_rate=s.quality_adjusted_containment_rate,
        zero_fabricated_figures=s.zero_fabricated_figures,
        zero_cross_taxpayer_leakage=s.zero_cross_taxpayer_leakage,
    )


@router.get("/insights", response_model=list[RegionalLanguageInsightResponse])
async def get_insights() -> list[RegionalLanguageInsightResponse]:
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
