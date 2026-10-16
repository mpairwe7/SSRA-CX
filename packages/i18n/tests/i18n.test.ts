import { describe, expect, it } from "vitest";
import { getMessages, getTextDirection, ROADMAP_LOCALES } from "../src/index.js";

describe("@ssra/i18n 8-Locale South Sudan Catalog", () => {
  it("provides localized UI catalogs across all 8 ROADMAP_LOCALES and RTL for Arabic", () => {
    expect(ROADMAP_LOCALES).toHaveLength(8);
    expect(getTextDirection("ar")).toBe("rtl");
    for (const loc of ROADMAP_LOCALES) {
      const msg = getMessages(loc);
      expect(msg.appTitle).toContain("SSRA");
      expect(msg.cashFreeBanner).toContain("https://etax.nra.gov.ss/");
    }
  });
});
