"""Stage 12: Temporal Post-Interaction Autonomous Goal Continuation (`GoalContinuationWorkflow` — SSRA Assist October 2026).

Enforces:
1. Only resumes goals when `evaluate_flag("FF_TEMPORAL_POST_INTERACTION_CONTINUATION")` is active.
2. Requires active taxpayer opt-in consent (`opt_in_consent_active=True`) and a resolved upstream dependency
   (`ETAX_TCC_APPROVAL`, `CUSTOMS_ASSESSMENT`, `DOCUMENT_HUMAN_REVIEW`, or `OFFICER_CALLBACK_READY`).
3. Enforces the WhatsApp 24-hour customer service window vs. SSRA-approved notification template
   (`TMPL_SSRA_GOAL_CONTINUATION_2026`).
4. Scrubs all PII/currency figures (`redact_pii`) and appends the official anti-impersonation portal footer
   (`https://etax.nra.gov.ss/`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ssra_core import ChannelName, IntentName, LocaleCode, evaluate_flag
from ssra_security import redact_pii

APPROVED_CONTINUATION_TEMPLATES: frozenset[str] = frozenset(
    {
        "TMPL_SSRA_GOAL_CONTINUATION_2026",
        "TMPL_SSRA_TCC_READY_2026",
        "TMPL_SSRA_DOCUMENT_REVIEWED_2026",
    }
)


@dataclass(frozen=True)
class GoalContinuationCandidate:
    goal_id: str
    subject_ref: str
    goal_type: IntentName
    current_step_index: int
    total_steps: int
    pending_dependency: Literal[
        "ETAX_TCC_APPROVAL",
        "CUSTOMS_ASSESSMENT",
        "DOCUMENT_HUMAN_REVIEW",
        "OFFICER_CALLBACK_READY",
    ]
    dependency_resolved: bool
    opt_in_consent_active: bool
    channel: ChannelName = ChannelName.WHATSAPP
    locale: LocaleCode = LocaleCode.EN
    within_whatsapp_24h_window: bool = False
    template_id: str = "TMPL_SSRA_GOAL_CONTINUATION_2026"
    status_note: str = "Your pending SSRA verification step is complete."


@dataclass(frozen=True)
class GoalContinuationDispatchSummary:
    evaluated_count: int
    resumed_count: int
    skipped_no_consent: int
    skipped_unresolved_dependency: int
    skipped_unapproved_template_or_flag: int
    dispatched_messages: tuple[dict[str, str], ...]


def build_continuation_message(
    candidate: GoalContinuationCandidate,
) -> str:
    """Build a localized, PII-redacted SSRA resumption prompt with anti-impersonation footer."""
    safe_note = redact_pii(candidate.status_note).redacted_text
    if candidate.locale == LocaleCode.AR:
        return (
            f"تحديث رسمي من هيئة الإيرادات (SSRA): {safe_note} "
            f"يمكنك متابعة الخطوة {candidate.current_step_index} من {candidate.total_steps} عبر البوابة الرسمية "
            "https://etax.nra.gov.ss/ فقط. لا تدفع نقداً لأي شخص."
        )
    if candidate.locale == LocaleCode.PGA:
        return (
            f"Khabar rasmi min SSRA: {safe_note} "
            f"Tagdar takamil khatwa {candidate.current_step_index} min {candidate.total_steps} fi "
            "https://etax.nra.gov.ss/ bas. Ma tadfa gurush cash li ayi zol."
        )
    return (
        f"Official SSRA Assist Update ({candidate.goal_type.value}): {safe_note} "
        f"You can now resume step {candidate.current_step_index} of {candidate.total_steps} on "
        "https://etax.nra.gov.ss/. Never pay cash to an individual collector."
    )


def run_post_interaction_goal_continuation(
    candidates: list[GoalContinuationCandidate],
) -> GoalContinuationDispatchSummary:
    """Evaluate and dispatch post-interaction autonomous goal continuations."""
    resumed = 0
    no_consent = 0
    unresolved = 0
    blocked_template_or_flag = 0
    dispatched: list[dict[str, str]] = []

    for cand in candidates:
        if not cand.opt_in_consent_active:
            no_consent += 1
            continue
        if not cand.dependency_resolved:
            unresolved += 1
            continue

        flag_ok = evaluate_flag(
            "FF_TEMPORAL_POST_INTERACTION_CONTINUATION",
            subject_ref=cand.subject_ref,
            channel=cand.channel.value,
            locale=cand.locale.value,
        )
        if not flag_ok:
            blocked_template_or_flag += 1
            continue

        if (
            cand.channel == ChannelName.WHATSAPP
            and not cand.within_whatsapp_24h_window
            and cand.template_id not in APPROVED_CONTINUATION_TEMPLATES
        ):
            blocked_template_or_flag += 1
            continue

        if (
            cand.channel != ChannelName.WHATSAPP
            and cand.template_id not in APPROVED_CONTINUATION_TEMPLATES
        ):
            blocked_template_or_flag += 1
            continue

        msg = build_continuation_message(cand)
        dispatched.append(
            {
                "goal_id": cand.goal_id,
                "subject_ref": cand.subject_ref,
                "channel": cand.channel.value,
                "locale": cand.locale.value,
                "template_id": cand.template_id,
                "next_goal_status": "READY_TO_RESUME",
                "message": msg,
            }
        )
        resumed += 1

    return GoalContinuationDispatchSummary(
        evaluated_count=len(candidates),
        resumed_count=resumed,
        skipped_no_consent=no_consent,
        skipped_unresolved_dependency=unresolved,
        skipped_unapproved_template_or_flag=blocked_template_or_flag,
        dispatched_messages=tuple(dispatched),
    )
