"""Phase 4 Voice/IVR ASR, TTS/MMS, Call Receptionist, Officer Call Brief & Lobby Engine (Section 11, CVE-2026-54233)."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Literal, Protocol

from ssra_core import LocaleCode, McpErrorCode, SSRAError
from ssra_security import redact_pii

# Launch a language on voice only after its word-error rate on SSRA test sets meets the gate (<= 0.12)
MAX_VOICE_WER_GATE: float = 0.12
MIN_UTTERANCE_ASR_CONFIDENCE: float = 0.75
MAX_VOICE_SPOKEN_SENTENCES: int = 3
MAX_SMS_CONTINUATION_CHARS: int = 160

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
    voice: str | None = None,
    hf_home: str = "/home/developer/huggingface_cache",
    recommended_tone: Literal[
        "standard_clear",
        "reassuring_step_by_step",
        "concise_urgent",
        "empathetic_deescalation",
    ] = "standard_clear",
) -> dict[str, Any]:
    """Build deterministic offline HuggingFace MMS-TTS / Orpheus synthesis envelope with locale-validated speaker tag and EQ prosody modulation."""
    desc = resolve_hf_voice_model_cache(locale, hf_home=hf_home)
    resolved_voice = resolve_tts_voice(locale.value, voice)
    speaking_rate = (
        0.92 if recommended_tone in ("reassuring_step_by_step", "empathetic_deescalation") else 1.0
    )
    sentence_pause_ms = (
        350 if recommended_tone in ("reassuring_step_by_step", "empathetic_deescalation") else 200
    )
    return {
        "tts_model": desc.tts_repo_id,
        "voice": resolved_voice,
        "locale": locale.value,
        "hf_cache_dir": desc.hf_cache_dir,
        "local_files_only": desc.local_files_only,
        "sample_rate_hz": 16000,
        "text_length": len(text.strip()),
        "recommended_tone": recommended_tone,
        "speaking_rate": speaking_rate,
        "sentence_pause_ms": sentence_pause_ms,
    }


def build_voice_prosody_eq_metadata(
    *,
    barge_in_count: int = 0,
    rms_energy_delta: float = 0.0,
    speech_rate_ratio: float = 1.0,
    consecutive_low_confidence_turns: int = 0,
) -> dict[str, str]:
    """Serialize voice acoustic prosody features into string metadata for `ConversationEvent.data.metadata`."""
    return {
        "voice_barge_in_count": str(max(0, barge_in_count)),
        "voice_rms_energy_delta": f"{max(0.0, rms_energy_delta):.2f}",
        "voice_speech_rate_ratio": f"{max(0.5, speech_rate_ratio):.2f}",
        "consecutive_low_confidence_turns": str(max(0, consecutive_low_confidence_turns)),
    }


@dataclass(frozen=True)
class VoiceWerEvidence:
    """A measured word-error rate for one language on a named SSRA test set (OQ-008)."""

    locale: LocaleCode
    word_error_rate: float
    test_set: str
    measured_on: date
    utterance_count: int


# Governed launch evidence for voice languages. An entry needs an SSRA-approved measurement on an
# SSRA test set (OQ-008). There is none yet, so every language routes callers to an officer.
APPROVED_VOICE_WER_EVIDENCE: Mapping[LocaleCode, VoiceWerEvidence] = MappingProxyType({})


def _wer_gate_failure(
    locale: LocaleCode, evidence: Mapping[LocaleCode, VoiceWerEvidence]
) -> str | None:
    """Return why a language may not run on voice, or None when its evidence meets the gate."""
    record = evidence.get(locale)
    if (
        record is None
        or record.locale != locale
        or record.utterance_count <= 0
        or not record.test_set.strip()
        or not math.isfinite(record.word_error_rate)
        or record.word_error_rate < 0.0
    ):
        return f"no approved word-error-rate evidence for {locale.value} (OQ-008)"
    if record.word_error_rate > MAX_VOICE_WER_GATE:
        return (
            f"{locale.value} word-error rate {record.word_error_rate:.2f} on {record.test_set} "
            f"is above the {MAX_VOICE_WER_GATE:.2f} gate"
        )
    return None


def is_voice_language_approved(
    locale: LocaleCode,
    evidence: Mapping[LocaleCode, VoiceWerEvidence] = APPROVED_VOICE_WER_EVIDENCE,
) -> bool:
    """Return whether governed word-error-rate evidence allows this language on voice."""
    return _wer_gate_failure(locale, evidence) is None


def route_voice_turn(
    *,
    session_id: str,
    locale: LocaleCode,
    recording_consent_granted: bool,
    wer_evidence: Mapping[LocaleCode, VoiceWerEvidence] = APPROVED_VOICE_WER_EVIDENCE,
    dtmf_digit: str | None = None,
    barge_in_detected: bool = False,
    utterance_confidence: float = 0.95,
    consecutive_low_confidence_turns: int = 0,
    enable_spoken_clarify_gate: bool = False,
) -> VoiceSessionDecision:
    """Route a voice turn across ASR, spoken ClarifyGate, hybrid DTMF disambiguation, and progressive warm transfer."""
    _ = barge_in_detected
    asr_engine = ASR_MODEL_BY_LOCALE[locale]
    tts_engine = TTS_MODEL_BY_LOCALE[locale]

    transfer_reasons = [
        reason
        for reason in (
            "caller pressed 0 for an officer" if dtmf_digit == "0" else None,
            _wer_gate_failure(locale, wer_evidence),
            f"{consecutive_low_confidence_turns} consecutive low-confidence turns"
            if consecutive_low_confidence_turns >= 2
            else None,
        )
        if reason
    ]
    if transfer_reasons:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            action="WARM_TRANSFER_TO_OFFICER",
            warm_transfer_summary=(
                f"Warm transfer from IVR ({locale.value}): {'; '.join(transfer_reasons)}."
            ),
        )

    should_clarify = (
        enable_spoken_clarify_gate
        and dtmf_digit is None
        and 0.60 <= utterance_confidence < MIN_UTTERANCE_ASR_CONFIDENCE
        and consecutive_low_confidence_turns <= 1
    )
    if should_clarify:
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            action="CLARIFY_INTENT_SPOKEN",
        )

    if dtmf_digit is not None or utterance_confidence < MIN_UTTERANCE_ASR_CONFIDENCE:
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
    """P1-9 Multi-Pool Voice/Call/Chat WebSocket Concurrency Cap & Slot Rekeying (`test_voice_ws_hardening.py`)."""

    def __init__(self, *, per_user_cap: int = 3, global_cap: int = 64) -> None:
        self.per_user_cap = max(1, per_user_cap)
        self.global_cap = max(1, global_cap)
        self._by_pool_user: dict[str, dict[str, int]] = {}
        self._total_by_pool: dict[str, int] = {}

    def active_count(self, pool: str = "voice") -> int:
        return self._total_by_pool.get(pool, 0)

    def try_acquire(self, user_key: str, *, pool: str = "voice") -> tuple[bool, int | None]:
        pool_users = self._by_pool_user.setdefault(pool, {})
        current = pool_users.get(user_key, 0)
        total = self._total_by_pool.get(pool, 0)
        if current >= self.per_user_cap or total >= self.global_cap:
            return False, 1013
        pool_users[user_key] = current + 1
        self._total_by_pool[pool] = total + 1
        return True, None

    def rekey_slot(
        self,
        old_user_key: str,
        new_user_key: str,
        *,
        pool: str = "voice",
        authenticated_per_user_cap: int | None = None,
    ) -> bool:
        """Atomically rekey an anonymous slot (`anon::ip`) to an authenticated `user_id` without changing pool total."""
        pool_users = self._by_pool_user.setdefault(pool, {})
        old_count = pool_users.get(old_user_key, 0)
        if old_count <= 0:
            return False
        if old_user_key == new_user_key:
            return True
        cap = (
            self.per_user_cap if authenticated_per_user_cap is None else authenticated_per_user_cap
        )
        new_count = pool_users.get(new_user_key, 0)
        if new_count >= cap:
            return False
        if old_count == 1:
            pool_users.pop(old_user_key, None)
        else:
            pool_users[old_user_key] = old_count - 1
        pool_users[new_user_key] = new_count + 1
        return True

    def release(self, user_key: str, *, pool: str = "voice") -> None:
        pool_users = self._by_pool_user.setdefault(pool, {})
        current = pool_users.get(user_key, 0)
        if current <= 0:
            return
        if current <= 1:
            pool_users.pop(user_key, None)
        else:
            pool_users[user_key] = current - 1
        self._total_by_pool[pool] = max(0, self._total_by_pool.get(pool, 0) - 1)


def is_ws_origin_allowed(
    origin: str | None,
    allowed_origins: set[str] | frozenset[str],
    *,
    require_origin: bool = True,
) -> bool:
    """Validate WebSocket `Origin` header (`test_voice_ws_hardening.py` & `CVE-2026-27978`)."""
    if not origin or origin.strip().lower() == "null":
        return not require_origin
    return origin.strip() in allowed_origins


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
    # The model that wrote the brief; None when it was built by the keyword rules below.
    model: str | None = None
    fallback: bool = False
    verified_artifacts: list[dict[str, Any]] = field(default_factory=list)
    recommended_officer_action: str = "Review verified e-Tax context and confirm next step"


_DISTRESS_WORDS_RE = re.compile(r"\b(?:urgent|blocked|seized|distress(?:ed)?)\b")
_FRUSTRATION_WORDS_RE = re.compile(r"\b(?:error|failed|frustrated|wrong)\b")
_CONFUSION_WORDS_RE = re.compile(r"\b(?:confused|confusing|understand)\b")


def _turn_seqs(turn: dict[str, Any] | None) -> list[int]:
    """Return a turn's sequence number as evidence, or nothing when it has no valid one."""
    seq = turn.get("seq") if turn is not None else None
    return [seq] if isinstance(seq, int) and not isinstance(seq, bool) and seq > 0 else []


