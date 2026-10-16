/**
 * Chatv2 Main Workbench Primitives (`packages/chat-ui/src/chat-workbench.ts`):
 * - Floating Top Strip (`buildFloatingChatHeader`) with WAI-ARIA menu focus hand-back
 * - Single-Toggle Voice Mode & 5-Bar Live Waveform (`buildChatComposerState`, `joinDictated`, `normalizeWaveformBars`)
 * - Connector Attribution (`buildConnectorAttribution`) & Speech Cleaner (`cleanMarkdownForSpeech`)
 * - Conversation Rail Recency Grouping (`groupConversationsByRecency`)
 */

import type { LocaleCode } from "@ssra/contracts";

export type AssistantPhase = "idle" | "thinking" | "searching" | "churning" | "streaming";

export type ConnectorOutcome = "found" | "no_record" | "needs_input" | "unavailable";
export type ConnectorSkipReason = "unavailable" | "not_offered" | "disabled";

export interface ConnectorUse {
  readonly namespace: string;
  readonly label: string;
  readonly mode: "live" | "simulation";
  readonly outcome?: ConnectorOutcome | undefined;
}

export interface ConnectorNotice {
  readonly namespace: string;
  readonly label: string;
  readonly reason: ConnectorSkipReason;
}

export interface FloatingChatHeaderDescriptor {
  readonly showCollapsedRailToggle: boolean;
  readonly railPeekActive: boolean;
  readonly conversationTitle: string | null;
  readonly conversationPinned: boolean;
  readonly locale: LocaleCode;
  readonly localeAutoDetect: boolean;
  readonly ariaMenuRole: "menu";
  readonly restoreFocusToTriggerBeforeModal: true;
}

export function buildFloatingChatHeader(params: {
  readonly hasStartedChat: boolean;
  readonly railCollapsed: boolean;
  readonly railPeekHover: boolean;
  readonly conversationTitle?: string | undefined;
  readonly conversationPinned?: boolean | undefined;
  readonly locale: LocaleCode;
  readonly localeAutoDetect?: boolean | undefined;
}): FloatingChatHeaderDescriptor {
  return {
    showCollapsedRailToggle: params.railCollapsed,
    railPeekActive: params.railCollapsed && params.railPeekHover,
    conversationTitle: params.hasStartedChat ? (params.conversationTitle ?? "New chat") : null,
    conversationPinned: Boolean(params.conversationPinned),
    locale: params.locale,
    localeAutoDetect: params.localeAutoDetect ?? true,
    ariaMenuRole: "menu",
    restoreFocusToTriggerBeforeModal: true,
  };
}

/**
 * Join what was already in the composer with dictated speech.
 */
export function joinDictated(base: string, spoken: string): string {
  const b = base.trimEnd();
  const s = spoken.trimStart();
  if (!b) return s;
  if (!s) return b;
  return `${b} ${s}`;
}

/**
 * Normalize 5 live microphone frequency bars into `[0.15..1.0]` for `.composer-waveform`.
 */
export function normalizeWaveformBars(levels?: readonly number[]): readonly number[] {
  const hasSignal =
    Array.isArray(levels) &&
    levels.length >= 5 &&
    levels.some((v) => Number.isFinite(v) && v > 0.05);
  return Array.from({ length: 5 }, (_, idx) => {
    if (!hasSignal || !levels) return 0.2;
    const raw = levels[idx] ?? 0.2;
    if (!Number.isFinite(raw)) return 0.2;
    return Math.min(1.0, Math.max(0.15, Number(raw.toFixed(2))));
  });
}

export interface ChatComposerStateDescriptor {
  readonly voiceMode: boolean;
  readonly narrationEnabled: boolean;
  readonly primaryAction: "send" | "stop" | "mic";
  readonly waveformBars: readonly number[];
  readonly dictationNotice: string | null;
  readonly placeholder: string;
}

/**
 * Entering `voiceMode` automatically enables spoken narration (eliminating redundant
 * "Voice" + "Narrate" checkboxes on 370px mobile viewports).
 */
export function buildChatComposerState(params: {
  readonly message: string;
  readonly isLoading: boolean;
  readonly isRecording: boolean;
  readonly voiceMode: boolean;
  readonly audioLevels?: readonly number[] | undefined;
  readonly dictationNotice?: string | null | undefined;
  readonly officerLiveChat?: boolean | undefined;
}): ChatComposerStateDescriptor {
  const primaryAction = params.isLoading
    ? "stop"
    : params.message.trim().length > 0
      ? "send"
      : "mic";
  return {
    voiceMode: params.voiceMode,
    narrationEnabled: params.voiceMode,
    primaryAction,
    waveformBars: normalizeWaveformBars(params.audioLevels),
    dictationNotice: params.dictationNotice ?? null,
    placeholder: params.officerLiveChat
      ? "Message the SSRA officer…"
      : "Ask SSRA Assist about TIN, PAYE, customs, or e-Tax…",
  };
}

/**
 * Clean Markdown & inline citation markers (`[1]`, `[Sec-18]`) before TTS synthesis.
 */
export function cleanMarkdownForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\[(?:cit_|\d+|Sec-|Art-)[^\]]*\](?!\()/gi, "")
    .replace(/https?:\/\/\S+/g, "official SSRA portal")
    .replace(/^\s*[-*+]\s+/gm, " ")
    .replace(/[*_~>#]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export interface ConversationSummaryItem {
  readonly id: string;
  readonly title: string;
  readonly updatedAtMs: number;
  readonly pinned?: boolean | undefined;
}

export interface GroupedConversationRail {
  readonly pinned: readonly ConversationSummaryItem[];
  readonly today: readonly ConversationSummaryItem[];
  readonly yesterday: readonly ConversationSummaryItem[];
  readonly previous7Days: readonly ConversationSummaryItem[];
  readonly older: readonly ConversationSummaryItem[];
}

export function groupConversationsByRecency(
  items: readonly ConversationSummaryItem[],
  nowMs: number,
  searchQuery = "",
): GroupedConversationRail {
  const q = searchQuery.trim().toLowerCase();
  const filtered = q ? items.filter((item) => item.title.toLowerCase().includes(q)) : [...items];
  const sorted = [...filtered].sort((a, b) => b.updatedAtMs - a.updatedAtMs);

  const pinned: ConversationSummaryItem[] = [];
  const today: ConversationSummaryItem[] = [];
  const yesterday: ConversationSummaryItem[] = [];
  const previous7Days: ConversationSummaryItem[] = [];
  const older: ConversationSummaryItem[] = [];

  const dayMs = 86_400_000;
  for (const item of sorted) {
    if (item.pinned) {
      pinned.push(item);
      continue;
    }
    const ageMs = Math.max(0, nowMs - item.updatedAtMs);
    if (ageMs < dayMs) {
      today.push(item);
    } else if (ageMs < 2 * dayMs) {
      yesterday.push(item);
    } else if (ageMs < 7 * dayMs) {
      previous7Days.push(item);
    } else {
      older.push(item);
    }
  }

  return { pinned, today, yesterday, previous7Days, older };
}
