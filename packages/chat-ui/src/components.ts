/**
 * WCAG 2.2 AA Accessible & HTML-Escaped Renderers for the 7 Registered Generative UI Components
 * (`packages/chat-ui/src/components.ts` — Section 9.3, ADR-005).
 */

import type { LocaleCode } from "@ssra/contracts";
import { resolveGenerativeUIComponent } from "./index.js";

/**
 * Escape HTML special characters (`&`, `<`, `>`, `"`, `'`) to block XSS injection.
 */
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
  readonly numericFontVariant: "tabular-nums";
  readonly safeHtml: string;
}

/**
 * Render an allow-listed Generative UI card as WCAG 2.2 AA accessible, HTML-escaped semantic markup.
 */
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
      numericFontVariant: "tabular-nums",
      safeHtml: `<div role="status" aria-live="polite" dir="${dir}" class="ssra-text-fallback">${safeText}</div>`,
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
        numericFontVariant: "tabular-nums",
        safeHtml: `<section role="region" aria-label="SSRA e-Tax Balance" dir="${dir}" data-component="BalanceCard" data-numeric="tabular-nums"><strong>TIN ${tin}</strong>: ${amt} SSP (${status}, as of ${asOf})</section>`,
      };
    }
    case "CalculatorForm": {
      const isWht = p.calculator_type === "WHT" || p.withholding_tax_ssp !== undefined;
      const calcType = isWht ? "WHT" : "PAYE";
      const rawTax = isWht ? (p.withholding_tax_ssp ?? "0") : (p.estimated_tax_ssp ?? "0");
      const tax = escapeHtmlStrict(String(rawTax));
      return {
        mode: "component",
        componentName: "CalculatorForm",
        ariaRole: "region",
        dir,
        numericFontVariant: "tabular-nums",
        safeHtml: `<section role="region" aria-label="SSRA Tax Estimate" dir="${dir}" data-component="CalculatorForm" data-numeric="tabular-nums"><span class="badge-estimate">ESTIMATE ONLY</span> ${calcType}: ${tax} SSP</section>`,
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
        numericFontVariant: "tabular-nums",
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
        numericFontVariant: "tabular-nums",
        safeHtml: `<section role="region" aria-label="Confirm Action" dir="${dir}" data-component="ConfirmActionSheet" data-tool="${tool}"><p>${summary}</p></section>`,
      };
    }
    case "FilingStatusTimeline": {
      const tin = escapeHtmlStrict(String(p.tin_masked));
      const status = escapeHtmlStrict(String(p.filing_status));
      const period = escapeHtmlStrict(String(p.last_filed_period));
      const asOfSuffix =
        typeof p.as_of === "string" && p.as_of.length > 0
          ? `, as of ${escapeHtmlStrict(p.as_of)}`
          : "";
      return {
        mode: "component",
        componentName: "FilingStatusTimeline",
        ariaRole: "region",
        dir,
        numericFontVariant: "tabular-nums",
        safeHtml: `<section role="region" aria-label="FilingStatusTimeline" dir="${dir}" data-component="FilingStatusTimeline" data-numeric="tabular-nums"><strong>TIN ${tin}</strong>: ${status} (Period ${period}${asOfSuffix})</section>`,
      };
    }
    case "CitationList": {
      const safeFallback = escapeHtmlStrict(fallbackText);
      const rawCitations = Array.isArray(p.citations)
        ? (p.citations as Array<Record<string, unknown>>)
        : [];
      const rawSteps = Array.isArray(p.guided_steps)
        ? (p.guided_steps as Array<Record<string, unknown>>)
        : [];
      const stepsMarkup =
        rawSteps.length > 0
          ? `<ol class="ssra-guided-steps" aria-label="Guided Steps">${rawSteps
              .map(
                (s) =>
                  `<li><strong>Step ${escapeHtmlStrict(String(s.step_number ?? ""))}: ${escapeHtmlStrict(String(s.title ?? ""))}</strong> — ${escapeHtmlStrict(String(s.instruction ?? ""))}</li>`,
              )
              .join("")}</ol>`
          : "";
      const citationsMarkup =
        rawCitations.length > 0
          ? `<ul class="ssra-citation-badges" aria-label="Approved Sources">${rawCitations
              .map(
                (c) =>
                  `<li data-anchor="${escapeHtmlStrict(String(c.section_anchor ?? ""))}">${escapeHtmlStrict(String(c.doc_title ?? ""))} (${escapeHtmlStrict(String(c.section_anchor ?? ""))})</li>`,
              )
              .join("")}</ul>`
          : "";
      return {
        mode: "component",
        componentName: "CitationList",
        ariaRole: "region",
        dir,
        numericFontVariant: "tabular-nums",
        safeHtml: `<section role="region" aria-label="CitationList" dir="${dir}" data-component="CitationList" data-container="inline-size"><p class="ssra-card-body">${safeFallback}</p>${stepsMarkup}${citationsMarkup}</section>`,
      };
    }
    case "HandoffCard": {
      const safeFallback = escapeHtmlStrict(fallbackText);
      const safeReason = escapeHtmlStrict(String(p.reason ?? "USER_REQUEST"));
      const safeQueue = escapeHtmlStrict(String(p.queue ?? "DOMESTIC_TAX"));
      const safePriority = escapeHtmlStrict(String(p.priority ?? "NORMAL"));
      return {
        mode: "component",
        componentName: "HandoffCard",
        ariaRole: "region",
        dir,
        numericFontVariant: "tabular-nums",
        safeHtml: `<section role="region" aria-label="HandoffCard" dir="${dir}" data-component="HandoffCard" data-reason="${safeReason}" data-queue="${safeQueue}" data-priority="${safePriority}"><header class="ssra-handoff-header"><strong>SSRA Officer Assistance (${safeQueue})</strong></header><p class="ssra-card-body">${safeFallback}</p></section>`,
      };
    }
  }
}