def _redacted_turn_text(turn: dict[str, Any], limit: int) -> str:
    """Redact a turn before shortening it, so truncation cannot split an identifier past redaction."""
    return redact_pii(str(turn.get("text", ""))).redacted_text[:limit]


def generate_officer_call_brief(
    *,
    call_id: str,
    turns: list[dict[str, Any]],
    transfer_reason: str,
    verified_artifacts: list[dict[str, Any]] | None = None,
) -> OfficerCallBrief:
    """Build the 10-second Officer Call Brief (`CallBriefCard.tsx`) with turn-sequence evidence links.

    The brief is assembled by keyword rules, not by a model, so ``model`` is None. It states only
    what the turns support: the caller's first and latest requests, the assistant's latest replies,
    and the transfer reason it was given.
    """
    caller_turns = [
        t for t in turns if t.get("speaker") == "caller" and str(t.get("text", "")).strip()
    ]
    ai_turns = [
        t for t in turns if t.get("speaker") == "assistant" and str(t.get("text", "")).strip()
    ]
    first_caller = caller_turns[0] if caller_turns else None
    last_caller = caller_turns[-1] if caller_turns else None
    redacted_goal = (
        _redacted_turn_text(first_caller, 240)
        if first_caller is not None
        else "The caller has not stated a goal yet"
    )

    ai_claims = [
        BriefClaim(text=_redacted_turn_text(t, 140), turn_seqs=_turn_seqs(t)) for t in ai_turns[-3:]
    ]

    combined_lower = " ".join(str(t.get("text", "")).lower() for t in caller_turns)
    sentiment: Literal["calm", "confused", "frustrated", "distressed"] = "calm"
    if _DISTRESS_WORDS_RE.search(combined_lower):
        sentiment = "distressed"
    elif _FRUSTRATION_WORDS_RE.search(combined_lower):
        sentiment = "frustrated"
    elif _CONFUSION_WORDS_RE.search(combined_lower):
        sentiment = "confused"

    return OfficerCallBrief(
        call_id=call_id,
        why_officer=BriefClaim(text=transfer_reason, turn_seqs=_turn_seqs(last_caller)),
        caller_goal=BriefClaim(text=redacted_goal, turn_seqs=_turn_seqs(first_caller)),
        ai_already_said=ai_claims,
        still_open=[
            BriefClaim(
                text=f"Latest caller request: {_redacted_turn_text(last_caller, 140)}",
                turn_seqs=_turn_seqs(last_caller),
            )
        ]
        if last_caller is not None
        else [],
        details_given=[
            {
                "label": "First caller message (redacted)",
                "value": redacted_goal[:80],
                "turn_seqs": _turn_seqs(first_caller),
            }
        ]
        if first_caller is not None
        else [],
        sentiment=sentiment,
        suggested_opener=(
            "Hello, I'm an SSRA officer. I have the notes from your call with the automated "
            "assistant. Let's go through your question together."
        ),
        turns_covered=len(turns),
        fallback=len(turns) == 0,
        verified_artifacts=list(verified_artifacts or []),
        recommended_officer_action=(
            f"Priority de-escalation & verify {transfer_reason.lower()}"
            if sentiment in ("distressed", "frustrated")
            else f"Verify {transfer_reason.lower()} and guide next e-Tax step"
        ),
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


LOBBY_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "call.started",
        "call.transfer_requested",
        "call.priority_raised",
        "call.claimed",
        "call.officer_disconnected",
        "call.transfer_timed_out",
        "call.risk",
        "call.bridged",
        "call.on_hold",
        "call.ended",
        "call.wrapped_up",
    }
)
LOBBY_PRIORITIES: frozenset[str] = frozenset({"normal", "high", "urgent"})
MAX_ENDED_CALL_TOMBSTONES: int = 4096


