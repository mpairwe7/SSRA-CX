/**
 * Taxpayer AI Call Receptionist & Exponential-Follower CallOrb (`packages/chat-ui/src/call-receptionist.ts`).
 *
 * Mirrors `components/call/CallScreen.tsx` & `components/call/CallOrb.tsx`:
 * 1. Pre-call recording consent gate (`status === "consent"`) before microphone capture begins.
 * 2. Call Language Chip (`"English · auto"` vs `"Juba Arabic · chosen"`, `role="menuitemradio"`).
 * 3. `CallOrb` exponential-follower (`computeCallOrbFrame`): playback (`output >= 0.06 && output >= input`)
 *    wins ties over mic input so speaker echo never flickers the orb to `"listening"`, easing in fast (`0.45`)
 *    and out slow (`0.12`). Under `prefers-reduced-motion: reduce` the level freezes at `0`, but the mode
 *    still says who has the floor: reduced motion removes the animation, not the information.
 * 4. Pinned-to-bottom caption scroll tracking (`PIN_THRESHOLD_PX = 48`).
 * 5. The live view says whether the caller is talking to the automated assistant or an officer, and
 *    whether the call is being recorded (AUD-045).
 */

import type { LocaleCode } from "@ssra/contracts";

export const PIN_THRESHOLD_PX = 48;

export type CallSessionStatus =
  | "consent"
  | "connecting"
  | "ai"
  | "transferring"
  | "on_hold"
  | "officer"
  | "reconnecting"
  | "ended";

export type CallLanguageSource = "auto" | "override" | "explicit";
export type OrbMode = "idle" | "listening" | "speaking";
export type CallAgentKind = "automated_assistant" | "officer" | "none";

export interface CallCaptionEntry {
  readonly id: string;
  readonly speaker: "caller" | "assistant" | "officer" | "system";
  readonly text: string;
  readonly partial?: boolean | undefined;
}

export interface CallLanguageChipDescriptor {
  readonly language: LocaleCode;
  readonly pinned: boolean;
  readonly chipLabel: string;
  readonly menuItemRole: "menuitemradio";
}

export function buildCallLanguageChip(
  language: LocaleCode,
  languageName: string,
  source: CallLanguageSource,
): CallLanguageChipDescriptor {
  const pinned = source === "override" || source === "explicit";
  return {
    language,
    pinned,
    chipLabel: pinned ? `${languageName} · chosen` : `${languageName} · auto`,
    menuItemRole: "menuitemradio",
  };
}

