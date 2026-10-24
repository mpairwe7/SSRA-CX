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
  readonly compactMobileMode: boolean;
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
  readonly viewportWidthPx?: number | undefined;
  readonly conversationTitle?: string | undefined;
  readonly conversationPinned?: boolean | undefined;
  readonly locale: LocaleCode;
  readonly localeAutoDetect?: boolean | undefined;
}): FloatingChatHeaderDescriptor {
  const compactMobileMode =
    params.viewportWidthPx !== undefined && Number.isFinite(params.viewportWidthPx)
      ? params.viewportWidthPx < 768
      : false;
  return {
    showCollapsedRailToggle: params.railCollapsed || compactMobileMode,
    railPeekActive: !compactMobileMode && params.railCollapsed && params.railPeekHover,
    compactMobileMode,
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
  readonly safeAreaBottomInsetCss: string;
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
    safeAreaBottomInsetCss: "max(0.75rem, env(safe-area-inset-bottom, 0px))",
  };
}

export interface HumanSubtleMicrocopyDescriptor {
  readonly phase: AssistantPhase;
  readonly locale: LocaleCode;
  readonly dir: "ltr" | "rtl";
  readonly statusText: string;
  readonly ariaLive: "polite";
  readonly showPulseIndicator: boolean;
}

const MICROCOPY_BY_PHASE: Readonly<
  Record<AssistantPhase, { readonly en: string; readonly ar: string; readonly pga: string }>
> = {
  idle: {
    en: "Ready. I’ll cite approved SSRA sources when they support an answer.",
    ar: "جاهز. سأذكر مصادر هيئة الإيرادات المعتمدة عندما تدعم الإجابة.",
    pga: "Jahiz. Gaaid azkur maraji SSRA lama yisandu al-ijaba.",
  },
  thinking: {
    en: "Reviewing your question…",
    ar: "جاري مراجعة سؤالك…",
    pga: "Gaaid yراجع sual بتاعك…",
  },
  searching: {
    en: "Checking published South Sudan tax laws and e-Tax guides…",
    ar: "جاري التحقق من القوانين الضريبية المعتمدة وأدلة بوابة الضرائب…",
    pga: "Gaaid yafhas qawanin ta dariba wa dalil e-Tax…",
  },
  churning: {
    en: "Verifying rates and statutory citations…",
    ar: "جاري التحقق من النسب والمراجع القانونية…",
    pga: "Gaaid yat'akkad min nisba wa qanun…",
  },
  streaming: {
    en: "Preparing your cited response…",
    ar: "جاري إعداد الإجابة الموثقة بالمراجع…",
    pga: "Gaaid yajahiz ijaba bil maraji…",
  },
};

/**
 * Build calm, non-robotic, culturally respectful micro-interaction status text
 * across assistant lifecycle phases (`idle`, `thinking`, `searching`, `churning`, `streaming`).
 */
export function buildHumanSubtleMicrocopy(
  phase: AssistantPhase,
  locale: LocaleCode,
  lowDataMode = false,
): HumanSubtleMicrocopyDescriptor {
  const row = MICROCOPY_BY_PHASE[phase];
  const statusText = locale === "ar" ? row.ar : locale === "pga" ? row.pga : row.en;
  return {
    phase,
    locale,
    dir: locale === "ar" ? "rtl" : "ltr",
    statusText,
    ariaLive: "polite",
    showPulseIndicator: !lowDataMode && phase !== "idle",
  };
}

const DOMAIN_LABELS_EN: Record<string, string> = {
  etax: "e-tax",
  ecustoms: "e-customs",
  eservices: "e-services",
  nra: "n r a",
  ssra: "s s r a",
  mofp: "m o f p",
  boss: "b o s s",
  mojca: "m o j c a",
  cms: "c m s",
  gov: "gov",
  ss: "s s",
};

const DOMAIN_LABELS_AR: Record<string, string> = {
  etax: "إي تاكس",
  ecustoms: "إي كاستمز",
  eservices: "إي سيرفيسز",
  nra: "إن آر إيه",
  ssra: "إس إس آر إيه",
  mofp: "إم أو إف بي",
  boss: "بي أو إس إس",
  mojca: "إم أو جيه سي إيه",
  cms: "سي إم إس",
  gov: "جوف",
  ss: "إس إس",
};

