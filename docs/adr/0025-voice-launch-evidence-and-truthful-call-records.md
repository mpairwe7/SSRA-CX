# ADR-025: Voice Launch Evidence and Truthful Call Records

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-24
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-018](./0018-staff-console-preview-and-trusted-session-gate.md), [ADR-024](./0024-voice-identity-step-up-and-carryover-fail-closed.md), [AUD-037 to AUD-040](../audit/findings.md#call-receptionist-audit-2026-10-24), [R2-J report](../audit/phase-R2-J-voice-truthful-records-report.md)

## Context

The master prompt allows a language on voice only after its word-error rate on SSRA test sets meets the 0.12 gate. `route_voice_turn` instead took a WER from its caller on every turn, and the benchmarks passed 0.05, so every language counted as approved. No WER has been measured on an SSRA test set (OQ-008).

The officer brief was built by keyword rules but attributed to a model. It asserted an open item that no turn supported, and its truncation could leak part of a TIN. Retention periods were hard-coded while OQ-009 is open, and the shared TTS cache stored audio of personal answers.

## Options Considered

1. **Keep the per-turn WER argument.** Any integration could approve a language by passing a number. Rejected.
2. **Load evidence from an environment variable or a runtime file.** It could change without review, and a missing file would still have to fail closed. Deferred until a signed evidence registry exists.
3. **A governed, read-only mapping in code that ships empty (chosen).** Every entry is a reviewed change. Tests and benchmarks inject labelled synthetic evidence explicitly.
4. **Brief attribution:** keep the model name (rejected: it is false), drop the field (rejected: it breaks the console contract), or set it to `None` and have the console say the brief was built by rules (chosen).
5. **Retention:** keep the hard-coded periods until SSRA Legal answers (rejected: invented values look approved), or leave every period unset until one is approved (chosen).

## Decision

1. Voice launch is decided by governed evidence, not by a runtime number. `APPROVED_VOICE_WER_EVIDENCE` maps a language to a `VoiceWerEvidence` record (WER, SSRA test set, date, utterance count). It ships empty. An entry is added only by a reviewed change that cites an SSRA-approved measurement. Without an entry, the caller goes to an officer.
2. Synthetic evidence is allowed only where it is injected explicitly and labelled synthetic: in tests, the phase-gate check, and the simulated speech scenarios of the benchmarks. Benchmark reports say that speech is simulated.
3. Staff-facing call records state only what the turns support. A rule-built brief has `model = None`, and the console says it was built by rules. Text is redacted before it is shortened. Transfer summaries list only the reasons that applied.
4. No retention period is assumed. `None` means keep nothing after the call, and storing raw audio requires an approved period.
5. The shared TTS cache stores only fixed, non-personal prompts.

## Consequences

- The voice channel cannot serve callers in any language until SSRA approves evidence for that language. This is the intended state until OQ-008 is answered.
- Adding evidence is a code change with review, which keeps an audit trail. A later move to a signed evidence registry would change only where the mapping is loaded from.
- Officers see less invented content in briefs; the open item may be the caller's own words rather than a summary.

## Reversal Cost

Medium. Accepting a runtime WER again would let any integration approve a language by passing a number, and attributing rule output to a model would mislead staff.

## Verification

Unit tests cover evidence validation, each transfer reason, the brief's attribution, latest replies, open item, word-boundary matching, missing sequence numbers, redaction before truncation, the retention defaults, and the cache allow-list. The phase-gate audit asserts that no language is approved. A probe against the R2-I code showed each defect before the fix.
