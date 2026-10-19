"""API router for admin bounded context (Kill switches & WORM audit verification)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ssra_api.admin.application import (
    default_kill_switch_state,
    get_admin_audit_head_hash,
    record_jit_admin_elevation,
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


@router.get("/kill-switches", response_model=KillSwitchResponse)
async def get_kill_switches() -> KillSwitchResponse:
    state = default_kill_switch_state()
    return KillSwitchResponse(
        degradation_level=state.degradation_level,
        disabled_tools=list(state.disabled_tools),
        disabled_channels=list(state.disabled_channels),
    )


@router.post("/kill-switches", response_model=KillSwitchResponse)
async def set_kill_switches(body: UpdateKillSwitchRequest) -> KillSwitchResponse:
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
    from ssra_core import McpErrorCode, SSRAError

    if not body.passkey_verified or not body.device_posture_compliant:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "JIT admin elevation requires WebAuthn passkey and compliant device posture",
            status_code=403,
        )
    if body.requester_staff_id == body.approver_staff_id:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "Maker-checker violation: approver_staff_id must differ from requester_staff_id",
            status_code=403,
        )
    record_jit_admin_elevation(
        requester_staff_id=body.requester_staff_id,
        approver_staff_id=body.approver_staff_id,
        duration_minutes=body.duration_minutes,
        reason=body.reason,
    )
    return JitElevationResponse(
        requester_staff_id=body.requester_staff_id,
        approver_staff_id=body.approver_staff_id,
        granted=True,
        duration_minutes=body.duration_minutes,
        status="GRANTED_TIMEBOXED_JIT_ADMIN",
    )
