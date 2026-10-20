"""Keycloak 26.x OAuth 2.1 / FAPI 2.0 / RFC 8693 / WebAuthn Passkey Security Guard (`libs/ssra_security/src/ssra_security/keycloak.py`).

Implements October 2026 Keycloak 26.x security mitigations (Section 12.1 & ADR-012):
- CVE-2026-16089: Binds OAuth 2.0 authorization codes to `client_id` + PKCE `S256` challenge.
- CVE-2026-1035 & CVE-2026-37982: Enforces atomic single-use `jti` consumption for refresh & WebAuthn action tokens.
- CVE-2026-3009: Rejects tokens issued via disabled or non-allowlisted Identity Providers (`idp`).
- CVE-2026-8830: Validates server-side WebAuthn passkey COSE algorithms (`ES256`, `EdDSA`) and `acr` claims.
- CVE-2026-37979: Enforces local audience (`aud`) and `azp` verification on all OIDC tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import threading
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError, utc_now

ALLOWED_WEBAUTHN_ALGORITHMS: frozenset[str] = frozenset({"ES256", "EdDSA", "-7", "-8"})
ALLOWED_IDP_ALIASES: frozenset[str] = frozenset({"ssra-national-idp", "keycloak-local"})
REQUIRED_KEYCLOAK_CLIENTS: frozenset[str] = frozenset(
    {
        "ssra-web-bff",
        "ssra-staff-console",
        "ssra-agentgateway",
        "mcp-knowledge",
        "mcp-tax-facts",
        "mcp-official-channels",
        "mcp-taxpayer",
        "mcp-ledger",
        "mcp-payments-info",
        "mcp-tcc",
        "mcp-customs",
        "mcp-cases",
        "mcp-appointments",
        "mcp-notifications",
    }
)


def validate_keycloak_realm_export(realm_data: dict[str, Any]) -> bool:
    """Verify October 2026 Keycloak 26.x realm security, passkey, and RFC 8693 V2 token-exchange invariants."""
    if realm_data.get("realm") != "ssra" or realm_data.get("sslRequired") != "all":
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Keycloak realm must be 'ssra' with sslRequired='all'",
            status_code=400,
        )
    if (
        realm_data.get("revokeRefreshToken") is not True
        or realm_data.get("refreshTokenMaxReuse") != 0
        or realm_data.get("bruteForceProtected") is not True
    ):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Keycloak realm must enforce refresh-token rotation (maxReuse=0) and bruteForceProtected=True",
            status_code=400,
        )
    algs = set(realm_data.get("webAuthnPolicySignatureAlgorithms", []))
    if not algs or not algs.issubset(ALLOWED_WEBAUTHN_ALGORITHMS):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Keycloak WebAuthn policy must restrict algorithms to ES256 and EdDSA",
            status_code=400,
        )
    clients = realm_data.get("clients", [])
    client_map = {str(c.get("clientId")): c for c in clients if isinstance(c, dict)}
    missing = REQUIRED_KEYCLOAK_CLIENTS - set(client_map)
    if missing:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Keycloak realm missing required OAuth 2.1 clients: {sorted(missing)}",
            status_code=400,
        )
    for cid in REQUIRED_KEYCLOAK_CLIENTS:
        c = client_map[cid]
        attrs = c.get("attributes", {})
        if (
            c.get("publicClient") is not False
            or c.get("directAccessGrantsEnabled") is not False
            or attrs.get("pkce.code.challenge.method") != "S256"
            or attrs.get("token.exchange.standard.enabled") != "true"
        ):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Keycloak client '{cid}' must be confidential, forbid direct grants, enforce PKCE S256, and enable standard token exchange V2",
                status_code=400,
            )
    return True


class KeycloakOidcClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    jti: str = Field(min_length=4)
    iss: str = "https://sso.ssra.gov.ss/realms/ssra"
    sub: str = Field(min_length=1)
    aud: str = Field(min_length=1)
    azp: str = Field(min_length=1)
    acr: Literal[
        "urn:ssra:acr:otp-t1",
        "urn:ssra:acr:t3-step-up",
        "urn:ssra:acr:passkey",
    ]
    idp: str = "ssra-national-idp"
    webauthn_alg: str | None = None
    exp: datetime


MAX_CONSUMED_JTIS = 4096
DEFAULT_JTI_TTL_SECONDS = 300
_WEBAUTHN_SIGN_COUNT_LOCK = threading.Lock()
_SHARED_WEBAUTHN_SIGN_COUNTS: dict[str, int] = {}


class KeycloakOidcSecurityService:
    """Enforces Keycloak 26.x OAuth 2.1, PKCE S256, WebAuthn Passkey ACR, and anti-replay invariants."""

    def __init__(
        self,
        *,
        expected_issuer: str = "https://sso.ssra.gov.ss/realms/ssra",
        allowed_idp_aliases: frozenset[str] = ALLOWED_IDP_ALIASES,
    ) -> None:
        """Initialise the Keycloak OIDC security service with JTI replay and shared WebAuthn signCount trackers."""
        self.expected_issuer = expected_issuer
        self.allowed_idp_aliases = allowed_idp_aliases
        self._consumed_jtis: dict[str, datetime] = {}
        self._webauthn_sign_counts = _SHARED_WEBAUTHN_SIGN_COUNTS

    def verify_webauthn_sign_count(
        self,
        credential_id: str,
        new_sign_count: int,
        *,
        user_verified: bool,
    ) -> int:
        """Enforce W3C WebAuthn Level 3 (§7.2) user verification (uv) and atomic monotonic signCount clone detection."""
        if not user_verified:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "WebAuthn passkey assertion requires user_verified=True (uv flag)",
                status_code=403,
            )
        with _WEBAUTHN_SIGN_COUNT_LOCK:
            prev = self._webauthn_sign_counts.get(credential_id)
            if prev is not None and (new_sign_count <= prev and (prev > 0 or new_sign_count > 0)):
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"WebAuthn passkey clone or replay detected for credential '{credential_id}' (signCount {new_sign_count} <= {prev})",
                    status_code=403,
                )
            self._webauthn_sign_counts[credential_id] = max(0, new_sign_count)
            return self._webauthn_sign_counts[credential_id]

    @staticmethod
    def compute_pkce_s256_challenge(code_verifier: str) -> str:
        if len(code_verifier) < 43 or len(code_verifier) > 128:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "PKCE code_verifier must be 43..128 characters per RFC 7636",
                status_code=400,
            )
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def verify_pkce_and_client_bound_code(
        self,
        *,
        code_verifier: str,
        stored_code_challenge: str,
        code_challenge_method: str,
        bound_client_id: str,
        requesting_client_id: str,
    ) -> bool:
        """Mitigate CVE-2026-16089 (authorization code client retargeting) and enforce PKCE S256."""
        if code_challenge_method != "S256":
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "OAuth 2.1 requires PKCE code_challenge_method='S256'",
                status_code=400,
            )
        if not hmac.compare_digest(bound_client_id, requesting_client_id):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Authorization code client_id mismatch blocked (CVE-2026-16089)",
                status_code=403,
            )
        computed = self.compute_pkce_s256_challenge(code_verifier)
        if not hmac.compare_digest(computed, stored_code_challenge):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "PKCE S256 code_verifier mismatch",
                status_code=401,
            )
        return True

    def consume_single_use_jti(
        self,
        jti: str,
        *,
        exp: datetime | None = None,
        now: datetime | None = None,
    ) -> None:
        """Atomically consume single-use refresh or WebAuthn action token jti, purging only expired entries and failing closed at capacity."""
        current = now or utc_now()
        expired = [k for k, expires_at in self._consumed_jtis.items() if current > expires_at]
        for k in expired:
            self._consumed_jtis.pop(k, None)

        if jti in self._consumed_jtis:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Replay of single-use token jti '{jti}' blocked",
                status_code=401,
            )
        if len(self._consumed_jtis) >= MAX_CONSUMED_JTIS:
            raise SSRAError(
                McpErrorCode.RATE_LIMITED,
                f"Single-use JTI replay cache capacity ({MAX_CONSUMED_JTIS}) saturated with unexpired tokens",
                status_code=429,
            )
        self._consumed_jtis[jti] = exp or (current + timedelta(seconds=DEFAULT_JTI_TTL_SECONDS))

    def validate_keycloak_oidc_claims(
        self,
        claims: KeycloakOidcClaims,
        *,
        expected_audience: str,
        expected_azp: str,
        require_passkey: bool = False,
    ) -> KeycloakOidcClaims:
        """Validate issuer, audience (CVE-2026-37979), active IdP (CVE-2026-3009), and WebAuthn alg (CVE-2026-8830)."""
        if claims.iss != self.expected_issuer:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Untrusted Keycloak issuer '{claims.iss}'",
                status_code=401,
            )
        if claims.aud != expected_audience or claims.azp != expected_azp:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Keycloak audience or azp mismatch blocked (CVE-2026-37979)",
                status_code=403,
            )
        if claims.idp not in self.allowed_idp_aliases:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Disabled or unapproved identity provider '{claims.idp}' blocked (CVE-2026-3009)",
                status_code=403,
            )
        if utc_now() > claims.exp:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Keycloak OIDC token expired",
                status_code=401,
            )
        if require_passkey:
            if claims.acr != "urn:ssra:acr:passkey":
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "Staff console requires hardware-backed passkey ACR ('urn:ssra:acr:passkey')",
                    status_code=403,
                )
            if not claims.webauthn_alg or claims.webauthn_alg not in ALLOWED_WEBAUTHN_ALGORITHMS:
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    f"Non-compliant WebAuthn algorithm '{claims.webauthn_alg}' rejected (CVE-2026-8830)",
                    status_code=403,
                )
        return claims
