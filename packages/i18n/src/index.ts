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

export const MESSAGES: Record<LocaleCode, LocaleMessages> = {
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
  din: {
    appTitle: "SSRA Assist — Akuma de Wëu de Paguot Thudän (SSRA)",
    assistantDisclosure:
      "Yin jam kekë kony de SSRA online. Yin lëu ba raan de luɔi de SSRA thiëëc në kaam ëbɛ̈n.",
    cashFreeBanner:
      "Löŋ de March 2026: Wëu de ajul kedhiɛ aa juac në https://etax.nra.gov.ss/ në bɛ̈ŋic. Duk wëu juac në cin tënë raan.",
    handoffButton: "Jam kekë Raan de Luɔi de SSRA",
    lowDataModeLabel: "2G Low-Data Text Mode (Thuɔŋjäŋ)",
    verifyChannelCta: "Caar Namba tedä Bɛ̈ŋ de SSRA de Yic",
  },
  nus: {
    appTitle: "SSRA Assist — Kuma Yiööth Paguot Thudän (SSRA)",
    assistantDisclosure: "Ruacni kɛ luak SSRA online. Dëëri raan luɔi SSRA thiëc kä thaa ëbɛ̈n.",
    cashFreeBanner:
      "Löŋ March 2026: Cuɔl yiööth diaal kä https://etax.nra.gov.ss/ rɛy bɛ̈ŋ. Cuɛ yiööth cuɔl kä tet raan.",
    handoffButton: "Ruacni kɛ Raan Luɔi SSRA",
    lowDataModeLabel: "2G Low-Data Text Mode (Thok Naath)",
    verifyChannelCta: "Caar Namba göör SSRA",
  },
  bfa: {
    appTitle: "SSRA Assist — Kiko'jin na Silingi ta Südän Nakwacak (SSRA)",
    assistantDisclosure: "Do kulya ko konyo lo SSRA online. Do bulö mörö ŋutu lo kita lo SSRA.",
    cashFreeBanner:
      "March 2026: Kaser lɔŋɔt tinan ko https://etax.nra.gov.ss/ ko banki. Buka tinan silingi ko könin.",
    handoffButton: "Kulya ko Ŋutu lo SSRA",
    lowDataModeLabel: "2G Low-Data Text Mode (Bari)",
    verifyChannelCta: "Moju Namba lo SSRA",
  },
  zne: {
    appTitle: "SSRA Assist — Basunungba Marã Rago Südän (SSRA)",
    assistantDisclosure: "Mo nafura na undohe nga ga SSRA. Mo rengbe ka sana tipa boro sunge SSRA.",
    cashFreeBanner:
      "March 2026: Tumosi marã dunduko rogo https://etax.nra.gov.ss/ rogo banki. Ka mo fu nga marã ku be boro ya.",
    handoffButton: "Fura na Boro Sunge SSRA",
    lowDataModeLabel: "2G Low-Data Text Mode (Zande)",
    verifyChannelCta: "Wisigi Namba ga SSRA",
  },
  shk: {
    appTitle: "SSRA Assist — Koma Jami Piny Sudan (SSRA)",
    assistantDisclosure: "Yïn kwop kï konyo SSRA online. Yïn lëu kwac ŋat tic SSRA.",
    cashFreeBanner:
      "March 2026: Cul jami bëëne yi https://etax.nra.gov.ss/ yi banki. Ba cul jami cin ŋat.",
    handoffButton: "Kwop kï Ŋat Tic SSRA",
    lowDataModeLabel: "2G Low-Data Text Mode (Dhøg Cøllø)",
    verifyChannelCta: "Nɛn Namba SSRA",
  },
};

export function getMessages(locale: LocaleCode): LocaleMessages {
  return MESSAGES[locale] ?? MESSAGES.en;
}
