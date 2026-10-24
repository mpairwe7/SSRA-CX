# ADR-028: Multi-Turn Conversation Continuity, Anaphoric Slot Carry-Over, and Toolathlon Multi-Step Tool Orchestration Hardening

- **Status:** Accepted as a repository safety baseline; not production authorization
- **Date:** 2026-10-24
- **Deciders:** SSRA Assist engineering maintainers
- **Reversal Cost:** Medium
- **Related:** [ADR-008](./0008-risk-tiered-autonomy-subject-binding-and-opa.md), [ADR-009](./0009-deterministic-tax-facts-registry-and-numeric-provenance.md), [ADR-017](./0017-agentic-cx-eq-4tier-memory-and-goal-continuation.md), [ADR-027](./0027-voice-multiturn-continuity-echo-guard-and-barge-in.md)

## Context

A QA and security audit of multi-turn conversation handling and multi-step MCP tool orchestration (`Toolathlon`-class trajectories) in `services/agent-runtime` identified four concrete gaps:

1. **Multi-Turn Slot & Context Amnesia (`_execute_graph_fast` & `understand_node`):**
   - `SSRAConversationRuntime._checkpoint_state_by_thread` previously persisted only `("affective_state", "language_candidate", "language_state")` across turns and discarded `prior_intent` and `prior_slots`.
   - When a taxpayer followed up an initial calculation or tariff query with an elliptical or anaphoric turn (for example, Turn 1: `"Calculate PAYE on 300,000 SSP"` -> Turn 2: `"What if it is 800,000 SSP?"`; Turn 1: `"What is the customs tariff for HS 8703.23?"` -> Turn 2: `"Estimate the duty for CIF $12,000"`; or Turn 1: `"Calculate withholding tax on 2,000,000 SSP for rent"` -> Turn 2: `"What if it is for technical fees?"`), `classify_intent_deterministic` fell back to generic `KNOWLEDGE_QA` or lost the prior `hs_code` / `amount_ssp` slot.
2. **Stalled Guided Journey Step Progression (`workflow_stack`):**
   - Starting a guided journey (`GUIDED_TIN_REGISTRATION`, `GUIDED_FILING_AND_PAYMENT`, `GUIDED_TCC`) pushed `ActiveWorkflowCursor(current_step=1)` onto `_workflow_stack_by_thread`, but follow-up turns saying `"next step"`, `"continue"`, or `"step 2"` reset `current_step=1` instead of advancing through steps `1 -> 2 -> 3`. Furthermore, asking a mid-journey side question (such as a PAYE calculation) gave no resumption cue that the guided journey was paused.
3. **Single-Tool Short-Circuiting in Compound Turns (`Toolathlon` ICLR 2026 / Toolathlon-Verified June 2026):**
   - In `execute_knowledge_qa_subgraph` and `compose_node`, early `return` statements after the first calculator or customs tool silently dropped secondary tools in compound turns (e.g., requesting both PAYE and Withholding Tax estimates in one turn, or combining `get_balance` with `get_filing_status` and `get_declaration_status`).
4. **Tool-Layer Repetition Loops, Quiet Failures, and Overlong Outputs (`arXiv:2610.10062`, Oct 2026 & Toolathlon Section 5.2):**
   - As shown in *Loud Failures, Quiet Failures: Fault Detection and Recovery in Tool-Using Language Model Agents* (`arXiv:2610.10062`), tool-using agents fail to detect `41.2%` of silent/plausible wrong tool outputs ("quiet failures") and repeat identical tool calls `3+` times in up to `22.2%` of fault trajectories.
   - `GovernedMcpGatewayClient` enforced only an aggregate `max_tool_calls=16` ceiling without per-turn identical-call deduplication/loop detection or list-length bounding (`MAX_TOOL_LIST_ITEMS`), and `verify_plan_outcomes` checked only provenance metadata without verifying mathematical/domain invariants on tool outputs.

## Options Considered

1. **Delegate multi-turn slot resolution and compound tool synthesis to unconstrained LLM prompts.** Rejected: violates SSRA Assist Principle 1 & 2 (deterministic routing, risk-tier lookup from `risk-tiers.yaml`, and 100% `numeric_provenance` validation).
2. **Require taxpayers to restate full intent and all parameters on every turn and restrict every turn to a single tool.** Rejected: breaks natural multi-turn dialogue and fails realistic multi-step `Toolathlon` workflows.
3. **Phased deterministic hardening across Working-Memory Checkpoint Carry-Over, Compound Multi-Tool Execution/Composition, and Gateway/Verifier Fault Guards (chosen).**

