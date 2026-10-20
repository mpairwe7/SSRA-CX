"""Application layer for admin bounded context (Kill switches & audit chain verification — Section 12.3)."""

from __future__ import annotations

from ssra_core import (
    FeatureFlagRule,
    McpErrorCode,
    SSRAError,
    get_default_feature_flag_engine,
)
from ssra_security import (
    GENESIS_HASH,
    PROTECTED_SECURITY_FLAGS,
    HashChainedAuditLedger,
)

from ssra_api.admin.domain import KillSwitchState
from ssra_api.outbox import get_outbox_store

_current_state = KillSwitchState(
    degradation_level=1,
    disabled_tools=(),
    disabled_channels=(),
)
_admin_audit = HashChainedAuditLedger()
_VERIFIED_STAFF_DIRECTORY: dict[str, dict[str, str | bool]] = {
    "stf_01": {
        "staff_id": "stf_01",
        "role": "admin",
        "passkey_verified": True,
        "device_posture_compliant": True,
    },
    "stf_supervisor_02": {
        "staff_id": "stf_supervisor_02",
        "role": "supervisor",
        "passkey_verified": True,
        "device_posture_compliant": True,
    },
    "secops_admin": {
        "staff_id": "secops_admin",
        "role": "secops",
        "passkey_verified": True,
        "device_posture_compliant": True,
    },
    "ssra_admin": {
        "staff_id": "ssra_admin",
        "role": "admin",
        "passkey_verified": True,
        "device_posture_compliant": True,
    },
    "ssra_auditor": {
        "staff_id": "ssra_auditor",
        "role": "auditor",
        "passkey_verified": True,
        "device_posture_compliant": True,
    },
}


def default_kill_switch_state() -> KillSwitchState:
    """Return the current active SecOps kill-switch state."""
    return _current_state


def update_kill_switch_state(
    *,
    degradation_level: int,
    disabled_tools: list[str],
    disabled_channels: list[str],
    actor: str = "secops_admin",
) -> KillSwitchState:
    """Update the active kill-switch state after verifying admin/secops staff RBAC and append a WORM audit event."""
    verified_actor = _verify_admin_or_secops_actor(actor)
    global _current_state
    _current_state = KillSwitchState(
        degradation_level=degradation_level,
        disabled_tools=tuple(disabled_tools),
        disabled_channels=tuple(disabled_channels),
    )
    _admin_audit.append(
        actor=verified_actor,
        action="admin.kill_switch.update",
        resource="ssra://admin/kill-switches",
        payload={
            "degradation_level": degradation_level,
            "disabled_tools": disabled_tools,
            "disabled_channels": disabled_channels,
        },
    )
    get_outbox_store().stage_domain_event(
        context_name="admin",
        event_type="ssra.admin.kill_switch.updated.v1",
        subject="kill-switches",
        data={
            "degradation_level": degradation_level,
            "disabled_tools": disabled_tools,
            "disabled_channels": disabled_channels,
        },
    )
    return _current_state


def verify_admin_audit_chain() -> tuple[bool, int]:
    """Verify cryptographic integrity of the admin WORM hash-chained audit ledger."""
    return _admin_audit.verify_integrity(), len(_admin_audit.events)


def get_admin_audit_head_hash() -> str:
    """Return the latest audit event SHA-256 hash or the 64-zero genesis hash when empty."""
    return _admin_audit.events[-1].hash if _admin_audit.events else GENESIS_HASH


