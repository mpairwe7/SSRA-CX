"""API router for admin bounded context (Kill switches & WORM audit verification)."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _raise_staff_session_required() -> NoReturn:
    """Fail closed until an approved staff identity adapter validates a server-side session."""
    raise SSRAError(
        McpErrorCode.NOT_AUTHORIZED,
        "Staff data and actions are unavailable until an approved server-verified session and role policy are configured (OQ-014).",
        status_code=403,
    )


def _raise_operational_status_unavailable() -> NoReturn:
    """Avoid presenting hard-coded reference values as live service telemetry."""
    raise SSRAError(
        McpErrorCode.UPSTREAM_UNAVAILABLE,
        "Operational status is unavailable until trusted health signals, freshness controls, and provenance are configured (OQ-013, OQ-015).",
        status_code=503,
    )


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
    official_portal: str


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


@router.get(
    "/kill-switches",
    response_model=KillSwitchResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def get_kill_switches() -> KillSwitchResponse:
    """Return kill-switch state only to a server-verified, authorized staff session."""
    _raise_staff_session_required()


@router.post(
    "/kill-switches",
    response_model=KillSwitchResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def set_kill_switches(body: UpdateKillSwitchRequest) -> KillSwitchResponse:
    """Update kill switches only after server-side staff authentication and authorization."""
    del body
    _raise_staff_session_required()


@router.get(
    "/audit-verify",
    response_model=AuditVerifyResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def verify_audit() -> AuditVerifyResponse:
    """Expose audit-chain records only to a server-verified auditor/staff session."""
    _raise_staff_session_required()


@router.get(
    "/public-status",
    response_model=PublicStatusResponse,
    responses={503: {"description": "Trusted operational status telemetry is not configured."}},
)
async def get_public_status() -> PublicStatusResponse:
    """Return live status only when trusted, fresh monitoring sources are connected."""
    _raise_operational_status_unavailable()


@router.post(
    "/jit-elevation",
    response_model=JitElevationResponse,
    responses={
        403: {"description": "Verified staff session and maker-checker policy are required."}
    },
)
async def request_jit_elevation(body: JitElevationRequest) -> JitElevationResponse:
    """Never infer passkey verification from request fields; require a trusted session adapter."""
    del body
    _raise_staff_session_required()


@router.get(
    "/feature-flags",
    response_model=list[FeatureFlagRuleResponse],
    responses={403: {"description": "Verified staff session is required."}},
)
async def get_feature_flags() -> list[FeatureFlagRuleResponse]:
    """Read feature flags only after server-side staff authentication and authorization."""
    _raise_staff_session_required()


@router.post(
    "/feature-flags",
    response_model=FeatureFlagRuleResponse,
    responses={403: {"description": "Verified staff session is required."}},
)
async def set_feature_flag(body: UpdateFeatureFlagRequest) -> FeatureFlagRuleResponse:
    """Mutate feature flags only after server-side staff authentication and authorization."""
    del body
    _raise_staff_session_required()
