import type { LocaleCode } from "@ssra/contracts";

export const PHASE1_LOCALES: readonly LocaleCode[] = ["en", "pga", "ar"] as const;
export const ROADMAP_LOCALES: readonly LocaleCode[] = [
  "en",
  "pga",
  "ar",
  "din",
  "nus",
  "bfa",
  "zne",
  "shk",
] as const;

export function getTextDirection(locale: LocaleCode): "ltr" | "rtl" {
  return locale === "ar" ? "rtl" : "ltr";
}

export interface LocaleMessages {
  readonly appTitle: string;
  readonly assistantDisclosure: string;
  readonly cashFreeBanner: string;
  readonly handoffButton: string;
  readonly lowDataModeLabel: string;
  readonly verifyChannelCta: string;
}

export const MESSAGES: Record<"en" | "pga" | "ar", LocaleMessages> = {
  en: {
    appTitle: "SSRA Assist — South Sudan Revenue Authority",
    assistantDisclosure:
      "You are speaking with SSRA's automated virtual assistant. You can request a human officer at any time.",
    cashFreeBanner:
      "March 2026 Directive: All taxes are paid exclusively via https://etax.nra.gov.ss/ into designated banks. Never pay cash to an individual collector.",
    handoffButton: "Speak to an SSRA Officer",
    lowDataModeLabel: "2G Low-Data Text Mode",
    verifyChannelCta: "Is this really SSRA? Verify a channel or payment account",
  },
  pga: {
    appTitle: "SSRA Assist — Hay'at Iradat Junub Al-Sudan (SSRA / NRA)",
    assistantDisclosure:
      "Inta btetkalam ma musa'id al-ali ta SSRA. Tegdar tatlub muwazaf rasmi fi ayi wakit.",
    cashFreeBanner:
      "Tawjih Maris 2026: Dafa ta dariba kullu bikun aabr https://etax.nra.gov.ss/ fi al-bunuk al-mu'tamada bas. Ma tedfa gurush cash le ayi zol.",
    handoffButton: "Atkalam ma Muwazaf SSRA",
    lowDataModeLabel: "Wad'a Taufir al-Bayanat (2G)",
    verifyChannelCta: "At'akkad min Hisab aw Raqam SSRA al-Rasmi",
  },
  ar: {
    appTitle: "مساعد هيئة إيرادات جنوب السودان (SSRA Assist)",
    assistantDisclosure:
      "أنت تتحدث مع المساعد الافتراضي الآلي لهيئة إيرادات جنوب السودان (SSRA). يمكنك طلب التحدث مع موظف مختص في أي وقت.",
    cashFreeBanner:
      "توجيه مارس 2026: تُسدد جميع الضرائب حصرياً عبر نظام الضرائب الإلكتروني https://etax.nra.gov.ss/ في البنوك المعتمدة. لا تدفع نقداً لأي محصل.",
    handoffButton: "التحدث مع موظف الهيئة",
    lowDataModeLabel: "وضع توفير البيانات (2G)",
    verifyChannelCta: "تحقق من الحسابات والقنوات الرسمية للهيئة",
  },
};

export function getMessages(locale: LocaleCode): LocaleMessages {
  if (locale === "ar") {
    return MESSAGES.ar;
  }
  if (locale === "pga") {
    return MESSAGES.pga;
  }
  return MESSAGES.en;
}
