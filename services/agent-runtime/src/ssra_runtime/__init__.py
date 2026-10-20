"""SSRA Assist Agent Runtime package."""

from ssra_runtime.graphs import SSRAConversationRuntime
from ssra_runtime.guardrails.eq_detector import (
    build_empathetic_preamble,
    compute_affective_state,
    should_trigger_eq_escalation,
)
from ssra_runtime.main import AguiStreamRequest, app, create_runtime_app
from ssra_runtime.memory import (
    ActiveGoalRecord,
    ConsentedUserPreferences,
    EpisodicMemoryRecord,
    HydratedCognitiveContext,
    SubjectPreferenceMemoryStore,
    strip_financial_figures_for_memory,
)
from ssra_runtime.nodes.language_state import (
    build_english_router_envelope,
    evaluate_language_state_transition,
    extract_preserved_statutory_tokens,
)
from ssra_runtime.nodes.planner import (
    ActiveWorkflowCursor,
    build_execution_plan,
    detect_compound_self_service_steps,
)
from ssra_runtime.nodes.verifier import OutcomeVerificationResult, verify_plan_outcomes
from ssra_runtime.schemas import PendingConfirmation, RuntimeTurnResponse, ToolArtifact

__all__ = [
    "ActiveGoalRecord",
    "ActiveWorkflowCursor",
    "AguiStreamRequest",
    "ConsentedUserPreferences",
    "EpisodicMemoryRecord",
    "HydratedCognitiveContext",
    "OutcomeVerificationResult",
    "PendingConfirmation",
    "RuntimeTurnResponse",
    "SSRAConversationRuntime",
    "SubjectPreferenceMemoryStore",
    "ToolArtifact",
    "app",
    "build_empathetic_preamble",
    "build_english_router_envelope",
    "build_execution_plan",
    "compute_affective_state",
    "create_runtime_app",
    "detect_compound_self_service_steps",
    "evaluate_language_state_transition",
    "extract_preserved_statutory_tokens",
    "should_trigger_eq_escalation",
    "strip_financial_figures_for_memory",
    "verify_plan_outcomes",
]
