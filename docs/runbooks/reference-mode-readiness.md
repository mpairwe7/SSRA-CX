# Reference Mode and Production Readiness

## Purpose

Keep process-local stores, synthetic fixtures, and incomplete providers from being mistaken for operational SSRA services.

## Runtime mode behavior

- `SSRA_RUNTIME_MODE` defaults to `production`. Missing or unrecognized values fail closed.
- The general and GPU local Compose profiles explicitly set `SSRA_RUNTIME_MODE=reference`. Reference responses include `X-SSRA-Runtime-Mode: reference`.
- The production/DR Compose overlay explicitly sets `SSRA_RUNTIME_MODE=production`.
- In production mode, Core API and agent-runtime requests, including `/healthz`, return RFC 9457 `503 UPSTREAM_UNAVAILABLE` until the durable-state and approved-provider work is complete.
- `services/api/tests/test_route_matrix.py` derives safe synthetic requests for every documented Core API operation. It verifies that every operation returns RFC 9457 `503` outside explicit reference mode and uses an independent, per-operation policy to check the `reference`-mode `200`, `403`, or `503` outcome. OpenAPI declarations are checked for alignment but do not provide the expected runtime result. This is source/reference evidence only.
- Identity verification, document scanning/analysis, appointment inventory, and analytics endpoints return 503 in every mode until their specific providers are approved and configured.
- The attachment inspection view reports analysis unavailable; it must not display scan/OCR results, guessed portal links or steps, identity verification, or statutory calculations without approved provenance.
- The staff console and Core API staff/admin/knowledge-release routes return 403 for staff data/actions until OQ-014 is closed. Caller-supplied IDs and passkey booleans do not authorize actions.

## Responding to 503 readiness failures

1. Check `SSRA_RUNTIME_MODE` without printing the environment or any credential values. Production must remain `production`.
2. Use the response `code` and the relevant OQ in `docs/open-questions.md` to identify the missing approval or implementation.
3. Keep the endpoint unavailable until the provider, persistence, authorization, and required verification are implemented and reviewed.
4. Do not change a production deployment to `reference` to restore service. Reference mode is for local fixtures and tests only.
5. Use the independently approved SSRA operational process for taxpayer or staff service while the application is unavailable.

## Current blockers

- OQ-005: identity, OTP, and SIM-swap providers plus durable identity binding.
- OQ-013 and OQ-014: analytics provenance and verified staff sessions.
- OQ-015: durable API state, RLS, checkpoint recovery, and transactional event delivery.
- OQ-016: authoritative appointment inventory and reservation provider.
- OQ-017: malware scanning, OCR provenance, and approved document guidance.

No production readiness claim should be made from a successful reference-mode test or a healthy local Compose container.
