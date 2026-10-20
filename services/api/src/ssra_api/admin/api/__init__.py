"""API router for admin bounded context (Kill switches & WORM audit verification)."""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from ssra_api.admin.application import (
    default_kill_switch_state,
    get_admin_audit_head_hash,
    list_admin_feature_flags,
    record_jit_admin_elevation,
    update_admin_feature_flag,
    update_kill_switch_state,
    verify_admin_audit_chain,
)
from ssra_api.outbox import get_outbox_store

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class KillSwitchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degradation_level: int
    disabled_tools: list[str]
    disabled_channels: list[str]


class UpdateKillSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degradation_level: int = Field(ge=1, le=5, default=1)
    disabled_tools: list[str] = Field(default_factory=list)
    disabled_channels: list[str] = Field(default_factory=list)


class AuditVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integrity_verified: bool
    events_count: int
    head_hash: str


class JitElevationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_staff_id: str = Field(min_length=3)
    approver_staff_id: str = Field(min_length=3)
    passkey_verified: bool
    device_posture_compliant: bool
    duration_minutes: int = Field(ge=1, le=60, default=30)
    reason: str = Field(min_length=5)


class JitElevationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_staff_id: str
    approver_staff_id: str
    granted: bool
    duration_minutes: int
    status: str


class PublicStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    degradation_level: int
    active_knowledge_snapshot: str
    channels: dict[str, str]
    upstreams: dict[str, str]
    official_portal: str = "https://etax.nra.gov.ss/"


class FeatureFlagRuleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    enabled: bool
    rollout_pct: int
    allowed_channels: list[str]
    allowed_locales: list[str]


class UpdateFeatureFlagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_name: str = Field(min_length=3)
    enabled: bool = True
    rollout_pct: int = Field(ge=0, le=100, default=100)


@router.get("/kill-switches", response_model=KillSwitchResponse)
async def get_kill_switches() -> KillSwitchResponse:
    """Return the current SecOps degradation level and disabled tools/channels."""
    state = default_kill_switch_state()
    return KillSwitchResponse(
        degradation_level=state.degradation_level,
        disabled_tools=list(state.disabled_tools),
        disabled_channels=list(state.disabled_channels),
    )


@router.post("/kill-switches", response_model=KillSwitchResponse)
async def set_kill_switches(body: UpdateKillSwitchRequest) -> KillSwitchResponse:
    """Update the active SecOps kill-switches and log the change to the WORM audit ledger."""
    state = update_kill_switch_state(
        degradation_level=body.degradation_level,
        disabled_tools=body.disabled_tools,
        disabled_channels=body.disabled_channels,
    )
    return KillSwitchResponse(
        degradation_level=state.degradation_level,
        disabled_tools=list(state.disabled_tools),
        disabled_channels=list(state.disabled_channels),
    )


@router.get("/audit-verify", response_model=AuditVerifyResponse)
async def verify_audit() -> AuditVerifyResponse:
    """Verify the admin WORM audit chain and return integrity status, event count, and head hash."""
    ok, count = verify_admin_audit_chain()
    return AuditVerifyResponse(
        integrity_verified=ok,
        events_count=count,
        head_hash=get_admin_audit_head_hash(),
    )


@router.get("/public-status", response_model=PublicStatusResponse)
async def get_public_status() -> PublicStatusResponse:
    """Return the public degradation-aware system status and active knowledge snapshot version."""
    state = default_kill_switch_state()
    disabled_ch = set(state.disabled_channels)
    return PublicStatusResponse(
        overall_status="OPERATIONAL" if state.degradation_level <= 3 else "DEGRADED_SAFE_MODE",
        degradation_level=state.degradation_level,
        active_knowledge_snapshot=get_outbox_store().active_knowledge_snapshot,
        channels={
            ch: ("PAUSED" if ch in disabled_ch else "OPERATIONAL")
            for ch in ("web", "whatsapp", "sms", "ussd", "voice")
        },
        upstreams={
            "etax": "OPERATIONAL",
            "ecustoms": "MOCK_ACTIVE_OQ002",
            "boss_fx": "OPERATIONAL",
        },
    )


@router.post("/jit-elevation", response_model=JitElevationResponse)
async def request_jit_elevation(body: JitElevationRequest) -> JitElevationResponse:
    """Grant time-boxed JIT admin elevation after verifying trusted staff directory & maker-checker controls."""
    record_jit_admin_elevation(
        requester_staff_id=body.requester_staff_id,
        approver_staff_id=body.approver_staff_id,
        duration_minutes=body.duration_minutes,
        reason=body.reason,
        passkey_verified=body.passkey_verified,
        device_posture_compliant=body.device_posture_compliant,
    )
    return JitElevationResponse(
        requester_staff_id=body.requester_staff_id,
        approver_staff_id=body.approver_staff_id,
        granted=True,
        duration_minutes=body.duration_minutes,
        status="GRANTED_TIMEBOXED_JIT_ADMIN",
    )


@router.get("/feature-flags", response_model=list[FeatureFlagRuleResponse])
async def get_feature_flags(
    x_ssra_staff_id: str = Header(default="secops_admin", alias="X-SSRA-Staff-Id"),
) -> list[FeatureFlagRuleResponse]:
    """List all registered SSRA Assist cohort/percentage feature flags (requires verified admin/secops staff)."""
    return [
        FeatureFlagRuleResponse(
            name=r.name,
            description=r.description,
            enabled=r.enabled,
            rollout_pct=r.rollout_pct,
            allowed_channels=list(r.allowed_channels),
            allowed_locales=list(r.allowed_locales),
        )
        for r in list_admin_feature_flags(actor=x_ssra_staff_id)
    ]


@router.post("/feature-flags", response_model=FeatureFlagRuleResponse)
async def set_feature_flag(
    body: UpdateFeatureFlagRequest,
    x_ssra_staff_id: str = Header(default="secops_admin", alias="X-SSRA-Staff-Id"),
) -> FeatureFlagRuleResponse:
    """Update a cohort/percentage feature flag and append a WORM audit event attributed to the verified staff actor."""
    rule = update_admin_feature_flag(
        flag_name=body.flag_name,
        enabled=body.enabled,
        rollout_pct=body.rollout_pct,
        actor=x_ssra_staff_id,
    )
    return FeatureFlagRuleResponse(
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        rollout_pct=rule.rollout_pct,
        allowed_channels=list(rule.allowed_channels),
        allowed_locales=list(rule.allowed_locales),
    )
