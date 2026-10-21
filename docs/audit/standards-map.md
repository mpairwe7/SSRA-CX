# R0 Standards Map

**Verification date:** 2026-10-22

**Use of this map:** It is a traceability aid, not a certification or claim of conformance. OWASP MCP references remain advisory because the project is evolving.

## Primary sources verified

| Reference | R0 use | Primary source |
|---|---|---|
| OWASP ASVS 5.0.0 | Public/API Level 2 and staff/gateway Level 3 control mapping. Requirement references use the versioned identifier form. | [ASVS 5.0.0](https://github.com/OWASP/ASVS) |
| OWASP Agentic Top 10 2026 | Agent behavior, identity, memory, tool, and cascade risks. | [OWASP Agentic Top 10](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) |
| OWASP MCP Top 10 | Advisory map for the MCP boundary. The project labels current entries MCP01:2025 through MCP10:2025 and calls itself living. | [OWASP MCP Top 10](https://owasp.org/projects/mcp-top-10?tab=top10) |
| NSA MCP guidance | Request binding, replay protection, authorization, and treating tool output as untrusted. | [NSA security design considerations](https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/4496698/nsa-releases-security-design-considerations-for-ai-driven-automation-leveraging/) |
| SLSA v1.2 | Build provenance and hardened-build target. | [SLSA Build Track](https://slsa.dev/spec/v1.2/build-track-basics) |
| NIST SSDF v1.1 | Secure development policy, toolchain, testing, and vulnerability-response mapping. | [NIST SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final) |
| CycloneDX 1.7 | Per-image software and ML-BOM evidence target. | [ECMA-424 2nd edition](https://ecma-international.org/publications-and-standards/standards/ecma-424/) |
| OpenSSF Model Signing | Model artifact signing and verification expectation. | [OpenSSF Model Signing](https://openssf.org/projects/model-signing/) |
| WCAG 2.2 | Rendered public and staff UI accessibility validation. | [WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| Next.js security update | Validated advisory target for a served Next runtime. R0 found no served Next package. | [Next.js security update, 14 October 2026](https://nextjs.org/blog/nextjs-security-update-october-14-2026) |

## Finding crosswalk

| Finding | ASVS / WCAG | Agentic / MCP / NSA | Supply chain / SSDF |
|---|---|---|---|
| AUD-001 | ASVS v5.0.0-16.5.2 | ASI06, ASI08 | SSDF PW.8 |
| AUD-002 | ASVS v5.0.0-15.2.5 and 16.5.2 | ASI02, ASI03, ASI08; MCP07/MCP08 advisory; NSA request binding | SSDF PW.8 |
| AUD-003 | ASVS v5.0.0-16.5.2 | ASI08 | SSDF PW.8 |
| AUD-004 | ASVS v5.0.0-4.1.3 and 15.3.3 | ASI03, ASI06; NSA authorization | SSDF PW.8 |
| AUD-005 | ASVS v5.0.0-15.2.5 and 16.5.2 | ASI08 | SSDF PO.3 |
| AUD-006 | ASVS v5.0.0-15.1.2 and 15.2.1 | — | SLSA Build L3; SSDF PO.3, PW.7, RV.1 |
| AUD-007 | ASVS v5.0.0-15.1.2, 15.2.1, and 15.2.4 | ASI04 | SLSA Build L3; CycloneDX 1.7; OMS; SSDF PO.3 and PS.3 |
| AUD-008 | ASVS v5.0.0-15.1.1 and 15.2.1 | — | SSDF PO.3 and PW.7 |
| AUD-009 | ASVS v5.0.0-4.1.3 | ASI03 and ASI05 | SSDF PW.8; WCAG 2.2 AA SC 1.4.10, 2.4.3, 2.4.7, 2.5.8 |
| AUD-010 | ASVS v5.0.0-15.2.5 | ASI02, ASI03, ASI08; MCP03, MCP06–MCP08 advisory; NSA | SSDF PW.8 |
| AUD-011 | SSRA grounded-or-silent invariant | ASI05, ASI09 | SSDF PW.8 |
| AUD-012 | ASVS v5.0.0-16.1.1, 16.2.1, 16.5.2 | ASI08 | SSDF PW.8 |
| AUD-013 | — | — | SSDF PO.3 and PW.8 |

## Control observations that R0 verified and R1-A implements

- R1-A sets an empty workflow permission default, declares minimal job scopes, requires 40-character action SHAs, prohibits `pull_request_target`, and requires non-persisted checkout credentials.
- R1-A adds a full-reachable-history Gitleaks CI job, pinned zizmor workflow audit, and SecOps ownership for workflow files. Local CI-policy regression tests reject a mutable action tag and omitted workflow-default permissions.
- R1-A applies pnpm's age, provenance, exotic-subdependency, and build-script policy together with uv's rolling one-week cooldown. The bounded uv security-fix record does not select artifact trust roots or create a broad exclusion.
- OQ-018 remains open: no observation here asserts production image/model signing, registry trust, or pre-start verification.
- The public BFF constructs a new safe turn body and suppresses client subject references before forwarding to the runtime.
- The reference runtime defaults to production mode and returns unavailable for unset or unknown mode values.
- Numeric-provenance, tool description hash, confirmation-token, PII-redaction, and hash-chain tests pass in the reference suite.
- Full-history Gitleaks passed manually at R0 and is now represented by a CI job; pull-request CI evidence is required before AUD-006 is closed.
