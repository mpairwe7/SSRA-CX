/**
 * Offline-First Statutory Resilience Pack & Adaptive 2G Voice Network Governor (`packages/chat-ui/src/offline-resilience.ts`).
 *
 * Provides zero-network, deterministic client-side capabilities for intermittent/offline South Sudan networks:
 * 1. Offline PAYE & Withholding Tax estimators (`calculateOfflinePayeEstimate`, `calculateOfflineWithholdingEstimate`)
 *    matching `knowledge/tax-facts/seed-2026.10.1.yaml` and badged `OFFLINE_ESTIMATE_ONLY`.
 * 2. Offline Anti-Impersonation Official Channel Verifier (`verifyOfflineOfficialChannel`) & SSRA Office Directory.
 * 3. Adaptive Opus Bitrate & Timeout Governor (`resolveAdaptiveVoiceNetworkProfile`: `12 kbps` on `2g`/`slow-2g`).
 */

export const OFFLINE_STATUTORY_SNAPSHOT_VERSION = "2026.10.1" as const;
export const OFFICIAL_ETAX_PORTAL_URL = "https://etax.nra.gov.ss/" as const;

export interface OfflineSsraOfficeEntry {
  readonly officeCode: "JUBA_HQ" | "NIMULE_CUSTOMS" | "WAU_BRANCH" | "MALAKAL_BRANCH";
  readonly name: string;
  readonly hoursAfricaJuba: string;
  readonly services: readonly string[];
}

export const OFFLINE_SSRA_OFFICE_DIRECTORY: readonly OfflineSsraOfficeEntry[] = [
  {
    officeCode: "JUBA_HQ",
    name: "SSRA Headquarters (Juba)",
    hoursAfricaJuba: "Mon–Fri 08:00–17:00 (Africa/Juba, UTC+02:00)",
    services: ["Domestic Tax", "Large Taxpayers", "e-Tax Support", "TCC Desk"],
  },
  {
    officeCode: "NIMULE_CUSTOMS",
    name: "SSRA Nimule Border Customs Station",
    hoursAfricaJuba: "Mon–Sat 08:00–17:00 (Africa/Juba, UTC+02:00)",
    services: ["e-Customs Declarations", "Advance BPT (4%)", "Tariff Verification"],
  },
  {
    officeCode: "WAU_BRANCH",
    name: "SSRA Wau Regional Branch",
    hoursAfricaJuba: "Mon–Fri 08:00–17:00 (Africa/Juba, UTC+02:00)",
    services: ["TIN Registration", "SME Filing Support", "Official Bank Payment Guidance"],
  },
  {
    officeCode: "MALAKAL_BRANCH",
    name: "SSRA Malakal Regional Branch",
    hoursAfricaJuba: "Mon–Fri 08:00–17:00 (Africa/Juba, UTC+02:00)",
    services: ["TIN Registration", "Domestic Tax Filing", "Taxpayer Assistance"],
  },
] as const;

export interface OfflinePayeEstimateResult {
  readonly grossMonthlySsp: number;
  readonly estimatedTaxSsp: number;
  readonly netMonthlySsp: number;
  readonly effectiveRatePercent: number;
  readonly filingDeadlineDay: 15;
  readonly isEstimate: true;
  readonly isOfflinePack: true;
  readonly snapshotVersion: typeof OFFLINE_STATUTORY_SNAPSHOT_VERSION;
  readonly sectionAnchor: "Part-IV-Sec-18-PAYE";
}

/**
 * Compute a deterministic offline monthly PAYE estimate matching `libs/ssra_rules` (`seed-2026.10.1.yaml`).
 */
export function calculateOfflinePayeEstimate(grossMonthlySsp: number): OfflinePayeEstimateResult {
  if (!Number.isFinite(grossMonthlySsp) || grossMonthlySsp < 0) {
    throw new RangeError("grossMonthlySsp must be a finite non-negative number");
  }
  const gross = Math.round(grossMonthlySsp * 100) / 100;
  let tax = 0;
  if (gross > 300_000) {
    tax = (gross - 300_000) * 0.2 + 100_000 * 0.15 + 100_000 * 0.1;
  } else if (gross > 200_000) {
    tax = (gross - 200_000) * 0.15 + 100_000 * 0.1;
  } else if (gross > 100_000) {
    tax = (gross - 100_000) * 0.1;
  }
  const roundedTax = Math.round(tax * 100) / 100;
  const net = Math.round((gross - roundedTax) * 100) / 100;
  const effRate = gross > 0 ? Math.round((roundedTax / gross) * 10000) / 100 : 0;
  return {
    grossMonthlySsp: gross,
    estimatedTaxSsp: roundedTax,
    netMonthlySsp: net,
    effectiveRatePercent: effRate,
    filingDeadlineDay: 15,
    isEstimate: true,
    isOfflinePack: true,
    snapshotVersion: OFFLINE_STATUTORY_SNAPSHOT_VERSION,
    sectionAnchor: "Part-IV-Sec-18-PAYE",
  };
}

