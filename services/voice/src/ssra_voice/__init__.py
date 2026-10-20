"""Phase 4 Voice/IVR ASR, TTS/MMS, Call Receptionist, Officer Call Brief & Lobby Engine (Section 11, CVE-2026-54233)."""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Literal

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
    utterance_confidence: float = 0.95,
    consecutive_low_confidence_turns: int = 0,
) -> VoiceSessionDecision:
    """Route a voice turn across ASR, hybrid DTMF disambiguation, and progressive warm transfer."""
    _ = barge_in_detected
    asr_engine = ASR_MODEL_BY_LOCALE[locale]
    tts_engine = TTS_MODEL_BY_LOCALE[locale]

    if (
        dtmf_digit == "0"
        or not is_voice_language_approved(locale, measured_wer)
        or consecutive_low_confidence_turns >= 2
    ):
        return VoiceSessionDecision(
            session_id=session_id,
            locale=locale,
            asr_engine=asr_engine,
            tts_engine=tts_engine,
            recording_enabled=recording_consent_granted,
            action="WARM_TRANSFER_TO_OFFICER",
            warm_transfer_summary=(
                f"Warm transfer from IVR ({locale.value}): caller pressed 0, language WER "
                f"{measured_wer:.2f} exceeded gate {MAX_VOICE_WER_GATE}, or consecutive low-confidence turns={consecutive_low_confidence_turns}."
            ),
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
        presets = {
            "low": cls(energy_threshold=0.025, silence_duration_ms=800, sample_rate=sample_rate),
            "medium": cls(energy_threshold=0.015, silence_duration_ms=600, sample_rate=sample_rate),
            "high": cls(energy_threshold=0.008, silence_duration_ms=400, sample_rate=sample_rate),
        }
        return presets.get(sensitivity.lower(), presets["medium"])


def split_tts_sentences(text: str) -> list[str]:
    """Split reply text into sentence chunks for sub-second time-to-first-audio."""
    cleaned = text.strip()
    if not cleaned:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]


class VoiceStreamSession:
    """V2 Streaming Voice Session (`voice_stream_v2.py`): sentence-chunked TTS, barge-in & speculative prefetch."""

    def __init__(
        self, *, session_id: str, locale: LocaleCode, vad: VADConfig | None = None
    ) -> None:
        self.session_id = session_id
        self.locale = locale
        self.vad = vad or VADConfig.from_sensitivity("medium")
        self.barge_in_cancelled = False
        self.speculative_prefetches: list[str] = []

    def trigger_barge_in(self) -> None:
        self.barge_in_cancelled = True

    def record_partial_transcript(self, partial_text: str) -> str | None:
        words = [w for w in partial_text.strip().split() if w]
        if len(words) >= 3:
            stable_prefix = " ".join(words[:4])
            self.speculative_prefetches.append(stable_prefix)
            return stable_prefix
        return None

    def stream_tts_sentences(self, text: str, *, voice: str | None = None) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for idx, sentence in enumerate(split_tts_sentences(text)):
            if self.barge_in_cancelled:
                break
            env = synthesize_tts_speech_envelope(text=sentence, locale=self.locale, voice=voice)
            env["sentence_index"] = idx
            env["sentence_text"] = sentence
            chunks.append(env)
        return chunks


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
    raw_audio_ttl_hours: int = 24
    transcript_ttl_days: int = 90
    analytics_ttl_days: int = 365
    store_raw_audio: bool = False


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


class TtsPhraseCache:
    """Bounded LRU TTS Phrase Cache (`TestTtsPhraseCache` in `test_voice_robustness.py`):
    Serves repeated phrases with `backend='<engine>+cache'` and `latency_ms=0.0`, and never caches failures.
    """

    def __init__(self, *, max_entries: int = 256) -> None:
        self.max_entries = max(1, max_entries)
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
        synthesizer: Any,
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
    action: Literal["BOUND_T1", "BOUND_T3", "REJECTED_SPOKEN_OTP", "WARM_TRANSFER_TO_OFFICER"]
    tin_masked: str | None
    recording_paused_for_dtmf: bool
    reason: str | None = None


def verify_voice_dtmf_step_up(
    *,
    dtmf_tin_digits: str,
    dtmf_otp_digits: str,
    input_modality: Literal["dtmf_rfc4733", "spoken_asr"] = "dtmf_rfc4733",
    requested_tier: Literal["T1", "T2", "T3", "T4"] = "T1",
    sim_swap_recent: bool = False,
) -> VoiceDtmfStepUpResult:
    """Enforce RFC 4733 DTMF-only TIN/OTP entry with recording pause and SIM-swap / T4 guards."""
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
    return VoiceDtmfStepUpResult(
        authorized=True,
        action="BOUND_T3" if requested_tier == "T3" else "BOUND_T1",
        tin_masked=f"••••{clean_tin[-4:]}",
        recording_paused_for_dtmf=True,
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


__all__ = [
    "ASR_MODEL_BY_LOCALE",
    "MAX_CARRYOVER_CONTEXT_CHARS",
    "MAX_COMPRESSED_AUDIO_BYTES",
    "MAX_DECODED_PCM_BYTES",
    "MAX_VOICE_WER_GATE",
    "TTS_DEFAULT_VOICE",
    "TTS_MODEL_BY_LOCALE",
    "TTS_VOICE_CATALOG",
    "VOICE_EVENT_TYPES",
    "BriefClaim",
    "CallLobbyManager",
    "ChatToCallCarryover",
    "HfVoiceModelDescriptor",
    "LobbyCallEntry",
    "OfficerCallBrief",
    "TtsCachedAudio",
    "TtsPhraseCache",
    "VADConfig",
    "VoiceRetentionPolicy",
    "VoiceSessionDecision",
    "VoiceStreamSession",
    "VoiceWebSocketConcurrencyGuard",
    "build_chat_to_call_carryover",
    "build_voice_consent_audit_entry",
    "generate_officer_call_brief",
    "is_voice_language_approved",
    "is_ws_origin_allowed",
    "looks_like_valid_audio_bytes",
    "resolve_hf_voice_model_cache",
    "resolve_mt_and_tts_turn_plan",
    "resolve_tts_voice",
    "route_voice_turn",
    "split_tts_sentences",
    "synthesize_tts_speech_envelope",
    "validate_audio_pcm_expansion_budget",
    "validate_call_wrap_up",
]
