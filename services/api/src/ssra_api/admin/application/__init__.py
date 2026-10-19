"""Application layer for admin bounded context (Kill switches & audit chain verification — Section 12.3)."""

from __future__ import annotations

from ssra_security import GENESIS_HASH, HashChainedAuditLedger

from ssra_api.admin.domain import KillSwitchState
from ssra_api.outbox import get_outbox_store

_current_state = KillSwitchState(
    degradation_level=1,
    disabled_tools=(),
    disabled_channels=(),
)
_admin_audit = HashChainedAuditLedger()


def default_kill_switch_state() -> KillSwitchState:
    return _current_state


def update_kill_switch_state(
    *,
    degradation_level: int,
    disabled_tools: list[str],
    disabled_channels: list[str],
    actor: str = "secops_admin",
) -> KillSwitchState:
    global _current_state
    _current_state = KillSwitchState(
        degradation_level=degradation_level,
        disabled_tools=tuple(disabled_tools),
        disabled_channels=tuple(disabled_channels),
    )
    _admin_audit.append(
        actor=actor,
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
    return _admin_audit.verify_integrity(), len(_admin_audit.events)


def get_admin_audit_head_hash() -> str:
    return _admin_audit.events[-1].hash if _admin_audit.events else GENESIS_HASH