function formatDomainForSpeech(domain: string, locale = "en"): string {
  const isAr = locale === "ar";
  const host = domain
    .trim()
    .toLowerCase()
    .replace(/^www\./, "");
  const labels = host.split(".").filter(Boolean);
  const map = isAr ? DOMAIN_LABELS_AR : DOMAIN_LABELS_EN;
  const dotWord = isAr ? " دوت " : " dot ";
  return labels.map((lbl) => map[lbl] ?? lbl).join(dotWord);
}

function formatEmailLocalForSpeech(user: string, locale = "en"): string {
  const dotWord = locale === "ar" ? " دوت " : " dot ";
  return user
    .replace(/\./g, dotWord)
    .replace(/_/g, " underscore ")
    .replace(/-/g, " dash ")
    .replace(/\+/g, " plus ")
    .replace(/\betax\b/gi, "e-tax")
    .replace(/\becustoms\b/gi, "e-customs")
    .replace(/\d/g, (d) => ` ${d} `)
    .replace(/[ \t]+/g, " ")
    .trim();
}

const STEP_WORDS_BY_LOCALE: Record<string, string> = {
  en: "Step",
  ar: "الخطوة",
  pga: "Khatwa",
  din: "Dhöl",
  nus: "Dia",
  bfa: "Daket",
  zne: "Di",
  shk: "Yoo",
};

/**
 * Clean Markdown, inline citation markers (`[1]`, `[Sec-18]`), numbered steps, contact details,
 * and official `.gov.ss` domains before TTS synthesis across all 8 South Sudan languages.
 */
export function cleanMarkdownForSpeech(text: string, locale = "en"): string {
  const isAr = locale === "ar";
  const starWord = isAr ? "نجمة" : "star";
  const hashWord = isAr ? "شباك" : locale === "pga" ? "shibak" : "hash";
  const atWord = isAr ? "آت" : "at";
  const plusWord = isAr ? "زائد" : "plus";
  const tinEndPrefix = isAr ? "الرقم الضريبي المنتهي بـ" : "T I N ending in";
  const webLinkWord = isAr ? "رابط إلكتروني" : "web link";
  const stepWord = STEP_WORDS_BY_LOCALE[locale] ?? "Step";

  const footerMatch =
    /(?:^|\n)[ \t]*(?:\*\*)?(?:You might also want to know|Related questions)\b/i.exec(text);
  const withoutFooter = footerMatch ? text.slice(0, footerMatch.index) : text;

  return withoutFooter
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\bhttps?:\/\/[^\s/@]{1,128}@[^\s.,;:!?)]{1,256}/gi, webLinkWord)
    .replace(/(?<!\w)\*(\d{2,4}(?:\*\d{1,4}){0,5})#(?!\w)/g, (_m, code: string) => {
      const segs = code.split("*").map((s) => s.split("").join(" "));
      return `${starWord} ${segs.join(` ${starWord} `)} ${hashWord}`;
    })
    .replace(
      /(?:(?:\bTIN|\bT\.I\.N\.)[ \t]+)?(?:••••|\*{4,8})(\d{4})\b/gi,
      (_m, d: string) => `${tinEndPrefix} ${d.split("").join(" ")}`,
    )
    .replace(
      /\b(?:T-?I-?N|T\.I\.N\.)(?::|[ \t]+(?:is|number|no\.?))?[ \t]{0,4}(\d{3})-(\d{3})-(\d{4})\b/gi,
      (_m, g1: string, g2: string, g3: string) =>
        `T I N ${g1.split("").join(" ")}, ${g2.split("").join(" ")}, ${g3.split("").join(" ")}`,
    )
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, "$1$2")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\[(?:cit_|\d+|Sec-|Art-)[^\]]*\](?!\()/gi, "")
    .replace(
      /(?<![:/A-Za-z0-9._%+-])\b([A-Za-z0-9._%+-]{1,64})@([A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,4})\b(?![/])/gi,
      (_m, user: string, domain: string) =>
        `${formatEmailLocalForSpeech(user, locale)} ${atWord} ${formatDomainForSpeech(domain, locale)}`,
    )
    .replace(
      /(?<![A-Za-z0-9@.-])(?:https?:\/\/)?((?:www\.)?(?:etax\.nra|ecustoms\.nra|cms\.nra|nra|etax\.ssra|assist\.ssra|ssra|business\.eservices|customs\.eservices|trade\.eservices|eservices|mofp|boss|mojca)\.gov\.ss)(?:\/(?![^\s]*@)[^\s.,;:!?)]*)?(?=$|\s|[,;:!?)](?=$|\s)|\.+(?=$|\s))/gi,
      (_m, host: string) => formatDomainForSpeech(host, locale),
    )
    .replace(/https?:\/\/\S+/gi, webLinkWord)
    .replace(
      /(?<!\w)\+211[ \t-]?(?:\(0\)[ \t-]?)?\(?0?([19]\d{2})\)?[ \t-]?(\d{3})[ \t-]?(\d{3})\b/g,
      (_m, g1: string, g2: string, g3: string) =>
        `${plusWord} 2 1 1, ${g1.split("").join(" ")}, ${g2.split("").join(" ")}, ${g3.split("").join(" ")}`,
    )
    .replace(
      /(?<![\w+])\(?(0[19]\d{2})\)?[ \t-](\d{3})[ \t-](\d{3})\b/g,
      (_m, g1: string, g2: string, g3: string) =>
        `${g1.split("").join(" ")}, ${g2.split("").join(" ")}, ${g3.split("").join(" ")}`,
    )
    .replace(
      /\b0800[ \t-]*(\d{3})[ \t-]*(\d{3})\b/g,
      (_m, g1: string, g2: string) => `0 800, ${g1.split("").join(" ")}, ${g2.split("").join(" ")}`,
    )
    .replace(
      /\bP\.?[ \t]?O\.?[ \t]?Box[ \t]{1,4}(\d{1,6})\b/gi,
      (_m, box: string) => `P O Box ${box.split("").join(" ")}`,
    )
    .replace(/^[ \t]*(\d{1,2})[.)][ \t]+/gm, `${stepWord} $1: `)
    .replace(/(?<=[:.!?؟])[ \t]+(\d{1,2})\.[ \t]+(?=[A-Z\u0600-\u06FF])/g, ` ${stepWord} $1: `)
    .replace(/^[ \t]*[-*+][ \t]+/gm, " ")
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
  readonly dateUnavailable: readonly ConversationSummaryItem[];
}

