"""Supervisor Conversation Graph built on LangGraph 1.2.x (Section 6.1).

Executes the 11-node deterministic shell in strict order:
1. ingress -> 2. deterministic_router -> 3. input_guard -> 4. understand -> 5. policy_gate
-> 6/7. specialist subgraph + tool_exec -> 10. confirm -> 8. compose -> 9. output_guard -> 11. egress
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from ssra_core import (
    AuthLevel,
    ChannelName,
    ConversationEvent,
    LocaleCode,
    RiskTier,
)
from ssra_security import HashChainedAuditLedger

from ssra_runtime.graphs.handoff import execute_handoff_subgraph
from ssra_runtime.graphs.knowledge_qa import execute_knowledge_qa_subgraph
from ssra_runtime.graphs.self_service import execute_self_service_subgraph
from ssra_runtime.nodes import (
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
from ssra_runtime.replay import ConversationReplayStore, ReconstructedTurnRecord
from ssra_runtime.schemas import RuntimeTurnResponse
from ssra_runtime.state import ConversationGraphState
from ssra_runtime.tools import GovernedMcpGatewayClient


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
        self.checkpointer = InMemorySaver()
        self._compiled = self._build_graph()

    def reconstruct_conversation(self, thread_id: str) -> list[ReconstructedTurnRecord]:
        return self.replay_store.reconstruct_thread(thread_id)

    def _build_graph(self) -> Any:
        builder: StateGraph[ConversationGraphState] = StateGraph(ConversationGraphState)

        def _knowledge_qa_node(state: ConversationGraphState) -> dict[str, Any]:
            return execute_knowledge_qa_subgraph(state, self.gateway)

        def _self_service_node(state: ConversationGraphState) -> dict[str, Any]:
            return execute_self_service_subgraph(state, self.gateway)

        def _confirm_node(state: ConversationGraphState) -> dict[str, Any]:
            return confirm_or_execute_write_node(state, self.gateway)

        def _egress_node(state: ConversationGraphState) -> dict[str, Any]:
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
            if state.get("deterministic_handled"):
                return "egress"
            return "input_guard"

        builder.add_conditional_edges(
            "deterministic_router",
            _after_router,
            {"egress": "egress", "input_guard": "input_guard"},
        )

        def _after_input_guard(state: ConversationGraphState) -> str:
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
        text_parts = [p.value for p in event.data.parts if p.kind == "text"]
        user_text = " ".join(text_parts).strip()

        initial_state: ConversationGraphState = {
            "thread_id": event.subject,
            "channel": event.data.channel,
            "locale": event.data.locale,
            "capabilities": event.data.capabilities,
            "auth_level": auth_level,
            "subject_ref": subject_ref,
            "raw_user_text": user_text,
            "confirmation_token_in": confirmation_token,
            "idempotency_key_in": idempotency_key,
            "answer": None,
            "artifacts": [],
            "citations": [],
            "safety_flags": [],
            "pending_confirmation": None,
            "handoff_state": None,
        }

        final_state: ConversationGraphState = self._compiled.invoke(
            initial_state,
            config={"configurable": {"thread_id": event.subject}},
        )

        resp = RuntimeTurnResponse(
            thread_id=event.subject,
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
            safety_flags=final_state.get("safety_flags", []),
            audit_event_hash=final_state.get("audit_event_hash", ""),
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
            model_route="ssra-sovereign/qwen2.5-14b-instruct",
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
