"""OpenTelemetry GenAI & MCP semantic conventions (v1.42 2026) & FinOps cost discipline (Sections 8.1, 13 & 14.3)."""

from __future__ import annotations

import math
import re
import secrets
from dataclasses import dataclass
from typing import Any, Literal

from ssra_core.contracts import ChannelName, IntentName, LocaleCode, RiskTier
from ssra_core.ids import new_id

_W3C_TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def ensure_w3c_traceparent(traceparent: str | None = None) -> str:
    """Validate or mint a W3C Trace Context `traceparent` header (`00-<trace_id>-<span_id>-01`)."""
    if traceparent:
        candidate = traceparent.strip().lower()
        match = _W3C_TRACEPARENT_RE.match(candidate)
        if match and match.group(1) != "0" * 32 and match.group(2) != "0" * 16:
            return candidate
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    return f"00-{trace_id}-{span_id}-01"


@dataclass(frozen=True)
class McpSpanAttributes:
    """OpenTelemetry GenAI & MCP Semantic Conventions (v1.39-v1.42 `semantic-conventions-genai`)."""

    span_name: str
    mcp_method_name: str
    mcp_protocol_version: str
    mcp_server_name: str
    gen_ai_operation_name: str
    gen_ai_tool_name: str
    gen_ai_tool_call_id: str
    gen_ai_tool_type: str
    ssra_risk_tier: str
    ssra_data_classification: str
    rpc_response_status_code: str
    traceparent: str

    def to_otel_dict(self) -> dict[str, str]:
        """Serialize MCP span attributes to an OpenTelemetry attribute dictionary."""
        return {
            "mcp.method.name": self.mcp_method_name,
            "mcp.protocol.version": self.mcp_protocol_version,
            "mcp.server.name": self.mcp_server_name,
            "gen_ai.operation.name": self.gen_ai_operation_name,
            "gen_ai.tool.name": self.gen_ai_tool_name,
            "gen_ai.tool.call.id": self.gen_ai_tool_call_id,
            "gen_ai.tool.type": self.gen_ai_tool_type,
            "ssra.risk_tier": self.ssra_risk_tier,
            "ssra.data_classification": self.ssra_data_classification,
            "rpc.response.status_code": self.rpc_response_status_code,
            "traceparent": self.traceparent,
        }


def build_mcp_span_attributes(
    *,
    server_name: str,
    tool_name: str,
    tier: RiskTier,
    data_classification: str = "PUBLIC",
    mcp_method: str = "tools/call",
    protocol_version: str = "2026-07-28",
    tool_call_id: str | None = None,
    status_code: str = "OK",
    traceparent: str | None = None,
) -> McpSpanAttributes:
    """Construct standardized OpenTelemetry MCP span attributes per `{mcp.method.name} {target}` convention."""
    resolved_tp = ensure_w3c_traceparent(traceparent)
    resolved_call_id = tool_call_id or new_id("call")
    target = f"{server_name}.{tool_name}" if tool_name else server_name
    return McpSpanAttributes(
        span_name=f"{mcp_method} {target}",
        mcp_method_name=mcp_method,
        mcp_protocol_version=protocol_version,
        mcp_server_name=server_name,
        gen_ai_operation_name="execute_tool" if mcp_method == "tools/call" else "mcp_request",
        gen_ai_tool_name=tool_name or mcp_method,
        gen_ai_tool_call_id=resolved_call_id,
        gen_ai_tool_type="extension",
        ssra_risk_tier=tier.value,
        ssra_data_classification=data_classification,
        rpc_response_status_code=status_code,
        traceparent=resolved_tp,
    )


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
        """Serialize GenAI span attributes to an OpenTelemetry attribute dictionary."""
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
    """Build OpenTelemetry GenAI span attributes with sovereign GPU prefix-cache cost attribution."""
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


@dataclass(frozen=True)
class AgenticCxSpanAttributes:
    """October 2026 SSRA Agentic CX, EQ & Workforce Collaboration OpenTelemetry Attributes."""

    goal_id: str
    goal_step_count: int
    goal_outcome: Literal[
        "autonomous_resolved",
        "async_continued",
        "eq_escalated",
        "t4_mandatory_handoff",
        "abstained",
    ]
    eq_emotion: str
    eq_intensity: float
    eq_frustration_velocity: float
    eq_tone_adapted: bool
    language_state: str
    locale: str
    handoff_clean: bool
    voice_ttfa_ms: float = 0.0
    hybrid_voice_mode: Literal["none", "s2s_fast_ack", "cascaded_governed"] = "none"
    offline_pack_used: bool = False

    def to_otel_dict(self) -> dict[str, Any]:
        """Serialize Agentic CX and EQ span attributes to an OpenTelemetry attribute dictionary."""
        return {
            "ssra.cx.goal.id": self.goal_id,
            "ssra.cx.goal.step_count": self.goal_step_count,
            "ssra.cx.goal.outcome": self.goal_outcome,
            "ssra.cx.eq.emotion": self.eq_emotion,
            "ssra.cx.eq.intensity": self.eq_intensity,
            "ssra.cx.eq.frustration_velocity": self.eq_frustration_velocity,
            "ssra.cx.eq.tone_adapted": self.eq_tone_adapted,
            "ssra.cx.language.state": self.language_state,
            "ssra.cx.language.locale": self.locale,
            "ssra.cx.handoff.clean": self.handoff_clean,
            "ssra.cx.voice.ttfa_ms": self.voice_ttfa_ms,
            "ssra.cx.voice.hybrid_mode": self.hybrid_voice_mode,
            "ssra.cx.offline.pack_used": self.offline_pack_used,
        }


def build_agentic_cx_span_attributes(
    *,
    goal_id: str,
    goal_step_count: int = 1,
    goal_outcome: Literal[
        "autonomous_resolved",
        "async_continued",
        "eq_escalated",
        "t4_mandatory_handoff",
        "abstained",
    ] = "autonomous_resolved",
    eq_emotion: str = "calm",
    eq_intensity: float = 0.1,
    eq_frustration_velocity: float = 0.0,
    eq_tone_adapted: bool = False,
    language_state: str = "LOCKED",
    locale: LocaleCode = LocaleCode.EN,
    handoff_clean: bool = True,
    voice_ttfa_ms: float = 0.0,
    hybrid_voice_mode: Literal["none", "s2s_fast_ack", "cascaded_governed"] = "none",
    offline_pack_used: bool = False,
) -> AgenticCxSpanAttributes:
    """Construct validated OpenTelemetry Agentic CX and EQ span attributes."""
    return AgenticCxSpanAttributes(
        goal_id=goal_id,
        goal_step_count=max(1, goal_step_count),
        goal_outcome=goal_outcome,
        eq_emotion=eq_emotion,
        eq_intensity=round(max(0.0, min(1.0, eq_intensity)), 2),
        eq_frustration_velocity=round(max(-1.0, min(1.0, eq_frustration_velocity)), 2),
        eq_tone_adapted=eq_tone_adapted,
        language_state=language_state,
        locale=locale.value,
        handoff_clean=handoff_clean,
        voice_ttfa_ms=round(max(0.0, voice_ttfa_ms), 2) if math.isfinite(voice_ttfa_ms) else 0.0,
        hybrid_voice_mode=hybrid_voice_mode,
        offline_pack_used=offline_pack_used,
    )