def _optional_timestamp(value: Any) -> float | None:
    """Return a provided wait-start timestamp, or None when the event supplied no usable one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    timestamp = float(value)
    return timestamp if math.isfinite(timestamp) else None


class CallLobbyManager:
    """Server/Console Call Lobby State Machine (`useCallConsoleStore.ts` pattern).

    The first officer to claim a waiting call owns it, ended calls cannot be revived by late
    events, and unknown event types are rejected. Only ``call.started`` can add a call, so a late
    event for an ended call whose tombstone has been evicted is rejected rather than reviving it.
    Each event is validated before the stored entry is changed.
    """

    def __init__(self) -> None:
        self.calls: dict[str, LobbyCallEntry] = {}
        self._ended: OrderedDict[str, None] = OrderedDict()

    def apply_event(self, event_type: str, data: dict[str, Any]) -> LobbyCallEntry:
        if event_type not in LOBBY_EVENT_TYPES:
            raise ValueError(f"Unsupported call lobby event '{event_type}'")
        call_id = str(data.get("call_id", "")).strip()
        if not call_id:
            raise ValueError("call_id is required")
        if call_id in self._ended:
            return LobbyCallEntry(call_id=call_id, status="ended")
        entry = self.calls.get(call_id)
        if entry is None:
            if event_type in {"call.ended", "call.wrapped_up"}:
                self._remember_ended(call_id)
                return LobbyCallEntry(call_id=call_id, status="ended")
            if event_type != "call.started":
                raise ValueError(
                    f"Call {call_id} is not in the lobby; only call.started can add it"
                )
            entry = LobbyCallEntry(call_id=call_id)
        if event_type == "call.started":
            entry.status = "ai"
        elif event_type == "call.transfer_requested":
            priority = _lobby_priority(data.get("priority", "normal"))
            entry.status = "transferring"
            entry.topic = str(data.get("topic", entry.topic))
            entry.priority = priority
            entry.reason = str(data.get("reason", ""))
            entry.waiting_since = _optional_timestamp(data.get("waiting_since"))
            entry.claimed_by = ""
            entry.claimed_name = ""
            entry.dismissed = False
        elif event_type == "call.priority_raised":
            # Raise priority and re-alert without clearing claimed_by or waiting_since
            entry.priority = _lobby_priority(data.get("priority", "urgent"))
            entry.reason = str(data.get("reason", entry.reason))
            entry.dismissed = False
        elif event_type == "call.claimed":
            officer_id = str(data.get("officer_id", "")).strip()
            if not officer_id:
                raise ValueError("officer_id is required to claim a call")
            if entry.status != "transferring":
                raise ValueError(f"Call {call_id} is not waiting for an officer")
            if entry.claimed_by and entry.claimed_by != officer_id:
                raise ValueError(f"Call {call_id} is already claimed by another officer")
            entry.claimed_by = officer_id
            entry.claimed_name = str(data.get("officer_name", ""))
        elif event_type == "call.officer_disconnected":
            entry.status = "transferring"
            entry.waiting_since = _optional_timestamp(data.get("waiting_since"))
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
            self._remember_ended(call_id)
            return entry
        self.calls[call_id] = entry
        return entry

    def _remember_ended(self, call_id: str) -> None:
        self._ended[call_id] = None
        if len(self._ended) > MAX_ENDED_CALL_TOMBSTONES:
            self._ended.popitem(last=False)


def _lobby_priority(value: Any) -> str:
    """Accept only the lobby's known priority levels."""
    priority = str(value).strip().lower()
    if priority not in LOBBY_PRIORITIES:
        raise ValueError(f"Unsupported call priority '{value}'")
    return priority


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


# Per-locale TTS Speaker Catalog (`test_sunbird_voice_selection.py` pattern):
# Every default speaker is first in its own locale catalog, and every tag is unique & locale-scoped.
TTS_VOICE_CATALOG: dict[str, tuple[str, ...]] = {
    "en": ("ssra_eng_0001", "ssra_eng_0002"),
    "ar": ("ssra_ara_0001", "ssra_ara_0002"),
    "pga": ("ssra_pga_0001", "ssra_pga_0002"),
    "din": ("ssra_din_0001", "ssra_din_0002"),
    "nus": ("ssra_nus_0001", "ssra_nus_0002"),
    "bfa": ("ssra_bfa_0001", "ssra_bfa_0002"),
    "zne": ("ssra_zne_0001", "ssra_zne_0002"),
    "shk": ("ssra_shk_0001", "ssra_shk_0002"),
}
TTS_DEFAULT_VOICE: dict[str, str] = {loc: tags[0] for loc, tags in TTS_VOICE_CATALOG.items()}


