/**
 * WCAG 2.2 AA Accessible & HTML-Escaped Renderers for the 7 Registered Generative UI Components
 * (`packages/chat-ui/src/components.ts` — Section 9.3, ADR-005).
 */

import type { LocaleCode } from "@ssra/contracts";
import { resolveGenerativeUIComponent } from "./index.js";

export function escapeHtmlStrict(raw: string): string {
  return raw
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export interface RenderedChatCard {
  readonly mode: "component" | "text_fallback";
  readonly componentName: string | null;
  readonly ariaRole: "region" | "status";
  readonly dir: "ltr" | "rtl";
  readonly safeHtml: string;
}

export function renderGenerativeUICard(
  candidate: { readonly name?: unknown; readonly props?: unknown } | null | undefined,
  fallbackText: string,
  options?: { readonly locale?: LocaleCode; readonly lowDataMode?: boolean },
): RenderedChatCard {
  const dir = options?.locale === "ar" ? "rtl" : "ltr";
  const resolved = resolveGenerativeUIComponent(candidate, fallbackText, {
    lowDataMode: options?.lowDataMode ?? false,
  });

  if (resolved.mode === "text_fallback" || !resolved.componentName || !resolved.validatedProps) {
    const safeText = escapeHtmlStrict(resolved.fallbackText);
    return {
      mode: "text_fallback",
      componentName: null,
      ariaRole: "status",
      dir,
      safeHtml: `<div role="status" dir="${dir}" class="ssra-text-fallback">${safeText}</div>`,
    };
  }

  const p = resolved.validatedProps;
  switch (resolved.componentName) {
    case "BalanceCard": {
      const tin = escapeHtmlStrict(String(p.tin_masked));
      const amt = escapeHtmlStrict(String(p.total_outstanding_ssp));
      const status = escapeHtmlStrict(String(p.filing_status));
      const asOf = escapeHtmlStrict(String(p.as_of));
      return {
        mode: "component",
        componentName: "BalanceCard",
        ariaRole: "region",
        dir,
        safeHtml: `<section role="region" aria-label="SSRA e-Tax Balance" dir="${dir}" data-component="BalanceCard"><strong>TIN ${tin}</strong>: ${amt} SSP (${status}, as of ${asOf})</section>`,
      };
    }
    case "CalculatorForm": {
      const calcType = escapeHtmlStrict(String(p.calculator_type ?? "PAYE"));
      const tax = escapeHtmlStrict(String(p.estimated_tax_ssp ?? "0"));
      return {
        mode: "component",
        componentName: "CalculatorForm",
        ariaRole: "region",
        dir,
        safeHtml: `<section role="region" aria-label="SSRA Tax Estimate" dir="${dir}" data-component="CalculatorForm"><span class="badge-estimate">ESTIMATE ONLY</span> ${calcType}: ${tax} SSP</section>`,
      };
    }
    case "PaymentInstructionsCard": {
      const id = escapeHtmlStrict(String(p.identifier));
      const status = escapeHtmlStrict(String(p.status));
      return {
        mode: "component",
        componentName: "PaymentInstructionsCard",
        ariaRole: "region",
        dir,
        safeHtml: `<section role="region" aria-label="Official Payment Verification" dir="${dir}" data-component="PaymentInstructionsCard"><strong>${status}</strong>: ${id} (https://etax.nra.gov.ss/)</section>`,
      };
    }
    case "ConfirmActionSheet": {
      const summary = escapeHtmlStrict(String(p.summary));
      const tool = escapeHtmlStrict(String(p.tool));
      return {
        mode: "component",
        componentName: "ConfirmActionSheet",
        ariaRole: "region",
        dir,
        safeHtml: `<section role="region" aria-label="Confirm Action" dir="${dir}" data-component="ConfirmActionSheet" data-tool="${tool}"><p>${summary}</p></section>`,
      };
    }
    case "FilingStatusTimeline":
    case "CitationList":
    case "HandoffCard": {
      const name = resolved.componentName;
      const safeFallback = escapeHtmlStrict(fallbackText);
      return {
        mode: "component",
        componentName: name,
        ariaRole: "region",
        dir,
        safeHtml: `<section role="region" aria-label="${name}" dir="${dir}" data-component="${name}">${safeFallback}</section>`,
      };
    }
  }
}
