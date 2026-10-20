"""Domain layer for analytics_api bounded context (Phase 3/4 Insights, User Feedback, Drift Monitors & 2026 CX Scorecard — Section 14.2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunnelSummary:
    quality_adjusted_containment_rate: float
    zero_fabricated_figures: bool
    zero_cross_taxpayer_leakage: bool


@dataclass(frozen=True)
class RegionalLanguageInsight:
    locale: str
    region: str
    top_intent: str
    containment_rate: float
    top_abstention_reason: str
    average_csat: float


@dataclass(frozen=True)
class UserFeedbackItem:
    feedback_id: str
    conversation_id: str
    csat: int
    reason: str
    locale: str


@dataclass(frozen=True)
class OnlineDriftMonitorSnapshot:
    intent_mix_kl_divergence: float
    abstention_rate_24h: float
    guardrail_trigger_rate_24h: float
    slo_burn_rate_alert: bool
    status: str


@dataclass(frozen=True)
class AgenticCxScorecard:
    quality_adjusted_autonomous_resolution_rate: float
    cross_session_goal_completion_rate: float
    customer_effort_repetition_rate: float
    eq_deescalation_save_rate: float
    clean_handoff_rate: float
    officer_high_eq_hours_saved_30d: float
    vernacular_parity_gap_pct: float
    zero_unverified_numeric_claims: bool
