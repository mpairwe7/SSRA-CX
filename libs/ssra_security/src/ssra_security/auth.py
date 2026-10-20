"""OAuth 2.1 RFC 8693 subject binding & single-use T2/T3 confirmation tokens (Sections 8.2, 8.3, 12.3)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from ssra_core import AuthLevel, McpErrorCode, RiskTier, SSRAError, new_id, utc_now

from ssra_security.audit import compute_canonical_digest


class SubjectTokenClaims(BaseModel):
    """Audience-, Scope- & RFC 8707 Resource-bound OAuth 2.1 / RFC 8693 exchanged token claims verified by MCP servers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jti: str = "jti_default"
    iss: str = "https://sso.ssra.gov.ss/realms/ssra"
    aud: str
    resource: str = "https://mcp.ssra.gov.ss"  # RFC 8707 Resource Indicator
    scope: str = (
        "mcp:tools:read"  # Progressive least-privilege scope (MCP 2026-07-28 Scope Minimization)
    )
    sub: str | None = None  # Opaque subject_ref for T1+
    caller_workload: str = "ssra-agent-runtime"
    auth_level: AuthLevel = AuthLevel.ANONYMOUS
    step_up_verified_at: datetime | None = None
    cnf_jkt: str | None = None  # RFC 9449 DPoP JWK SHA-256 thumbprint binding (ASVS 5.0 V10.3.5 L3)
    exp: datetime


def compute_least_privilege_mcp_scope(audience: str, tier: RiskTier) -> str:
    """Compute progressive, least-privilege OAuth 2.1 scope for an MCP server and risk tier."""
    srv = audience.removeprefix("mcp-")
    if tier == RiskTier.T3:
        return f"mcp:{srv}:step_up"
    if tier == RiskTier.T2:
        return f"mcp:{srv}:write"
    return f"mcp:{srv}:read"


def verify_mcp_scope_sufficiency(
    *,
    granted_scope: str,
    audience: str,
    required_tier: RiskTier,
) -> bool:
    """Verify hierarchical scope sufficiency per MCP 2026-07-28 Scope Minimization specification."""
    srv = audience.removeprefix("mcp-")
    tokens = set(granted_scope.split())
    if "*" in tokens or "all" in tokens or "full-access" in tokens:
        # Omnibus / wildcard scopes are prohibited by MCP 2026-07-28 Scope Minimization
        return False
    allowed_for_tier: dict[RiskTier, set[str]] = {
        RiskTier.T0: {
            "mcp:tools:read",
            f"mcp:{srv}:read",
            f"mcp:{srv}:write",
            f"mcp:{srv}:step_up",
            f"mcp:{srv}:invoke",
        },
        RiskTier.T1: {
            f"mcp:{srv}:read",
            f"mcp:{srv}:write",
            f"mcp:{srv}:step_up",
            f"mcp:{srv}:invoke",
        },
        RiskTier.T2: {
            f"mcp:{srv}:write",
            f"mcp:{srv}:step_up",
            f"mcp:{srv}:invoke",
        },
        RiskTier.T3: {
            f"mcp:{srv}:step_up",
        },
    }
    accepted = allowed_for_tier.get(required_tier, set())
    return bool(tokens & accepted)


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


MAX_CONFIRMATION_RECORDS = 2048
MAX_STEP_UP_AGE_SECONDS = 300
_SHARED_JTI_LOCK = threading.Lock()
_SHARED_CONSUMED_JTIS: dict[str, datetime] = {}
_SHARED_CONFIRM_LOCK = threading.Lock()
_SHARED_CONSUMED_CONFIRMATIONS: dict[str, datetime] = {}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(val: str) -> bytes:
    pad = "=" * (-len(val) % 4)
    return base64.urlsafe_b64decode(val + pad)


