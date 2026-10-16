import { describe, expect, it } from "vitest";
import { presentTurnAnswerForWeb } from "../src/app/[locale]/(chat)/page.js";
import { renderPublicHomeModel } from "../src/app/[locale]/(public)/page.js";
import { renderPublicStatusBanner } from "../src/app/[locale]/(public)/status.js";
import {
  buildHttpOnlySessionCookieHeader,
  buildSessionLogoutHeaders,
  dispatchServiceWorkerLogoutPurge,
  validateBffCsrfMutation,
} from "../src/app/api/auth/session/route.js";
import { buildRuntimeStreamRequest } from "../src/app/api/chat/stream/route.js";
import { validateClientUpload } from "../src/app/api/uploads/route.js";
import { generatePwaManifest } from "../src/app/manifest.js";
import { applyTaxpayerTurnMeta, buildTaxpayerChatTurnView } from "../src/components/index.js";
import { createAltchaChallenge, verifyAltchaSolution } from "../src/lib/security/altcha.js";
import { SharedValkeyCacheHandler } from "../src/lib/valkey-cache-handler.js";
import { executeProxy } from "../src/proxy.js";

describe("@ssra/web Next.js 16 proxy.ts, RTL i18n, and BFF stream", () => {
  it("sets strict nonce CSP, Trusted-Types, frame-ancestors 'none' and RTL dir for Arabic", () => {
    const decision = executeProxy({
      pathname: "/ar",
      acceptLanguage: "ar",
      saveDataHeader: "on",
      hasHttpOnlySessionCookie: false,
      nonce: "nonce_test_123",
    });
    expect(decision.status).toBe(200);
    expect(decision.locale).toBe("ar");
    expect(decision.dir).toBe("rtl");
    expect(decision.lowDataMode).toBe(true);
    expect(decision.headers["Content-Security-Policy"]).toContain("'nonce-nonce_test_123'");
    expect(decision.headers["Content-Security-Policy"]).toContain("frame-ancestors 'none'");
    expect(decision.headers["Content-Security-Policy"]).toContain(
      "require-trusted-types-for 'script'",
    );
    expect(decision.headers["Cache-Control"]).toBe("private, no-cache, no-store, must-revalidate");

    // CVE-2026-27979: Block untrusted next-resume header
    expect(
      executeProxy({
        pathname: "/en",
        nonce: "n1",
        nextResumeHeader: "1",
      }).status,
    ).toBe(400);

    // CVE-2026-64649: Block untrusted Host header
    expect(
      executeProxy({
        pathname: "/en",
        nonce: "n1",
        hostHeader: "evil.example.com",
        allowedHosts: ["assist.ssra.gov.ss"],
      }).status,
    ).toBe(400);

    // CVE-2026-27978: Reject 'null' Origin on CSRF mutation & CVE-2026-50184 Clear-Site-Data on logout
    expect(
      validateBffCsrfMutation({
        method: "POST",
        originHeader: "null",
        allowedOrigin: "https://assist.ssra.gov.ss",
        csrfCookieToken: "tok1",
        csrfHeaderToken: "tok1",
      }),
    ).toEqual({ valid: false, reason: "CSRF_NULL_ORIGIN_REJECTED" });
    const logout = buildSessionLogoutHeaders();
    expect(logout["Set-Cookie"]).toContain("Max-Age=0");
    expect(logout["Clear-Site-Data"]).toBe('"cache", "cookies", "storage"');
    expect(logout["Cache-Control"]).toBe("no-store");
    const posted: Array<{ readonly type: string }> = [];
    expect(
      dispatchServiceWorkerLogoutPurge({
        serviceWorker: {
          controller: {
            postMessage: (m) => posted.push(m),
          },
        },
      }),
    ).toBe(true);
    expect(posted).toEqual([{ type: "SSRA_LOGOUT_PURGE" }]);
  });

  it("blocks unauthenticated access to /[locale]/account routes", () => {
    const blocked = executeProxy({
      pathname: "/en/account/balance",
      hasHttpOnlySessionCookie: false,
      nonce: "n1",
    });
    expect(blocked.status).toBe(401);

    const allowed = executeProxy({
      pathname: "/en/account/balance",
      hasHttpOnlySessionCookie: true,
      nonce: "n1",
    });
    expect(allowed.status).toBe(200);
  });

  it("renders public home model and BFF AG-UI stream payload", () => {
    const arHome = renderPublicHomeModel("ar");
    expect(arHome.dir).toBe("rtl");
    expect(arHome.officialPortalUrl).toBe("https://etax.nra.gov.ss/");

    const req = buildRuntimeStreamRequest({
      message: "How much is PAYE on 250,000 SSP?",
      locale: "en",
      lowDataMode: false,
    });
    expect(req.url).toBe("http://localhost:8001/v1/agui/stream");

    const presented = presentTurnAnswerForWeb({
      segments: [{ text: "PAYE is 25,000 SSP.", citation_ids: ["cit_1"] }],
      citations: [
        {
          id: "cit_1",
          snapshot_version: "2026.10.1",
          doc_title: "Taxation Act 2009",
          section_anchor: "Sec-18",
          effective_from: "2024-07-01",
        },
      ],
      numbers: [{ value: "25000", unit: "SSP", source_ref: "calc" }],
      ui_component: null,
      is_estimate: true,
      abstained: false,
    });
    expect(presented.isEstimate).toBe(true);

    const updatedTurn = applyTaxpayerTurnMeta(
      {
        serverTurnId: null,
        citations: [],
        nextActions: [],
        escalationRequired: false,
      },
      {
        turn_id: "turn_01",
        next_actions: ["Verify TIN", "Speak to an SSRA Officer"],
        escalation_required: true,
        officer_hours: {
          on_duty: true,
          hours: "08:00–17:00 CAT",
          next_on_duty: null,
        },
      },
    );
    expect(updatedTurn.serverTurnId).toBe("turn_01");
    expect(updatedTurn.nextActions).toEqual(["Verify TIN", "Speak to an SSRA Officer"]);
    expect(updatedTurn.officerHours?.onDuty).toBe(true);
    expect(updatedTurn.escalationRequired).toBe(true);
  });

  it("verifies self-hosted ALTCHA proof-of-work bot defence challenge", async () => {
    const challenge = await createAltchaChallenge(42, "salt_ssra_1", "secret_key");
    const valid = await verifyAltchaSolution(
      {
        ...challenge,
        number: 42,
      },
      "secret_key",
    );
    expect(valid).toBe(true);

    const wrong = await verifyAltchaSolution(
      {
        ...challenge,
        number: 99,
      },
      "secret_key",
    );
    expect(wrong).toBe(false);
  });

  it("enforces BFF httpOnly session cookies, CSRF checks, 2MB upload caps, and PWA manifest", () => {
    const cookie = buildHttpOnlySessionCookieHeader("sess_01929540");
    expect(cookie).toContain("__Host-ssra_session=sess_01929540");
    expect(cookie).toContain("HttpOnly; Secure; SameSite=Lax");

    expect(
      validateBffCsrfMutation({
        method: "POST",
        originHeader: "https://evil.example.com",
        allowedOrigin: "https://assist.ssra.gov.ss",
        csrfCookieToken: "tok_1",
        csrfHeaderToken: "tok_1",
      }),
    ).toEqual({ valid: false, reason: "CSRF_ORIGIN_MISMATCH" });

    expect(validateClientUpload({ mimeType: "application/pdf", sizeBytes: 500_000 }).accepted).toBe(
      true,
    );
    expect(
      validateClientUpload({ mimeType: "application/x-msdownload", sizeBytes: 100 }).accepted,
    ).toBe(false);

    const manifest = generatePwaManifest();
    expect(manifest.display).toBe("standalone");
    expect(manifest.shortcuts).toHaveLength(3);

    const view = buildTaxpayerChatTurnView(
      {
        segments: [{ text: "Official portal is etax.nra.gov.ss", citation_ids: ["cit_1"] }],
        citations: [
          {
            id: "cit_1",
            snapshot_version: "2026.10.1",
            doc_title: "SSRA Guide",
            section_anchor: "Sec-1",
            effective_from: "2026-03-01",
          },
        ],
        numbers: [],
        ui_component: null,
        is_estimate: false,
        abstained: false,
      },
      "ar",
      true,
    );
    expect(view.header.dir).toBe("rtl");
    expect(view.card.mode).toBe("text_fallback");

    const statusBanner = renderPublicStatusBanner(4);
    expect(statusBanner.overallStatus).toBe("DEGRADED_SAFE_MODE");
    expect(statusBanner.officialPortalUrl).toBe("https://etax.nra.gov.ss/");

    const cache = new SharedValkeyCacheHandler();
    expect(
      cache.set("page:/en/tin", "cached-tin-html", {
        tags: ["knowledge", "tin"],
        snapshotVersion: "2026.10.1",
      }),
    ).toBe(true);
    expect(cache.get("page:/en/tin", "2026.10.1")?.value).toBe("cached-tin-html");
    expect(cache.get("page:/en/tin", "2026.11.0")).toBeNull();
    // Never cache personal T1-T3 routes
    expect(
      cache.set("page:/en/account", "secret", {
        tags: ["account"],
        snapshotVersion: "2026.10.1",
        isPersonalAuthenticatedRoute: true,
      }),
    ).toBe(false);
    expect(cache.revalidateTag("knowledge")).toBe(1);
  });
});
