"""SSRA Assist security library."""

from ssra_security.audit import (
    GENESIS_HASH,
    AuditEvent,
    HashChainedAuditLedger,
    compute_audit_event_hash,
    compute_canonical_digest,
)
from ssra_security.auth import (
    ConfirmationRecord,
    ConfirmationTokenManager,
    SubjectTokenClaims,
    TokenExchangeService,
    compute_action_digest,
)
from ssra_security.encryption import OpenBaoTransitEncryptor
from ssra_security.redaction import RedactionResult, mask_tin, redact_pii
from ssra_security.siem import (
    OcsfSecurityEvent,
    SiemSeverity,
    classify_siem_severity,
    format_audit_event_as_cef,
    format_audit_event_as_ocsf,
    validate_inter_model_handoff,
)

__all__ = [
    "GENESIS_HASH",
    "AuditEvent",
    "ConfirmationRecord",
    "ConfirmationTokenManager",
    "HashChainedAuditLedger",
    "OcsfSecurityEvent",
    "OpenBaoTransitEncryptor",
    "RedactionResult",
    "SiemSeverity",
    "SubjectTokenClaims",
    "TokenExchangeService",
    "classify_siem_severity",
    "compute_action_digest",
    "compute_audit_event_hash",
    "compute_canonical_digest",
    "format_audit_event_as_cef",
    "format_audit_event_as_ocsf",
    "mask_tin",
    "redact_pii",
    "validate_inter_model_handoff",
]
