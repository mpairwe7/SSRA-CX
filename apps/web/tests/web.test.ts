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
import {
  buildRuntimeStreamRequest,
  POST as streamChatPost,
} from "../src/app/api/chat/stream/route.js";
import { validateClientUpload } from "../src/app/api/uploads/route.js";
import { generatePwaManifest } from "../src/app/manifest.js";
import { applyTaxpayerTurnMeta, buildTaxpayerChatTurnView } from "../src/components/index.js";
import {
  consumeAltchaSolution,
  createAltchaChallenge,
  verifyAltchaSolution,
} from "../src/lib/security/altcha.js";
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
    expect(decision.headers["Content-Security-Policy"]).toContain("worker-src 'self'");
    expect(decision.headers["x-nonce"]).toBe("nonce_test_123");
    expect(decision.headers["Cache-Control"]).toBe("private, no-cache, no-store, must-revalidate");

    // 8-locale ROADMAP_LOCALES negotiation in proxy.ts (including Tier C & RFC 9110 q-value weighting)
    expect(
      executeProxy({
        pathname: "/din/chat",
        nonce: "n_din",
      }).locale,
    ).toBe("din");
    expect(
      executeProxy({
        pathname: "/",
        acceptLanguage: "en-US,en;q=0.9,din;q=0.1",
        nonce: "n_q",
      }).locale,
    ).toBe("en");
    expect(
      executeProxy({
        pathname: "/",
        acceptLanguage: "din;q=0,pga;q=0.8,en;q=0.5",
        nonce: "n_q0",
      }).locale,
    ).toBe("pga");

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
      lastEventId: "thr_1:ev:2",
      traceparent: "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
      confirmationToken: "cfm_01",
      idempotencyKey: "idem_01",
    });
    expect(req.url).toBe("http://localhost:8001/v1/agui/stream");
    expect(req.headers["Last-Event-ID"]).toBe("thr_1:ev:2");
    expect(req.headers.traceparent).toContain("00-4bf92f3577b34da6a3ce929d0e0e4736");
    expect(JSON.parse(req.body).confirmation_token).toBe("cfm_01");

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
    const tooLongRes = await streamChatPost(
      new Request("https://assist.ssra.gov.ss/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "x".repeat(4001), locale: "en" }),
      }),
    );
    expect(tooLongRes.status).toBe(413);
    const challenge = await createAltchaChallenge(42, "salt_ssra_1", "secret_key", 5000, 2_000_000);
    expect(challenge.salt.endsWith("&")).toBe(true);
    await expect(createAltchaChallenge(9000, "salt_ssra_1", "secret_key", 5000)).rejects.toThrow(
      RangeError,
    );
    await expect(createAltchaChallenge(42, "bad:salt", "secret_key", 5000)).rejects.toThrow(
      RangeError,
    );
    const valid = await verifyAltchaSolution(
      {
        ...challenge,
        number: 42,
      },
      "secret_key",
      5000,
      1_500_000,
    );
    expect(valid).toBe(true);

    // Expired challenge rejected
    const expired = await verifyAltchaSolution(
      {
        ...challenge,
        number: 42,
      },
      "secret_key",
      5000,
      2_500_000,
    );
    expect(expired).toBe(false);

    // Single-use replay consumption (CVE-2025-68113)
    const firstConsume = await consumeAltchaSolution(
      {
        ...challenge,
        number: 42,
      },
      "secret_key",
      5000,
      1_500_000,
    );
    expect(firstConsume).toBe(true);
    const replayConsume = await consumeAltchaSolution(
      {
        ...challenge,
        number: 42,
      },
      "secret_key",
      5000,
      1_500_000,
    );
    expect(replayConsume).toBe(false);

    const postRes = await streamChatPost(
      new Request("https://assist.ssra.gov.ss/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Last-Event-ID": "thr_1:ev:1",
        },
        body: JSON.stringify({
          message: "What is BPT?",
          locale: "en",
          confirmationToken: "cfm_1",
          idempotencyKey: "idem_1",
        }),
      }),
      async (_url, init) =>
        new Response(String(init?.body ?? ""), {
          status: 200,
          headers: init?.headers as Record<string, string>,
        }),
    );
    expect(postRes.status).toBe(200);
    expect(postRes.headers.get("Last-Event-ID")).toBe("thr_1:ev:1");

    const wrong = await verifyAltchaSolution(
      {
        ...challenge,
        number: 99,
      },
      "secret_key",
      5000,
      1_500_000,
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
    expect(
      validateClientUpload({
        mimeType: "application/pdf",
        sizeBytes: 1000,
        filename: "../../etc/passwd",
      }),
    ).toEqual({ accepted: false, reason: "UNSAFE_FILENAME" });
    expect(
      validateClientUpload({
        mimeType: "application/pdf",
        sizeBytes: 1000,
        filename: "invoice.pdf.exe",
      }),
    ).toEqual({ accepted: false, reason: "UNSAFE_FILENAME" });

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