def resolve_tts_voice(locale: str, requested_voice: str | None = None) -> str | None:
    """Resolve a locale-scoped TTS speaker tag (`test_sunbird_voice_selection.py`):
    - Returns `None` for unknown locales (`"xx"`).
    - Replaces `None`, empty strings, foreign backend names (`en-US-AriaNeural`), or tags
      belonging to another locale with `TTS_DEFAULT_VOICE[locale]`.
    """
    loc = (locale or "").strip().lower()
    catalog = TTS_VOICE_CATALOG.get(loc)
    if not catalog:
        return None
    if requested_voice and requested_voice in catalog:
        return requested_voice
    return TTS_DEFAULT_VOICE[loc]


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_ABBREV_PROTECT_RE = re.compile(
    r"\b(Sec|Reg|Art|No|Vol|Ch|Pt|Dr|Mr|Mrs|Ms)\.\s+",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class VADConfig:
    """Energy-based Voice Activity Detection thresholds (`voice_stream.py`)."""

    energy_threshold: float = 0.015
    silence_duration_ms: int = 600
    min_speech_duration_ms: int = 250
    max_utterance_s: float = 30.0
    sample_rate: int = 16_000

    @classmethod
    def from_sensitivity(cls, sensitivity: str = "medium", sample_rate: int = 16_000) -> VADConfig:
        """Construct a `VADConfig` preset from a named sensitivity level (`low`, `medium`, `high`)."""
        presets = {
            "low": cls(energy_threshold=0.025, silence_duration_ms=800, sample_rate=sample_rate),
            "medium": cls(energy_threshold=0.015, silence_duration_ms=600, sample_rate=sample_rate),
            "high": cls(energy_threshold=0.008, silence_duration_ms=400, sample_rate=sample_rate),
        }
        return presets.get(sensitivity.lower(), presets["medium"])


def split_tts_sentences(text: str) -> list[str]:
    """Split reply text into sentence chunks while preserving statutory abbreviations (`Sec. 18`, `Reg. 1.21`)."""
    cleaned = text.strip()
    if not cleaned:
        return []
    protected = _ABBREV_PROTECT_RE.sub(r"\1<DOT> ", cleaned)
    return [
        s.replace("<DOT>", ".").strip() for s in _SENTENCE_SPLIT_RE.split(protected) if s.strip()
    ]


class VoiceStreamSession:
    """V2 Streaming Voice Session (`voice_stream_v2.py`): sentence-chunked TTS, full-duplex barge-in & speculative prefetch."""

    def __init__(
        self, *, session_id: str, locale: LocaleCode, vad: VADConfig | None = None
    ) -> None:
        """Initialize a streaming voice session with VAD thresholds and full-duplex barge-in state."""
        self.session_id = session_id
        self.locale = locale
        self.vad = vad or VADConfig.from_sensitivity("medium")
        self.barge_in_cancelled = False
        self.interrupted_at_sentence_index: int | None = None
        self.unspoken_sentences: list[str] = []
        self.speculative_prefetches: list[str] = []

    def trigger_barge_in(self, *, sentence_index: int | None = None) -> None:
        """Cancel active TTS playback immediately (<80ms) on caller barge-in and record interrupt index."""
        if sentence_index is None:
            self.barge_in_cancelled = True
        else:
            self.interrupted_at_sentence_index = max(0, sentence_index)

    def reset_barge_in(self) -> None:
        """Reset per-turn barge-in interruption state before streaming the next reply."""
        self.barge_in_cancelled = False
        self.interrupted_at_sentence_index = None
        self.unspoken_sentences = []

    def record_partial_transcript(self, partial_text: str) -> str | None:
        """Record a 4-word stable partial transcript prefix for speculative retrieval prefetch."""
        words = [w for w in partial_text.strip().split() if w]
        if len(words) >= 3:
            stable_prefix = " ".join(words[:4])
            self.speculative_prefetches.append(stable_prefix)
            return stable_prefix
        return None

    def stream_tts_sentences(self, text: str, *, voice: str | None = None) -> list[dict[str, Any]]:
        """Synthesize reply sentences in order, halting on barge-in and recording unspoken sentences."""
        sentences = split_tts_sentences(text)
        chunks: list[dict[str, Any]] = []
        self.unspoken_sentences = []
        for idx, sentence in enumerate(sentences):
            if self.barge_in_cancelled or (
                self.interrupted_at_sentence_index is not None
                and idx >= self.interrupted_at_sentence_index
            ):
                self.unspoken_sentences = sentences[idx:]
                break
            env = synthesize_tts_speech_envelope(text=sentence, locale=self.locale, voice=voice)
            env["sentence_index"] = idx
            env["sentence_text"] = sentence
            chunks.append(env)
        return chunks

    def resume_after_network_drop(
        self,
        text: str,
        *,
        last_acked_sentence_index: int,
        voice: str | None = None,
    ) -> list[dict[str, Any]]:
        """Resume sentence-chunked TTS after a transient 2G WebSocket/WebRTC drop from `last_acked_sentence_index + 1`."""
        self.reset_barge_in()
        all_chunks = self.stream_tts_sentences(text, voice=voice)
        return [c for c in all_chunks if int(c["sentence_index"]) > last_acked_sentence_index]


VOICE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "recording_start",
        "recording_end",
        "transcript_stored",
        "audio_deleted",
        "consent_checked",
        "consent_denied",
        "retention_cleanup",
        "session_start",
        "session_end",
        "barge_in",
        "call_started",
        "call_transferred",
        "officer_joined",
        "call_ended",
        "staff_viewed_call",
        "staff_viewed_brief",
        "staff_viewed_caller_history",
        "staff_listened_call",
        "officer_claimed",
        "officer_released",
        "officer_ended_call",
        "officer_hold_on",
        "officer_hold_off",
        "officer_transferred",
        "officer_wrapup_saved",
        "officer_callback_done",
    }
)


@dataclass(frozen=True)
class VoiceRetentionPolicy:
    """Voice retention periods. None means no approved period (OQ-009 item 1): keep nothing after the call."""

    raw_audio_ttl_hours: int | None = None
    transcript_ttl_days: int | None = None
    analytics_ttl_days: int | None = None
    store_raw_audio: bool = False

    def __post_init__(self) -> None:
        if self.store_raw_audio and self.raw_audio_ttl_hours is None:
            raise ValueError(
                "Raw call audio cannot be stored without an approved retention period (OQ-009)"
            )


def build_voice_consent_audit_entry(
    *,
    event_type: str,
    session_id: str,
    audio_bytes: bytes = b"",
    policy: VoiceRetentionPolicy | None = None,
) -> dict[str, Any]:
    """Record a privacy-preserving voice audit entry (`voice_consent.py`):
    Raw audio is never stored by default — only its SHA-256 hash is logged.
    """
    if event_type not in VOICE_EVENT_TYPES:
        raise ValueError(f"Unsupported voice audit event_type '{event_type}'")
    active_policy = policy or VoiceRetentionPolicy()
    return {
        "event_type": event_type,
        "session_id": session_id,
        "audio_sha256": hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else None,
        "raw_audio_stored": active_policy.store_raw_audio,
        "transcript_ttl_days": active_policy.transcript_ttl_days,
        "retention_status": "approved"
        if active_policy.transcript_ttl_days is not None
        else "pending_oq_009",
    }


def looks_like_valid_audio_bytes(data: bytes) -> bool:
    """Verify binary audio container headers (`TestAudioSniff` in `test_voice_robustness.py`):
    Accepts WAV (`RIFF....WAVE`), Ogg/Opus (`OggS`), MP3 (`ID3` / `\\xff\\xfb` / `\\xff\\xf3`), or FLAC (`fLaC`) >= 32 bytes;
    rejects HTML error pages (`<html>rate limited</html>`), RIFF/WEBP images, or truncated headers (`b"RIFF"`).
    """
    if len(data) < 32:
        return False
    return (data.startswith(b"RIFF") and data[8:12] == b"WAVE") or data.startswith(
        (b"OggS", b"ID3", b"\xff\xfb", b"\xff\xf3", b"fLaC")
    )


@dataclass(frozen=True)
class TtsCachedAudio:
    audio: bytes
    backend: str
    voice: str
    language: str
    latency_ms: float
    error: str | None = None


class TtsSynthesizer(Protocol):
    def __call__(self, text: str, /, *, language: str, voice: str) -> TtsCachedAudio: ...


def _normalize_phrase(text: str) -> str:
    return " ".join(text.split())


