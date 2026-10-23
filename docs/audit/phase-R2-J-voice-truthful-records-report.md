# Phase R2-J Report: Voice Launch Evidence and Truthful Call Records

**Date:** 2026-10-24

**Status:** Source remediation implemented. Gate R2 has not been evaluated or approved.
**Scope:** AUD-037 to AUD-040 in `services/voice`, the two benchmark generators, `tools/verify_phase_gates.py`, and the staff console's brief card.

## Evidence boundary

No live telephony path exists, and the SSRA GPU stack was not running during this phase. All evidence comes from unit tests, the evaluation suite, offline checks, and a probe of the R2-I code. The committed benchmark reports were not regenerated.

## Before and after

A probe ran the same calls against the R2-I code and the R2-J code:

| Behaviour | R2-I | R2-J |
|---|---|---|
| Dinka turn with no measured WER (caller passed 0.05) | `STREAM_ASR` | `WARM_TRANSFER_TO_OFFICER`: "no approved word-error-rate evidence for din (OQ-008)" |
| Brief attribution for a rule-built brief | `ssra-sovereign/sunflower-qwen3.5-9b` | `None`; console shows "Built by keyword rules, not by a model" |
| Mood for "Show me my filing options" | `confused` (matched "how" inside "Show") | `calm` |
| Open item | "Resolve caller asked for an officer and confirm next filing/payment step" | "Latest caller request: Show me my filing options" |
| Assistant reply with a TIN across the 140-character cut | First five digits leaked (`10020`) | Redacted before truncation |
| Default transcript retention | 90 days | `None` (pending OQ-009) |
| Personal answer synthesized twice | Served from the shared cache | Synthesized each time; not stored |

## Implemented controls

- `VoiceWerEvidence` and the empty, read-only `APPROVED_VOICE_WER_EVIDENCE`. `is_voice_language_approved(locale, evidence)` and `route_voice_turn(…, wer_evidence=…)` treat missing, mismatched, non-finite, or negative evidence as none. The transfer summary lists only the reasons that applied: keypad 0, missing or failing evidence, or repeated low-confidence turns.
- The officer brief keeps `model = None`, lists the latest three assistant replies, uses the latest caller request as the open item, matches mood keywords as whole words, links evidence only to valid sequence numbers, redacts before truncating, and uses an opener that does not quote the caller.
- `VoiceRetentionPolicy` has no default periods, and refuses to store raw audio without an approved period. Audit entries record `retention_status`.
- `TtsPhraseCache` caches only `fixed_voice_prompts()` or an explicit allow-list, and its synthesizer is typed.
- The benchmark generators label speech scenarios as simulated (docstring, Markdown report line, and `speech_scenarios_simulated` in the JSON) and use labelled synthetic WER evidence. They no longer list SunflowerASR as part of the stack.
- `tools/verify_phase_gates.py` asserts that no language is approved and lists OQ-008 among the Gate 4 blockers. No gate advanced.

See [ADR-025](../adr/0025-voice-launch-evidence-and-truthful-call-records.md).

## Validation

| Check | Result |
|---|---|
| Probe against the R2-I code | Each defect above reproduced |
| `services/voice/tests` (2 tests) and `evals/suites/test_backend_hardening_and_full_coverage.py` (5 tests) | Pass |
| Offline routing of the benchmarks' simulated speech scenarios | 300 of 300 and 6,000 of 6,000 as designed |
| `tools/verify_phase_gates.py` | Pass; no gate advanced |
| Console: Biome, `tsc --noEmit`, Vitest | Pass |
| Ruff, Ruff format, strict basedpyright (voice package, gate tool, benchmarks) | Pass, 0 errors |

## Threat-model delta

- **Removed:** voice launch by a caller-supplied number, model attribution of rule output, partial TIN disclosure in briefs, invented retention, and personal answers in a shared audio cache.
- **Unchanged:** voice still has no live path. OQ-008 (WER evidence) and OQ-009 (retention) decide when the controls can admit traffic.

## Residual work

- R2-K: AUD-041 and AUD-042, and the UI and ASR robustness gaps found while preparing it.
- R3 decision: AUD-043.
- Regenerate the benchmark reports on the GPU profile so the committed reports carry the simulation note.
