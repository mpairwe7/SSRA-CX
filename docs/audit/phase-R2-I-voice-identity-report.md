# Phase R2-I Report: Voice Identity Step-Up, Carryover Tokens, and Call Lobby Integrity

**Date:** 2026-10-24

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-034, AUD-035, and AUD-036 in `services/voice/src/ssra_voice/__init__.py`.

## Evidence boundary

No live telephony path exists. These functions are called only by tests, evaluation suites, and benchmark tools, so the defects were latent. This phase makes them fail closed before any IVR is connected. It provides no telephony, identity provider, or production readiness.

## What was wrong

| Finding | At `70a6d1a` |
|---|---|
| AUD-034 | `verify_voice_dtmf_step_up(dtmf_tin_digits="1002001234", dtmf_otp_digits="123456", requested_tier="T3")` returned `authorized=True, action="BOUND_T3"`. No OTP check, no attempt limit; the unit test asserted it |
| AUD-035 | Without `SSRA_VOICE_CARRYOVER_HMAC_KEY`, tokens were signed with a constant committed to this repository; no issue time or expiry |
| AUD-036 | A second claim replaced the first officer; claims accepted in any state; a late event after `call.ended` recreated the call; unknown events and priorities accepted; a missing wait start became `1.0` |

## Implemented controls

- `verify_voice_dtmf_step_up(…, otp_verifier=None, attempts_used=0)`. With no verifier, the result is `WARM_TRANSFER_TO_OFFICER`, with the reason citing OQ-005. A verifier that returns false gives `OTP_REJECTED`. Three attempts give `WARM_TRANSFER_TO_OFFICER`. The masked TIN is returned only after verification.
- `_carryover_signing_key()` requires 32 bytes or more and otherwise raises `UPSTREAM_UNAVAILABLE` (`503`). `issued_at` is signed, and verification rejects tokens older than 900 seconds or more than 60 seconds in the future. With the key unset, carryover stays disabled. `.env.example` was not changed, because workspace policy forbids committing `.env*` files; the key is documented in ADR-024.
- `CallLobbyManager` accepts only the events in `LOBBY_EVENT_TYPES` and the priorities in `normal`, `high`, and `urgent`. A claim needs an `officer_id` and a call that is waiting for an officer; the first claim wins. Ended calls leave a tombstone (bounded at 4,096) so late events return an ended entry instead of reviving the call. A missing `waiting_since` stays `None`.

See [ADR-024](../adr/0024-voice-identity-step-up-and-carryover-fail-closed.md).

## Validation

| Check | Result |
|---|---|
| Tightened `services/voice/tests/test_voice.py` on `70a6d1a` | Fails at the step-up assertion (`authorized` was `True` with no verifier) |
| `services/voice/tests` and `evals/suites/test_backend_hardening_and_full_coverage.py` after the fix | Pass (6 tests) |
| Ruff and Ruff format | Pass |
| basedpyright (strict), against the worktree source | 0 errors |

## Threat-model delta

- **Removed:** voice subject binding without verification, forgeable and non-expiring carryover tokens, and conflicting call ownership on the officer desk.
- **New dependency:** future IVR work must supply an `OtpVerifier` backed by the OQ-005 provider and a carryover key.

## Residual work

- R2-J: AUD-037 to AUD-040.
- R2-K: AUD-041 and AUD-042.
- R3 decision: AUD-043 (platform exposure).