class TtsPhraseCache:
    """Bounded LRU TTS Phrase Cache (`TestTtsPhraseCache` in `test_voice_robustness.py`):
    Serves repeated phrases with `backend='<engine>+cache'` and `latency_ms=0.0`, and never caches failures.

    The cache is shared across calls, so it stores audio only for fixed, non-personal prompts
    (``fixed_voice_prompts()`` by default). Any other text is synthesized and returned without
    being kept.
    """

    def __init__(
        self, *, max_entries: int = 256, cacheable_phrases: frozenset[str] | None = None
    ) -> None:
        self.max_entries = max(1, max_entries)
        phrases = fixed_voice_prompts() if cacheable_phrases is None else cacheable_phrases
        self._cacheable = frozenset(_normalize_phrase(p) for p in phrases)
        self._store: OrderedDict[str, TtsCachedAudio] = OrderedDict()

    @staticmethod
    def _make_key(text: str, *, language: str, voice: str) -> str:
        norm = " ".join(text.strip().lower().split())
        digest = hashlib.sha256(f"{language}:{voice}:{norm}".encode()).hexdigest()
        return f"tts:{language}:{voice}:{digest}"

    def get_or_synthesize(
        self,
        text: str,
        *,
        language: str,
        voice: str | None,
        synthesizer: TtsSynthesizer,
    ) -> TtsCachedAudio:
        resolved_voice = resolve_tts_voice(language, voice)
        if resolved_voice is None:
            return TtsCachedAudio(
                audio=b"",
                backend="error",
                voice="",
                language=language,
                latency_ms=0.0,
                error=f"Unsupported TTS locale '{language}'",
            )
        if _normalize_phrase(text) not in self._cacheable:
            return synthesizer(text, language=language, voice=resolved_voice)
        key = self._make_key(text, language=language, voice=resolved_voice)
        cached = self._store.get(key)
        if cached is not None:
            self._store.move_to_end(key)
            return TtsCachedAudio(
                audio=cached.audio,
                backend=f"{cached.backend}+cache",
                voice=cached.voice,
                language=cached.language,
                latency_ms=0.0,
            )
        fresh: TtsCachedAudio = synthesizer(text, language=language, voice=resolved_voice)
        if not fresh.error and looks_like_valid_audio_bytes(fresh.audio):
            if len(self._store) >= self.max_entries:
                self._store.popitem(last=False)
            self._store[key] = fresh
        return fresh


def resolve_mt_and_tts_turn_plan(
    *,
    source_locale: str,
    original_transcript: str,
    inbound_translated_en: str | None,
    english_reply_text: str,
    outbound_translated_text: str | None,
    requested_voice: str | None = None,
) -> dict[str, Any]:
    """Honest MT Degradation & Language-Matched Voice Selection (`TestMtDegradation` in `test_voice_robustness.py`):
    1. If inbound MT (`source_locale -> en`) fails, pass `original_transcript` labeled with `source_locale` (never mislabeled as `en`).
    2. If outbound MT (`en -> source_locale`) fails, speak `english_reply_text` using the `en` TTS voice (`ssra_eng_0001`), never mangling English with a local-language voice.
    """
    src = source_locale.strip().lower()
    mt_degraded: list[str] = []

    if src == "en":
        llm_locale = "en"
        llm_message = original_transcript
    elif inbound_translated_en and inbound_translated_en.strip():
        llm_locale = "en"
        llm_message = inbound_translated_en.strip()
    else:
        mt_degraded.append(f"{src}-en")
        llm_locale = src
        llm_message = original_transcript

    if src == "en":
        reply_language = "en"
        spoken_text = english_reply_text
    elif outbound_translated_text and outbound_translated_text.strip():
        reply_language = src
        spoken_text = outbound_translated_text.strip()
    else:
        mt_degraded.append(f"en-{src}")
        reply_language = "en"
        spoken_text = english_reply_text

    tts_voice = resolve_tts_voice(
        reply_language, requested_voice if reply_language == src else None
    )
    return {
        "llm_locale": llm_locale,
        "llm_message": llm_message,
        "reply_language": reply_language,
        "spoken_text": spoken_text,
        "tts_voice": tts_voice,
        "mt_degraded": mt_degraded,
    }


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


@dataclass(frozen=True)
class VoiceDtmfStepUpResult:
    authorized: bool
    action: Literal[
        "BOUND_T1", "BOUND_T3", "REJECTED_SPOKEN_OTP", "OTP_REJECTED", "WARM_TRANSFER_TO_OFFICER"
    ]
    tin_masked: str | None
    recording_paused_for_dtmf: bool
    reason: str | None = None


# Checks a keypad OTP for a TIN against the approved identity provider (OQ-005). It must compare
# in constant time and enforce the provider's own expiry and single use.
OtpVerifier = Callable[[str, str], bool]
MAX_DTMF_STEP_UP_ATTEMPTS: int = 3


class StepUpAttemptStore(Protocol):
    """Per-call count of rejected keypad codes, kept for the life of the call in durable state (OQ-015)."""

    def failed_attempts(self, call_id: str) -> int: ...

    def record_failed_attempt(self, call_id: str) -> int:
        """Add one rejected code for the call and return the new total."""
        ...


def verify_voice_dtmf_step_up(
    *,
    dtmf_tin_digits: str,
    dtmf_otp_digits: str,
    input_modality: Literal["dtmf_rfc4733", "spoken_asr"] = "dtmf_rfc4733",
    requested_tier: Literal["T1", "T2", "T3", "T4"] = "T1",
    sim_swap_recent: bool = False,
    otp_verifier: OtpVerifier | None = None,
    call_id: str,
    attempt_store: StepUpAttemptStore,
) -> VoiceDtmfStepUpResult:
    """Enforce RFC 4733 DTMF-only TIN/OTP entry with recording pause and SIM-swap / T4 guards.

    Well-formed digits are not proof of identity. The OTP must be confirmed by an approved
    ``otp_verifier``; without one the call goes to an officer instead of binding a subject. Each
    rejected code is recorded in ``attempt_store`` against ``call_id``, so the three-attempt limit
    cannot be reset by the caller. If the verifier or the store fails, nothing is bound and the call
    goes to an officer.
    """
    if requested_tier == "T4" or sim_swap_recent:
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="WARM_TRANSFER_TO_OFFICER",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="T4 action or recent SIM-swap signal requires live SSRA officer",
        )
    if input_modality != "dtmf_rfc4733":
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="REJECTED_SPOKEN_OTP",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="Spoken TIN/OTP over ASR is prohibited; enter digits on telephone keypad (DTMF)",
        )
    clean_tin = "".join(ch for ch in dtmf_tin_digits if ch in "0123456789")
    clean_otp = "".join(ch for ch in dtmf_otp_digits if ch in "0123456789")
    if not (9 <= len(clean_tin) <= 12) or len(clean_otp) != 6:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "DTMF step-up requires 9..12 ASCII TIN digits and 6 ASCII OTP digits",
            status_code=400,
        )
    if not call_id.strip():
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "DTMF step-up requires the call_id that keypad attempts are counted against",
            status_code=400,
        )
    too_many_attempts = VoiceDtmfStepUpResult(
        authorized=False,
        action="WARM_TRANSFER_TO_OFFICER",
        tin_masked=None,
        recording_paused_for_dtmf=True,
        reason="Too many keypad verification attempts on this call",
    )
    if otp_verifier is None:
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="WARM_TRANSFER_TO_OFFICER",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="No approved OTP verifier is configured (OQ-005); identity cannot be confirmed on this call",
        )
    try:
        if attempt_store.failed_attempts(call_id) >= MAX_DTMF_STEP_UP_ATTEMPTS:
            return too_many_attempts
        if otp_verifier(clean_tin, clean_otp):
            return VoiceDtmfStepUpResult(
                authorized=True,
                action="BOUND_T3" if requested_tier == "T3" else "BOUND_T1",
                tin_masked=f"••••{clean_tin[-4:]}",
                recording_paused_for_dtmf=True,
            )
        failures = attempt_store.record_failed_attempt(call_id)
    except Exception:
        # A provider or attempt-store failure must never bind a subject, and the caller still needs help.
        return VoiceDtmfStepUpResult(
            authorized=False,
            action="WARM_TRANSFER_TO_OFFICER",
            tin_masked=None,
            recording_paused_for_dtmf=True,
            reason="Identity verification is unavailable on this call",
        )
    if failures >= MAX_DTMF_STEP_UP_ATTEMPTS:
        return too_many_attempts
    return VoiceDtmfStepUpResult(
        authorized=False,
        action="OTP_REJECTED",
        tin_masked=None,
        recording_paused_for_dtmf=True,
        reason="The keypad code was not accepted",
    )


