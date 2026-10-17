/**
 * Phase 4 Speech & Voice Interaction Flows (`packages/chat-ui/src/voice-notes.ts`):
 * - Low-bitrate Opus Voice Notes (`validateVoiceNoteSubmission`, <= 60s, <= 256 KB, consent gate)
 * - End-of-Turn Acoustic Detector (`levelDbfs`, `zeroCrossingRate`, `isVocalAcousticProfile`, `EndOfTurnDetector` — `endOfTurn.ts` pattern)
 * - Web Audio Earcons / Signifiers (`AUDIO_SIGNIFIER_SPECS` — `audioSignifiers.ts` pattern)
 * - WCAG 2.2 SC 1.4.2 Audio Control `NarrationBar` (`buildNarrationBarView` — `NarrationBar.tsx` G200 pattern)
 */

import type { LocaleCode } from "@ssra/contracts";

export const MAX_VOICE_NOTE_DURATION_SECONDS = 60;
export const MAX_VOICE_NOTE_BYTES = 256 * 1024;
export const ALLOWED_VOICE_MIME_TYPES = new Set([
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/mp4",
]);

export interface VoiceNoteSubmission {
  readonly locale: LocaleCode;
  readonly mimeType: string;
  readonly durationSeconds: number;
  readonly sizeBytes: number;
  readonly recordingConsentGranted: boolean;
}

export function validateVoiceNoteSubmission(input: VoiceNoteSubmission): {
  readonly accepted: boolean;
  readonly reason?: string;
} {
  if (!input.recordingConsentGranted) {
    return {
      accepted: false,
      reason: "VOICE_RECORDING_CONSENT_REQUIRED",
    };
  }
  if (!ALLOWED_VOICE_MIME_TYPES.has(input.mimeType)) {
    return {
      accepted: false,
      reason: "UNSUPPORTED_AUDIO_CODEC_USE_OPUS",
    };
  }
  if (input.durationSeconds <= 0 || input.durationSeconds > MAX_VOICE_NOTE_DURATION_SECONDS) {
    return {
      accepted: false,
      reason: "EXCEEDS_MAX_60S_DURATION",
    };
  }
  if (input.sizeBytes <= 0 || input.sizeBytes > MAX_VOICE_NOTE_BYTES) {
    return {
      accepted: false,
      reason: "EXCEEDS_256KB_LOW_BANDWIDTH_VOICE_CAP",
    };
  }
  return { accepted: true };
}

export type TurnEvent = "speech" | "end" | "no-speech" | "too-long";

export interface EndOfTurnOptions {
  readonly silenceMs: number;
  readonly minSpeechMs?: number | undefined;
  readonly noSpeechMs?: number | undefined;
  readonly maxTurnMs?: number | undefined;
}

const ONSET_DB = 12;
const HOLD_DB = 6;
const MIN_SPEECH_DBFS = -50;
const SILENT_DBFS = -100;
const FLOOR_QUANTILE = 0.1;
const FLOOR_WINDOW_MS = 4000;
const CALIBRATION_MS = 300;
const GAP_MS = 250;
const HEARD_MS = 150;
const MAX_FRAME_MS = 250;

export function levelDbfs(samples: Float32Array): number {
  let sum = 0;
  let validCount = 0;
  for (let i = 0; i < samples.length; i++) {
    const v = samples[i] ?? 0;
    if (Number.isFinite(v)) {
      sum += v * v;
      validCount++;
    }
  }
  const rms = validCount > 0 ? Math.sqrt(sum / validCount) : 0;
  return rms > 0 ? Math.max(SILENT_DBFS, 20 * Math.log10(rms)) : SILENT_DBFS;
}

export function zeroCrossingRate(samples: Float32Array): number {
  if (samples.length < 2) return 0;
  let crossings = 0;
  for (let i = 1; i < samples.length; i++) {
    const cur = samples[i] ?? 0;
    const prev = samples[i - 1] ?? 0;
    if ((cur >= 0 && prev < 0) || (cur < 0 && prev >= 0)) {
      crossings++;
    }
  }
  return crossings / samples.length;
}

export function isVocalAcousticProfile(samples: Float32Array): boolean {
  if (samples.length < 128) return true;
  return zeroCrossingRate(samples) <= 0.45;
}

/**
 * Adaptive room-floor End-of-Turn Detector (`endOfTurn.ts`).
 * Freezes `speechFloor` once speech begins so a steady voice never becomes its own floor.
 */
export class EndOfTurnDetector {
  private readonly silenceMs: number;
  private readonly minSpeechMs: number;
  private readonly noSpeechMs: number;
  private readonly maxTurnMs: number;
  private readonly recent: Array<{ at: number; db: number }> = [];
  private startedAt: number | null = null;
  private lastAt: number | null = null;
  private lastSoundAt = 0;
  private burstStart: number | null = null;
  private burstMs = 0;
  private soundRunMs = 0;
  private heard = false;
  private speaking = false;
  private speechFloor = SILENT_DBFS;
  private finished = false;

