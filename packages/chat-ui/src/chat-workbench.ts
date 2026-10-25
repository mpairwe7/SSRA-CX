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

function toAsciiDigitsForSpeech(raw: string): string {
  return raw.replace(/[٠-٩]/g, (ch) => String(ch.charCodeAt(0) - 0x0660));
}

function formatEmailLocalForSpeech(user: string, locale = "en"): string {
  const isAr = locale === "ar";
  const dotWord = isAr ? " دوت " : " dot ";
  const underWord = isAr ? " شرطة سفلية " : " underscore ";
  const dashWord = isAr ? " شرطة " : " dash ";
  const plusWord = isAr ? " زائد " : " plus ";
  return user
    .replace(/\./g, dotWord)
    .replace(/_/g, underWord)
    .replace(/-/g, dashWord)
    .replace(/\+/g, plusWord)
    .replace(/\betax\b/gi, isAr ? "إي تاكس" : "e-tax")
    .replace(/\becustoms\b/gi, isAr ? "إي كاستمز" : "e-customs")
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
  const isPga = locale === "pga";
  const starWord = isAr ? "نجمة" : "star";
  const hashWord = isAr ? "شباك" : isPga ? "shibak" : "hash";
  const atWord = isAr ? "آت" : "at";
  const plusWord = isAr ? "زائد" : "plus";
  const tinEndPrefix = isAr ? "الرقم الضريبي المنتهي بـ" : "T I N ending in";
  const tinPrefix = isAr ? "الرقم الضريبي" : "T I N";
  const poBoxWord = isAr ? "صندوق بريد" : isPga ? "Sandug Barid" : "P O Box";
  const secWord = isAr ? "المادة" : isPga ? "Madda" : "Section";
  const artWord = isAr ? "المادة" : isPga ? "Madda" : "Article";
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
        `${tinPrefix} ${g1.split("").join(" ")}, ${g2.split("").join(" ")}, ${g3.split("").join(" ")}`,
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
      /(?<![A-Za-z0-9@.-])<?(?:https?:\/\/)?((?:www\.)?(?:etax\.nra|ecustoms\.nra|cms\.nra|nra|etax\.ssra|assist\.ssra|ssra|business\.eservices|customs\.eservices|trade\.eservices|eservices|mofp|boss|mojca)\.gov\.ss)(?:\/(?![^\s]*@)[^\s.,;:!?)>\]"'،؛؟»]*)?>?(?=$|\s|[,;:!?)>\]"'،؛؟»](?=$|\s)|\.+(?=$|\s))/gi,
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
      (_m, box: string) => `${poBoxWord} ${box.split("").join(" ")}`,
    )
    .replace(/\bSec\.\s*(\d+[A-Za-z]?)\b/g, `${secWord} $1`)
    .replace(/\bArt\.\s*(\d+[A-Za-z]?)\b/g, `${artWord} $1`)
    .replace(
      /^[ \t]*(\d{1,2}|[٠-٩]{1,2})[.)][ \t]+/gm,
      (_m, num: string) => `${stepWord} ${toAsciiDigitsForSpeech(num)}: `,
    )
    .replace(
      /(?<=[:.!?؟؛;])[ \t]+(\d{1,2}|[٠-٩]{1,2})[.)][ \t]+(?=[A-Za-z0-9\u0600-\u06FF\u00C0-\u024F])/g,
      (_m, num: string) => ` ${stepWord} ${toAsciiDigitsForSpeech(num)}: `,
    )
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

/**
 * Reviewed Phase 1 UI Translation Dictionary (`en`, `pga`, `ar`) with safe English fallback
 * for unreviewed Phase 2 languages (`din`, `nus`, `bfa`, `zne`, `shk`) per `OQ-008` / `FE-G5`
 * and `FinalYearProject/App/frontend/src/lib/i18n/index.ts`.
 */
