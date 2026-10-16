"""OpenTelemetry GenAI semantic conventions & per-intent/channel cost attribution (Sections 13 & 14.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

    def to_otel_dict(self) -> dict[str, Any]:
        return {
            "gen_ai.system": self.gen_ai_system,
            "gen_ai.request.model": self.gen_ai_request_model,
            "gen_ai.usage.input_tokens": self.gen_ai_usage_input_tokens,
            "gen_ai.usage.output_tokens": self.gen_ai_usage_output_tokens,
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
) -> GenAISpanAttributes:
    intent_val = intent.value if isinstance(intent, IntentName) else str(intent)
    # Sovereign GPU baseline cost attribution + WhatsApp per-message fee tracking
    token_cost = ((input_tokens * 0.0001) + (output_tokens * 0.0003)) / 1000.0
    channel_cost = 0.005 if channel == ChannelName.WHATSAPP else 0.0
    return GenAISpanAttributes(
        gen_ai_system="ssra.sovereign.vllm",
        gen_ai_request_model=model,
        gen_ai_usage_input_tokens=input_tokens,
        gen_ai_usage_output_tokens=output_tokens,
        ssra_channel=channel.value,
        ssra_locale=locale.value,
        ssra_intent=intent_val,
        ssra_risk_tier=tier.value,
        ssra_knowledge_snapshot=knowledge_snapshot,
        ssra_estimated_cost_usd=round(token_cost + channel_cost, 8),
    )
