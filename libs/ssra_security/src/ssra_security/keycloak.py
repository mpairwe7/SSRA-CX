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
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field
from ssra_core import McpErrorCode, SSRAError, new_id, utc_now

ALLOWED_WEBAUTHN_ALGORITHMS: frozenset[str] = frozenset({"ES256", "EdDSA", "-7", "-8"})
ALLOWED_JWT_SIGNING_ALGORITHMS: frozenset[str] = frozenset({"ES256", "RS256", "PS256", "EdDSA"})
ALLOWED_IDP_ALIASES: frozenset[str] = frozenset({"ssra-national-idp", "keycloak-local"})
ALLOWED_TOKEN_EXCHANGE_ACTORS: frozenset[str] = frozenset(
    {"ssra-agent-runtime", "ssra-agentgateway", "ssra-web-bff", "ssra-staff-console"}
)
REQUIRED_KEYCLOAK_CLIENTS: frozenset[str] = frozenset(
    {
        "ssra-web-bff",
        "ssra-staff-console",
        "ssra-api",
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


def _is_valid_bff_uri(uri: Any, *, expected_paths: tuple[str, ...]) -> bool:
    if not isinstance(uri, str) or "*" in uri:
        return False
    parsed = urlparse(uri)
    return (
        parsed.username is None
        and parsed.password is None
        and parsed.path in expected_paths
        and not parsed.query
        and not parsed.fragment
        and bool(parsed.hostname)
        and (
            parsed.scheme == "https"
            or (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
        )
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
            c.get("enabled") is not True
            or c.get("publicClient") is not False
            or c.get("implicitFlowEnabled") is not False
            or c.get("directAccessGrantsEnabled") is not False
            or attrs.get("pkce.code.challenge.method") != "S256"
            or attrs.get("token.exchange.standard.enabled") != "true"
        ):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Keycloak client '{cid}' must be enabled, confidential, forbid implicit/direct grants (CVE-2026-7571), enforce PKCE S256, and enable standard token exchange V2",
                status_code=400,
            )
    for dpop_cid in ("ssra-web-bff", "ssra-staff-console", "ssra-api", "ssra-agentgateway"):
        dpop_client = client_map[dpop_cid]
        dpop_attrs = dpop_client.get("attributes", {})
        is_interactive_bff = dpop_cid in ("ssra-web-bff", "ssra-staff-console")
        redirect_uris = dpop_client.get("redirectUris", [])
        web_origins = dpop_client.get("webOrigins", [])
        redirect_ok = not is_interactive_bff or (
            isinstance(redirect_uris, list)
            and bool(redirect_uris)
            and all(
                _is_valid_bff_uri(u, expected_paths=("/signin/callback",)) for u in redirect_uris
            )
            and isinstance(web_origins, list)
            and bool(web_origins)
            and all(_is_valid_bff_uri(o, expected_paths=("", "/")) for o in web_origins)
            and bool(str(dpop_attrs.get("post.logout.redirect.uris") or "").strip())
        )
        bcl_url_ok = not is_interactive_bff or (
            dpop_client.get("frontchannelLogout") is False
            and bool(str(dpop_attrs.get("backchannel.logout.url") or "").strip())
            and redirect_ok
        )
        dpop_ok = (
            dpop_attrs.get("oauth2.dpop.bound.access.tokens") == "true"
            and dpop_attrs.get("backchannel.logout.session.required") == "true"
            and dpop_attrs.get("backchannel.logout.revoke.offline.tokens") == "true"
            and bcl_url_ok
        )
        if not dpop_ok:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                f"Keycloak client '{dpop_cid}' must enforce RFC 9449 DPoP-bound access tokens and OIDC backchannel logout session/offline revocation (CVE-2026-107623)",
                status_code=400,
            )
    idps = realm_data.get("identityProviders", [])
    idp_ok = bool(idps) and all(
        isinstance(idp, dict)
        and idp.get("trustEmail") is False
        and isinstance(idp.get("config"), dict)
        and idp["config"].get("validateSignature") == "true"
        for idp in idps
    )
    if not idp_ok:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Keycloak identityProviders must enforce trustEmail=False (CVE-2026-14781) and validateSignature='true' (CVE-2026-18569)",
            status_code=400,
        )
    scope_mappings = realm_data.get("scopeMappings", [])
    console_scope_roles: set[str] = set()
    if isinstance(scope_mappings, list):
        for sm in scope_mappings:
            if (
                isinstance(sm, dict)
                and (sm.get("client") or sm.get("clientId")) == "ssra-staff-console"
            ):
                roles_list = sm.get("roles", [])
                if isinstance(roles_list, list):
                    console_scope_roles.update(str(r) for r in roles_list)
    if not {"ssra_staff", "ssra_admin", "ssra_auditor"}.issubset(console_scope_roles):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Keycloak realm scopeMappings for 'ssra-staff-console' must allow ssra_staff, ssra_admin, and ssra_auditor roles",
            status_code=400,
        )
    events_ok = (
        realm_data.get("eventsEnabled") is True and realm_data.get("adminEventsEnabled") is True
    )
    if not events_ok:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Keycloak realm must enable security events and admin audit events (ASVS 5.0 V16)",
            status_code=400,
        )
    return True


