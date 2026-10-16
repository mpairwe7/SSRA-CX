"""Phase 4 Voice/IVR ASR, TTS/MMS, Call Receptionist, Officer Call Brief & Lobby Engine (Section 11, CVE-2026-54233)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from ssra_core import LocaleCode, McpErrorCode, SSRAError
from ssra_security import redact_pii

# Launch a language on voice only after its word-error rate on SSRA test sets meets the gate (<= 0.12)
MAX_VOICE_WER_GATE: float = 0.12

# CVE-2026-54233: Cap decoded float32 PCM output at 15.36 MB (120s @ 16kHz mono float32) to prevent OPUS decompression bombs
MAX_DECODED_PCM_BYTES: int = 15_360_000
MAX_COMPRESSED_AUDIO_BYTES: int = 2_097_152

# ASR model selection per Section 11: vLLM Whisper Large v3 Turbo for en/ar; HF Meta MMS/Omnilingual ASR for pga & local languages
ASR_MODEL_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "openai/whisper-large-v3-turbo",
    LocaleCode.AR: "openai/whisper-large-v3-turbo",
    LocaleCode.PGA: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.DIN: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.NUS: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.BFA: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.ZNE: "facebook/omnilingual-asr-mms-1b-all",
    LocaleCode.SHK: "facebook/omnilingual-asr-mms-1b-all",
}

# TTS (Text-to-Speech) model selection via HuggingFace offline cache (`facebook/mms-tts-*` VITS checkpoints)
TTS_MODEL_BY_LOCALE: dict[LocaleCode, str] = {
    LocaleCode.EN: "facebook/mms-tts-eng",
    LocaleCode.AR: "facebook/mms-tts-ara",
    LocaleCode.PGA: "facebook/mms-tts-ara",
    LocaleCode.DIN: "facebook/mms-tts-dik",
    LocaleCode.NUS: "facebook/mms-tts-nus",
    LocaleCode.BFA: "facebook/mms-tts-bfa",
    LocaleCode.ZNE: "facebook/mms-tts-zne",
    LocaleCode.SHK: "facebook/mms-tts-shk",
}


@dataclass(frozen=True)
class VoiceSessionDecision:
    session_id: str
    locale: LocaleCode
    asr_engine: str
    tts_engine: str
    recording_enabled: bool
    action: str  # STREAM_ASR | DTMF_MENU | WARM_TRANSFER_TO_OFFICER
    warm_transfer_summary: str | None = None


@dataclass(frozen=True)
class HfVoiceModelDescriptor:
    locale: LocaleCode
    asr_repo_id: str
    tts_repo_id: str
    serving_backend: str
    hf_cache_dir: str
    local_files_only: bool


def resolve_hf_voice_model_cache(
    locale: LocaleCode,
    *,
    hf_home: str = "/home/developer/huggingface_cache",
) -> HfVoiceModelDescriptor:
    """Resolve local HuggingFace cache paths for ASR (`vLLM` / `MMS`) and TTS (`MMS-TTS`) with `local_files_only=True`."""
    asr_repo = ASR_MODEL_BY_LOCALE[locale]
    tts_repo = TTS_MODEL_BY_LOCALE[locale]
    backend = (
        "vllm-audio-transcriptions"
        if locale in (LocaleCode.EN, LocaleCode.AR)
        else "hf-mms-offline"
    )
    return HfVoiceModelDescriptor(
        locale=locale,
        asr_repo_id=asr_repo,
        tts_repo_id=tts_repo,
        serving_backend=backend,
        hf_cache_dir=f"{hf_home.rstrip('/')}/hub",
        local_files_only=True,
    )


def validate_audio_pcm_expansion_budget(
    *,
    compressed_bytes: int,
    duration_seconds: float,
    sample_rate_hz: int = 16000,
) -> int:
    """Guard vLLM /v1/audio/transcriptions against OPUS/float32 PCM decompression bombs (CVE-2026-54233)."""
    if compressed_bytes <= 0 or compressed_bytes > MAX_COMPRESSED_AUDIO_BYTES:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Compressed audio size ({compressed_bytes} bytes) exceeds 2 MB limit",
            status_code=413,
        )
    if duration_seconds <= 0 or sample_rate_hz <= 0:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Audio duration_seconds and sample_rate_hz must be positive",
            status_code=400,
        )
    estimated_pcm_bytes = int(duration_seconds * sample_rate_hz * 4)  # float32 = 4 bytes/sample
    if estimated_pcm_bytes > MAX_DECODED_PCM_BYTES:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            f"Decoded PCM expansion ({estimated_pcm_bytes} bytes) exceeds CVE-2026-54233 safety cap ({MAX_DECODED_PCM_BYTES} bytes)",
            status_code=413,
        )
    return estimated_pcm_bytes


def synthesize_tts_speech_envelope(
    *,
    text: str,
    locale: LocaleCode,
    hf_home: str = "/home/developer/huggingface_cache",
) -> dict[str, Any]:
    """Build deterministic offline HuggingFace MMS-TTS VITS synthesis envelope."""
    desc = resolve_hf_voice_model_cache(locale, hf_home=hf_home)
    return {
        "tts_model": desc.tts_repo_id,
        "locale": locale.value,
        "hf_cache_dir": desc.hf_cache_dir,
        "local_files_only": desc.local_files_only,
        "sample_rate_hz": 16000,
        "text_length": len(text.strip()),
    }


def is_voice_language_approved(locale: LocaleCode, measured_wer: float) -> bool:
    _ = locale
    return 0.0 <= measured_wer <= MAX_VOICE_WER_GATE


def route_voice_turn(
    *,
    session_id: str,
    locale: LocaleCode,
    measured_wer: float,
    recording_consent_granted: bool,
    dtmf_digit: str | None = None,
    barge_in_detected: bool = False,
) -> VoiceSessionDecision:
    _ = barge_in_detected
    asr_engine = ASR_MODEL_BY_LOCALE[locale]
    tts_engine = TTS_MODEL_BY_LOCALE[locale]

    if dtmf_digit == "0" or not is_voice_language_approved(locale, measured_wer):
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            action="WARM_TRANSFER_TO_OFFICER",
            warm_transfer_summary=(
                f"Warm transfer from IVR ({locale.value}): caller pressed 0 or language WER "
                f"{measured_wer:.2f} exceeded gate {MAX_VOICE_WER_GATE}."
            ),
        )

    if dtmf_digit is not None:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            action="DTMF_MENU",
        )

    return VoiceSessionDecision(
        session_id=session_id,
        locale=locale,
        asr_engine=asr_engine,
        tts_engine=tts_engine,
        recording_enabled=recording_consent_granted,
        action="STREAM_ASR",
    )


class VoiceWebSocketConcurrencyGuard:
    """P1-9 Voice WebSocket Concurrency Cap (`voice_ws_v2.py` pattern): per-user (3) & global (64)."""

    def __init__(self, *, per_user_cap: int = 3, global_cap: int = 64) -> None:
        self.per_user_cap = max(1, per_user_cap)
        self.global_cap = max(1, global_cap)
        self._by_user: dict[str, int] = {}
        self._total = 0

    def try_acquire(self, user_key: str) -> tuple[bool, int | None]:
        current = self._by_user.get(user_key, 0)
        if current >= self.per_user_cap or self._total >= self.global_cap:
            return False, 1013
        self._by_user[user_key] = current + 1
        self._total += 1
        return True, None

    def release(self, user_key: str) -> None:
        current = self._by_user.get(user_key, 0)
        if current <= 1:
            self._by_user.pop(user_key, None)
        else:
            self._by_user[user_key] = current - 1
        self._total = max(0, self._total - 1)


@dataclass(frozen=True)
class BriefClaim:
    text: str
    turn_seqs: list[int]


@dataclass(frozen=True)
class OfficerCallBrief:
    call_id: str
    why_officer: BriefClaim
    caller_goal: BriefClaim
    ai_already_said: list[BriefClaim]
    still_open: list[BriefClaim]
    details_given: list[dict[str, Any]]
    sentiment: Literal["calm", "confused", "frustrated", "distressed"]
    suggested_opener: str
    turns_covered: int
    model: str = "ssra-sovereign/sunflower-qwen3.5-9b"
    fallback: bool = False


def generate_officer_call_brief(
    *,
    call_id: str,
    turns: list[dict[str, Any]],
    transfer_reason: str,
) -> OfficerCallBrief:
    """Build the 10-second Officer Call Brief (`CallBriefCard.tsx`) with turn-sequence evidence links."""
    caller_turns = [t for t in turns if t.get("speaker") == "caller"]
    ai_turns = [t for t in turns if t.get("speaker") == "assistant"]

    first_caller_seq = int(caller_turns[0].get("seq", 1)) if caller_turns else 1
    last_caller_seq = int(caller_turns[-1].get("seq", 1)) if caller_turns else 1
    raw_goal = (
        str(caller_turns[0].get("text", "Taxpayer inquiry")) if caller_turns else "Taxpayer inquiry"
    )
    redacted_goal = redact_pii(raw_goal).redacted_text

    ai_claims = [
        BriefClaim(
            text=redact_pii(str(t.get("text", ""))[:140]).redacted_text,
            turn_seqs=[int(t.get("seq", idx + 1))],
        )
        for idx, t in enumerate(ai_turns[:3])
        if str(t.get("text", "")).strip()
    ]

    combined_lower = " ".join(str(t.get("text", "")).lower() for t in caller_turns)
    sentiment: Literal["calm", "confused", "frustrated", "distressed"] = "calm"
    if any(w in combined_lower for w in ("urgent", "blocked", "seized", "distress")):
        sentiment = "distressed"
    elif any(w in combined_lower for w in ("error", "failed", "frustrated", "wrong")):
        sentiment = "frustrated"
    elif any(w in combined_lower for w in ("confused", "how", "understand")):
        sentiment = "confused"

    return OfficerCallBrief(
        call_id=call_id,
        why_officer=BriefClaim(text=transfer_reason, turn_seqs=[last_caller_seq]),
        caller_goal=BriefClaim(text=redacted_goal, turn_seqs=[first_caller_seq]),
        ai_already_said=ai_claims,
        still_open=[
            BriefClaim(
                text=f"Resolve {transfer_reason.lower()} and confirm next filing/payment step",
                turn_seqs=[last_caller_seq],
            )
        ],
        details_given=[
            {
                "label": "Redacted Summary",
                "value": redacted_goal[:80],
                "turn_seqs": [first_caller_seq],
            }
        ],
        sentiment=sentiment,
        suggested_opener=(
            f"Hello, I am an SSRA officer and I can see your inquiry regarding '{redacted_goal[:60]}' — let's resolve this together."
        ),
        turns_covered=len(turns),
        fallback=len(turns) == 0,
    )


@dataclass
class LobbyCallEntry:
    call_id: str
    status: Literal["ai", "transferring", "bridged", "ended"] = "ai"
    topic: str = "general"
    priority: str = "normal"
    language: str = "en"
    waiting_since: float | None = None
    reason: str = ""
    claimed_by: str = ""
    claimed_name: str = ""
    on_hold: bool = False
    needs_callback: bool = False
    risk_level: Literal["none", "watch", "at_risk"] = "none"
    risk_signals: list[str] = field(default_factory=list)
    dismissed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class CallLobbyManager:
    """Server/Console Call Lobby State Machine (`useCallConsoleStore.ts` pattern)."""

    def __init__(self) -> None:
        self.calls: dict[str, LobbyCallEntry] = {}

    def apply_event(self, event_type: str, data: dict[str, Any]) -> LobbyCallEntry:
        call_id = str(data.get("call_id", "")).strip()
        if not call_id:
            raise ValueError("call_id is required")
        entry = self.calls.get(call_id) or LobbyCallEntry(call_id=call_id)
        if event_type == "call.started":
            entry.status = "ai"
        elif event_type == "call.transfer_requested":
            entry.status = "transferring"
            entry.topic = str(data.get("topic", entry.topic))
            entry.priority = str(data.get("priority", "normal"))
            entry.reason = str(data.get("reason", ""))
            entry.waiting_since = float(data.get("waiting_since", 1.0))
            entry.claimed_by = ""
            entry.claimed_name = ""
            entry.dismissed = False
        elif event_type == "call.priority_raised":
            # Raise priority and re-alert without clearing claimed_by or waiting_since
            entry.priority = str(data.get("priority", "urgent"))
            entry.reason = str(data.get("reason", entry.reason))
            entry.dismissed = False
        elif event_type == "call.claimed":
            entry.claimed_by = str(data.get("officer_id", ""))
            entry.claimed_name = str(data.get("officer_name", ""))
        elif event_type == "call.officer_disconnected":
            entry.status = "transferring"
            entry.waiting_since = float(data.get("waiting_since", 1.0))
            entry.reason = "officer_disconnected"
            entry.claimed_by = ""
            entry.claimed_name = ""
        elif event_type == "call.transfer_timed_out":
            entry.status = "ai"
            entry.waiting_since = None
            entry.needs_callback = True
            entry.claimed_by = ""
            entry.claimed_name = ""
        elif event_type == "call.risk":
            lvl = str(data.get("level", "none"))
            entry.risk_level = (
                "at_risk" if lvl == "at_risk" else "watch" if lvl == "watch" else "none"
            )
            entry.risk_signals = [str(s) for s in (data.get("signals") or [])]
        elif event_type == "call.bridged":
            entry.status = "bridged"
            entry.waiting_since = None
        elif event_type == "call.on_hold":
            entry.on_hold = bool(data.get("on", False))
        elif event_type in {"call.ended", "call.wrapped_up"}:
            entry.status = "ended"
            self.calls.pop(call_id, None)
            return entry
        self.calls[call_id] = entry
        return entry


_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
MAX_CARRYOVER_CONTEXT_CHARS = 240


@dataclass(frozen=True)
class ChatToCallCarryover:
    conversation_id: str
    topic_id: str
    topic_label: str
    tax_domain: str
    context: str
    local_models_only: bool = True


def build_chat_to_call_carryover(
    *,
    conversation_id: str,
    owner_user_id: str | None,
    owner_session_id: str | None,
    caller_user_id: str | None = None,
    caller_session_id: str | None = None,
    topic_id: str = "general_tax",
    topic_label: str = "General tax inquiry",
    tax_domain: str = "domestic_tax",
) -> ChatToCallCarryover | None:
    """G122 Cross-Channel Chat-to-Call Carryover (`test_call_carryover.py`):

    1. Rejects malformed IDs (`../conversations`, spaces).
    2. A `conversation_id` alone unlocks nothing: caller must match `owner_user_id` or `owner_session_id`.
    3. Emits ONLY a coarse English task account (<= 240 chars) — never the taxpayer's verbatim words.
    4. Forces `local_models_only = True` on all voice call turns.
    """
    if not _SAFE_ID_RE.match(conversation_id):
        return None
    if caller_user_id and not _SAFE_ID_RE.match(caller_user_id):
        return None
    if caller_session_id and not _SAFE_ID_RE.match(caller_session_id):
        return None

    user_matched = bool(owner_user_id and caller_user_id and owner_user_id == caller_user_id)
    session_matched = bool(
        not owner_user_id
        and owner_session_id
        and caller_session_id
        and owner_session_id == caller_session_id
    )
    if not (user_matched or session_matched):
        return None

    coarse = f"Current task: {topic_label}. Tax domains discussed: {tax_domain}."[
        :MAX_CARRYOVER_CONTEXT_CHARS
    ]
    return ChatToCallCarryover(
        conversation_id=conversation_id,
        topic_id=topic_id,
        topic_label=topic_label,
        tax_domain=tax_domain,
        context=coarse,
        local_models_only=True,
    )


def validate_call_wrap_up(
    *,
    note: str,
    outcome: Literal["resolved", "escalated", "callback_scheduled"],
    caller_satisfaction: int | None,
    caller_satisfaction_status: Literal["answered", "not_said"],
    ai_rating: int | None = None,
) -> dict[str, Any]:
    """Validate Officer Call Wrap-Up (`WrapUpPanel.tsx` pattern)."""
    cleaned_note = note.strip()
    if not cleaned_note:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Please provide a call wrap-up note",
            status_code=400,
        )
    if caller_satisfaction_status == "answered":
        if caller_satisfaction is None or not (1 <= caller_satisfaction <= 5):
            raise SSRAError(
                McpErrorCode.VALIDATION_FAILED,
                "Record how satisfied the caller said they were (1..5), or mark that they didn't say",
                status_code=400,
            )
    if ai_rating is not None and not (1 <= ai_rating <= 5):
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "Optional AI pre-transfer rating must be between 1 and 5",
            status_code=400,
        )
    return {
        "note": redact_pii(cleaned_note).redacted_text,
        "outcome": outcome,
        "caller_satisfaction": None
        if caller_satisfaction_status == "not_said"
        else caller_satisfaction,
        "caller_satisfaction_status": caller_satisfaction_status,
        "ai_rating": ai_rating,
    }


__all__ = [
    "ASR_MODEL_BY_LOCALE",
    "MAX_CARRYOVER_CONTEXT_CHARS",
    "MAX_COMPRESSED_AUDIO_BYTES",
    "MAX_DECODED_PCM_BYTES",
    "MAX_VOICE_WER_GATE",
    "TTS_MODEL_BY_LOCALE",
    "BriefClaim",
    "CallLobbyManager",
    "ChatToCallCarryover",
    "HfVoiceModelDescriptor",
    "LobbyCallEntry",
    "OfficerCallBrief",
    "VoiceSessionDecision",
    "VoiceWebSocketConcurrencyGuard",
    "build_chat_to_call_carryover",
    "generate_officer_call_brief",
    "is_voice_language_approved",
    "resolve_hf_voice_model_cache",
    "route_voice_turn",
    "synthesize_tts_speech_envelope",
    "validate_audio_pcm_expansion_budget",
    "validate_call_wrap_up",
]