export const SSRA_UI_TRANSLATIONS = {
  en: {
    "landing.eyebrow": "Republic of South Sudan · SSRA / NRA Grounded AI Assistant",
    "landing.headline": "How can I help with your South Sudan taxes today?",
    "landing.subtitle":
      "Ask about TIN registration, PAYE, TCC, customs, or e-Tax. Answers cite approved sources when available. If a source cannot be confirmed, SSRA Assist will say so and offer staff help.",
    "composer.placeholder":
      "Ask about SSRA taxes, TIN, PAYE, TCC, or customs in English, Arabic, or Juba Arabic…",
    "composer.dropFiles":
      "Drop files or screenshots to inspect (PDF, DOCX, XLSX, CSV, TXT, or image)",
    "header.callReceptionist": "Call receptionist",
    "header.languageAuto": "Response language: Auto-detect (currently {value})",
    "header.languageSelected": "Response language: {value}",
    "message.spoken": "Spoken",
    "message.latest": "Latest",
  },
  pga: {
    "landing.eyebrow": "Jumhuriya ta South Sudan · Musaa'id SSRA / NRA",
    "landing.headline": "Kif ana agdar asaidu inta fi darayib ta South Sudan al-yom?",
    "landing.subtitle":
      "Is'al an TIN, PAYE, TCC, Jamarik, aw e-Tax. Ijaba bitzkur maraji SSRA lama yisanduha. Iza al-masdar mish mu'akkad, SSRA Assist bitwaddeh da wa bitqaddim musaa'ada min الموظفين.",
    "composer.placeholder": "As'al ayi su'al ala TIN, PAYE, TCC, aw Jamarik bi Arabi Juba...",
    "composer.dropFiles":
      "Khalli malafat aw sura ta shasha hina (PDF, DOCX, XLSX, CSV, TXT, aw sura)",
    "header.callReceptionist": "Ittasil bil istiqbal",
    "header.languageAuto": "Lugha ta ijaba: Tilqa'i ({value})",
    "header.languageSelected": "Lugha ta ijaba: {value}",
    "message.spoken": "Bil sot",
    "message.latest": "Al-akhir",
  },
  ar: {
    "landing.eyebrow": "جمهورية جنوب السودان · المساعد الذكي لهيئة الإيرادات (SSRA / NRA)",
    "landing.headline": "كيف يمكنني مساعدتك في ضرائب جنوب السودان اليوم؟",
    "landing.subtitle":
      "اسأل عن تسجيل الرقم الضريبي أو PAYE أو شهادة الامتثال أو الجمارك أو e-Tax. تذكر الإجابات المصادر المعتمدة عند توفرها. إذا تعذر تأكيد المصدر، سنوضح ذلك ونقترح التواصل مع موظف.",
    "composer.placeholder":
      "اسأل عن الرقم الضريبي TIN أو ضريبة الدخل PAYE أو شهادة الامتثال TCC أو الجمارك...",
    "composer.dropFiles": "أفلت الملفات أو لقطات الشاشة هنا للفحص (PDF أو DOCX أو XLSX أو صورة)",
    "header.callReceptionist": "موظف الاستقبال الصوتي",
    "header.languageAuto": "لغة الإجابة: تلقائي ({value})",
    "header.languageSelected": "لغة الإجابة: {value}",
    "message.spoken": "منطوق صوتياً",
    "message.latest": "الأحدث",
  },
} as const;

export type UiTranslationKey = keyof typeof SSRA_UI_TRANSLATIONS.en;

export function translateUiString(
  locale: string,
  key: UiTranslationKey,
  vars?: Readonly<Record<string, string | number>>,
): string {
  const dict =
    locale === "ar"
      ? SSRA_UI_TRANSLATIONS.ar
      : locale === "pga"
        ? SSRA_UI_TRANSLATIONS.pga
        : SSRA_UI_TRANSLATIONS.en;
  const template: string = dict[key] ?? SSRA_UI_TRANSLATIONS.en[key];
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    Object.hasOwn(vars, name) ? String(vars[name]) : whole,
  );
}

const SUPPORTED_LOCALE_SET: ReadonlySet<LocaleCode> = new Set([
  "en",
  "ar",
  "pga",
  "din",
  "nus",
  "bfa",
  "zne",
  "shk",
]);