## Decision

1. **Phase 1 — Multi-Turn Slot Carry-Over & Guided Journey Progression (`conversation.py`, `understand.py`, `state.py`):**
   - `_checkpoint_state_by_thread` persists `prior_intent`, non-PII `prior_slots` (`amount_ssp`, `hs_code`, `cif_value_usd`, `wht_category`, `verification_mode`, `office_code`), and bounded `running_summary` across turns within the same `thread_id`.
   - `_resolve_multiturn_followup` deterministically resolves:
     - Guided-journey continuation cues (`"next step"`, `"continue"`, `"proceed"`, `"step 2"`, `"step 3"`), advancing `ActiveWorkflowCursor.current_step` up to `total_steps` and marking `status="COMPLETED"` at completion;
     - Customs `hs_code` carry-over when a follow-up turn supplies `cif_value_usd` or asks to estimate duty;
     - `CALCULATE_WITHHOLDING` follow-ups that change either the statutory category (`_has_explicit_wht_category_cue`) or the amount (`_ANAPHORIC_FOLLOWUP_RE`);
     - `CALCULATE_PAYE` anaphoric follow-ups (`"What if it is 800,000 SSP?"`).
2. **Phase 2 — Toolathlon Compound Multi-Tool Execution & Grounded Composition (`planner.py`, `knowledge_qa.py`, `compose.py`):**
   - `classify_intent_deterministic` extracts multiple monetary amounts in order (`_extract_all_monetary_amounts`) and flags `compound_wht=True` when PAYE and Withholding Tax are requested together.
   - `build_execution_plan` and `execute_knowledge_qa_subgraph` execute compound T0 tool chains (`calculate_paye_estimate` + `calculate_withholding_estimate` + `customs.estimate_duties`/`lookup_tariff`) with error isolation on secondary steps (`failed_steps`) and run `verify_plan_outcomes` across all T0 and T1 plans.
   - `compose_node` synthesizes all executed calculator, customs, ledger balance, filing status, declaration status, and TCC artifacts—preserving every `Citation` and `NumericClaim` so `validate_numeric_provenance` verifies 100% of figures—and appends a paused-journey resumption notice when a side question is answered while `workflow_stack` has an incomplete cursor.
3. **Phase 3 — Quiet-Failure Invariant Verification, Turn-Scoped Read Memoization & Loop Detection (`schemas.py`, `mcp_client.py`, `verifier.py`):**
   - `TurnBudget` tracks per-turn canonical tool-call fingerprints (`tool_call_counts`, `max_identical_tool_calls=2`) and `memoized_read_artifacts`.
   - `GovernedMcpGatewayClient.invoke_tool`:
     - Blocks duplicate state-changing (`T2`/`T3`) tool calls within the same turn (`TOOL_LOOP_DETECTED`);
     - Returns the memoized `ToolArtifact` on a second identical idempotent read (`T0`/`T1`) call within the same turn, and blocks a third identical call with `McpErrorCode.RATE_LIMITED` (`TOOL_LOOP_DETECTED`);
     - Bounds list fields in `structuredContent` to `MAX_TOOL_LIST_ITEMS = 25` with `_truncated_items=True`.
   - `verify_plan_outcomes` (`_detect_quiet_tool_fault`) verifies mathematical and domain invariants on `calculate_paye_estimate`, `calculate_withholding_estimate`, `estimate_duties`, and `get_balance`, flagging `QUIET_FAULT_DETECTED:<server>.<tool>:<reason>` and `verified=False` whenever a tool returns corrupted figures.

## Consequences

- Taxpayers can ask natural multi-turn follow-ups (`"What if it is 800,000 SSP?"`, `"What if it is for technical fees?"`, `"Estimate the duty for CIF $12,000"`, `"Next step"`) and compound multi-tool questions without losing context or dropping secondary tool results.
- Runaway identical tool calls and silent mathematical corruption in tool outputs are caught deterministically before reaching the taxpayer.

## Reversal Cost

Medium. Reverting these controls reintroduces multi-turn slot amnesia, single-tool truncation on compound queries, and unchecked quiet tool faults.

## Verification

Covered by `evals/suites/test_trajectories_and_channels.py` and `services/agent-runtime/tests/test_runtime.py`.