export type OfflineWithholdingCategory =
  | "rent"
  | "government_contracts"
  | "technical_fees"
  | "dividends_interest_royalties";

const OFFLINE_WHT_RATES: Record<OfflineWithholdingCategory, number> = {
  rent: 20,
  government_contracts: 20,
  technical_fees: 15,
  dividends_interest_royalties: 10,
};

export interface OfflineWithholdingEstimateResult {
  readonly category: OfflineWithholdingCategory;
  readonly grossAmountSsp: number;
  readonly ratePercent: number;
  readonly withholdingTaxSsp: number;
  readonly netPayableSsp: number;
  readonly isEstimate: true;
  readonly isOfflinePack: true;
  readonly snapshotVersion: typeof OFFLINE_STATUTORY_SNAPSHOT_VERSION;
  readonly sectionAnchor: "Part-IX-Withholding-Tax";
}

/**
 * Compute a deterministic offline Withholding Tax (WHT) estimate matching `libs/ssra_rules` (`seed-2026.10.1.yaml`).
 */
export function calculateOfflineWithholdingEstimate(
  grossAmountSsp: number,
  category: OfflineWithholdingCategory = "rent",
): OfflineWithholdingEstimateResult {
  if (!Number.isFinite(grossAmountSsp) || grossAmountSsp < 0) {
    throw new RangeError("grossAmountSsp must be a finite non-negative number");
  }
  const ratePercent = OFFLINE_WHT_RATES[category] ?? 20;
  const gross = Math.round(grossAmountSsp * 100) / 100;
  const wht = Math.round(gross * (ratePercent / 100) * 100) / 100;
  const net = Math.round((gross - wht) * 100) / 100;
  return {
    category,
    grossAmountSsp: gross,
    ratePercent,
    withholdingTaxSsp: wht,
    netPayableSsp: net,
    isEstimate: true,
    isOfflinePack: true,
    snapshotVersion: OFFLINE_STATUTORY_SNAPSHOT_VERSION,
    sectionAnchor: "Part-IX-Withholding-Tax",
  };
}

export function verifyOfflineOfficialChannel(candidate: string): {
  readonly status: "OFFICIAL_VERIFIED" | "UNVERIFIED_OR_SCAM";
  readonly officialPortal: typeof OFFICIAL_ETAX_PORTAL_URL;
  readonly guidance: string;
} {
  const norm = candidate.trim().toLowerCase();
  if (norm === "https://etax.nra.gov.ss/" || norm === "etax.nra.gov.ss") {
    return {
      status: "OFFICIAL_VERIFIED",
      officialPortal: OFFICIAL_ETAX_PORTAL_URL,
      guidance:
        "Verified SSRA National e-Tax Portal. All tax registration, filing, and bank payment remittance run through https://etax.nra.gov.ss/.",
    };
  }
  return {
    status: "UNVERIFIED_OR_SCAM",
    officialPortal: OFFICIAL_ETAX_PORTAL_URL,
    guidance:
      "WARNING (March 2026 Cash-Free Directive): Unverified channel or collector. Never pay cash or transfer money to an individual. Pay only via https://etax.nra.gov.ss/ into designated commercial banks.",
  };
}

export interface AdaptiveVoiceNetworkProfile {
  readonly opusBitrateKbps: 12 | 24;
  readonly frameDurationMs: 20 | 60;
  readonly streamTimeoutMs: 6000 | 12000;
  readonly speculativePrefetchEnabled: boolean;
  readonly preferVoiceNoteOrUssdFallback: boolean;
}

/**
 * Select Opus audio framing and timeout parameters based on 2G/3G link quality.
 */
export function resolveAdaptiveVoiceNetworkProfile(params: {
  readonly effectiveType?: "slow-2g" | "2g" | "3g" | "4g" | string | undefined;
  readonly rttMs?: number | undefined;
  readonly saveData?: boolean | undefined;
}): AdaptiveVoiceNetworkProfile {
  const isConstrained =
    Boolean(params.saveData) ||
    params.effectiveType === "slow-2g" ||
    params.effectiveType === "2g" ||
    (typeof params.rttMs === "number" && params.rttMs > 800);

  if (isConstrained) {
    return {
      opusBitrateKbps: 12,
      frameDurationMs: 60,
      streamTimeoutMs: 12000,
      speculativePrefetchEnabled: false,
      preferVoiceNoteOrUssdFallback: true,
    };
  }
  return {
    opusBitrateKbps: 24,
    frameDurationMs: 20,
    streamTimeoutMs: 6000,
    speculativePrefetchEnabled: true,
    preferVoiceNoteOrUssdFallback: false,
  };
}