const EXPLICIT_SWITCH_MAP: ReadonlyArray<readonly [RegExp, LocaleCode]> = [
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+juba\s+arabic\b|\bbi\s+arabi\s+juba\b|بالعربي\s+جوبا|بعربي\s+جوبا/i,
    "pga",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+arabic\b|(?:تحدث|تكلم|اجب|أجب|رد|اشرح)\s+(?:بالعربي|بالعربية|عربي)/i,
    "ar",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+english\b|(?:تحدث|تكلم|اجب|أجب|رد)\s+بالانجليزي/i,
    "en",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+(?:dinka|thuɔŋjäŋ|thuongjang)\b/i,
    "din",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+(?:nuer|thok\s+naath|thok\s+nath)\b/i,
    "nus",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+(?:bari|kutuk\s+na\s+bari)\b/i,
    "bfa",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+(?:pazande|zande)\b/i,
    "zne",
  ],
  [
    /\b(?:answer|reply|respond|speak|explain|switch|talk)\b[^.!?]{0,25}\b(?:in|to)\s+(?:shilluk|dhøg\s+cøllø|dhog\s+collo)\b/i,
    "shk",
  ],
];

const ARABIC_SCRIPT_RE = /[\u0600-\u06FF]/;
const PGA_ARABIC_MARKERS_RE =
  /(?:^|\s)(?:شنو|عشان|بتاع|بتاعي|بتاعت|هسي|قروش|بيشتغل|ندفع|نسجل)(?=\s|$|[؟،.])/g;
const PGA_LATIN_MARKERS_RE =
  /\b(?:kif|shunu|gaaid|agdar|asaidu|tasjil|dariba|darayib|jamarik|bitaa|al-yom)\b/;
const DIN_MARKERS_RE = /\b(?:thuongjang|ajul|weu|bengic|akuma|tene|caar|nhialic|muk)\b/;
const NUS_MARKERS_RE = /\b(?:thok|naath|nath|guaath|kuäär|miem|rwac)\b/;
const BFA_MARKERS_RE = /\b(?:kutuk|nyepo|konyo|bari|molok|gwoso)\b/;
const ZNE_MARKERS_RE = /\b(?:pazande|marimo|kumba|pai|gbia)\b/;
const SHK_MARKERS_RE = /\b(?:collo|dhog|jwok|kwer|kyew)\b/;

/**
 * Instant client-side language & explicit-switch detector matching `ssra_voice`
 * and `FinalYearProject` `adoptResponseLocale`. Bounded to 1,024 chars (`<0.05ms` CPU).
 */
export function detectClientTextLanguageHint(
  text: string,
  currentLocale: LocaleCode = "en",
): { readonly detectedLocale: LocaleCode; readonly explicitSwitch: boolean } {
  const clean = String(text || "")
    .trim()
    .slice(0, 1024);
  if (!clean) return { detectedLocale: currentLocale, explicitSwitch: false };

  for (const [pattern, target] of EXPLICIT_SWITCH_MAP) {
    if (pattern.test(clean)) {
      return { detectedLocale: target, explicitSwitch: true };
    }
  }

  if (ARABIC_SCRIPT_RE.test(clean)) {
    const pgaArabicHits = clean.match(PGA_ARABIC_MARKERS_RE) ?? [];
    return {
      detectedLocale: pgaArabicHits.length > 0 ? "pga" : "ar",
      explicitSwitch: false,
    };
  }

  const folded = clean
    .toLowerCase()
    .replace(/ë/g, "e")
    .replace(/ɛ/g, "e")
    .replace(/ɔ/g, "o")
    .replace(/ŋ/g, "ng")
    .replace(/[öä]/g, "a")
    .replace(/ï/g, "i")
    .replace(/ü/g, "u")
    .replace(/ø/g, "o");

  if (PGA_LATIN_MARKERS_RE.test(folded)) {
    return { detectedLocale: "pga", explicitSwitch: false };
  }
  if (DIN_MARKERS_RE.test(folded)) {
    return { detectedLocale: "din", explicitSwitch: false };
  }
  if (NUS_MARKERS_RE.test(folded)) {
    return { detectedLocale: "nus", explicitSwitch: false };
  }
  if (BFA_MARKERS_RE.test(folded)) {
    return { detectedLocale: "bfa", explicitSwitch: false };
  }
  if (ZNE_MARKERS_RE.test(folded)) {
    return { detectedLocale: "zne", explicitSwitch: false };
  }
  if (SHK_MARKERS_RE.test(folded)) {
    return { detectedLocale: "shk", explicitSwitch: false };
  }

  return { detectedLocale: currentLocale, explicitSwitch: false };
}