def build_voice_spoken_turn_and_sms_followup(
    *,
    reply_text: str,
    citation_anchor: str | None = None,
    is_estimate: bool = False,
) -> dict[str, Any]:
    """Cap spoken reply at <= 3 sentences with explicit estimate framing and generate a <= 160-char SMS continuation receipt."""
    sentences = split_tts_sentences(reply_text)[:MAX_VOICE_SPOKEN_SENTENCES]
    spoken = " ".join(sentences)
    if is_estimate and "estimate" not in spoken.lower():
        spoken = f"Estimate only. {spoken}"
    anchor_suffix = f" ({citation_anchor})" if citation_anchor else ""
    sms_raw = f"SSRA OFFICIAL: {spoken}{anchor_suffix} Ref: https://etax.nra.gov.ss/"
    sms_text = sms_raw[:MAX_SMS_CONTINUATION_CHARS]
    return {
        "spoken_text": spoken,
        "sentence_count": len(sentences),
        "is_estimate": is_estimate,
        "sms_continuation_text": sms_text,
    }


_EN_APPROVED_TOOL_WAIT_FILLER = "One moment while I check the official SSRA records."

# Only single-script, SSRA-approved fillers are active; Tier B/C locales pending OQ-008 voice clip sign-off fall back safely to _EN_APPROVED_TOOL_WAIT_FILLER
_TOOL_WAIT_FILLERS: dict[LocaleCode, str] = {
    LocaleCode.EN: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.AR: "لحظة واحدة، أتحقق الآن من سجلات هيئة الإيرادات الرسمية.",
    LocaleCode.PGA: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.DIN: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.NUS: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.BFA: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.ZNE: _EN_APPROVED_TOOL_WAIT_FILLER,
    LocaleCode.SHK: _EN_APPROVED_TOOL_WAIT_FILLER,
}


def get_localized_tool_wait_filler(locale: LocaleCode = LocaleCode.EN) -> str:
    """Return a zero-digit, pre-cacheable filler utterance (`<250ms` TTFA) spoken while MCP tools execute."""
    return _TOOL_WAIT_FILLERS.get(locale, _TOOL_WAIT_FILLERS[LocaleCode.EN])


def fixed_voice_prompts() -> frozenset[str]:
    """Return the fixed, non-personal prompts whose audio may be cached and reused across calls."""
    return frozenset(_TOOL_WAIT_FILLERS.values())


@dataclass(frozen=True)
class HybridVoiceRouteDecision:
    """Decision from the October 2026 Hybrid Speech Router."""

    mode: Literal["S2S_FAST_ACK_CACHED", "CASCADED_GOVERNED_STT_LLM_TTS"]
    emit_tool_wait_filler: bool
    filler_text: str | None
    target_ttfa_ms: int
    requires_numeric_provenance: bool


def select_hybrid_voice_execution_mode(
    *,
    locale: LocaleCode = LocaleCode.EN,
    requires_tool_call: bool = True,
    contains_statutory_figures: bool = True,
    is_pure_greeting_or_backchannel: bool = False,
) -> HybridVoiceRouteDecision:
    """Select between `S2S_FAST_ACK_CACHED` (<250ms TTFA) and `CASCADED_GOVERNED_STT_LLM_TTS`.

    Invariant: Any turn involving MCP tools, OPA policies, or statutory figures MUST use
    `CASCADED_GOVERNED_STT_LLM_TTS` (optionally preceded by a pre-cached tool-wait filler).
    """
    is_fast_ack = (
        is_pure_greeting_or_backchannel
        and not requires_tool_call
        and not contains_statutory_figures
    )
    if is_fast_ack:
        return HybridVoiceRouteDecision(
            mode="S2S_FAST_ACK_CACHED",
            emit_tool_wait_filler=False,
            filler_text=None,
            target_ttfa_ms=220,
            requires_numeric_provenance=False,
        )
    filler = get_localized_tool_wait_filler(locale) if requires_tool_call else None
    return HybridVoiceRouteDecision(
        mode="CASCADED_GOVERNED_STT_LLM_TTS",
        emit_tool_wait_filler=requires_tool_call,
        filler_text=filler,
        target_ttfa_ms=240 if requires_tool_call else 380,
        requires_numeric_provenance=True,
    )


_MASKED_TIN_SPEECH_RE = re.compile(r"••••(\d{4})")
_SEC_ANCHOR_SPEECH_RE = re.compile(r"\bPart-([IVX]+)-Sec-(\d+)\b", flags=re.IGNORECASE)


def normalize_statutory_text_for_speech(text: str, locale: LocaleCode = LocaleCode.EN) -> str:
    """Expand statutory anchors, masked TINs, and portal URLs for natural TTS pronunciation without altering numbers."""
    _ = locale
    out = _MASKED_TIN_SPEECH_RE.sub(
        lambda m: f"T I N ending in {' '.join(m.group(1))}",
        text,
    )
    out = _SEC_ANCHOR_SPEECH_RE.sub(
        lambda m: f"Part {m.group(1)}, Section {m.group(2)}",
        out,
    )
    out = out.replace("https://etax.nra.gov.ss/", "e-tax dot n r a dot gov dot s s")
    return out