export function groupConversationsByRecency(
  items: readonly ConversationSummaryItem[],
  nowMs: number,
  searchQuery = "",
): GroupedConversationRail {
  const normalizeSearch = (value: string) => value.normalize("NFKC").toLocaleLowerCase();
  const q = normalizeSearch(searchQuery.trim());
  const filtered = q ? items.filter((item) => normalizeSearch(item.title).includes(q)) : [...items];
  const timestamp = (value: number) =>
    Number.isFinite(value) && Math.abs(value) <= 8.64e15 ? value : Number.NEGATIVE_INFINITY;
  const sorted = [...filtered].sort((a, b) => {
    const delta = timestamp(b.updatedAtMs) - timestamp(a.updatedAtMs);
    return Number.isNaN(delta) || delta === 0 ? a.id.localeCompare(b.id) : delta;
  });

  const pinned: ConversationSummaryItem[] = [];
  const today: ConversationSummaryItem[] = [];
  const yesterday: ConversationSummaryItem[] = [];
  const previous7Days: ConversationSummaryItem[] = [];
  const older: ConversationSummaryItem[] = [];
  const dateUnavailable: ConversationSummaryItem[] = [];

  const dayOrdinal = (value: number): number | null => {
    const ms = timestamp(value);
    if (!Number.isFinite(ms)) return null;
    try {
      const parts = new Intl.DateTimeFormat("en", {
        timeZone: "Africa/Juba",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(new Date(ms));
      const part = (type: Intl.DateTimeFormatPartTypes) =>
        Number(parts.find((entry) => entry.type === type)?.value);
      const year = part("year");
      const month = part("month");
      const day = part("day");
      return Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)
        ? Math.floor(Date.UTC(year, month - 1, day) / 86_400_000)
        : null;
    } catch {
      return null;
    }
  };
  const todayOrdinal = dayOrdinal(nowMs);
  for (const item of sorted) {
    if (item.pinned) {
      pinned.push(item);
      continue;
    }
    const itemOrdinal = dayOrdinal(item.updatedAtMs);
    const ageDays =
      todayOrdinal === null || itemOrdinal === null ? null : todayOrdinal - itemOrdinal;
    if (ageDays === null || ageDays < 0) {
      dateUnavailable.push(item);
      continue;
    }
    if (ageDays === 0) {
      today.push(item);
    } else if (ageDays === 1) {
      yesterday.push(item);
    } else if (ageDays <= 7) {
      previous7Days.push(item);
    } else {
      older.push(item);
    }
  }

  return { pinned, today, yesterday, previous7Days, older, dateUnavailable };
}
