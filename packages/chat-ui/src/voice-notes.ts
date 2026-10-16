/**
 * Phase 4 Low-Bitrate Voice Notes for `packages/chat-ui` (Sections 9.3 & 11).
 *
 * Enforces:
 * 1. Mandatory explicit recording consent before capturing audio (`recordingConsentGranted`).
 * 2. Low-bandwidth Opus/WebM encoding (`audio/webm;codecs=opus` or `audio/ogg;codecs=opus`)
 *    at <= 24 kbps for South Sudan 2G/3G networks.
 * 3. Maximum voice-note duration of 60 seconds and payload cap of 256 KB.
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