_NUMERIC_TOKEN_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])")


def verify_spoken_figure_fidelity(
    spoken_text: str,
    expected_numeric_values: list[str] | tuple[str, ...],
    *,
    strict_no_extra_numbers: bool = False,
    allowed_context_numbers: list[str] | tuple[str, ...] = (),
) -> bool:
    """Verify that every required `NumericClaim` value appears as an exact whole numeric token in the TTS-prepared text."""
    spoken_tokens = set(_NUMERIC_TOKEN_RE.findall(re.sub(r"(?<=\d),(?=\d{3})", "", spoken_text)))
    expected_clean = {
        str(val).replace(",", "").strip() for val in expected_numeric_values if str(val).strip()
    }
    for clean_val in expected_clean:
        if clean_val not in spoken_tokens:
            return False
    if strict_no_extra_numbers:
        allowed_all = expected_clean | {
            str(c).replace(",", "").strip() for c in allowed_context_numbers if str(c).strip()
        }
        if not spoken_tokens.issubset(allowed_all):
            return False
    return True


@dataclass(frozen=True)
class EdgeFieldApplianceProfile:
    """Offline/intermittent Edge Field-Office Appliance Profile for SSRA border posts (`NIMULE_CUSTOMS`, `WAU_BRANCH`, `MALAKAL_BRANCH`)."""

    office_code: str
    backhaul_online: bool
    llm_model: str
    asr_backend: str
    tts_backend: str
    opus_bitrate_kbps: int
    allowed_tiers: tuple[str, ...]
    store_and_forward_outbox_enabled: bool


def resolve_edge_appliance_profile(
    *,
    office_code: str = "NIMULE_CUSTOMS",
    backhaul_online: bool = False,
) -> EdgeFieldApplianceProfile:
    """Select the quantized on-premises edge voice/LLM profile when NCA backhaul is offline or constrained."""
    if backhaul_online:
        return EdgeFieldApplianceProfile(
            office_code=office_code,
            backhaul_online=True,
            llm_model="ssra-sovereign/sunflower-qwen3.5-9b",
            asr_backend="vllm-audio-transcriptions",
            tts_backend="orpheus-3b-tts-multilingual",
            opus_bitrate_kbps=24,
            allowed_tiers=("T0", "T1", "T2", "T3"),
            store_and_forward_outbox_enabled=False,
        )
    return EdgeFieldApplianceProfile(
        office_code=office_code,
        backhaul_online=False,
        llm_model="ssra-sovereign/qwen2.5-3b-cpu-gguf",
        asr_backend="hf-mms-offline-int8",
        tts_backend="hf-mms-tts-offline-int8",
        opus_bitrate_kbps=12,
        allowed_tiers=("T0",),
        store_and_forward_outbox_enabled=True,
    )


@dataclass(frozen=True)
class SpokenNumberVerbalization:
    """Dual-representation envelope holding canonical digit transcript and TTS-friendly verbalized text."""

    canonical_transcript: str
    phonetic_tts_text: str
    figures_verified: bool
    locale: LocaleCode


_CURRENCY_SPEECH_MAP: dict[LocaleCode, tuple[str, str]] = {
    LocaleCode.EN: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.AR: ("جنيه جنوب سوداني", "دولار أمريكي"),
    LocaleCode.PGA: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.DIN: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.NUS: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.BFA: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.ZNE: ("South Sudanese Pounds", "U S Dollars"),
    LocaleCode.SHK: ("South Sudanese Pounds", "U S Dollars"),
}


def verbalize_statutory_figures_for_tts(
    text: str,
    *,
    locale: LocaleCode = LocaleCode.EN,
    expected_numeric_values: list[str] | tuple[str, ...] = (),
    allowed_context_numbers: list[str] | tuple[str, ...] = (),
) -> SpokenNumberVerbalization:
    """Enforce `FLAG_SPOKEN_FIGURE_GUARD` (`strict_no_extra_numbers=True`) and produce dual canonical-digit + phonetic-currency TTS text."""
    verified = verify_spoken_figure_fidelity(
        text,
        expected_numeric_values,
        strict_no_extra_numbers=True,
        allowed_context_numbers=allowed_context_numbers,
    )
    if not verified:
        raise SSRAError(
            McpErrorCode.VALIDATION_FAILED,
            "FLAG_SPOKEN_FIGURE_GUARD blocked TTS synthesis: spoken figure mismatch with verified NumericClaims",
            status_code=422,
        )
    phonetic = normalize_statutory_text_for_speech(text, locale=locale)
    ssp_word, usd_word = _CURRENCY_SPEECH_MAP.get(locale, _CURRENCY_SPEECH_MAP[LocaleCode.EN])
    phonetic = re.sub(r"\bSSP\b", ssp_word, phonetic)
    phonetic = re.sub(r"\bUSD\b", usd_word, phonetic)
    return SpokenNumberVerbalization(
        canonical_transcript=text,
        phonetic_tts_text=phonetic,
        figures_verified=True,
        locale=locale,
    )


def sync_affective_state_to_call_lobby(
    lobby: CallLobbyManager,
    *,
    call_id: str,
    primary_emotion: str,
    intensity: float,
    frustration_velocity: float,
    signals: list[str] | tuple[str, ...] = (),
) -> LobbyCallEntry:
    """Push real-time acoustic/text emotion spikes into `CallLobbyManager` (`at_risk` / `watch` + priority raise)."""
    if primary_emotion == "distressed" or intensity >= 0.80 or frustration_velocity >= 0.45:
        previous = lobby.calls.get(call_id)
        was_at_risk = previous is not None and previous.risk_level == "at_risk"
        entry = lobby.apply_event(
            "call.risk",
            {"call_id": call_id, "level": "at_risk", "signals": list(signals)},
        )
        if was_at_risk:
            return entry
        return lobby.apply_event(
            "call.priority_raised",
            {"call_id": call_id, "priority": "urgent", "reason": f"eq_{primary_emotion}"},
        )
    if primary_emotion in ("frustrated", "anxious") or intensity >= 0.50:
        return lobby.apply_event(
            "call.risk",
            {"call_id": call_id, "level": "watch", "signals": list(signals)},
        )
    return lobby.apply_event(
        "call.risk",
        {"call_id": call_id, "level": "none", "signals": []},
    )


@dataclass(frozen=True)
class CallToWebCarryover:
    """Symmetric Voice-to-Web carryover descriptor (`VR-G3`) with HMAC-SHA256 integrity signature (`SEC-G5`)."""

    call_id: str
    conversation_id: str
    active_goal_id: str
    resume_step_index: int
    pending_action: str
    local_models_only: bool = True
    issued_at: int = 0
    carryover_hmac: str = ""


