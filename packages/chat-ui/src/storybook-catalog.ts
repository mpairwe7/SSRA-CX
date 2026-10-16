/**
 * Storybook Fixture Catalog for the 7 Allow-Listed Generative UI Chat Cards
 * (`packages/chat-ui/src/storybook-catalog.ts` — Sections 9.3 & 9.6).
 *
 * Used by visual regression, a11y (`axe-core`), and contract tests across `en`, `pga`, and RTL `ar`.
 */

import type { GenerativeUIComponentName } from "@ssra/contracts";
import { renderGenerativeUICard } from "./components.js";

export interface GenerativeUIStoryFixture {
  readonly storyId: string;
  readonly componentName: GenerativeUIComponentName;
  readonly props: Record<string, unknown>;
  readonly fallbackText: string;
}

export const GENERATIVE_UI_STORYBOOK_FIXTURES: readonly GenerativeUIStoryFixture[] = [
  {
    storyId: "balance-card-compliant",
    componentName: "BalanceCard",
    props: {
      tin_masked: "••••1234",
      total_outstanding_ssp: "0",
      currency: "SSP",
      filing_status: "COMPLIANT",
      as_of: "2026-10-16",
    },
    fallbackText: "For TIN ••••1234, your balance is 0 SSP as of 2026-10-16.",
  },
  {
    storyId: "filing-status-timeline-due",
    componentName: "FilingStatusTimeline",
    props: {
      tin_masked: "••••5678",
      filing_status: "FILING_DUE",
      last_filed_period: "2026-09",
    },
    fallbackText: "TIN ••••5678 last filed period 2026-09 (status: FILING_DUE).",
  },
  {
    storyId: "payment-instructions-verified",
    componentName: "PaymentInstructionsCard",
    props: {
      identifier: "https://etax.nra.gov.ss/",
      status: "OFFICIAL_VERIFIED",
      guidance: "Remit all taxes exclusively through e-Tax into designated commercial banks.",
      official_portal: "https://etax.nra.gov.ss/",
    },
    fallbackText: "OFFICIAL_VERIFIED: https://etax.nra.gov.ss/",
  },
  {
    storyId: "calculator-form-paye",
    componentName: "CalculatorForm",
    props: {
      calculator_type: "PAYE",
      gross_monthly_ssp: "250000",
      estimated_tax_ssp: "25000",
      net_monthly_ssp: "225000",
      effective_rate_percent: "10",
      filing_deadline_day: 15,
      is_estimate: true,
    },
    fallbackText: "ESTIMATE ONLY: PAYE on 250,000 SSP is 25,000 SSP.",
  },
  {
    storyId: "citation-list-statutory",
    componentName: "CitationList",
    props: {
      citations: [
        {
          id: "cit_1",
          snapshot_version: "2026.10.1",
          doc_title: "Taxation Act 2009 (as amended)",
          section_anchor: "Part-IV-Sec-18",
          effective_from: "2024-07-01",
        },
      ],
    },
    fallbackText: "Source: Taxation Act 2009, Part-IV-Sec-18.",
  },
  {
    storyId: "confirm-action-sheet-t2",
    componentName: "ConfirmActionSheet",
    props: {
      confirmation_token: "cfm_01929540",
      idempotency_key: "idem_01929540",
      tool: "appointments.book_appointment",
      action_digest: "a".repeat(64),
      summary: "Book appointment at JUBA_HQ on 2026-10-20 09:00 EAT.",
    },
    fallbackText: "Confirm booking appointment at JUBA_HQ.",
  },
  {
    storyId: "handoff-card-t4",
    componentName: "HandoffCard",
    props: {
      reason: "T4_POLICY",
      queue: "DOMESTIC_TAX",
      priority: "HIGH",
    },
    fallbackText: "Routing to an SSRA Domestic Tax Officer.",
  },
] as const;

export function verifyAllStorybookFixturesRenderAccessibly(): boolean {
  for (const fixture of GENERATIVE_UI_STORYBOOK_FIXTURES) {
    for (const locale of ["en", "pga", "ar"] as const) {
      const rendered = renderGenerativeUICard(
        { name: fixture.componentName, props: fixture.props },
        fixture.fallbackText,
        { locale },
      );
      if (rendered.mode !== "component" || rendered.componentName !== fixture.componentName) {
        return false;
      }
      if (locale === "ar" && rendered.dir !== "rtl") {
        return false;
      }
    }
  }
  return true;
}