class ConfirmationTokenManager:
    """Issues and validates single-use, short-TTL HMAC-SHA256 confirmation tokens bound to argument hashes.

    Note: `_SHARED_CONSUMED_CONFIRMATIONS` enforces single-use replay rejection across manager instances
    within a single OS process; multi-process deployments must back `tid` consumption with an atomic
    Valkey `SET NX EX` or PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` store.
    """

    def __init__(self, ttl_seconds: int = 300, signing_secret: str | None = None) -> None:
        """Initialise the confirmation token manager with a thread lock, TTL, and HMAC signing secret."""
        self._ttl_seconds = ttl_seconds
        raw_secret = signing_secret or os.environ.get("SSRA_CONFIRM_HMAC_SECRET")
        if not raw_secret:
            runtime_env = (
                (os.environ.get("SSRA_ENV") or os.environ.get("APP_ENV") or "development")
                .strip()
                .lower()
            )
            if runtime_env not in ("local", "dev", "development", "test"):
                raise RuntimeError("SSRA_CONFIRM_HMAC_SECRET must be set in production")
            raw_secret = "ssra-dev-confirm-hmac-key"  # noqa: S105
        self._secret = raw_secret.encode("utf-8")
        self._lock = threading.Lock()
        self._records: dict[str, ConfirmationRecord] = {}
        self._idempotency_results: dict[str, dict[str, Any]] = {}

    def _sign_token(
        self,
        *,
        token_id: str,
        conversation_id: str,
        tool_name: str,
        action_digest: str,
        idempotency_key: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> str:
        payload = {
            "tid": token_id,
            "cid": conversation_id,
            "tool": tool_name,
            "dig": action_digest,
            "idem": idempotency_key,
            "iat": issued_at.isoformat(),
            "exp": expires_at.isoformat(),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        tag = hmac.new(self._secret, payload_bytes, hashlib.sha256).digest()
        return f"{token_id}.{_b64url_encode(payload_bytes)}.{_b64url_encode(tag)}"

    def _verify_stateless_signed_token(self, token: str) -> ConfirmationRecord | None:
        """Verify an HMAC-SHA256 signed confirmation token across worker replicas in constant time."""
        parts = token.split(".")
        if len(parts) != 3 or not parts[0].startswith("cfm"):
            return None
        try:
            payload_bytes = _b64url_decode(parts[1])
            expected_tag = _b64url_decode(parts[2])
        except ValueError:
            return None
        actual_tag = hmac.new(self._secret, payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(actual_tag, expected_tag):
            return None
        try:
            data = json.loads(payload_bytes.decode("utf-8"))
            if not isinstance(data, dict) or data.get("tid") != parts[0]:
                return None
            issued_at = datetime.fromisoformat(str(data["iat"]))
            expires_at = datetime.fromisoformat(str(data["exp"]))
            with _SHARED_CONFIRM_LOCK:
                is_consumed = token in _SHARED_CONSUMED_CONFIRMATIONS
            return ConfirmationRecord(
                token=token,
                conversation_id=str(data["cid"]),
                tool_name=str(data["tool"]),
                action_digest=str(data["dig"]),
                idempotency_key=str(data["idem"]),
                issued_at=issued_at,
                expires_at=expires_at,
                used_at=issued_at if is_consumed else None,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None

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
        """Issue a single-use, HMAC-SHA256 argument-digest-bound confirmation token, purging expired records first."""
        issued = now or utc_now()
        expires = issued + timedelta(seconds=self._ttl_seconds)
        token_id = new_id("cfm")
        idem_key = idempotency_key or new_id("idem")
        digest = compute_action_digest(
            tool_name=tool_name, arguments=arguments, subject_ref=subject_ref
        )
        token = self._sign_token(
            token_id=token_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            action_digest=digest,
            idempotency_key=idem_key,
            issued_at=issued,
            expires_at=expires,
        )
        rec = ConfirmationRecord(
            token=token,
            conversation_id=conversation_id,
            tool_name=tool_name,
            action_digest=digest,
            idempotency_key=idem_key,
            issued_at=issued,
            expires_at=expires,
        )
        with self._lock:
            self._records = {k: v for k, v in self._records.items() if issued <= v.expires_at}
            if len(self._records) >= MAX_CONFIRMATION_RECORDS:
                self._records.pop(next(iter(self._records)), None)
            self._records[token] = rec
        return rec

    def get_record(self, token: str) -> ConfirmationRecord | None:
        """Look up a confirmation record by token string (or verify statelessly across replicas)."""
        with self._lock:
            rec = self._records.get(token)
            if rec is not None:
                with _SHARED_CONFIRM_LOCK:
                    is_consumed = token in _SHARED_CONSUMED_CONFIRMATIONS
                if is_consumed and rec.used_at is None:
                    rec.used_at = rec.issued_at
                return rec
            stateless_rec = self._verify_stateless_signed_token(token)
            if stateless_rec is not None:
                self._records[token] = stateless_rec
            return stateless_rec

    def consume_token(
        self,
        *,
        token: str,
        tool_name: str,
        arguments: dict[str, Any],
        subject_ref: str | None,
        idempotency_key: str,
        conversation_id: str | None = None,
        now: datetime | None = None,
    ) -> ConfirmationRecord:
        """Consume a single-use confirmation token atomically after verifying HMAC, TTL, thread, and argument digest."""
        current = now or utc_now()
        expected_digest = compute_action_digest(
            tool_name=tool_name, arguments=arguments, subject_ref=subject_ref
        )
        with self._lock:
            rec = self._records.get(token)
            if rec is None:
                rec = self._verify_stateless_signed_token(token)
                if rec is not None:
                    self._records[token] = rec
            if rec is None:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "Invalid or unknown confirmation_token",
                    status_code=403,
                )
            with _SHARED_CONFIRM_LOCK:
                is_consumed = token in _SHARED_CONSUMED_CONFIRMATIONS
            if rec.used_at is not None or is_consumed:
                rec.used_at = rec.used_at or current
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
            if rec.tool_name != tool_name:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "confirmation_token tool_name mismatch",
                    status_code=403,
                )
            if conversation_id is not None and rec.conversation_id != conversation_id:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "confirmation_token conversation_id mismatch (cross-thread replay blocked)",
                    status_code=403,
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
            with _SHARED_CONFIRM_LOCK:
                for k in [
                    k for k, exp_at in _SHARED_CONSUMED_CONFIRMATIONS.items() if exp_at < current
                ]:
                    del _SHARED_CONSUMED_CONFIRMATIONS[k]
                _SHARED_CONSUMED_CONFIRMATIONS[token] = rec.expires_at
            return rec


class TokenExchangeService:
    """RFC 8693 OAuth 2.1 Token Exchange & RFC 9449 DPoP thumbprint helper used by agentgateway and MCP servers."""

    def __init__(self, signing_secret: str | None = None) -> None:
        """Initialise the token exchange service with an HMAC signing secret and shared JTI replay cache."""
        raw_secret = signing_secret or "ssra-dev-hmac-key"
        self._secret = raw_secret.encode("utf-8")
        self._consumed_jtis = _SHARED_CONSUMED_JTIS

    def mint_exchanged_token(
        self,
        *,
        audience: str,
        auth_level: AuthLevel,
        subject_ref: str | None = None,
        resource: str | None = None,
        scope: str | None = None,
        caller_workload: str = "ssra-agent-runtime",
        step_up_verified_at: datetime | None = None,
        cnf_jkt: str | None = None,
        ttl_seconds: int = 60,
    ) -> str:
        """Mint an RFC 8693 audience-, resource-, least-privilege-scope-, and optional RFC 9449 DPoP-bound JWT."""
        now = utc_now()
        srv = audience.removeprefix("mcp-")
        if scope is not None:
            resolved_scope = scope
        elif auth_level == AuthLevel.T3_STEP_UP:
            resolved_scope = f"mcp:{srv}:read mcp:{srv}:write mcp:{srv}:step_up"
        elif auth_level in (AuthLevel.T1_TIN_BOUND, AuthLevel.STAFF_PASSKEY):
            resolved_scope = f"mcp:{srv}:read mcp:{srv}:write"
        else:
            resolved_scope = f"mcp:{srv}:read"
        resolved_step_up = (
            step_up_verified_at
            if step_up_verified_at is not None
            else (now if auth_level == AuthLevel.T3_STEP_UP else None)
        )
        claims = SubjectTokenClaims(
            jti=new_id("jti"),
            aud=audience,
            resource=resource or f"https://mcp.ssra.gov.ss/servers/{audience}",
            scope=resolved_scope,
            sub=subject_ref,
            caller_workload=caller_workload,
            auth_level=auth_level,
            step_up_verified_at=resolved_step_up,
            cnf_jkt=cnf_jkt,
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
        expected_resource: str | None = None,
        expected_dpop_jkt: str | None = None,
        enforce_single_use_jti: bool = False,
    ) -> SubjectTokenClaims:
        """Verify RFC 8693 token signature, audience, RFC 8707 resource, scope, RFC 9449 DPoP thumbprint, and T3 step-up freshness."""
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
        if expected_resource is not None and claims.resource != expected_resource:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"RFC 8707 resource '{claims.resource}' does not match '{expected_resource}'",
                status_code=403,
            )
        if utc_now() > claims.exp:
            raise SSRAError(McpErrorCode.NOT_AUTHORIZED, "Bearer token expired", status_code=401)

        if expected_dpop_jkt is not None or claims.cnf_jkt is not None:
            dpop_ok = bool(
                claims.cnf_jkt
                and expected_dpop_jkt
                and hmac.compare_digest(claims.cnf_jkt, expected_dpop_jkt)
            )
            if not dpop_ok:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "RFC 9449 DPoP sender-constrained cnf.jkt thumbprint mismatch (ASVS 5.0 V10.3.5)",
                    status_code=401,
                )

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
        if required_tier == RiskTier.T3:
            if claims.auth_level != AuthLevel.T3_STEP_UP or claims.step_up_verified_at is None:
                raise SSRAError(
                    McpErrorCode.STEP_UP_REQUIRED,
                    "Tier T3 requires fresh step-up authentication",
                    status_code=403,
                )
            if (utc_now() - claims.step_up_verified_at) > timedelta(
                seconds=MAX_STEP_UP_AGE_SECONDS
            ):
                raise SSRAError(
                    McpErrorCode.STEP_UP_REQUIRED,
                    f"Tier T3 step-up authentication expired (> {MAX_STEP_UP_AGE_SECONDS}s max_age)",
                    status_code=403,
                )
        if not verify_mcp_scope_sufficiency(
            granted_scope=claims.scope,
            audience=expected_audience,
            required_tier=required_tier,
        ):
            err_code = (
                McpErrorCode.STEP_UP_REQUIRED
                if required_tier == RiskTier.T3
                else McpErrorCode.NOT_AUTHORIZED
            )
            req_scope = compute_least_privilege_mcp_scope(expected_audience, required_tier)
            raise SSRAError(
                err_code,
                f"Insufficient OAuth 2.1 scope '{claims.scope}'; operation requires '{req_scope}'",
                status_code=403,
            )

        if enforce_single_use_jti:
            with _SHARED_JTI_LOCK:
                now_dt = utc_now()
                active = {
                    k: exp_dt for k, exp_dt in self._consumed_jtis.items() if now_dt <= exp_dt
                }
                self._consumed_jtis.clear()
                self._consumed_jtis.update(active)
                is_replayed_or_full = (
                    claims.jti in self._consumed_jtis
                    or len(self._consumed_jtis) >= MAX_CONFIRMATION_RECORDS
                )
                if is_replayed_or_full:
                    raise SSRAError(
                        McpErrorCode.NOT_AUTHORIZED
                        if claims.jti in self._consumed_jtis
                        else McpErrorCode.RATE_LIMITED,
                        f"Single-use exchanged token jti '{claims.jti}' replay or capacity blocked",
                        status_code=401 if claims.jti in self._consumed_jtis else 429,
                    )
                self._consumed_jtis[claims.jti] = claims.exp
        return claims