CARRYOVER_TTL_SECONDS: int = 900
CARRYOVER_CLOCK_SKEW_SECONDS: int = 60
MIN_CARRYOVER_KEY_BYTES: int = 32


def _carryover_signing_key(signing_salt: str | None) -> bytes:
    """Return the configured carryover key, failing closed when none of adequate length is set."""
    key = signing_salt or os.environ.get("SSRA_VOICE_CARRYOVER_HMAC_KEY") or ""
    key_bytes = key.encode("utf-8")
    if len(key_bytes) < MIN_CARRYOVER_KEY_BYTES:
        raise SSRAError(
            McpErrorCode.UPSTREAM_UNAVAILABLE,
            "Call carryover signing key is not configured (SSRA_VOICE_CARRYOVER_HMAC_KEY, at least 32 bytes)",
            status_code=503,
        )
    return key_bytes


def _compute_carryover_hmac(
    *,
    call_id: str,
    conversation_id: str,
    owner_user_id: str,
    active_goal_id: str,
    resume_step_index: int,
    pending_action: str,
    local_models_only: bool,
    issued_at: int,
    signing_salt: str | None = None,
) -> str:
    """Compute an HMAC-SHA256 signature binding all CallToWebCarryover fields and issue time to the owner."""
    msg = json.dumps(
        [
            call_id,
            conversation_id,
            owner_user_id,
            active_goal_id,
            resume_step_index,
            pending_action,
            local_models_only,
            issued_at,
        ],
        separators=(",", ":"),
    )
    return hmac.new(
        _carryover_signing_key(signing_salt), msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def build_call_to_web_carryover(
    *,
    call_id: str,
    conversation_id: str,
    owner_user_id: str,
    caller_user_id: str,
    active_goal_id: str = "goal_guided_tcc",
    resume_step_index: int = 2,
    pending_action: str = "upload_supporting_receipt",
    signing_salt: str | None = None,
    now: float | None = None,
) -> CallToWebCarryover | None:
    """Build a session-bound, HMAC-signed Voice-to-Web carryover token when caller and owner identities match."""
    is_valid = (
        bool(_SAFE_ID_RE.match(call_id))
        and bool(_SAFE_ID_RE.match(conversation_id))
        and bool(_SAFE_ID_RE.match(owner_user_id))
        and bool(_SAFE_ID_RE.match(active_goal_id))
        and owner_user_id == caller_user_id
    )
    if not is_valid:
        return None
    step_idx = max(1, resume_step_index)
    bounded_action = pending_action[:120]
    issued_at = int(time.time() if now is None else now)
    sig = _compute_carryover_hmac(
        call_id=call_id,
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        active_goal_id=active_goal_id,
        resume_step_index=step_idx,
        pending_action=bounded_action,
        local_models_only=True,
        issued_at=issued_at,
        signing_salt=signing_salt,
    )
    return CallToWebCarryover(
        call_id=call_id,
        conversation_id=conversation_id,
        active_goal_id=active_goal_id,
        resume_step_index=step_idx,
        pending_action=bounded_action,
        local_models_only=True,
        issued_at=issued_at,
        carryover_hmac=sig,
    )


def verify_call_to_web_carryover(
    carryover: CallToWebCarryover,
    *,
    caller_user_id: str,
    signing_salt: str | None = None,
    now: float | None = None,
) -> bool:
    """Verify the HMAC signature (`hmac.compare_digest`), caller ownership, and freshness of a carryover token (`SEC-G5`)."""
    current = time.time() if now is None else now
    age = current - carryover.issued_at
    if age > CARRYOVER_TTL_SECONDS or age < -CARRYOVER_CLOCK_SKEW_SECONDS:
        return False
    expected = _compute_carryover_hmac(
        call_id=carryover.call_id,
        conversation_id=carryover.conversation_id,
        owner_user_id=caller_user_id,
        active_goal_id=carryover.active_goal_id,
        resume_step_index=carryover.resume_step_index,
        pending_action=carryover.pending_action[:120],
        local_models_only=carryover.local_models_only,
        issued_at=carryover.issued_at,
        signing_salt=signing_salt,
    )
    return hmac.compare_digest(carryover.carryover_hmac, expected)


__all__ = [
    "APPROVED_VOICE_WER_EVIDENCE",
    "ASR_MODEL_BY_LOCALE",
    "CARRYOVER_TTL_SECONDS",
    "LOBBY_EVENT_TYPES",
    "MAX_CARRYOVER_CONTEXT_CHARS",
    "MAX_COMPRESSED_AUDIO_BYTES",
    "MAX_DECODED_PCM_BYTES",
    "MAX_DTMF_STEP_UP_ATTEMPTS",
    "MAX_VOICE_WER_GATE",
    "TTS_DEFAULT_VOICE",
    "TTS_MODEL_BY_LOCALE",
    "TTS_VOICE_CATALOG",
    "VOICE_EVENT_TYPES",
    "BriefClaim",
    "CallLobbyManager",
    "CallToWebCarryover",
    "ChatToCallCarryover",
    "EdgeFieldApplianceProfile",
    "HfVoiceModelDescriptor",
    "HybridVoiceRouteDecision",
    "LobbyCallEntry",
    "OfficerCallBrief",
    "OtpVerifier",
    "SpokenNumberVerbalization",
    "StepUpAttemptStore",
    "TtsCachedAudio",
    "TtsPhraseCache",
    "TtsSynthesizer",
    "VADConfig",
    "VoiceRetentionPolicy",
    "VoiceSessionDecision",
    "VoiceStreamSession",
    "VoiceWebSocketConcurrencyGuard",
    "VoiceWerEvidence",
    "build_call_to_web_carryover",
    "build_chat_to_call_carryover",
    "build_voice_consent_audit_entry",
    "build_voice_prosody_eq_metadata",
    "build_voice_spoken_turn_and_sms_followup",
    "fixed_voice_prompts",
    "generate_officer_call_brief",
    "get_localized_tool_wait_filler",
    "is_voice_language_approved",
    "is_ws_origin_allowed",
    "looks_like_valid_audio_bytes",
    "normalize_statutory_text_for_speech",
    "resolve_edge_appliance_profile",
    "resolve_hf_voice_model_cache",
    "resolve_mt_and_tts_turn_plan",
    "resolve_tts_voice",
    "route_voice_turn",
    "select_hybrid_voice_execution_mode",
    "split_tts_sentences",
    "sync_affective_state_to_call_lobby",
    "synthesize_tts_speech_envelope",
    "validate_audio_pcm_expansion_budget",
    "validate_call_wrap_up",
    "verbalize_statutory_figures_for_tts",
    "verify_call_to_web_carryover",
    "verify_spoken_figure_fidelity",
    "verify_voice_dtmf_step_up",
]
