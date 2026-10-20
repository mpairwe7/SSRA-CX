"""Supervisor Conversation Graph built on LangGraph 1.2.x (Section 6.1).

Executes the 11-node deterministic shell in strict order:
1. ingress -> 2. deterministic_router -> 3. input_guard -> 4. understand -> 5. policy_gate
-> 6/7. specialist subgraph + tool_exec -> 10. confirm -> 8. compose -> 9. output_guard -> 11. egress
"""

from __future__ import annotations

import re
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from ssra_core import (
    Answer,
    AnswerSegment,
    AuthLevel,
    ChannelBulkhead,
    ChannelName,
    Citation,
    ConversationEvent,
    GenerativeUIComponent,
    GenerativeUIComponentName,
    HandoffTicket,
    Intent,
    IntentName,
    LocaleCode,
    McpErrorCode,
    RiskTier,
    SSRAError,
)
from ssra_llm import AnonymousT0SemanticCache, SovereignModelRouter
from ssra_security import HashChainedAuditLedger, redact_pii

from ssra_runtime.graphs.handoff import execute_handoff_subgraph
from ssra_runtime.graphs.knowledge_qa import execute_knowledge_qa_subgraph
from ssra_runtime.graphs.self_service import execute_self_service_subgraph
from ssra_runtime.memory import SubjectPreferenceMemoryStore
from ssra_runtime.nodes import (
    ActiveWorkflowCursor,
    compose_node,
    confirm_or_execute_write_node,
    deterministic_router_node,
    egress_node,
    ingress_node,
    input_guard_node,
    output_guard_node,
    policy_gate_node,
    understand_node,
)
from ssra_runtime.nodes.planner import MAX_WORKFLOW_STACK_DEPTH
from ssra_runtime.replay import ConversationReplayStore, ReconstructedTurnRecord
from ssra_runtime.schemas import PendingConfirmation, RuntimeTurnResponse
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient

_SAFE_THREAD_ID_RE = re.compile(r"^[A-Za-z0-9_:-]{1,128}$")
MAX_TRACKED_RUNTIME_THREADS: int = 2048


def validate_safe_thread_id(thread_id: str) -> str:
    """Validate thread_id format per CVE-2026-48776 to prevent path traversal or key injection."""
    cleaned = thread_id.strip()
    if not _SAFE_THREAD_ID_RE.match(cleaned):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Unsafe or malformed thread_id '{thread_id[:32]}' rejected (CVE-2026-48776)",
            status_code=400,
        )
    return cleaned


def validate_safe_subject_ref(subject_ref: str, *, auth_level: AuthLevel) -> str:
    """Validate subject_ref format and block anonymous subject-binding smuggling (ASI03)."""
    if auth_level == AuthLevel.ANONYMOUS:
        raise SSRAError(
            McpErrorCode.NOT_AUTHORIZED,
            "Anonymous turns cannot bind a non-null subject_ref (ASI03 Confused-Deputy guard)",
            status_code=401,
        )
    cleaned = subject_ref.strip()
    if not _SAFE_THREAD_ID_RE.match(cleaned):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Unsafe or malformed subject_ref '{subject_ref[:32]}' rejected (ASI03)",
            status_code=400,
        )
    return cleaned


def verify_checkpoint_primitives_only(value: Any) -> bool:
    """Verify state values are JSON-safe primitives or Pydantic models (CVE-2026-48775 / CVE-2026-27794)."""
    if value is None or isinstance(value, (str, int, float, bool, BaseModel)):
        return True
    if isinstance(value, (list, tuple)):
        return all(verify_checkpoint_primitives_only(v) for v in value)
    if isinstance(value, dict):
        return all(
            isinstance(k, str) and verify_checkpoint_primitives_only(v) for k, v in value.items()
        )
    return False