export interface AdoptedLocaleDecision {
  readonly locale: LocaleCode;
  readonly detectedLocale: LocaleCode;
  readonly localeExplicit: boolean;
  readonly shouldSwitchInterface: boolean;
  readonly badgeLabel: string;
}

/**
 * Adopt the backend's detected language (`data.locale` or `english_router_envelope.detected_input_language`)
 * following `FinalYearProject/App/frontend/src/store/useChatStore.ts` `adoptResponseLocale`.
 */
export function adoptDetectedResponseLocale(params: {
  readonly currentLocale: LocaleCode;
  readonly localeExplicit: boolean;
  readonly responseLocale?: string | null | undefined;
  readonly localeSource?: string | null | undefined;
  readonly explicitUserSwitch?: boolean | undefined;
}): AdoptedLocaleDecision {
  const candidate = (params.responseLocale ?? "").trim().toLowerCase() as LocaleCode;
  const validDetected = SUPPORTED_LOCALE_SET.has(candidate) ? candidate : params.currentLocale;
  const isExplicitRequest =
    params.explicitUserSwitch === true || params.localeSource === "explicit_request";
  const nextExplicit = isExplicitRequest ? true : params.localeExplicit;
  const nextLocale =
    isExplicitRequest || !params.localeExplicit ? validDetected : params.currentLocale;
  return {
    locale: nextLocale,
    detectedLocale: validDetected,
    localeExplicit: nextExplicit,
    shouldSwitchInterface: isExplicitRequest,
    badgeLabel: nextExplicit
      ? validDetected.toUpperCase()
      : `AUTO · ${validDetected.toUpperCase()}`,
  };
}

export type ComposerSpeechState =
  | "idle"
  | "starting"
  | "listening"
  | "processing"
  | "unavailable"
  | "error";

export interface ComposerSpeechControlsDescriptor {
  readonly dictateButton: {
    readonly iconName: "mic";
    readonly testId: "composer-mic";
    readonly ariaLabel: string;
    readonly tooltip: string;
    readonly className: string;
    readonly disabled: boolean;
  };
  readonly autoVoiceButton: {
    readonly iconName: "voiceWave";
    readonly testId: "composer-voicemode";
    readonly ariaLabel: string;
    readonly ariaPressed: boolean;
    readonly tooltip: string;
    readonly className: string;
    readonly isPrimarySlot: boolean;
  };
  readonly primarySlotMode: "voicemode" | "send" | "stop";
}

/**
 * Models the two side-by-side speech controls in the Main Chat composer toolbar
 * (`FinalYearProject/App/frontend/src/components/ChatInput.tsx` lines 780-851):
 * 1. Dictate (`mic-circle-btn`, `ICONS.mic`) — fills the textarea via `joinDictated`
 * 2. Auto Voice Mode (`voicemode-circle-btn`, `ICONS.voiceWave`) — hands-free turn-taking & `VoiceModeDock`
 */
export function buildComposerSpeechControls(params: {
  readonly speechState: ComposerSpeechState;
  readonly voiceMode: boolean;
  readonly hasText: boolean;
  readonly isLoading: boolean;
  readonly isUploading?: boolean | undefined;
}): ComposerSpeechControlsDescriptor {
  const { speechState, voiceMode, hasText, isLoading } = params;
  const isUploading = Boolean(params.isUploading);
  const dictateAriaLabel =
    speechState === "listening"
      ? "Stop listening"
      : speechState === "starting"
        ? "Opening the microphone"
        : speechState === "processing"
          ? "Transcribing"
          : "Start speaking";
  const dictateTooltip =
    speechState === "listening"
      ? "Stop listening"
      : speechState === "starting"
        ? "Opening the microphone…"
        : speechState === "processing"
          ? "Transcribing…"
          : "Dictate";
  const dictateClasses = ["composer-circle-btn", "mic-circle-btn"];
  if (speechState === "listening") dictateClasses.push("btn-recording");
  if (speechState === "starting" || speechState === "processing") {
    dictateClasses.push("is-processing");
  }

  const primarySlotMode: "voicemode" | "send" | "stop" = isLoading
    ? "stop"
    : hasText || isUploading
      ? "send"
      : "voicemode";

  const autoVoiceClasses = ["composer-circle-btn", "voicemode-circle-btn"];
  if (voiceMode) autoVoiceClasses.push("is-active");
  if (primarySlotMode === "voicemode") autoVoiceClasses.push("is-primary-slot");

  return {
    dictateButton: {
      iconName: "mic",
      testId: "composer-mic",
      ariaLabel: dictateAriaLabel,
      tooltip: dictateTooltip,
      className: dictateClasses.join(" "),
      disabled:
        speechState === "unavailable" ||
        isLoading ||
        speechState === "starting" ||
        speechState === "processing",
    },
    autoVoiceButton: {
      iconName: "voiceWave",
      testId: "composer-voicemode",
      ariaLabel: voiceMode ? "Exit voice conversation mode" : "Enter voice conversation mode",
      ariaPressed: voiceMode,
      tooltip: voiceMode ? "Exit voice mode" : "Enter voice mode",
      className: autoVoiceClasses.join(" "),
      isPrimarySlot: primarySlotMode === "voicemode",
    },
    primarySlotMode,
  };
}

