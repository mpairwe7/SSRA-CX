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
export type OrbMode = "idle" | "listening" | "thinking" | "speaking";
export type OrbState = OrbMode;
export type CallTurnPhase = "listening" | "thinking" | "speaking";
export type CallControlAction =
  | "repeat"
  | "slower"
  | "normal_speed"
  | "more_detail"
  | "accept_offer"
  | "decline_offer";
export type CallAgentKind = "automated_assistant" | "officer" | "none";

export const SPEECH_RATE_NORMAL = 1.0;
export const SPEECH_RATE_SLOW = 0.82;

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
  readonly overrideState?: OrbState | undefined;
}): CallOrbFrameState {
  if (!params.active) {
    return { mode: "idle", smoothedLevel: 0, cssOrbLevel: "0" };
  }
  const input = Number.isFinite(params.inputLevel) ? Math.max(0, params.inputLevel) : 0;
  const output = Number.isFinite(params.outputLevel) ? Math.max(0, params.outputLevel) : 0;
  const prev = Number.isFinite(params.previousSmoothed) ? Math.max(0, params.previousSmoothed) : 0;

  const speaking = output >= 0.06 && output >= input;
  const listening = !speaking && input >= 0.06;
  const derivedMode: OrbMode =
    params.overrideState ?? (speaking ? "speaking" : listening ? "listening" : "idle");
  if (params.prefersReducedMotion) {
    return { mode: derivedMode, smoothedLevel: 0, cssOrbLevel: "0" };
  }
  const target = speaking ? output : listening ? input : 0;

  let smoothed = prev + (target - prev) * (target > prev ? 0.45 : 0.12);
  if (smoothed < 0.002) smoothed = 0;

  return {
    mode: derivedMode,
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

export type CallControlDirective =
  | {
      readonly kind: "repeat_speech";
      readonly textToSpeak: string;
      readonly speechRate: number;
    }
  | {
      readonly kind: "set_speech_rate";
      readonly speechRateSlow: boolean;
      readonly speechRate: number;
    }
  | {
      readonly kind: "send_followup_turn";
      readonly prompt: string;
    }
  | {
      readonly kind: "resolve_offer";
      readonly accepted: boolean;
      readonly offerKey: string;
    };

/**
 * Resolve an in-call receptionist control strip action (`CallScreen.tsx` `sendControl` parity).
 */
export function resolveCallControlDirective(
  action: CallControlAction,
  state: {
    readonly lastAssistantText: string;
    readonly speechRateSlow: boolean;
    readonly pendingOffer?: string | undefined;
  },
): CallControlDirective {
  if (action === "repeat") {
    return {
      kind: "repeat_speech",
      textToSpeak: String(state.lastAssistantText || "").trim(),
      speechRate: state.speechRateSlow ? SPEECH_RATE_SLOW : SPEECH_RATE_NORMAL,
    };
  }
  if (action === "slower" || action === "normal_speed") {
    const slow = action === "slower";
    return {
      kind: "set_speech_rate",
      speechRateSlow: slow,
      speechRate: slow ? SPEECH_RATE_SLOW : SPEECH_RATE_NORMAL,
    };
  }
  if (action === "more_detail") {
    return {
      kind: "send_followup_turn",
      prompt: "Please provide more detail on the previous answer.",
    };
  }
  return {
    kind: "resolve_offer",
    accepted: action === "accept_offer",
    offerKey: String(state.pendingOffer || ""),
  };
}

const SPOKEN_CONTROL_MAX_WORDS = 8;
const SPOKEN_REPEAT_RE =
  /\b(?:repeat\s+that|say\s+that\s+again|could\s+you\s+repeat|pardon\s+me|what\s+did\s+you\s+say|أعد\s+ذلك|ممكن\s+تعيد)\b/i;
const SPOKEN_SLOW_RE =
  /\b(?:speak\s+slower|more\s+slowly|talk\s+slower|slow\s+down|تحدث\s+ببطء|تكلم\s+ببطء)\b/i;
const SPOKEN_NORMAL_RE =
  /\b(?:speak\s+(?:normally|faster)|normal\s+(?:speed|pace)|regular\s+(?:speed|pace)|talk\s+faster|سرعة\s+عادية)\b/i;
const SPOKEN_MORE_RE = /\b(?:tell\s+me\s+more|more\s+detail|تفاصيل\s+أكثر)\b/i;
const SPOKEN_HANGUP_RE =
  /\b(?:hang\s+up|end\s+(?:the\s+)?call|disconnect|good[\s-]?bye|مع\s+السلامة|أنهي\s+المكالمة)\b/i;
const SPOKEN_DONE_RE =
  /^[\s,!.?]*(?:(?:ok|okay|thanks|thank\s+you|alright|great|no)[\s,!.?]+)?(?:that'?s\s+all|that\s+is\s+all|good[\s-]?bye|bye\s+bye|bye|i'?m\s+done)(?:[\s,!.?]+(?:for\s+(?:now|today)|thank\s+you|thanks|bye))?[\s,!.?]*$/i;

/**
 * Detect short spoken in-call receptionist controls (`brain.py` `_CONTROL_MAX_WORDS = 8` parity).
 */
export function detectSpokenCallControl(transcript: string): CallControlAction | "hangup" | null {
  const clean = String(transcript || "").trim();
  if (!clean) return null;
  if (SPOKEN_DONE_RE.test(clean)) return "hangup";
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length > SPOKEN_CONTROL_MAX_WORDS) return null;
  if (SPOKEN_HANGUP_RE.test(clean)) return "hangup";
  if (SPOKEN_REPEAT_RE.test(clean)) return "repeat";
  if (SPOKEN_SLOW_RE.test(clean)) return "slower";
  if (SPOKEN_NORMAL_RE.test(clean)) return "normal_speed";
  if (SPOKEN_MORE_RE.test(clean)) return "more_detail";
  return null;
}

export type VoiceDockPhase =
  | "opening"
  | "listening"
  | "hearing"
  | "pausing"
  | "transcribing"
  | "thinking"
  | "preparing"
  | "speaking"
  | "paused"
  | "idle";

export const PAUSE_SHOWN_FROM = 0.25;

export const VOICE_PAUSE_OPTIONS: readonly { readonly value: string; readonly label: string }[] = [
  { value: "0", label: "Off" },
  { value: "800", label: "0.8 s" },
  { value: "1200", label: "1.2 s" },
  { value: "2000", label: "2 s" },
];

export function orbStateForVoiceDock(phase: VoiceDockPhase): OrbState {
  if (phase === "listening" || phase === "hearing" || phase === "pausing") return "listening";
  if (
    phase === "opening" ||
    phase === "transcribing" ||
    phase === "thinking" ||
    phase === "preparing"
  ) {
    return "thinking";
  }
  if (phase === "speaking" || phase === "paused") return "speaking";
  return "idle";
}

export interface VoiceModeDockView {
  readonly effectivePhase: VoiceDockPhase;
  readonly floor: OrbState;
  readonly label: string;
  readonly detail: string;
  readonly detailAriaHidden: boolean;
  readonly announcement: string;
  readonly primaryAction: "busy" | "send" | "stop" | "interrupt" | "talk";
  readonly primaryLabel: string;
  readonly showCountdownRing: boolean;
  readonly showMicOffButton: boolean;
  readonly showPauseButton: boolean;
}

/**
 * Build the `VoiceModeDock` view model (`FinalYearProject` `components/VoiceModeDock.tsx` parity).
 */
export function buildVoiceModeDockView(params: {
  readonly phase: VoiceDockPhase;
  readonly workingLabel?: string | undefined;
  readonly heard?: string | null | undefined;
  readonly notice?: string | null | undefined;
  readonly sentence?: string | null | undefined;
  readonly lastSentence?: string | null | undefined;
  readonly autoSend: boolean;
  readonly paused?: boolean | undefined;
}): VoiceModeDockView {
  const effectivePhase: VoiceDockPhase =
    params.phase === "speaking" && params.paused ? "paused" : params.phase;
  const floor = orbStateForVoiceDock(effectivePhase);
  const micOpen =
    effectivePhase === "opening" ||
    effectivePhase === "listening" ||
    effectivePhase === "hearing" ||
    effectivePhase === "pausing";
  const reading =
    effectivePhase === "preparing" || effectivePhase === "speaking" || effectivePhase === "paused";
  const sentenceShown = reading ? String(params.sentence || params.lastSentence || "").trim() : "";

  const labels: Record<VoiceDockPhase, string> = {
    opening: "Starting microphone…",
    listening: "Listening…",
    hearing: "Hearing you…",
    pausing: "Sending in a moment…",
    transcribing: "Transcribing…",
    thinking: params.workingLabel || "Working on your answer…",
    preparing: "Preparing voice reply…",
    speaking: "Speaking…",
    paused: "Paused",
    idle: "Voice mode ready",
  };
  const label = labels[effectivePhase];

  const youSaid = params.heard ? `You said: "${params.heard}"` : "";
  const defaultDetails: Record<VoiceDockPhase, string> = {
    opening: "Allow microphone access to speak.",
    listening: params.autoSend
      ? "Speak your question — pauses send automatically."
      : "Speak your question, then tap Send.",
    hearing: params.autoSend
      ? "Speak your question — pauses send automatically."
      : "Speak your question, then tap Send.",
    pausing: "Keep speaking or tap Send now.",
    transcribing: "Converting speech to text…",
    thinking: youSaid,
    preparing: youSaid,
    speaking: sentenceShown || "Tap the microphone to interrupt and ask a follow-up.",
    paused: sentenceShown || "Reading paused.",
    idle: "Tap the microphone to start speaking.",
  };
  const noticeText = String(params.notice || "").trim();
  const detail = noticeText || defaultDetails[effectivePhase];
  const detailAriaHidden =
    !noticeText && (effectivePhase === "speaking" || effectivePhase === "paused");

  // Screen reader announcement: silent while mic is open or TTS is speaking so it never talks over audio
  const announcement = micOpen
    ? ""
    : effectivePhase === "thinking" || effectivePhase === "preparing"
      ? "Working on your answer…"
      : effectivePhase === "speaking"
        ? ""
        : [label, noticeText].filter(Boolean).join(". ");

  const primaryAction: "busy" | "send" | "stop" | "interrupt" | "talk" =
    effectivePhase === "opening"
      ? "busy"
      : micOpen
        ? "send"
        : effectivePhase === "transcribing" || effectivePhase === "thinking"
          ? "stop"
          : reading
            ? "interrupt"
            : "talk";

  const primaryLabels: Record<typeof primaryAction, string> = {
    busy: "Starting microphone",
    send: "Send voice turn now",
    stop: "Stop answer generation",
    interrupt: "Interrupt and speak",
    talk: "Start speaking",
  };

  return {
    effectivePhase,
    floor,
    label,
    detail,
    detailAriaHidden,
    announcement,
    primaryAction,
    primaryLabel: primaryLabels[primaryAction],
    showCountdownRing: primaryAction === "send" && params.autoSend,
    showMicOffButton: micOpen && effectivePhase !== "opening",
    showPauseButton: effectivePhase === "speaking" || effectivePhase === "paused",
  };
}

export type CallCaptionBlock =
  | {
      readonly kind: "paragraph";
      readonly text: string;
    }
  | {
      readonly kind: "numbered_list";
      readonly items: readonly { readonly stepNumber: number; readonly text: string }[];
    };

/**
 * Structure a Call Receptionist agent caption into paragraphs and numbered step items
 * so procedures (`1. ... 2. ...`) are never rendered as a flat unparagraphing wall of text.
 */
export function structureCallReceptionistBlocks(text: string): readonly CallCaptionBlock[] {
  const cleaned = String(text ?? "").trim();
  if (!cleaned) return [];
  const blocks: CallCaptionBlock[] = [];
  const rawParagraphs = cleaned.split(/\n\s*\n+/);
  for (const para of rawParagraphs) {
    const trimmedPara = para.trim();
    if (!trimmedPara) continue;
    // Split inline numbered steps ("To register: 1. Open portal. 2. Enter TIN.") into separate lines
    const normalizedLines = trimmedPara
      .replace(/(?<=[:.!?؟])\s+(?=\d{1,2}[.)]\s+[A-Z\u0600-\u06FF])/g, "\n")
      .split(/\n+/)
      .map((l) => l.trim())
      .filter(Boolean);
    const listItems: { stepNumber: number; text: string }[] = [];
    for (const line of normalizedLines) {
      const m = /^(\d{1,2})[.)]\s+(.+)$/.exec(line);
      if (m?.[1] && m[2]) {
        listItems.push({ stepNumber: Number(m[1]), text: m[2].trim() });
      } else {
        if (listItems.length > 0) {
          blocks.push({ kind: "numbered_list", items: [...listItems] });
          listItems.length = 0;
        }
        blocks.push({ kind: "paragraph", text: line });
      }
    }
    if (listItems.length > 0) {
      blocks.push({ kind: "numbered_list", items: [...listItems] });
    }
  }
  return blocks;
}