def record_jit_admin_elevation(
    *,
    requester_staff_id: str,
    approver_staff_id: str,
    duration_minutes: int,
    reason: str,
    passkey_verified: bool = True,
    device_posture_compliant: bool = True,
) -> str:
    """Verify requester/approver against the trusted staff directory and append a WORM audit event."""
    if not passkey_verified or not device_posture_compliant:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "JIT admin elevation requires WebAuthn passkey and compliant device posture",
            status_code=403,
        )
    if requester_staff_id == approver_staff_id:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "Maker-checker violation: approver_staff_id must differ from requester_staff_id",
            status_code=403,
        )
    req_rec = _VERIFIED_STAFF_DIRECTORY.get(requester_staff_id)
    app_rec = _VERIFIED_STAFF_DIRECTORY.get(approver_staff_id)
    is_valid_actors = (
        req_rec is not None
        and app_rec is not None
        and bool(req_rec.get("passkey_verified"))
        and bool(req_rec.get("device_posture_compliant"))
        and bool(app_rec.get("passkey_verified"))
        and bool(app_rec.get("device_posture_compliant"))
        and app_rec.get("role") in {"supervisor", "secops", "admin"}
    )
    if not is_valid_actors or req_rec is None or app_rec is None:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "JIT admin elevation requires verified staff identities with active WebAuthn passkey and supervisor/secops approval",
            status_code=403,
        )
    verified_requester = str(req_rec["staff_id"])
    verified_approver = str(app_rec["staff_id"])
    ev = _admin_audit.append(
        actor=verified_approver,
        on_behalf_of=verified_requester,
        action="admin.jit_elevation.grant",
        resource=f"staff://{verified_requester}",
        payload={
            "requester_staff_id": verified_requester,
            "approver_staff_id": verified_approver,
            "duration_minutes": duration_minutes,
            "reason": reason,
        },
    )
    get_outbox_store().stage_domain_event(
        context_name="admin",
        event_type="ssra.admin.jit_elevation.granted.v1",
        subject=verified_requester,
        data={
            "requester_staff_id": verified_requester,
            "approver_staff_id": verified_approver,
            "duration_minutes": duration_minutes,
            "reason": reason,
            "audit_hash": ev.hash,
        },
    )
    return ev.hash


def _verify_admin_or_secops_actor(actor_staff_id: str) -> str:
    """Validate that `actor_staff_id` is a passkey-verified admin/secops/supervisor staff member."""
    rec = _VERIFIED_STAFF_DIRECTORY.get(actor_staff_id)
    is_authorized = (
        rec is not None
        and bool(rec.get("passkey_verified"))
        and bool(rec.get("device_posture_compliant"))
        and rec.get("role") in {"admin", "secops", "supervisor"}
    )
    if not is_authorized or rec is None:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            f"Admin feature-flag access requires verified admin/secops staff identity (received '{actor_staff_id}')",
            status_code=403,
        )
    return str(rec["staff_id"])


def list_admin_feature_flags(*, actor: str = "secops_admin") -> list[FeatureFlagRule]:
    """Return all registered SSRA Assist feature-flag rules after verifying staff authorization."""
    _verify_admin_or_secops_actor(actor)
    return get_default_feature_flag_engine().list_rules()


def update_admin_feature_flag(
    *,
    flag_name: str,
    enabled: bool,
    rollout_pct: int = 100,
    actor: str = "secops_admin",
) -> FeatureFlagRule:
    """Update a feature-flag cohort rollout percentage and append a WORM audit event + outbox CloudEvent."""
    verified_actor = _verify_admin_or_secops_actor(actor)
    if flag_name in PROTECTED_SECURITY_FLAGS and (not enabled or rollout_pct < 100):
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            f"Protected security control flag '{flag_name}' cannot be disabled via runtime override",
            status_code=403,
        )
    rule = get_default_feature_flag_engine().set_flag_override(
        flag_name,
        enabled=enabled,
        rollout_pct=rollout_pct,
    )
    _admin_audit.append(
        actor=verified_actor,
        action="admin.feature_flag.update",
        resource=f"ssra://admin/feature-flags/{flag_name}",
        payload={
            "flag_name": flag_name,
            "enabled": rule.enabled,
            "rollout_pct": rule.rollout_pct,
        },
    )
    get_outbox_store().stage_domain_event(
        context_name="admin",
        event_type="ssra.admin.feature_flag.updated.v1",
        subject=flag_name,
        data={
            "flag_name": flag_name,
            "enabled": rule.enabled,
            "rollout_pct": rule.rollout_pct,
            "actor": verified_actor,
        },
    )
    return rule