  constructor(opts: EndOfTurnOptions) {
    this.silenceMs = opts.silenceMs;
    this.minSpeechMs = opts.minSpeechMs ?? 300;
    this.noSpeechMs = opts.noSpeechMs ?? 8000;
    this.maxTurnMs = opts.maxTurnMs ?? 60_000;
  }

  get hasSpeech(): boolean {
    return this.speaking;
  }

  push(db: number, now: number): TurnEvent | null {
    if (this.finished || !Number.isFinite(now)) return null;
    this.startedAt ??= now;
    const frameMs = Math.min(MAX_FRAME_MS, Math.max(0, now - (this.lastAt ?? now)));
    this.lastAt = now;
    const safeDb = Number.isFinite(db) ? db : SILENT_DBFS;
    const level = Math.max(SILENT_DBFS, safeDb);
    const floor = this.speaking ? this.speechFloor : this.floor(now, level);
    const onset = Math.max(floor + ONSET_DB, MIN_SPEECH_DBFS);
    const sounding = level >= onset - HOLD_DB;

    if (now - this.startedAt >= this.maxTurnMs) return this.finish("too-long");
    if (this.speaking) {
      if (sounding) this.lastSoundAt = now;
      return now - this.lastSoundAt >= this.silenceMs ? this.finish("end") : null;
    }

    if (sounding) this.lastSoundAt = now;
    this.soundRunMs = sounding || level >= MIN_SPEECH_DBFS ? this.soundRunMs + frameMs : 0;
    if (this.soundRunMs >= HEARD_MS) this.heard = true;

    if (this.burstStart === null) {
      if (level >= onset && now - this.startedAt >= CALIBRATION_MS) {
        this.burstStart = now;
        this.burstMs = 0;
      }
    } else if (now - this.lastSoundAt > GAP_MS) {
      this.burstStart = null;
    } else if (sounding) {
      this.burstMs += frameMs;
    }

    if (this.burstStart !== null && this.burstMs >= this.minSpeechMs) {
      this.speaking = true;
      this.speechFloor = floor;
      return "speech";
    }
    if (now - this.startedAt >= this.noSpeechMs && !this.heard) {
      return this.finish("no-speech");
    }
    return null;
  }

  private floor(now: number, level: number): number {
    this.recent.push({ at: now, db: level });
    while (this.recent.length > 1 && now - (this.recent[0]?.at ?? now) > FLOOR_WINDOW_MS) {
      this.recent.shift();
    }
    const sorted = this.recent.map((f) => f.db).sort((a, b) => a - b);
    return sorted[Math.floor((sorted.length - 1) * FLOOR_QUANTILE)] ?? SILENT_DBFS;
  }

  private finish(event: TurnEvent): TurnEvent {
    this.finished = true;
    return event;
  }
}

export const AUDIO_SIGNIFIER_SPECS = {
  micStart: {
    waveType: "sine" as const,
    startHz: 440,
    endHz: 880,
    durationMs: 120,
    vibratePattern: [25] as const,
  },
  micStop: {
    waveType: "sine" as const,
    startHz: 880,
    endHz: 440,
    durationMs: 100,
    vibratePattern: [15, 30, 15] as const,
  },
  error: {
    waveType: "triangle" as const,
    startHz: 220,
    endHz: 160,
    durationMs: 180,
    vibratePattern: [40, 40] as const,
  },
} as const;

export function buildNarrationBarView(params: {
  readonly active: boolean;
  readonly loading: boolean;
  readonly paused: boolean;
  readonly failed: boolean;
  readonly sentence: string | null;
}) {
  if (params.failed && !params.active) {
    return {
      visible: true,
      mode: "failed" as const,
      testId: "narration-failed" as const,
      statusRole: "status" as const,
      statusText: "Could not read the answer aloud",
      showRetry: true,
      showDismiss: true,
      pauseResumeDisabled: true,
      stopKeyShortcut: "Escape" as const,
      sentenceAriaHidden: true as const,
    };
  }
  if (!params.active) {
    return {
      visible: false,
      mode: "hidden" as const,
      testId: null,
      statusRole: null,
      statusText: "",
      showRetry: false,
      showDismiss: false,
      pauseResumeDisabled: true,
      stopKeyShortcut: "Escape" as const,
      sentenceAriaHidden: true as const,
    };
  }
  return {
    visible: true,
    mode: "playing" as const,
    testId: "narration-bar" as const,
    statusRole: "region" as const,
    statusText: params.loading
      ? "Preparing audio…"
      : params.paused
        ? "Reading paused"
        : "Reading aloud",
    showRetry: false,
    showDismiss: false,
    pauseResumeDisabled: params.loading,
    stopKeyShortcut: "Escape" as const,
    sentenceAriaHidden: true as const,
  };
}
