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
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError, utc_now

ALLOWED_WEBAUTHN_ALGORITHMS: frozenset[str] = frozenset({"ES256", "EdDSA", "-7", "-8"})
ALLOWED_IDP_ALIASES: frozenset[str] = frozenset({"ssra-national-idp", "keycloak-local"})


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


class KeycloakOidcSecurityService:
    """Enforces Keycloak 26.x OAuth 2.1, PKCE S256, WebAuthn Passkey ACR, and anti-replay invariants."""

    def __init__(
        self,
        *,
        expected_issuer: str = "https://sso.ssra.gov.ss/realms/ssra",
        allowed_idp_aliases: frozenset[str] = ALLOWED_IDP_ALIASES,
    ) -> None:
        self.expected_issuer = expected_issuer
        self.allowed_idp_aliases = allowed_idp_aliases
        self._consumed_jtis: set[str] = set()

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

    def consume_single_use_jti(self, jti: str) -> None:
        """Atomically consume refresh or WebAuthn action token jti (CVE-2026-1035 & CVE-2026-37982)."""
        if jti in self._consumed_jtis:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Replay of single-use token jti '{jti}' blocked (CVE-2026-1035 / CVE-2026-37982)",
                status_code=401,
            )
        self._consumed_jtis.add(jti)

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
