/**
 * 2G/Offline Outbox Queue for `apps/web` PWA (Section 9.2, 11, ADR-011).
 *
 * Security Invariants:
 * 1. Only anonymous `T0` public questions may be queued in the offline outbox on shared devices.
 * 2. Any `T1`–`T4` personal query or message containing a 9–12 digit TIN (including separated or
 *    Arabic-Indic numerals) is rejected from client storage.
 * 3. Bounded capacity (`maxItems = 25`) prevents unbounded memory/storage growth.
 */

import type { LocaleCode, RiskTier } from "@ssra/contracts";

export interface QueuedOutboxMessage {
  readonly id: string;
  readonly message: string;
  readonly locale: LocaleCode;
  readonly tier: RiskTier;
  readonly queuedAtIso: string;
}

export const MAX_OFFLINE_VOICE_NOTE_BYTES = 64 * 1024;
export const MAX_OFFLINE_VOICE_NOTE_SECONDS = 30;

export interface QueuedOfflineVoiceNote {
  readonly id: string;
  readonly locale: LocaleCode;
  readonly tier: RiskTier;
  readonly mimeType: "audio/webm;codecs=opus" | "audio/ogg;codecs=opus";
  readonly durationSeconds: number;
  readonly sizeBytes: number;
  readonly recordingConsentGranted: boolean;
  readonly queuedAtIso: string;
}

const UNMASKED_TIN_OR_PHONE_PATTERN = /\d{9,12}|\+?211\d{9}/;
const UNMASKED_NATIONAL_ID_OR_EMAIL_PATTERN =
  /\b[RP]\d{7,8}\b|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/i;

/**
 * Detect unmasked TINs, `+211` phone numbers, South Sudan National IDs (including Arabic-Indic numerals), or emails.
 */
function containsUnmaskedTin(message: string): boolean {
  const numeralNormalized = message
    .normalize("NFKC")
    .replace(/[\u0660-\u0669]/g, (digit) => String(digit.charCodeAt(0) - 0x0660));
  if (UNMASKED_NATIONAL_ID_OR_EMAIL_PATTERN.test(numeralNormalized)) {
    return true;
  }
  const stripped = numeralNormalized.replace(/[\s\-.]/g, "");
  return UNMASKED_TIN_OR_PHONE_PATTERN.test(stripped);
}

export class OfflineOutboxQueue {
  private readonly items: QueuedOutboxMessage[] = [];
  private readonly voiceNotes: QueuedOfflineVoiceNote[] = [];
  private readonly maxItems: number;

  public constructor(maxItems = 25) {
    if (!Number.isInteger(maxItems) || maxItems < 1) {
      throw new RangeError("maxItems must be a positive integer");
    }
    this.maxItems = maxItems;
  }

  public enqueue(item: QueuedOutboxMessage): {
    readonly queued: boolean;
    readonly reason?: string;
  } {
    if (item.tier !== "T0") {
      return {
        queued: false,
        reason: "SECURITY_POLICY_T0_ONLY_OFFLINE_QUEUE",
      };
    }
    if (containsUnmaskedTin(item.message)) {
      return {
        queued: false,
        reason: "SECURITY_POLICY_PII_REJECTED_FROM_OFFLINE_QUEUE",
      };
    }
    if (this.items.length >= this.maxItems) {
      return {
        queued: false,
        reason: "OFFLINE_OUTBOX_CAPACITY_EXCEEDED",
      };
    }
    this.items.push(item);
    return { queued: true };
  }

  public drainAll(): QueuedOutboxMessage[] {
    return this.items.splice(0, this.items.length);
  }

  /**
   * Queue a compressed <= 64 KB (`<= 30s` @ 12 kbps Opus) T0 public voice note for store-and-forward transcription when offline.
   */
  public enqueueVoiceNote(note: QueuedOfflineVoiceNote): {
    readonly queued: boolean;
    readonly reason?: string;
  } {
    if (note.tier !== "T0") {
      return { queued: false, reason: "SECURITY_POLICY_T0_ONLY_OFFLINE_QUEUE" };
    }
    if (!note.recordingConsentGranted) {
      return { queued: false, reason: "VOICE_RECORDING_CONSENT_REQUIRED" };
    }
    if (
      !Number.isFinite(note.durationSeconds) ||
      note.durationSeconds <= 0 ||
      note.durationSeconds > MAX_OFFLINE_VOICE_NOTE_SECONDS
    ) {
      return { queued: false, reason: "EXCEEDS_30S_OFFLINE_VOICE_NOTE_CAP" };
    }
    if (
      !Number.isFinite(note.sizeBytes) ||
      note.sizeBytes <= 0 ||
      note.sizeBytes > MAX_OFFLINE_VOICE_NOTE_BYTES
    ) {
      return { queued: false, reason: "EXCEEDS_64KB_OFFLINE_VOICE_NOTE_CAP" };
    }
    if (this.voiceNotes.length >= this.maxItems) {
      return { queued: false, reason: "OFFLINE_OUTBOX_CAPACITY_EXCEEDED" };
    }
    this.voiceNotes.push(note);
    return { queued: true };
  }

  public drainVoiceNotes(): QueuedOfflineVoiceNote[] {
    return this.voiceNotes.splice(0, this.voiceNotes.length);
  }

  public clearOnLogout(): void {
    this.items.length = 0;
    this.voiceNotes.length = 0;
  }

  public get size(): number {
    return this.items.length;
  }
}
