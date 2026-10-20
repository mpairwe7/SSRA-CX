# ADR-012: BFF Authentication with Keycloak OIDC, WebAuthn Passkeys, and Server-Side Sessions

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA SecOps
- **Reversal Cost:** Medium
- **Linked Open Questions:** `OQ-005`
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 8.2, 9.4, 12.1, 12.3, Appendix A

---

## 1. Problem Statement

How do we authenticate both taxpayers (progressive OTP + TIN proofing) and SSRA staff (SSO + WebAuthn passkeys) across `apps/web` and `apps/console` while ensuring OAuth 2.1 access and refresh tokens never reach browser JavaScript?

## 2. Context

Storing JWTs in `localStorage` or JS-accessible cookies exposes taxpayers and staff to token theft if any client-side script vulnerability occurs. Both OWASP ASVS 5.0 (Level 2 for `apps/web`, Level 3 for `apps/console`) and Section 9.4 mandate the Backend-for-Frontend (BFF) pattern: server-side sessions in Valkey/PostgreSQL backed by `httpOnly`, `Secure`, `SameSite=Lax` cookies, with Keycloak serving as the central OAuth 2.1 / OIDC identity provider and WebAuthn passkey authority.

In September 2025, Auth.js joined Better Auth, leaving two viable standards-based options for the Next.js 16 BFF: `openid-client` (`6.8.8`) directly or `better-auth` (`1.7.7`) with its generic OIDC plugin.

## 3. Options Considered

1. **Client-Side OIDC SPA Flow (Tokens in Browser Memory/Storage):** Violates Section 9.4 (*"tokens never reach browser JavaScript"*) and complicates RFC 8693 token exchange. Rejected.
2. **Direct `openid-client` (`6.8.8`) in Next.js 16 Route Handlers + Valkey Server-Side Session Store (Selected as Core BFF Primitive, with `better-auth` `1.7.7` compatible wrapper):** Gives explicit, minimal-surface control over PKCE (`S256`), Keycloak WebAuthn ACR (`acr_values`), step-up authentication (`max_age=0` for `T3`), and Valkey session storage without hidden magic.

## 4. Decision

We adopt the **Next.js 16 BFF Session Pattern** using `openid-client@6.8.8` (with `better-auth@1.7.7` session conventions) backed by **Keycloak** and **Valkey**:

1. **Zero Tokens in Browser JS:**
   - The browser receives only an opaque, cryptographically signed session ID in a `__Host-ssra_session` cookie (`httpOnly`, `Secure`, `SameSite=Lax`, `Path=/`).
   - OAuth 2.1 access tokens, refresh tokens, and verified `subject_ref` claims live exclusively in Valkey (encrypted at rest and scoped with short TTLs: 15 min idle for `apps/console`, 30 min idle for authenticated `apps/web`).
2. **Staff Console (`apps/console`) — ASVS L3 & Passkeys:**
   - Enforces Keycloak 26.4.11 OIDC login with mandatory WebAuthn Level 3 passkey authentication (`phr` / FIDO2 resident keys, `ES256`/`EdDSA`, `user_verified=True` `uv` flag, and monotonic `signCount` clone detection in `KeycloakOidcSecurityService.verify_webauthn_sign_count`), `acr.loa.map` step-up levels (`urn:ssra:acr:otp-t1` -> 1, `urn:ssra:acr:t3-step-up` -> 3, `urn:ssra:acr:passkey` -> 3), and RBAC role claims (`agent`, `supervisor`, `qa`, `legal_approver`, `secops`, `admin`, `auditor`).
   - Deploys via a multi-stage Quarkus pre-built image (`infra/keycloak/Dockerfile`: `kc.sh build --db=postgres --health-enabled=true --metrics-enabled=true --features=passkeys,token-exchange-standard:v2` + `start --optimized --import-realm` as non-root `USER 10001:10001`) with dedicated management health/metrics probes on port `9000` (`/health/ready`), `KC_PROXY_HEADERS=xforwarded`, and Standard Token Exchange V2 (`token.exchange.standard.enabled=true`) + RFC 9449 DPoP `cnf_jkt` sender-constrained thumbprint binding across `ssra-web-bff`, `ssra-staff-console`, `ssra-agentgateway`, and all 11 `mcp-*` resource clients (`infra/keycloak/ssra-realm.json`).
3. **Taxpayer Web (`apps/web`) — Progressive Identity Proofing:**
   - Starts anonymous (`T0`).
   - Elevates to `T1`/`T2` via deterministic OTP + TIN verification (`identity_link` service + Keycloak custom authenticator), binding an opaque `subject_ref` to the BFF session.
   - Elevates to `T3` via fresh step-up OTP (`step_up_verified_at` required and within `MAX_STEP_UP_AGE_SECONDS = 300`). Single-use token `jti` values are tracked with a `300s` TTL and `MAX_CONSUMED_JTIS = 4096` capacity, purging only expired entries and failing closed (`429 RATE_LIMITED`) if saturated with unexpired tokens.
4. **CSRF & Bot Defence:**
   - Constant-time double-submit / `Origin` + custom header CSRF validation (`timingSafeTokenMatch`) on all state-changing BFF routes, plus self-hosted **ALTCHA** proof-of-work verification (`createAltchaChallenge`, `verifyAltchaSolution`, `consumeAltchaSolution`) with `CVE-2025-68113` (`GHSA-6gvq-jcmp-8959`) salt-delimiter binding, challenge expiration (`expiresAt`), and single-use replay rejection.

## 5. Consequences

- **Positive:** Eliminates XSS token exfiltration, enables instant server-side session revocation in Valkey, and cleanly feeds `agentgateway` RFC 8693 token exchange.
- **Negative / Trade-offs:** Every BFF request performs a sub-millisecond Valkey session lookup.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. Session handling is isolated inside `apps/web/src/lib/auth/` and `apps/console/src/lib/auth/`.
