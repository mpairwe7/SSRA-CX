import { describe, expect, it } from "vitest";
import {
  AnswerSchema,
  ConversationEventSchema,
  GenerativeUIComponentNameSchema,
  SCHEMA_BUNDLE_SHA256,
  TaxFactSchema,
} from "../src/index.js";

describe("@ssra/contracts schemas", () => {
  it("validates a canonical CloudEvents 1.0 ConversationEvent", () => {
    const parsed = ConversationEventSchema.parse({
      specversion: "1.0",
      id: "01929540-0000-7000-8000-000000000001",
      source: "urn:ssra:channel:web",
      type: "ssra.conversation.message.v1",
      subject: "thr_01929540",
      time: "2026-10-16T08:00:00Z",
      datacontenttype: "application/json",
      data: {
        locale: "en",
        channel: "web",
        parts: [{ kind: "text", value: "How do I register for a TIN on eTax?" }],
        capabilities: {
          max_len: 4096,
          rich_ui: true,
          buttons: true,
          media: false,
          latency_budget_ms: 6000,
          async_only: false,
        },
      },
    });
    expect(parsed.subject).toBe("thr_01929540");
    expect(SCHEMA_BUNDLE_SHA256).toHaveLength(64);
  });

  it("allows only the 7 registered Generative UI component names", () => {
    expect(GenerativeUIComponentNameSchema.options).toEqual([
      "BalanceCard",
      "FilingStatusTimeline",
      "PaymentInstructionsCard",
      "CalculatorForm",
      "CitationList",
      "ConfirmActionSheet",
      "HandoffCard",
    ]);
    expect(() => GenerativeUIComponentNameSchema.parse("ArbitraryScriptWidget")).toThrow();
  });

  it("validates Answer numeric provenance and TaxFact contracts", () => {
    const answer = AnswerSchema.parse({
      segments: [
        {
          text: "Monthly PAYE returns are due by day 15 of the following month.",
          citation_ids: ["cit_1"],
        },
      ],
      citations: [
        {
          id: "cit_1",
          snapshot_version: "2026.10.1",
          doc_title: "South Sudan Taxation Act 2009 (as amended)",
          section_anchor: "Part-IV-Sec-18",
          effective_from: "2024-07-01",
        },
      ],
      numbers: [
        {
          value: "15",
          unit: "DAY_OF_MONTH",
          source_ref: "paye.filing.deadline_day",
        },
      ],
      ui_component: null,
      is_estimate: false,
      abstained: false,
    });
    expect(answer.numbers[0]?.source_ref).toBe("paye.filing.deadline_day");

    const fact = TaxFactSchema.parse({
      key: "paye.filing.deadline_day",
      value: "15",
      unit: "DAY_OF_MONTH",
      currency: "NONE",
      applies_to: "All employers withholding PAYE in South Sudan",
      effective_from: "2024-07-01",
      effective_to: null,
      legal_ref: "Taxation Act 2009 as amended, Part IV Section 18",
      approved_by: "SSRA Legal Directorate (Seed v2026.10.1)",
      version: "2026.10.1",
    });
    expect(fact.key).toBe("paye.filing.deadline_day");
  });
});
