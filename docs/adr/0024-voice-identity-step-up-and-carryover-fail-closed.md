# ADR-024: Voice Identity Step-Up and Carryover Tokens Fail Closed

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-24
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** High
- **Related:** [ADR-008](./0008-risk-tiered-autonomy-subject-binding-and-opa.md), [ADR-012](./0012-bff-authentication-keycloak-passkeys-and-sessions.md), [ADR-019](./0019-fail-closed-reference-runtime-mode.md), [AUD-034](../audit/findings.md#aud-034--s1-latent--identity-binding--voice-dtmf-step-up-authorized-any-well-formed-tin-and-otp), [AUD-035](../audit/findings.md#aud-035--s1-latent--token-integrity--call-to-web-carryover-tokens-were-signed-with-a-public-constant-and-never-expired), [R2-I report](../audit/phase-R2-I-voice-identity-report.md)

## Context

`ssra_voice.verify_voice_dtmf_step_up` returned `authorized=True` for any well-formed TIN and OTP, so a voice call could bind a subject without verifying anything. Call-to-web carryover tokens fell back to a signing key committed to this repository and had no expiry. Neither path is connected to a live IVR yet, but both would become live as soon as one is.

Invariant 8 requires identity verification outside the model, with strict subject binding. Invariant 11 requires missing configuration to fail closed. OQ-005 (identity proofing) has not chosen an OTP provider.

## Decision

1. Voice step-up accepts an injected `OtpVerifier(tin, otp) -> bool`. The verifier is the approved identity provider's check, which must compare in constant time and enforce the provider's expiry and single use. Without a verifier, the call goes to an officer. A rejected code returns `OTP_REJECTED`, and three attempts send the call to an officer. Spoken OTPs, T4 requests, and recent SIM swaps keep their existing refusals.
2. Carryover tokens require `SSRA_VOICE_CARRYOVER_HMAC_KEY` of at least 32 random bytes from the deployment's secret store, otherwise the call fails with `503`. With the key unset, carryover is disabled. `issued_at` is part of the signed message, and tokens are valid for 15 minutes with 60 seconds of clock skew.
3. No default key and no default verifier ship in code. Tests inject synthetic ones.

## Consequences

- Voice cannot bind a taxpayer until SSRA approves an identity provider (OQ-005) and an engineer wires its verifier. Until then, calls that need identity go to officers.
- Deployments must provision a carryover key; there is no silent fallback.
- An adapter that bypasses these functions would bypass the controls. Any future IVR integration must call them and be reviewed against this ADR.

## Reversal Cost

High. Restoring format-only step-up or a default key would re-open cross-taxpayer identity binding and token forgery as soon as voice goes live.

## Verification

`services/voice/tests/test_voice.py` covers no verifier, wrong code, exhausted attempts, a verified code, a short key, wrong owner, expiry, and each tampered field. The tightened step-up assertion fails on `70a6d1a`.
