"""OAuth 2.1 RFC 8693 subject binding & single-use T2/T3 confirmation tokens (Sections 8.2, 8.3, 12.3)."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from ssra_core import AuthLevel, McpErrorCode, RiskTier, SSRAError, new_id, utc_now

from ssra_security.audit import compute_canonical_digest


class SubjectTokenClaims(BaseModel):
    """Audience-bound OAuth 2.1 / RFC 8693 exchanged token claims verified by MCP servers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iss: str = "https://sso.ssra.gov.ss/realms/ssra"
    aud: str
    sub: str | None = None  # Opaque subject_ref for T1+
    caller_workload: str = "ssra-agent-runtime"
    auth_level: AuthLevel = AuthLevel.ANONYMOUS
    step_up_verified_at: datetime | None = None
    exp: datetime


class ConfirmationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    conversation_id: str
    tool_name: str
    action_digest: str
    idempotency_key: str
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None = None


def compute_action_digest(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    subject_ref: str | None,
) -> str:
    clean_args = {
        k: v
        for k, v in arguments.items()
        if k not in ("confirmation_token", "idempotency_key", "_meta")
    }
    return compute_canonical_digest(
        {
            "tool_name": tool_name,
            "arguments": clean_args,
            "subject_ref": subject_ref or "ANONYMOUS",
        }
    )


class ConfirmationTokenManager:
    """Issues and validates single-use, short-TTL confirmation tokens bound to argument hashes."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl_seconds = ttl_seconds
        self._records: dict[str, ConfirmationRecord] = {}
        self._idempotency_results: dict[str, dict[str, Any]] = {}

    def issue_token(
        self,
        *,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        subject_ref: str | None,
        idempotency_key: str | None = None,
        now: datetime | None = None,
    ) -> ConfirmationRecord:
        issued = now or utc_now()
        token = new_id("cfm")
        idem_key = idempotency_key or new_id("idem")
        digest = compute_action_digest(
            tool_name=tool_name, arguments=arguments, subject_ref=subject_ref
        )
        rec = ConfirmationRecord(
            token=token,
            conversation_id=conversation_id,
            tool_name=tool_name,
            action_digest=digest,
            idempotency_key=idem_key,
            issued_at=issued,
            expires_at=issued + timedelta(seconds=self._ttl_seconds),
        )
        self._records[token] = rec
        return rec

    def consume_token(
        self,
        *,
        token: str,
        tool_name: str,
        arguments: dict[str, Any],
        subject_ref: str | None,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ConfirmationRecord:
        current = now or utc_now()
        rec = self._records.get(token)
        if rec is None:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Invalid or unknown confirmation_token",
                status_code=403,
            )
        if rec.used_at is not None:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "confirmation_token has already been used (single-use policy)",
                status_code=403,
            )
        if current > rec.expires_at:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "confirmation_token has expired",
                status_code=403,
            )
        expected_digest = compute_action_digest(
            tool_name=tool_name, arguments=arguments, subject_ref=subject_ref
        )
        if not hmac.compare_digest(rec.action_digest, expected_digest):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "confirmation_token argument hash mismatch (tampered arguments or subject)",
                status_code=403,
            )
        if rec.idempotency_key != idempotency_key:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "idempotency_key does not match confirmed action",
                status_code=400,
            )
        rec.used_at = current
        return rec


class TokenExchangeService:
    """RFC 8693 OAuth 2.1 Token Exchange helper used by agentgateway and MCP servers."""

    def __init__(self, signing_secret: str | None = None) -> None:
        raw_secret = signing_secret or "ssra-dev-hmac-key"
        self._secret = raw_secret.encode("utf-8")

    def mint_exchanged_token(
        self,
        *,
        audience: str,
        auth_level: AuthLevel,
        subject_ref: str | None = None,
        step_up_verified_at: datetime | None = None,
        ttl_seconds: int = 60,
    ) -> str:
        now = utc_now()
        claims = SubjectTokenClaims(
            aud=audience,
            sub=subject_ref,
            auth_level=auth_level,
            step_up_verified_at=step_up_verified_at,
            exp=now + timedelta(seconds=ttl_seconds),
        )
        payload_json = claims.model_dump_json()
        sig = hmac.new(self._secret, payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{payload_json}.{sig}"

    def verify_exchanged_token(
        self,
        token: str,
        *,
        expected_audience: str,
        required_tier: RiskTier,
    ) -> SubjectTokenClaims:
        if "." not in token:
            raise SSRAError(McpErrorCode.NOT_AUTHORIZED, "Malformed bearer token", status_code=401)
        payload_json, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(
            self._secret, payload_json.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise SSRAError(McpErrorCode.NOT_AUTHORIZED, "Invalid token signature", status_code=401)
        claims = SubjectTokenClaims.model_validate(json.loads(payload_json))
        if claims.aud != expected_audience:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Token audience '{claims.aud}' does not match '{expected_audience}'",
                status_code=403,
            )
        if utc_now() > claims.exp:
            raise SSRAError(McpErrorCode.NOT_AUTHORIZED, "Bearer token expired", status_code=401)

        if required_tier in (RiskTier.T1, RiskTier.T2, RiskTier.T3):
            if not claims.sub or claims.auth_level not in (
                AuthLevel.T1_TIN_BOUND,
                AuthLevel.T3_STEP_UP,
                AuthLevel.STAFF_PASSKEY,
            ):
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"Tier {required_tier} requires verified TIN-bound subject_ref",
                    status_code=403,
                )
        if required_tier == RiskTier.T3 and claims.auth_level != AuthLevel.T3_STEP_UP:
            raise SSRAError(
                McpErrorCode.STEP_UP_REQUIRED,
                "Tier T3 requires fresh step-up authentication",
                status_code=403,
            )
        return claims
