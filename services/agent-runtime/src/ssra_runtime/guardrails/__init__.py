"""Runtime guardrails package."""

from ssra_runtime.guardrails.eq_detector import (
    build_empathetic_preamble,
    compute_affective_state,
    should_trigger_eq_escalation,
)
from ssra_runtime.guardrails.grounding import (
    GroundingResult,
    detect_conflicting_chunks,
    validate_grounding,
)
from ssra_runtime.guardrails.injection import InjectionCheckResult, check_prompt_injection
from ssra_runtime.guardrails.neutrality import NeutralityResult, validate_neutrality_and_promises
from ssra_runtime.guardrails.numeric_provenance import (
    NumericProvenanceResult,
    validate_numeric_provenance,
)
from ssra_runtime.guardrails.pii import (
    PiiGuardResult,
    mask_tin,
    redact_pii,
    verify_no_cross_subject_or_unmasked_pii,
)

__all__ = [
    "GroundingResult",
    "InjectionCheckResult",
    "NeutralityResult",
    "NumericProvenanceResult",
    "PiiGuardResult",
    "build_empathetic_preamble",
    "check_prompt_injection",
    "compute_affective_state",
    "detect_conflicting_chunks",
    "mask_tin",
    "redact_pii",
    "should_trigger_eq_escalation",
    "validate_grounding",
    "validate_neutrality_and_promises",
    "validate_numeric_provenance",
    "verify_no_cross_subject_or_unmasked_pii",
]