class SSRAConversationRuntime:
    """Deterministic LangGraph supervisor runtime with checkpointer and governed MCP gateway."""

    def __init__(
        self,
        *,
        gateway: GovernedMcpGatewayClient | None = None,
        audit_ledger: HashChainedAuditLedger | None = None,
        replay_store: ConversationReplayStore | None = None,
    ) -> None:
        self.gateway = gateway or GovernedMcpGatewayClient()
        self.audit_ledger = audit_ledger or HashChainedAuditLedger()
        self.replay_store = replay_store or ConversationReplayStore()
        self.preference_store = SubjectPreferenceMemoryStore()
        self.model_router = SovereignModelRouter()
        self.semantic_cache = AnonymousT0SemanticCache()
        self.channel_bulkhead = ChannelBulkhead()
        self.checkpointer = InMemorySaver()
        self._disabled_channels: set[ChannelName] = set()
        self._thread_subject_binding: dict[str, str] = {}
        self._pending_by_thread: dict[str, tuple[PendingConfirmation, Intent | None, RiskTier]] = {}
        self._workflow_stack_by_thread: dict[str, list[dict[str, Any]]] = {}
        self._compiled = self._build_graph()

    def apply_officer_handback_resolution(
        self,
        *,
        thread_id: str,
        approved_next_intent: IntentName,
        return_to_ai_step: int = 1,
        resolution_summary: str = "",
    ) -> ActiveWorkflowCursor:
        """Seed a conversation thread's `workflow_stack` with an officer's verified hand-back cursor."""
        safe_id = validate_safe_thread_id(thread_id)
        cursor = ActiveWorkflowCursor(
            workflow_id=f"wf_{safe_id}",
            journey_intent=approved_next_intent,
            current_step=max(1, return_to_ai_step),
            total_steps=3,
            status="ACTIVE",
            officer_note=redact_pii(resolution_summary).redacted_text[:200],
        )
        stack = self._workflow_stack_by_thread.setdefault(safe_id, [])
        stack.append(cursor.model_dump(mode="json"))
        if len(stack) > MAX_WORKFLOW_STACK_DEPTH:
            del stack[:-MAX_WORKFLOW_STACK_DEPTH]
        return cursor

    def set_kill_switches(
        self,
        *,
        degradation_level: int = 1,
        disabled_tools: list[str] | tuple[str, ...] = (),
        disabled_channels: list[str] | tuple[str, ...] = (),
    ) -> None:
        """Apply live SecOps kill-switches to the model router, MCP gateway, and channel ingress."""
        self.model_router.set_degradation_level(degradation_level)
        for existing in list(self.gateway.disabled_tools):
            self.gateway.set_tool_kill_switch(existing, disabled=False)
        for tool_key in disabled_tools:
            self.gateway.set_tool_kill_switch(tool_key, disabled=True)
        self._disabled_channels = {
            ChannelName(ch) for ch in disabled_channels if ch in ChannelName._value2member_map_
        }

    def reconstruct_conversation(self, thread_id: str) -> list[ReconstructedTurnRecord]:
        """Reconstruct the immutable turn-by-turn forensic history for a validated thread_id."""
        safe_id = validate_safe_thread_id(thread_id)
        return self.replay_store.reconstruct_thread(safe_id)

    def _build_graph(self) -> Any:
        """Compile the 11-node deterministic LangGraph state machine."""
        builder: StateGraph[ConversationGraphState] = StateGraph(ConversationGraphState)

        def _knowledge_qa_node(state: ConversationGraphState) -> dict[str, Any]:
            """Invoke the knowledge_qa specialist subgraph."""
            return execute_knowledge_qa_subgraph(state, self.gateway)

        def _self_service_node(state: ConversationGraphState) -> dict[str, Any]:
            """Invoke the self_service specialist subgraph."""
            return execute_self_service_subgraph(state, self.gateway)

        def _confirm_node(state: ConversationGraphState) -> dict[str, Any]:
            """Invoke the T2/T3 confirmation or write-execution node."""
            return confirm_or_execute_write_node(state, self.gateway)

        def _egress_node(state: ConversationGraphState) -> dict[str, Any]:
            """Invoke the egress audit and running-summary node."""
            return egress_node(state, self.audit_ledger)

        builder.add_node("ingress", ingress_node)
        builder.add_node("deterministic_router", deterministic_router_node)
        builder.add_node("input_guard", input_guard_node)
        builder.add_node("understand", understand_node)
        builder.add_node("policy_gate", policy_gate_node)
        builder.add_node("knowledge_qa", _knowledge_qa_node)
        builder.add_node("self_service", _self_service_node)
        builder.add_node("handoff", execute_handoff_subgraph)
        builder.add_node("confirm", _confirm_node)
        builder.add_node("compose", compose_node)
        builder.add_node("output_guard", output_guard_node)
        builder.add_node("egress", _egress_node)

        builder.add_edge(START, "ingress")
        builder.add_edge("ingress", "deterministic_router")

        def _after_router(state: ConversationGraphState) -> str:
            """Route deterministic turns directly to egress or continue to input_guard."""
            if state.get("deterministic_handled"):
                return "egress"
            return "input_guard"

        builder.add_conditional_edges(
            "deterministic_router",
            _after_router,
            {"egress": "egress", "input_guard": "input_guard"},
        )

        def _after_input_guard(state: ConversationGraphState) -> str:
            """Route blocked adversarial inputs to egress or continue to understand."""
            if state.get("policy_decision") == "DENY":
                return "egress"
            return "understand"

        builder.add_conditional_edges(
            "input_guard",
            _after_input_guard,
            {"egress": "egress", "understand": "understand"},
        )

        builder.add_edge("understand", "policy_gate")

        def _route_subgraph(state: ConversationGraphState) -> str:
            """Select the specialist subgraph determined by policy_gate."""
            return state.get("selected_subgraph", "knowledge_qa")

        builder.add_conditional_edges(
            "policy_gate",
            _route_subgraph,
            {
                "knowledge_qa": "knowledge_qa",
                "self_service": "self_service",
                "handoff": "handoff",
            },
        )

        builder.add_edge("knowledge_qa", "compose")
        builder.add_edge("self_service", "confirm")
        builder.add_edge("confirm", "compose")
        builder.add_edge("handoff", "compose")
        builder.add_edge("compose", "output_guard")

        def _after_output_guard(state: ConversationGraphState) -> str:
            """Loop back to compose once on validator feedback or proceed to egress."""
            if state.get("validator_feedback") and state.get("answer") is None:
                return "compose"
            return "egress"

        builder.add_conditional_edges(
            "output_guard",
            _after_output_guard,
            {"compose": "compose", "egress": "egress"},
        )
        builder.add_edge("egress", END)

        return builder.compile(checkpointer=self.checkpointer)

    def run_turn(
        self,
        event: ConversationEvent,
        *,
        auth_level: AuthLevel = AuthLevel.ANONYMOUS,
        subject_ref: str | None = None,
        confirmation_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> RuntimeTurnResponse:
        """Execute a full conversation turn with subject-binding, kill-switches, and forensic replay."""
        safe_thread_id = validate_safe_thread_id(event.subject)
        if subject_ref is not None:
            subject_ref = validate_safe_subject_ref(subject_ref, auth_level=auth_level)

        # ASI03 / ASI06: Prevent cross-subject thread hijacking on bound threads
        bound_subject = self._thread_subject_binding.get(safe_thread_id)
        if bound_subject is not None and subject_ref is not None and subject_ref != bound_subject:
            raise SSRAError(
                McpErrorCode.NOT_AUTHORIZED,
                f"Cross-subject thread hijacking blocked on thread '{safe_thread_id}' (ASI03)",
                status_code=403,
            )
        if subject_ref is not None:
            self._thread_subject_binding[safe_thread_id] = subject_ref

        text_parts = [p.value for p in event.data.parts if p.kind == "text"]
        user_text = " ".join(text_parts).strip()

        # Hydrate consented accessibility/low-data preferences & 4-tier active goals if stored for subject_ref (Section 6.5)
        capabilities = event.data.capabilities
        seed_slots: dict[str, Any] = {}
        for meta_k in (
            "voice_barge_in_count",
            "voice_rms_energy_delta",
            "voice_speech_rate_ratio",
            "consecutive_low_confidence_turns",
            "repeated_clarification_count",
        ):
            if meta_k in event.data.metadata:
                seed_slots[meta_k] = event.data.metadata[meta_k]
        if event.data.metadata.get("eq_preemptive_escalate") == "true":
            seed_slots["eq_preemptive_escalate"] = True

        if subject_ref is not None:
            hydrated = self.preference_store.hydrate_subject_context(subject_ref)
            if hydrated.preferences is not None and hydrated.preferences.low_data_mode:
                capabilities = capabilities.model_copy(update={"rich_ui": False})
            if hydrated.active_goals:
                seed_slots["resumable_goal_id"] = hydrated.active_goals[0].goal_id

        # Enforce active channel kill-switch or Level 5 static FAQ safe mode before graph execution
        if (
            event.data.channel in self._disabled_channels
            or self.model_router.degradation_level == 5
        ):
            is_channel_paused = event.data.channel in self._disabled_channels
            reason_code = (
                "CHANNEL_PAUSED_KILL_SWITCH" if is_channel_paused else "DEGRADATION_L5_STATIC_FAQ"
            )
            faq_cit = Citation(
                id="cit_l5_static_faq",
                snapshot_version="2026.10.1",
                doc_title="SSRA Official e-Tax & Cash-Free Bank Collection Guide",
                section_anchor="Part-I-Sec-1-TIN-Registration",
                effective_from="2026-03-01",
                url="https://etax.nra.gov.ss/",
            )
            fallback_text = (
                f"SSRA Assist Safe Mode ({reason_code}): Visit the official portal at "
                "https://etax.nra.gov.ss/ for TIN registration, return filing, and designated bank "
                "payment instructions. We have queued a callback with an SSRA officer."
            )[: capabilities.max_len]
            ticket = HandoffTicket(
                conversation_id=safe_thread_id,
                reason="GUARD_FALLBACK",
                queue="DOMESTIC_TAX",
                summary=f"Safe-mode fallback ({reason_code}) routed to officer callback.",
                citations=[faq_cit.id],
                priority="HIGH",
            )
            ans = Answer(
                segments=[AnswerSegment(text=fallback_text, citation_ids=[faq_cit.id])],
                citations=[faq_cit],
                numbers=[],
                ui_component=GenerativeUIComponent(
                    name=GenerativeUIComponentName.HANDOFF_CARD,
                    props={
                        "reason": ticket.reason,
                        "queue": ticket.queue,
                        "priority": ticket.priority,
                    },
                )
                if capabilities.rich_ui
                else None,
                is_estimate=False,
                abstained=True,
            )
            aud_ev = self.audit_ledger.append(
                actor="ssra-agent-runtime",
                on_behalf_of=subject_ref,
                action="conversation.turn.safe_mode_egress",
                resource=f"thread://{safe_thread_id}",
                payload={"reason": reason_code, "channel": event.data.channel.value},
            )
            route_decision = self.model_router.select_route(node_name="compose", tier=RiskTier.T0)
            resp = RuntimeTurnResponse(
                thread_id=safe_thread_id,
                channel=event.data.channel,
                locale=event.data.locale,
                auth_level=auth_level,
                tier=RiskTier.T0,
                policy_decision="HANDOFF",
                intent=None,
                answer=ans,
                artifacts=[],
                citations=[faq_cit],
                pending_confirmation=None,
                handoff_ticket=ticket,
                safety_flags=[reason_code],
                audit_event_hash=aud_ev.hash,
            )
            self.replay_store.record_turn(
                thread_id=resp.thread_id,
                channel=resp.channel,
                locale=resp.locale,
                auth_level=resp.auth_level,
                subject_ref=subject_ref,
                redacted_input=redact_pii(user_text).redacted_text,
                intent_name="safe_mode_fallback",
                risk_tier=resp.tier,
                policy_decision=resp.policy_decision,
                prompt_version="2026.10.1",
                model_route=route_decision.selected_model,
                knowledge_snapshot_version="2026.10.1",
                tool_calls=[],
                citations=[faq_cit.section_anchor],
                numbers=[],
                output_text=fallback_text,
                abstained=True,
                safety_flags=[reason_code],
                audit_event_hash=aud_ev.hash,
            )
            return resp

        # Microsoft agent-framework#8132: Restore pending confirmation context when resuming with confirmation_token
        restored_pending: PendingConfirmation | None = None
        restored_intent: Intent | None = None
        restored_tier: RiskTier | None = None
        if confirmation_token and safe_thread_id in self._pending_by_thread:
            restored_pending, restored_intent, restored_tier = self._pending_by_thread[
                safe_thread_id
            ]

        initial_state: ConversationGraphState = {
            "thread_id": safe_thread_id,
            "channel": event.data.channel,
            "locale": event.data.locale,
            "capabilities": capabilities,
            "auth_level": auth_level,
            "subject_ref": subject_ref,
            "raw_user_text": user_text,
            "slots": seed_slots,
            "workflow_stack": list(self._workflow_stack_by_thread.get(safe_thread_id, [])),
            "confirmation_token_in": confirmation_token,
            "idempotency_key_in": idempotency_key,
            "answer": None,
            "artifacts": [],
            "citations": [],
            "safety_flags": [],
            "pending_confirmation": restored_pending,
            "handoff_state": None,
        }
        if restored_intent is not None:
            initial_state["intent"] = restored_intent
        if restored_tier is not None:
            initial_state["tier"] = restored_tier

        assert verify_checkpoint_primitives_only(initial_state)

        self.channel_bulkhead.acquire(event.data.channel)
        try:
            final_state: ConversationGraphState = self._compiled.invoke(
                initial_state,
                config={
                    "configurable": {"thread_id": safe_thread_id},
                    "recursion_limit": 25,
                },
            )
        finally:
            self.channel_bulkhead.release(event.data.channel)

        out_pending = final_state.get("pending_confirmation")
        if out_pending is not None:
            self._pending_by_thread[safe_thread_id] = (
                out_pending,
                final_state.get("intent"),
                final_state.get("tier", RiskTier.T2),
            )
        else:
            self._pending_by_thread.pop(safe_thread_id, None)

        verif_dict = final_state.get("outcome_verification") or {}
        outcome_verified = bool(verif_dict.get("verified", True))

        resp = RuntimeTurnResponse(
            thread_id=safe_thread_id,
            channel=final_state.get("channel", ChannelName.WEB),
            locale=final_state.get("locale", LocaleCode.EN),
            auth_level=final_state.get("auth_level", AuthLevel.ANONYMOUS),
            tier=final_state.get("tier", RiskTier.T0),
            policy_decision=final_state.get("policy_decision", "ALLOW"),  # type: ignore[arg-type]
            intent=final_state.get("intent"),
            answer=final_state["answer"],  # type: ignore[arg-type, typeddict-item]
            artifacts=final_state.get("artifacts", []),
            citations=final_state.get("citations", []),
            pending_confirmation=final_state.get("pending_confirmation"),
            handoff_ticket=final_state.get("handoff_state"),
            handoff_envelope=final_state.get("handoff_envelope"),
            affective_state=final_state.get("affective_state"),
            english_router_envelope=final_state.get("english_router_envelope"),
            plan=final_state.get("plan"),
            outcome_verified=outcome_verified,
            safety_flags=final_state.get("safety_flags", []),
            audit_event_hash=final_state.get("audit_event_hash", ""),
        )
        if resp.intent is not None and resp.intent.intent in (
            IntentName.GUIDED_TIN_REGISTRATION,
            IntentName.GUIDED_FILING_AND_PAYMENT,
            IntentName.GUIDED_TCC,
        ):
            cursor = ActiveWorkflowCursor(
                workflow_id=f"wf_{safe_thread_id}",
                journey_intent=resp.intent.intent,
                current_step=1,
                total_steps=3 if resp.intent.intent == IntentName.GUIDED_TIN_REGISTRATION else 2,
                status="PAUSED_FOR_DELEGATION",
            )
            stack = self._workflow_stack_by_thread.setdefault(safe_thread_id, [])
            stack.append(cursor.model_dump(mode="json"))
            if len(stack) > MAX_WORKFLOW_STACK_DEPTH:
                del stack[:-MAX_WORKFLOW_STACK_DEPTH]

        if subject_ref is not None and resp.intent is not None:
            blockers = verif_dict.get("blocker_codes") or []
            self.preference_store.record_episode(
                subject_ref=subject_ref,
                channel=resp.channel,
                locale=resp.locale,
                intent=resp.intent.intent,
                outcome_status=(
                    "ESCALATED"
                    if resp.handoff_ticket is not None
                    else "PENDING_ASYNC"
                    if resp.pending_confirmation is not None
                    else "RESOLVED"
                ),
                raw_summary=" ".join(s.text for s in resp.answer.segments)[:240],
                unresolved_blocker_code=str(blockers[0]) if blockers else None,
            )
            if resp.intent.intent in (
                IntentName.GUIDED_TIN_REGISTRATION,
                IntentName.GUIDED_FILING_AND_PAYMENT,
                IntentName.GUIDED_TCC,
            ):
                self.preference_store.upsert_active_goal(
                    subject_ref=subject_ref,
                    goal_type=resp.intent.intent,
                    current_step_index=1,
                    total_steps=(
                        3 if resp.intent.intent == IntentName.GUIDED_TIN_REGISTRATION else 2
                    ),
                    completed_steps=["step_1_guided_briefing"],
                    resume_channel=resp.channel,
                    status="IN_PROGRESS",
                )
            elif resp.pending_confirmation is not None:
                tool_goal_map = {
                    "create_case": IntentName.CREATE_CASE,
                    "book_appointment": IntentName.BOOK_APPOINTMENT,
                    "report_scam": IntentName.REPORT_SCAM,
                }
                pending_goal_type = tool_goal_map.get(
                    resp.pending_confirmation.tool,
                    resp.intent.intent,
                )
                self.preference_store.upsert_active_goal(
                    subject_ref=subject_ref,
                    goal_type=pending_goal_type,
                    goal_id=f"goal_{pending_goal_type.value}",
                    current_step_index=1,
                    total_steps=2,
                    completed_steps=[a.tool for a in resp.artifacts],
                    resume_channel=resp.channel,
                    status="WAITING_ASYNC",
                )
            elif confirmation_token is not None and resp.artifacts:
                target_gid = f"goal_{resp.intent.intent.value}"
                for active_g in self.preference_store.list_active_goals(subject_ref):
                    if active_g.status == "WAITING_ASYNC" and (
                        active_g.goal_id == target_gid or active_g.goal_type == resp.intent.intent
                    ):
                        merged_steps = [
                            *active_g.completed_steps,
                            *(
                                a.tool
                                for a in resp.artifacts
                                if a.tool not in active_g.completed_steps
                            ),
                        ]
                        self.preference_store.upsert_active_goal(
                            subject_ref=subject_ref,
                            goal_type=active_g.goal_type,
                            goal_id=active_g.goal_id,
                            current_step_index=active_g.total_steps,
                            total_steps=active_g.total_steps,
                            completed_steps=merged_steps,
                            resume_channel=resp.channel,
                            status="COMPLETED",
                        )
        route_decision = self.model_router.select_route(node_name="compose", tier=resp.tier)
        self.semantic_cache.put(
            snapshot_version="2026.10.1",
            locale=resp.locale,
            query=user_text,
            tier=resp.tier,
            auth_level=resp.auth_level,
            answer=resp.answer,
        )
        self.replay_store.record_turn(
            thread_id=resp.thread_id,
            channel=resp.channel,
            locale=resp.locale,
            auth_level=resp.auth_level,
            subject_ref=subject_ref,
            redacted_input=final_state.get("redacted_user_text", user_text),
            intent_name=resp.intent.intent.value if resp.intent else "deterministic",
            risk_tier=resp.tier,
            policy_decision=resp.policy_decision,
            prompt_version="2026.10.1",
            model_route=route_decision.selected_model,
            knowledge_snapshot_version="2026.10.1",
            tool_calls=[
                {
                    "id": a.id,
                    "server": a.server,
                    "tool": a.tool,
                    "provenance": a.provenance,
                }
                for a in resp.artifacts
            ],
            citations=[c.section_anchor for c in resp.citations],
            numbers=[
                {"value": n.value, "unit": n.unit.value, "source_ref": n.source_ref}
                for n in resp.answer.numbers
            ],
            output_text=" ".join(s.text for s in resp.answer.segments),
            abstained=resp.answer.abstained,
            safety_flags=resp.safety_flags,
            audit_event_hash=resp.audit_event_hash,
        )
        return resp
