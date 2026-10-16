/**
 * Next.js 16 Web App Manifest (`apps/web/src/app/manifest.ts` — Section 9.2, ADR-011).
 */

export function generatePwaManifest() {
  return {
    name: "SSRA Assist — South Sudan Revenue Authority",
    short_name: "SSRA Assist",
    description:
      "Official multilingual virtual assistant for the South Sudan Revenue Authority (SSRA / NRA).",
    start_url: "/en",
    display: "standalone",
    background_color: "#f8fafc",
    theme_color: "#0b2545",
    shortcuts: [
      {
        name: "Register for a TIN",
        url: "/en?journey=tin_registration",
      },
      {
        name: "Calculate PAYE Estimate",
        url: "/en?journey=paye_calculator",
      },
      {
        name: "Is This Really SSRA? (Verify Channel)",
        url: "/en?journey=verify_official",
      },
    ],
  } as const;
}
