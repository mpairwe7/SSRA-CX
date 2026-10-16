"""OpenTelemetry GenAI semantic conventions (v1.32+ 2026) & FinOps cost discipline (Sections 13 & 14.3)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from ssra_core.contracts import ChannelName, IntentName, LocaleCode, RiskTier


@dataclass(frozen=True)
class GenAISpanAttributes:
    gen_ai_system: str
    gen_ai_request_model: str
    gen_ai_usage_input_tokens: int
    gen_ai_usage_output_tokens: int
    ssra_channel: str
    ssra_locale: str
    ssra_intent: str
    ssra_risk_tier: str
    ssra_knowledge_snapshot: str
    ssra_estimated_cost_usd: float
    gen_ai_usage_cache_read_input_tokens: int = 0
    gen_ai_response_ttft_ms: float = 0.0

    def to_otel_dict(self) -> dict[str, Any]:
        return {
            "gen_ai.system": self.gen_ai_system,
            "gen_ai.request.model": self.gen_ai_request_model,
            "gen_ai.usage.input_tokens": self.gen_ai_usage_input_tokens,
            "gen_ai.usage.output_tokens": self.gen_ai_usage_output_tokens,
            "gen_ai.usage.cache_read_input_tokens": self.gen_ai_usage_cache_read_input_tokens,
            "gen_ai.response.ttft_ms": self.gen_ai_response_ttft_ms,
            "ssra.channel": self.ssra_channel,
            "ssra.locale": self.ssra_locale,
            "ssra.intent": self.ssra_intent,
            "ssra.risk_tier": self.ssra_risk_tier,
            "ssra.knowledge_snapshot": self.ssra_knowledge_snapshot,
            "ssra.cost.estimated_usd": self.ssra_estimated_cost_usd,
        }


def build_genai_span_attributes(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    channel: ChannelName,
    locale: LocaleCode,
    intent: IntentName | str,
    tier: RiskTier,
    knowledge_snapshot: str = "2026.10.1",
    cached_input_tokens: int = 0,
    ttft_ms: float = 0.0,
    sms_segments: int = 0,
) -> GenAISpanAttributes:
    intent_val = intent.value if isinstance(intent, IntentName) else str(intent)
    bounded_cached = max(0, min(input_tokens, cached_input_tokens))
    uncached_input = max(0, input_tokens - bounded_cached)
    # Sovereign GPU baseline cost attribution (90% discount on vLLM prefix-cached input tokens)
    token_cost = (
        (uncached_input * 0.0001) + (bounded_cached * 0.00001) + (max(0, output_tokens) * 0.0003)
    ) / 1000.0
    if channel == ChannelName.WHATSAPP:
        channel_cost = 0.005
    elif channel == ChannelName.SMS:
        channel_cost = max(1, sms_segments) * 0.012
    else:
        channel_cost = 0.0
    return GenAISpanAttributes(
        gen_ai_system="ssra.sovereign.vllm",
        gen_ai_request_model=model,
        gen_ai_usage_input_tokens=input_tokens,
        gen_ai_usage_output_tokens=output_tokens,
        gen_ai_usage_cache_read_input_tokens=bounded_cached,
        gen_ai_response_ttft_ms=round(max(0.0, ttft_ms), 2) if math.isfinite(ttft_ms) else 0.0,
        ssra_channel=channel.value,
        ssra_locale=locale.value,
        ssra_intent=intent_val,
        ssra_risk_tier=tier.value,
        ssra_knowledge_snapshot=knowledge_snapshot,
        ssra_estimated_cost_usd=round(token_cost + channel_cost, 8),
    )


FinOpsAction = Literal[
    "NORMAL",
    "USE_T0_SEMANTIC_CACHE_OR_FAQ",
    "DOWNGRADE_COMPOSITION_VERBOSITY",
    "PRESERVE_SAFETY_VERIFIERS",
]


@dataclass(frozen=True)
class FinOpsBudgetDecision:
    tier: RiskTier
    action: FinOpsAction
    effective_max_tokens: int
    safety_verifiers_preserved: bool


def evaluate_finops_turn_budget(
    *,
    tier: RiskTier,
    daily_budget_utilization: float,
    requested_max_tokens: int = 1024,
) -> FinOpsBudgetDecision:
    """Enforce Section 13 Cost Discipline: never downgrade T2/T3 safety verifiers; trim verbosity or T0 first."""
    if not math.isfinite(daily_budget_utilization) or daily_budget_utilization < 0.0:
        raise ValueError("daily_budget_utilization must be a finite non-negative float")
    if requested_max_tokens <= 0:
        raise ValueError("requested_max_tokens must be positive")

    if daily_budget_utilization < 0.90:
        return FinOpsBudgetDecision(
            tier=tier,
            action="NORMAL",
            effective_max_tokens=requested_max_tokens,
            safety_verifiers_preserved=True,
        )

    if tier == RiskTier.T0:
        return FinOpsBudgetDecision(
            tier=tier,
            action="USE_T0_SEMANTIC_CACHE_OR_FAQ",
            effective_max_tokens=min(requested_max_tokens, 256),
            safety_verifiers_preserved=True,
        )
    if tier == RiskTier.T1:
        return FinOpsBudgetDecision(
            tier=tier,
            action="DOWNGRADE_COMPOSITION_VERBOSITY",
            effective_max_tokens=min(requested_max_tokens, 384),
            safety_verifiers_preserved=True,
        )
    return FinOpsBudgetDecision(
        tier=tier,
        action="PRESERVE_SAFETY_VERIFIERS",
        effective_max_tokens=min(requested_max_tokens, 512),
        safety_verifiers_preserved=True,
    )
