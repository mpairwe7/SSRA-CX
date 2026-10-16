/**
 * Taxpayer AI Call Receptionist & Exponential-Follower CallOrb (`packages/chat-ui/src/call-receptionist.ts`).
 *
 * Mirrors `components/call/CallScreen.tsx` & `components/call/CallOrb.tsx`:
 * 1. Pre-call recording consent gate (`status === "consent"`) before microphone capture begins.
 * 2. Call Language Chip (`"English · auto"` vs `"Juba Arabic · chosen"`, `role="menuitemradio"`).
 * 3. `CallOrb` exponential-follower (`computeCallOrbFrame`): playback (`output >= 0.06 && output >= input`)
 *    wins ties over mic input so speaker echo never flickers the orb to `"listening"`, easing in fast (`0.45`)
 *    and out slow (`0.12`), and freezing at `0` under `prefers-reduced-motion: reduce`.
 * 4. Pinned-to-bottom caption scroll tracking (`PIN_THRESHOLD_PX = 48`).
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
  if (!params.active || params.prefersReducedMotion) {
    return { mode: "idle", smoothedLevel: 0, cssOrbLevel: "0" };
  }
  const input = Number.isFinite(params.inputLevel) ? Math.max(0, params.inputLevel) : 0;
  const output = Number.isFinite(params.outputLevel) ? Math.max(0, params.outputLevel) : 0;
  const prev = Number.isFinite(params.previousSmoothed) ? Math.max(0, params.previousSmoothed) : 0;

  const speaking = output >= 0.06 && output >= input;
  const listening = !speaking && input >= 0.06;
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
  readonly statusPillTone: "active" | "transferring" | "ended";
  readonly formattedDuration: string;
  readonly languageChip: CallLanguageChipDescriptor;
  readonly canRequestOfficer: boolean;
  readonly canRequestCallback: boolean;
}

export function buildCallReceptionistScreen(params: {
  readonly status: CallSessionStatus;
  readonly durationSeconds: number;
  readonly language: LocaleCode;
  readonly languageName: string;
  readonly languageSource: CallLanguageSource;
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
      statusPillTone: "ended",
      formattedDuration: "00:00",
      languageChip,
      canRequestOfficer: false,
      canRequestCallback: false,
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
  };
}
