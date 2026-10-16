/**
 * Public System Status & Degradation Ladder View (`apps/web/src/app/[locale]/(public)/status.ts` — Section 13).
 */

export interface PublicStatusBannerView {
  readonly overallStatus: "OPERATIONAL" | "DEGRADED_SAFE_MODE";
  readonly degradationLevel: 1 | 2 | 3 | 4 | 5;
  readonly userNotice: string;
  readonly officialPortalUrl: "https://etax.nra.gov.ss/";
}

export function renderPublicStatusBanner(
  degradationLevel: 1 | 2 | 3 | 4 | 5,
): PublicStatusBannerView {
  const isDegraded = degradationLevel >= 4;
  return {
    overallStatus: isDegraded ? "DEGRADED_SAFE_MODE" : "OPERATIONAL",
    degradationLevel,
    userNotice: isDegraded
      ? "SSRA Assist is currently operating in Verified Retrieval & Static FAQ Safe Mode. All tax calculations and official portal links (https://etax.nra.gov.ss/) remain active."
      : "All SSRA Assist channels (Web, WhatsApp, SMS, USSD) and deterministic tax calculators are operational.",
    officialPortalUrl: "https://etax.nra.gov.ss/",
  };
}