export interface MainChatLayoutAlignmentDescriptor {
  readonly headerCallIconName: "phone";
  readonly headerCallButtonClass: "icon-btn call-btn hdrv2-call";
  readonly composerDictateIconName: "mic";
  readonly composerAutoVoiceIconName: "voiceWave";
  readonly messageListScrollFadeMaskCss: string;
  readonly landingMaxWidthPx: 720;
  readonly landingSubtitleCentered: true;
  readonly assistantAvatarSizePx: 32;
  readonly userSpokenTagEnabled: true;
  readonly composerDragDropEnabled: true;
  readonly composerClipboardPasteEnabled: true;
  readonly iosTouchFontSizeMinPx: 16;
}

/**
 * Codifies the `FinalYearProject` (`chatv2`) Main Chat layout alignment & interaction contract.
 */
export function buildMainChatLayoutAlignment(): MainChatLayoutAlignmentDescriptor {
  return {
    headerCallIconName: "phone",
    headerCallButtonClass: "icon-btn call-btn hdrv2-call",
    composerDictateIconName: "mic",
    composerAutoVoiceIconName: "voiceWave",
    messageListScrollFadeMaskCss:
      "linear-gradient(to bottom, transparent 0, #000 18px, #000 calc(100% - 18px), transparent 100%)",
    landingMaxWidthPx: 720,
    landingSubtitleCentered: true,
    assistantAvatarSizePx: 32,
    userSpokenTagEnabled: true,
    composerDragDropEnabled: true,
    composerClipboardPasteEnabled: true,
    iosTouchFontSizeMinPx: 16,
  };
}

export interface LanguageMenuOptionDescriptor {
  readonly value: "auto" | "en" | "pga" | "ar" | "din" | "nus" | "bfa" | "zne" | "shk";
  readonly label: string;
  readonly native: string;
  readonly reviewed: boolean;
}

export const SSRA_LANGUAGE_MENU_OPTIONS: readonly LanguageMenuOptionDescriptor[] = [
  {
    value: "auto",
    label: "Auto-detect",
    native: "Answers follow the language you type",
    reviewed: true,
  },
  { value: "en", label: "English", native: "English (en)", reviewed: true },
  {
    value: "pga",
    label: "Juba Arabic",
    native: "Arabi Juba · عربي جوبا (pga)",
    reviewed: true,
  },
  { value: "ar", label: "Arabic", native: "العربية (ar)", reviewed: true },
  {
    value: "din",
    label: "Thuɔŋjäŋ Dinka",
    native: "Thuɔŋjäŋ (din) · Not yet reviewed (interface in English)",
    reviewed: false,
  },
  {
    value: "nus",
    label: "Thok Naath Nuer",
    native: "Thok Naath (nus) · Not yet reviewed (interface in English)",
    reviewed: false,
  },
  {
    value: "bfa",
    label: "Bari",
    native: "Kutuk na Bari (bfa) · Not yet reviewed (interface in English)",
    reviewed: false,
  },
  {
    value: "zne",
    label: "Pazande",
    native: "Pazande (zne) · Not yet reviewed (interface in English)",
    reviewed: false,
  },
  {
    value: "shk",
    label: "Dhøg Cøllø Shilluk",
    native: "Dhøg Cøllø (shk) · Not yet reviewed (interface in English)",
    reviewed: false,
  },
];