class DpopProofClaims(BaseModel):
    """RFC 9449 §4.2 Demonstrating Proof-of-Possession (DPoP) JWT proof claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jti: str = Field(min_length=4)
    htm: str = Field(min_length=3)
    htu: str = Field(min_length=8)
    iat: datetime
    ath: str | None = None
    cnf_jkt: str = Field(min_length=8)


class BackchannelLogoutClaims(BaseModel):
    """OIDC Back-Channel Logout 1.0 (§2.4 & §2.6) `logout+jwt` token claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jti: str = Field(min_length=4)
    iss: str = Field(min_length=1)
    aud: str = Field(min_length=1)
    sub: str | None = None
    sid: str | None = None
    events: dict[str, dict[str, Any]]
    iat: datetime
    exp: datetime
    nonce: str | None = None
    jwt_alg: str = "ES256"


class ParRequestRecord(BaseModel):
    """RFC 9126 Pushed Authorization Request (`request_uri`) single-use realm-bound record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_uri: str
    realm: str
    client_id: str
    code_challenge_s256: str
    expires_at: datetime


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
        enabled_client_ids: frozenset[str] = REQUIRED_KEYCLOAK_CLIENTS,
    ) -> None:
        """Initialise the Keycloak OIDC security service with JTI replay, enabled clients, and WebAuthn signCount trackers."""
        self.expected_issuer = expected_issuer
        self.allowed_idp_aliases = allowed_idp_aliases
        self.enabled_client_ids = enabled_client_ids
        self._consumed_jtis: dict[str, datetime] = {}
        self._par_requests: dict[str, ParRequestRecord] = {}
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
        if claims.aud not in self.enabled_client_ids or claims.azp not in self.enabled_client_ids:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Token exchange or authentication targeting a disabled/unregistered client blocked (CVE-2026-93999)",
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

    def verify_dpop_proof(
        self,
        proof: DpopProofClaims,
        *,
        expected_htm: str,
        expected_htu: str,
        expected_cnf_jkt: str,
        bound_access_token: str | None = None,
        max_clock_skew_seconds: int = 120,
        now: datetime | None = None,
    ) -> DpopProofClaims:
        """Verify an RFC 9449 §4.2 DPoP proof (`htm`, `htu`, `iat` freshness, single-use `jti`, `ath`, and `cnf_jkt`)."""
        current = now or utc_now()
        clean_htu = expected_htu.split("?", 1)[0].split("#", 1)[0]
        proof_htu = proof.htu.split("?", 1)[0].split("#", 1)[0]
        if proof.htm.upper() != expected_htm.upper() or proof_htu != clean_htu:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "RFC 9449 DPoP proof htm or htu mismatch",
                status_code=401,
            )
        age_seconds = abs((current - proof.iat).total_seconds())
        if age_seconds > max_clock_skew_seconds:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"RFC 9449 DPoP proof iat outside {max_clock_skew_seconds}s freshness window",
                status_code=401,
            )
        if not hmac.compare_digest(proof.cnf_jkt, expected_cnf_jkt):
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "RFC 9449 DPoP proof JWK thumbprint (cnf_jkt) mismatch",
                status_code=403,
            )
        if bound_access_token is not None:
            expected_ath = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(bound_access_token.encode("ascii")).digest()
                )
                .rstrip(b"=")
                .decode("ascii")
            )
            if not proof.ath or not hmac.compare_digest(proof.ath, expected_ath):
                raise SSRAError(
                    McpErrorCode.NOT_AUTHORIZED,
                    "RFC 9449 DPoP proof access-token hash (ath) mismatch",
                    status_code=401,
                )
        self.consume_single_use_jti(
            proof.jti,
            exp=max(current, proof.iat) + timedelta(seconds=max_clock_skew_seconds),
            now=current,
        )
        return proof

    def validate_backchannel_logout_token(
        self,
        logout_claims: BackchannelLogoutClaims,
        *,
        expected_audience: str,
        max_clock_skew_seconds: int = 120,
        now: datetime | None = None,
    ) -> BackchannelLogoutClaims:
        """Validate an OIDC Back-Channel Logout 1.0 (§2.4 & §2.6) token and consume its `jti` until `exp`."""
        current = now or utc_now()
        iat_fresh = abs((current - logout_claims.iat).total_seconds()) <= max_clock_skew_seconds
        valid_bcl = (
            logout_claims.jwt_alg in ALLOWED_JWT_SIGNING_ALGORITHMS
            and logout_claims.iss == self.expected_issuer
            and logout_claims.aud == expected_audience
            and logout_claims.aud in self.enabled_client_ids
            and logout_claims.nonce is None
            and current <= logout_claims.exp
            and iat_fresh
            and "http://schemas.openid.net/event/backchannel-logout" in logout_claims.events
            and bool(logout_claims.sid or logout_claims.sub)
        )
        if not valid_bcl:
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Invalid OIDC Back-Channel Logout token claims (OIDC Back-Channel Logout 1.0 §2.4 / CVE-2026-18569)",
                status_code=400,
            )
        self.consume_single_use_jti(logout_claims.jti, exp=logout_claims.exp, now=current)
        return logout_claims

    def issue_and_bind_par_request_uri(
        self,
        *,
        realm: str,
        client_id: str,
        code_challenge_s256: str,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> ParRequestRecord:
        """Mint an RFC 9126 PAR `request_uri` bound to `(realm, client_id, code_challenge_s256)` (`#50135`)."""
        current = now or utc_now()
        for k in [k for k, r in self._par_requests.items() if current > r.expires_at]:
            self._par_requests.pop(k, None)
        if len(self._par_requests) >= MAX_CONSUMED_JTIS:
            raise SSRAError(
                McpErrorCode.RATE_LIMITED,
                f"PAR request_uri cache capacity ({MAX_CONSUMED_JTIS}) saturated with unexpired requests",
                status_code=429,
            )
        req_uri = f"urn:ietf:params:oauth:request_uri:{new_id('par')}"
        rec = ParRequestRecord(
            request_uri=req_uri,
            realm=realm,
            client_id=client_id,
            code_challenge_s256=code_challenge_s256,
            expires_at=current + timedelta(seconds=ttl_seconds),
        )
        self._par_requests[req_uri] = rec
        return rec

    def consume_par_request_uri(
        self,
        request_uri: str,
        *,
        realm: str,
        client_id: str,
        prompt: str | None = None,
        now: datetime | None = None,
    ) -> ParRequestRecord:
        """Atomically consume a single-use PAR `request_uri`, blocking cross-realm/client reuse (`#50135`) and `prompt=none` bypass (`CVE-2026-96446`)."""
        current = now or utc_now()
        rec = self._par_requests.pop(request_uri, None)
        is_valid = (
            rec is not None
            and rec.realm == realm
            and rec.client_id == client_id
            and current <= rec.expires_at
            and (prompt or "").strip().lower() != "none"
        )
        if not is_valid or rec is None:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "RFC 9126 PAR request_uri invalid, expired, replayed, or prompt=none bypass blocked (CVE-2026-96446)",
                status_code=400,
            )
        return rec

    def validate_token_exchange_delegation(
        self,
        *,
        subject_sub: str,
        actor_sub: str,
        audience: str,
        cnf_jkt: str | None,
    ) -> dict[str, str]:
        """Validate RFC 8693 token-exchange delegation (`#52691`), active audience (`CVE-2026-93999`), and sender constraint (`CVE-2026-97846`)."""
        delegation_ok = (
            bool(subject_sub.strip())
            and actor_sub in ALLOWED_TOKEN_EXCHANGE_ACTORS
            and audience in self.enabled_client_ids
            and bool(cnf_jkt and len(cnf_jkt.strip()) >= 8)
        )
        if not delegation_ok or cnf_jkt is None:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                "Token exchange delegation rejected: requires allowlisted actor (#52691), enabled audience (CVE-2026-93999), and DPoP cnf_jkt binding (CVE-2026-97846)",
                status_code=403,
            )
        return {
            "sub": subject_sub.strip(),
            "act": actor_sub,
            "aud": audience,
            "cnf_jkt": cnf_jkt.strip(),
        }