export function formatCallDurationMmSs(seconds: number): string {
  const safe = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export interface CallOrbFrameState {
  readonly mode: OrbMode;
  readonly smoothedLevel: number;
  readonly cssOrbLevel: string;
}

/**
 * Compute one animation frame of `CallOrb` (`CallOrb.tsx`).
 * Playback (`output`) wins ties over `input` so speaker echo does not misreport who has the floor.
 */
export function computeCallOrbFrame(params: {
  readonly active: boolean;
  readonly prefersReducedMotion: boolean;
  readonly previousSmoothed: number;
  readonly inputLevel: number;
  readonly outputLevel: number;
}): CallOrbFrameState {
  if (!params.active) {
    return { mode: "idle", smoothedLevel: 0, cssOrbLevel: "0" };
  }
  const input = Number.isFinite(params.inputLevel) ? Math.max(0, params.inputLevel) : 0;
  const output = Number.isFinite(params.outputLevel) ? Math.max(0, params.outputLevel) : 0;
  const prev = Number.isFinite(params.previousSmoothed) ? Math.max(0, params.previousSmoothed) : 0;

  const speaking = output >= 0.06 && output >= input;
  const listening = !speaking && input >= 0.06;
  if (params.prefersReducedMotion) {
    const still: OrbMode = speaking ? "speaking" : listening ? "listening" : "idle";
    return { mode: still, smoothedLevel: 0, cssOrbLevel: "0" };
  }
  const target = speaking ? output : listening ? input : 0;

  let smoothed = prev + (target - prev) * (target > prev ? 0.45 : 0.12);
  if (smoothed < 0.002) smoothed = 0;

  const mode: OrbMode = speaking ? "speaking" : listening ? "listening" : "idle";
  return {
    mode,
    smoothedLevel: Number(smoothed.toFixed(3)),
    cssOrbLevel: smoothed.toFixed(3),
  };
}

export function evaluateCaptionScrollPin(params: {
  readonly scrollHeight: number;
  readonly scrollTop: number;
  readonly clientHeight: number;
}): {
  readonly pinnedToBottom: boolean;
  readonly showJumpToLatest: boolean;
} {
  const distanceFromBottom = params.scrollHeight - params.scrollTop - params.clientHeight;
  const pinnedToBottom = distanceFromBottom < PIN_THRESHOLD_PX;
  return {
    pinnedToBottom,
    showJumpToLatest: !pinnedToBottom,
  };
}

export interface CallReceptionistScreenDescriptor {
  readonly dialogRole: "dialog";
  readonly ariaModal: true;
  readonly viewMode: "pre_call_consent" | "live_call";
  readonly statusPillTone: "not_started" | "active" | "transferring" | "ended";
  readonly formattedDuration: string;
  readonly languageChip: CallLanguageChipDescriptor;
  readonly canRequestOfficer: boolean;
  readonly canRequestCallback: boolean;
  /** Who the caller is talking to right now, so an AI is never mistaken for a person. */
  readonly speakingWith: CallAgentKind;
  /** True only while the call engine reports that this call is being recorded. */
  readonly recordingIndicator: boolean;
}

function callAgentKind(status: CallSessionStatus): CallAgentKind {
  if (status === "ai" || status === "transferring") return "automated_assistant";
  if (status === "officer" || status === "on_hold") return "officer";
  return "none";
}

export function buildCallReceptionistScreen(params: {
  readonly status: CallSessionStatus;
  readonly durationSeconds: number;
  readonly language: LocaleCode;
  readonly languageName: string;
  readonly languageSource: CallLanguageSource;
  /** Whether the call engine is recording this call (only after the caller consented). */
  readonly recording: boolean;
}): CallReceptionistScreenDescriptor {
  const languageChip = buildCallLanguageChip(
    params.language,
    params.languageName,
    params.languageSource,
  );
  if (params.status === "consent") {
    return {
      dialogRole: "dialog",
      ariaModal: true,
      viewMode: "pre_call_consent",
      statusPillTone: "not_started",
      formattedDuration: "00:00",
      languageChip,
      canRequestOfficer: false,
      canRequestCallback: false,
      speakingWith: "none",
      recordingIndicator: false,
    };
  }
  const statusPillTone =
    params.status === "ai" || params.status === "officer"
      ? "active"
      : params.status === "connecting" ||
          params.status === "transferring" ||
          params.status === "on_hold" ||
          params.status === "reconnecting"
        ? "transferring"
        : "ended";

  return {
    dialogRole: "dialog",
    ariaModal: true,
    viewMode: "live_call",
    statusPillTone,
    formattedDuration: formatCallDurationMmSs(params.durationSeconds),
    languageChip,
    canRequestOfficer: params.status === "ai",
    canRequestCallback: params.status === "transferring" || params.status === "on_hold",
    speakingWith: callAgentKind(params.status),
    recordingIndicator: params.recording && params.status !== "ended",
  };
}

/** Post-TTS room/speaker echo cooldown before re-arming SpeechRecognition (MARIA OS / Speko 2026). */
export const POST_TTS_ECHO_COOLDOWN_MS = 450;
/** Maximum consecutive no-speech / silent recognition retries before pausing hands-free mode. */
export const MAX_CONSECUTIVE_SPEECH_RETRIES = 3;

const BACKCHANNEL_SET: ReadonlySet<string> = new Set([
  "mm",
  "mmm",
  "mm hm",
  "mmhm",
  "uh huh",
  "okay",
  "ok",
  "i see",
  "right",
  "got it",
  "نعم",
  "تمام",
  "ايوه",
  "أيوة",
]);

function normalizeSpeechTokens(text: string): string[] {
  const matches = String(text ?? "")
    .toLowerCase()
    .match(/[\p{L}\p{N}]+/gu);
  return matches ? matches.filter((t) => t.length > 0) : [];
}

/** True when a short listener acknowledgement should not barge-in or cancel active TTS. */
export function isBackchannelText(text: string): boolean {
  const tokens = normalizeSpeechTokens(text);
  if (tokens.length === 0 || tokens.length > 2) return false;
  return BACKCHANNEL_SET.has(tokens.join(" "));
}

/**
 * Detect when a browser SpeechRecognition transcript is acoustic echo of the assistant's own TTS.
 */
export function isLikelyAssistantEcho(params: {
  readonly transcript: string;
  readonly lastAssistantText: string;
  readonly elapsedSinceTtsEndMs?: number | null | undefined;
}): boolean {
  const callerTokens = normalizeSpeechTokens(params.transcript);
  const assistantTokens = normalizeSpeechTokens(params.lastAssistantText);
  if (callerTokens.length === 0 || assistantTokens.length === 0) return false;

  const callerJoined = callerTokens.join(" ");
  const assistantJoined = assistantTokens.join(" ");
  const callerPadded = ` ${callerJoined} `;
  const assistantPadded = ` ${assistantJoined} `;
  const assistantSet = new Set(assistantTokens);
  let matched = 0;
  for (const tok of callerTokens) {
    if (assistantSet.has(tok)) matched += 1;
  }
  const overlap = matched / callerTokens.length;

  const elapsed = params.elapsedSinceTtsEndMs;
  const inEchoTail =
    typeof elapsed === "number" && Number.isFinite(elapsed) && elapsed <= POST_TTS_ECHO_COOLDOWN_MS;

  if (inEchoTail) {
    if (assistantPadded.includes(callerPadded)) return true;
    if (callerTokens.length >= 2 && overlap >= 0.75) return true;
  }
  if (callerTokens.length >= 4 && (assistantPadded.includes(callerPadded) || overlap >= 0.85)) {
    return true;
  }
  return false;
}

export interface VoiceTurnContinuationDecision {
  readonly action:
    | "submit_turn"
    | "ignore_echo"
    | "ignore_backchannel"
    | "retry_listen"
    | "pause_after_retries";
  readonly nextRetryCount: number;
  readonly resumeDelayMs: number;
}

/**
 * Decide how a continuous browser voice session should handle a recognition result or silence end.
 */
export function evaluateVoiceTurnContinuation(params: {
  readonly transcript: string;
  readonly lastAssistantText: string;
  readonly assistantSpeaking: boolean;
  readonly elapsedSinceTtsEndMs?: number | null | undefined;
  readonly consecutiveEmptyRetries: number;
  readonly continuousEnabled: boolean;
}): VoiceTurnContinuationDecision {
  const trimmed = String(params.transcript ?? "").trim();
  if (!trimmed) {
    const nextRetry = Math.max(0, params.consecutiveEmptyRetries) + 1;
    if (!params.continuousEnabled || nextRetry > MAX_CONSECUTIVE_SPEECH_RETRIES) {
      return { action: "pause_after_retries", nextRetryCount: nextRetry, resumeDelayMs: 0 };
    }
    return {
      action: "retry_listen",
      nextRetryCount: nextRetry,
      resumeDelayMs: POST_TTS_ECHO_COOLDOWN_MS,
    };
  }
  if (
    isLikelyAssistantEcho({
      transcript: trimmed,
      lastAssistantText: params.lastAssistantText,
      elapsedSinceTtsEndMs: params.assistantSpeaking ? 0 : params.elapsedSinceTtsEndMs,
    })
  ) {
    return {
      action: "ignore_echo",
      nextRetryCount: params.consecutiveEmptyRetries,
      resumeDelayMs: POST_TTS_ECHO_COOLDOWN_MS,
    };
  }
  if (params.assistantSpeaking && isBackchannelText(trimmed)) {
    return {
      action: "ignore_backchannel",
      nextRetryCount: params.consecutiveEmptyRetries,
      resumeDelayMs: 0,
    };
  }
  return {
    action: "submit_turn",
    nextRetryCount: 0,
    resumeDelayMs: POST_TTS_ECHO_COOLDOWN_MS,
  };
}
