"""Application layer for analytics_api bounded context (Phase 4 Insights, Feedback & Drift Monitors)."""

from __future__ import annotations

from ssra_core import new_id

from ssra_api.analytics_api.domain import (
    FunnelSummary,
    OnlineDriftMonitorSnapshot,
    RegionalLanguageInsight,
    UserFeedbackItem,
)

_feedback_store: list[UserFeedbackItem] = []


def get_funnel_summary_use_case() -> FunnelSummary:
    return FunnelSummary(
        quality_adjusted_containment_rate=0.96,
        zero_fabricated_figures=True,
        zero_cross_taxpayer_leakage=True,
    )


def get_regional_language_insights_use_case() -> list[RegionalLanguageInsight]:
    return [
        RegionalLanguageInsight(
            locale="en",
            region="JUBA_HQ",
            top_intent="guided_tin_registration",
            containment_rate=0.97,
            top_abstention_reason="T4_WAIVER_ESCALATION",
            average_csat=4.7,
        ),
        RegionalLanguageInsight(
            locale="pga",
            region="WAU",
            top_intent="verify_official_channel",
            containment_rate=0.95,
            top_abstention_reason="STEP_UP_OTP_REQUIRED",
            average_csat=4.6,
        ),
        RegionalLanguageInsight(
            locale="ar",
            region="NIMULE_CUSTOMS",
            top_intent="calculate_paye",
            containment_rate=0.96,
            top_abstention_reason="CUSTOMS_TARIFF_OQ002",
            average_csat=4.6,
        ),
    ]


def record_user_feedback_use_case(
    *, conversation_id: str, csat: int, reason: str, locale: str
) -> UserFeedbackItem:
    item = UserFeedbackItem(
        feedback_id=new_id("fbk"),
        conversation_id=conversation_id,
        csat=csat,
        reason=reason,
        locale=locale,
    )
    _feedback_store.append(item)
    return item


def evaluate_online_drift_monitors_use_case(
    *,
    intent_mix_kl_divergence: float = 0.03,
    abstention_rate_24h: float = 0.08,
    guardrail_trigger_rate_24h: float = 0.01,
) -> OnlineDriftMonitorSnapshot:
    alert = (
        intent_mix_kl_divergence > 0.15
        or abstention_rate_24h > 0.25
        or guardrail_trigger_rate_24h > 0.05
    )
    return OnlineDriftMonitorSnapshot(
        intent_mix_kl_divergence=intent_mix_kl_divergence,
        abstention_rate_24h=abstention_rate_24h,
        guardrail_trigger_rate_24h=guardrail_trigger_rate_24h,
        slo_burn_rate_alert=alert,
        status="DRIFT_ALERT" if alert else "HEALTHY",
    )