export interface HeaderLanguageMenuModel {
  readonly triggerCode: string;
  readonly showAutoBadge: boolean;
  readonly triggerSrLabel: string;
  readonly triggerTitle: string;
  readonly checkedValue: LanguageMenuOptionDescriptor["value"];
  readonly activeIndex: number;
  readonly rovingIndex: number;
  readonly options: readonly (LanguageMenuOptionDescriptor & {
    readonly checked: boolean;
    readonly tabIndex: 0 | -1;
  })[];
}

/**
 * Build the `FinalYearProject` (`LanguageMenu.tsx`) header trigger and focus-trapped
 * `role="radiogroup"` dialog state for SSRA Assist's 8 South Sudan languages + Auto-detect.
 */
export function buildHeaderLanguageMenuModel(params: {
  readonly locale: string;
  readonly detectedLocale?: string;
  readonly localeExplicit: boolean;
  readonly focusIndex?: number | null;
}): HeaderLanguageMenuModel {
  const effectiveCode = (
    params.localeExplicit ? params.locale : (params.detectedLocale ?? params.locale)
  )
    .trim()
    .toLowerCase();
  const currentOpt: LanguageMenuOptionDescriptor = SSRA_LANGUAGE_MENU_OPTIONS.find(
    (o) => o.value !== "auto" && o.value === effectiveCode,
  ) ?? {
    value: "en",
    label: "English",
    native: "English (en)",
    reviewed: true,
  };
  const showAutoBadge = !params.localeExplicit;
  const checkedValue: LanguageMenuOptionDescriptor["value"] = showAutoBadge
    ? "auto"
    : currentOpt.value;
  const activeIndex = Math.max(
    0,
    SSRA_LANGUAGE_MENU_OPTIONS.findIndex((o) => o.value === checkedValue),
  );
  const rovingIndex =
    params.focusIndex !== undefined &&
    params.focusIndex !== null &&
    params.focusIndex >= 0 &&
    params.focusIndex < SSRA_LANGUAGE_MENU_OPTIONS.length
      ? params.focusIndex
      : activeIndex;
  return {
    triggerCode: currentOpt.value.toUpperCase(),
    showAutoBadge,
    triggerSrLabel: showAutoBadge
      ? `Response language: Auto-detect (currently ${currentOpt.label})`
      : `Response language: ${currentOpt.label}`,
    triggerTitle: showAutoBadge ? "Response language: auto-detected" : "Response language",
    checkedValue,
    activeIndex,
    rovingIndex,
    options: SSRA_LANGUAGE_MENU_OPTIONS.map((opt, idx) => ({
      ...opt,
      checked: opt.value === checkedValue,
      tabIndex: idx === rovingIndex ? 0 : -1,
    })),
  };
}

/**
 * WAI-ARIA `role="radiogroup"` roving keyboard navigation (`ArrowDown`/`ArrowRight`,
 * `ArrowUp`/`ArrowLeft`, `Home`, `End`, and single-character type-ahead), matching
 * `FinalYearProject/App/frontend/src/components/LanguageMenu.tsx`.
 */
export function resolveLanguageMenuKeyNavigation(params: {
  readonly key: string;
  readonly currentIndex: number;
  readonly options?: readonly LanguageMenuOptionDescriptor[];
}): number | null {
  const opts = params.options ?? SSRA_LANGUAGE_MENU_OPTIONS;
  if (opts.length === 0) return null;
  const cur = ((params.currentIndex % opts.length) + opts.length) % opts.length;
  if (params.key === "ArrowDown" || params.key === "ArrowRight") {
    return (cur + 1) % opts.length;
  }
  if (params.key === "ArrowUp" || params.key === "ArrowLeft") {
    return (cur - 1 + opts.length) % opts.length;
  }
  if (params.key === "Home") {
    return 0;
  }
  if (params.key === "End") {
    return opts.length - 1;
  }
  if (/^[a-z]$/i.test(params.key)) {
    const lower = params.key.toLowerCase();
    const match = opts.findIndex((o) => o.label.toLowerCase().startsWith(lower));
    if (match >= 0) return match;
  }
  return null;
}
