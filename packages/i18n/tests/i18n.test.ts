import { describe, expect, it } from "vitest";
import { getMessages, getTextDirection, PHASE1_LOCALES, ROADMAP_LOCALES } from "../src/index.js";

describe("@ssra/i18n", () => {
  it("supports BCP-47 tags en, ar (RTL), pga and Phase 4 national languages", () => {
    expect(PHASE1_LOCALES).toEqual(["en", "pga", "ar"]);
    expect(ROADMAP_LOCALES).toContain("din");
    expect(ROADMAP_LOCALES).toContain("nus");
    expect(getTextDirection("ar")).toBe("rtl");
    expect(getTextDirection("en")).toBe("ltr");
    expect(getTextDirection("pga")).toBe("ltr");
    expect(getMessages("ar").cashFreeBanner).toContain("etax.nra.gov.ss");
  });
});
