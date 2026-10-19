/**
 * AG-UI Client & Allow-Listed Generative UI Registry (Section 9.3, ADR-005).
 *
 * Security rule: The agent may ONLY request the 7 registered components by name,
 * with Zod-validated props. Unknown component names or invalid props safely fall
 * back to plain text. The model never emits raw HTML or JavaScript.
 */

import { CitationSchema, type GenerativeUIComponentName } from "@ssra/contracts";
import { z } from "zod";

export const BalanceCardPropsSchema = z.object({
  tin_masked: z.string().regex(/^••••\d{4}$/),
  total_outstanding_ssp: z.string().min(1),
  currency: z.literal("SSP"),
  filing_status: z.string().min(1),
  as_of: z.string().min(1),
});

export const FilingStatusTimelinePropsSchema = z.object({
  tin_masked: z.string().regex(/^••••\d{4}$/),
  filing_status: z.string().min(1),
  last_filed_period: z.string().min(1),
  as_of: z.string().optional(),
});

export const PaymentInstructionsCardPropsSchema = z.object({
  identifier: z.string().min(1),
  status: z.enum(["OFFICIAL_VERIFIED", "UNVERIFIED_OR_SCAM"]),
  guidance: z.string().min(1),
  official_portal: z.literal("https://etax.nra.gov.ss/"),
});

export const CalculatorFormPropsSchema = z
  .object({
    calculator_type: z.enum(["PAYE", "WHT"]).optional(),
    gross_monthly_ssp: z.string().optional(),
    estimated_tax_ssp: z.string().optional(),
    net_monthly_ssp: z.string().optional(),
    effective_rate_percent: z.string().optional(),
    filing_deadline_day: z.number().int().optional(),
    category: z.string().optional(),
    gross_amount_ssp: z.string().optional(),
    rate_percent: z.string().optional(),
    withholding_tax_ssp: z.string().optional(),
    net_payable_ssp: z.string().optional(),
    is_estimate: z.literal(true),
  })
  .refine(
    (val) => {
      if (val.estimated_tax_ssp !== undefined && val.withholding_tax_ssp !== undefined) {
        return false;
      }
      if (val.calculator_type === "WHT" && val.estimated_tax_ssp !== undefined) {
        return false;
      }
      if (val.calculator_type === "PAYE" && val.withholding_tax_ssp !== undefined) {
        return false;
      }
      return true;
    },
    { message: "CalculatorForm props must not mix PAYE and WHT tax amounts" },
  );

export const CitationListPropsSchema = z.object({
  citations: z.array(CitationSchema),
});

export const ConfirmActionSheetPropsSchema = z.object({
  confirmation_token: z.string().min(1),
  idempotency_key: z.string().min(1),
  tool: z.string().min(1),
  action_digest: z.string().length(64),
  summary: z.string().min(1),
});

export const HandoffCardPropsSchema = z.object({
  reason: z.string().min(1),
  queue: z.string().optional(),
  priority: z.string().optional(),
});

export const GENERATIVE_UI_PROP_SCHEMAS: Record<GenerativeUIComponentName, z.ZodTypeAny> = {
  BalanceCard: BalanceCardPropsSchema,
  FilingStatusTimeline: FilingStatusTimelinePropsSchema,
  PaymentInstructionsCard: PaymentInstructionsCardPropsSchema,
  CalculatorForm: CalculatorFormPropsSchema,
  CitationList: CitationListPropsSchema,
  ConfirmActionSheet: ConfirmActionSheetPropsSchema,
  HandoffCard: HandoffCardPropsSchema,
};

export interface ResolvedGenerativeUI {
  readonly mode: "component" | "text_fallback";
  readonly componentName: GenerativeUIComponentName | null;
  readonly validatedProps: Record<string, unknown> | null;
  readonly fallbackText: string;
}

/**
 * Validate a candidate Generative UI component against the closed 7-card Zod 4 registry, falling back to text.
 */
export function resolveGenerativeUIComponent(
  candidate: { readonly name?: unknown; readonly props?: unknown } | null | undefined,
  fallbackText: string,
  options?: { readonly lowDataMode?: boolean },
): ResolvedGenerativeUI {
  if (options?.lowDataMode || !candidate || typeof candidate.name !== "string") {
    return {
      mode: "text_fallback",
      componentName: null,
      validatedProps: null,
      fallbackText,
    };
  }

  const schema =
    GENERATIVE_UI_PROP_SCHEMAS[candidate.name as GenerativeUIComponentName] ?? undefined;
  if (!schema) {
    return {
      mode: "text_fallback",
      componentName: null,
      validatedProps: null,
      fallbackText,
    };
  }

  const parsed = schema.safeParse(candidate.props ?? {});
  if (!parsed.success) {
    return {
      mode: "text_fallback",
      componentName: null,
      validatedProps: null,
      fallbackText,
    };
  }

  return {
    mode: "component",
    componentName: candidate.name as GenerativeUIComponentName,
    validatedProps: parsed.data as Record<string, unknown>,
    fallbackText,
  };
}

export * from "./agui-stream.js";
export * from "./call-receptionist.js";
export * from "./chat-workbench.js";
export * from "./components.js";
export * from "./document-analysis.js";
export * from "./mcp-apps-sandbox.js";
export * from "./offline-outbox.js";
export * from "./reveal-queue.js";
export * from "./storybook-catalog.js";
export * from "./voice-notes.js";
