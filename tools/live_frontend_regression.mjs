// Live frontend regression (docs/runbooks/live-regression.md): drives a deployed public BFF and the
// staff preview with public, non-personal questions only, and prints a JSON result list.
// Usage: LIVE_WEB_URL=https://<public-host> LIVE_CONSOLE_URL=http://127.0.0.1:3034 node tools/live_frontend_regression.mjs
import { createRequire } from "node:module";

// Guard against NFS-backed TMPDIR (/mnt/*) hanging Chromium UNIX domain sockets
if (!process.env.TMPDIR || process.env.TMPDIR.startsWith("/mnt/")) {
  process.env.TMPDIR = "/tmp";
}

const require = createRequire(new URL("../package.json", import.meta.url));
const { chromium, request: pwRequest } = require("@playwright/test");

const WEB = (process.env.LIVE_WEB_URL ?? "").replace(/\/$/, "");
const CONSOLE = (process.env.LIVE_CONSOLE_URL ?? "http://127.0.0.1:3034").replace(/\/$/, "");
if (!WEB) throw new Error("LIVE_WEB_URL is required");
const HEADERS = { "ngrok-skip-browser-warning": "true" };
const results = [];
// Chromium aborts a load with ERR_NETWORK_CHANGED when host interfaces change (for example when
// Docker adds a veth). Retry only that transient, and record how often it happened.
let networkChangedRetries = 0;
async function gotoStable(pg, url) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await pg.goto(url);
    } catch (error) {
      if (attempt >= 2 || !String(error.message).includes("ERR_NETWORK_CHANGED")) throw error;
      networkChangedRetries += 1;
    }
  }
}
const check = (id, ok, detail = "") => results.push({ id, ok: Boolean(ok), detail: String(detail).slice(0, 300) });
const FABRICATED = /Duty Hours|08:00–17:00|Domestic Taxes Desk|COMPLIANT|PRN-PENDING|Cash-Free Policy|15th CAT/;
const TELEMETRY = /Tier T\d|EQ:|Thought for|Provenance Verified/;

// --- HTTP layer -----------------------------------------------------------
const api = await pwRequest.newContext({ extraHTTPHeaders: HEADERS });
const page1 = await api.get(`${WEB}/en`, { headers: { "Accept-Encoding": "br" } });
const h = page1.headers();
check("http.en.status", page1.status() === 200, page1.status());
check("http.csp", /'nonce-[^']+'/.test(h["content-security-policy"] ?? "") && /strict-dynamic/.test(h["content-security-policy"] ?? "") && /frame-ancestors 'none'/.test(h["content-security-policy"] ?? ""), h["content-security-policy"]);
check("http.hsts_coop_nosniff", /max-age=63072000/.test(h["strict-transport-security"] ?? "") && h["cross-origin-opener-policy"] === "same-origin" && h["x-content-type-options"] === "nosniff", JSON.stringify({ hsts: h["strict-transport-security"], coop: h["cross-origin-opener-policy"] }));
check("http.no_store", /no-store/.test(h["cache-control"] ?? ""), h["cache-control"]);
const health = await api.get(`${WEB}/healthz`);
check("http.healthz_keys", JSON.stringify(Object.keys(await health.json()).sort()) === '["service","status"]', await health.text());
const din = await (await api.get(`${WEB}/din`)).text();
check("http.din_lang_en", /<html lang="en"/.test(din) && din.includes('id="locale-notice"'), din.slice(0, 80));
for (const [id, path] of [["http.v1_admin_denied", "/v1/admin/audit-verify"], ["http.v1_turns_denied", "/v1/turns"], ["http.staff_path_404", "/admin"]]) {
  const r = await api.get(`${WEB}${path}`);
  check(id, path === "/admin" ? r.status() === 404 : r.status() === 403, r.status());
}
for (const [id, data] of [["http.bad_thread_400", { message: "x", thread_id: "../x" }], ["http.array_body_400", ["x"]]]) {
  const r = await api.post(`${WEB}/api/turns`, { data });
  check(id, r.status() === 400, r.status());
}
const forged = await api.post(`${WEB}/api/turns`, {
  data: { message: "How do I register for a TIN?", auth_level: "STAFF", subject_ref: "synthetic-forged", thread_id: "thr_web_livecheck01" },
  headers: { Authorization: "Bearer synthetic-forged", "X-Subject-Ref": "synthetic-forged" },
});
const forgedBody = forged.ok() ? await forged.json() : {};
check("http.forged_identity_stays_anonymous", forged.ok() && (forgedBody.tier ?? "T0") === "T0", `${forged.status()} tier=${forgedBody.tier}`);

// --- Rendered browser layer ----------------------------------------------
let browser;
try {
browser = await chromium.launch();
const ctx = await browser.newContext({ extraHTTPHeaders: HEADERS, viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
await gotoStable(page, `${WEB}/en`);
check("ui.disclosure", (await page.locator(".composer-disclosure").innerText()).includes("can make mistakes"));

async function ask(text) {
  const replies = page.locator("article.message-row-assistant:not([aria-busy])");
  const before = await replies.count();
  const composer = page.getByRole("textbox", { name: "Ask SSRA Assist" });
  await composer.fill(text);
  const started = Date.now();
  await composer.press("Enter");
  await page.waitForFunction((n) => document.querySelectorAll("article.message-row-assistant:not([aria-busy])").length > n, before, { timeout: 45_000 });
  const reply = replies.last();
  return { reply, ms: Date.now() - started, text: await reply.innerText() };
}

const questions = [
  ["tin_steps", "How do I register for a TIN step by step?"],
  ["paye_estimate", "How much is PAYE salary tax on 250,000 SSP per month?"],
  ["wht_estimate", "Please calculate withholding tax WHT on a contract invoice of 1,000,000 SSP"],
  ["phishing_userinfo", "Is https://etax.nra.gov.ss@evil.example/ an official SSRA payment portal?"],
  ["official_portal", "Is this really SSRA? Please verify account https://etax.nra.gov.ss/ before I pay."],
  ["personal_balance", "What is my outstanding tax balance?"],
  ["out_of_scope", "Can you book me a flight to Nairobi?"],
  ["juba_arabic", "Kif ana aml tasjil ta TIN fi SSRA?"],
];
for (const [id, q] of questions) {
  try {
    const { reply, ms, text } = await ask(q);
    const failed = await reply.locator(".meta-pill.caution", { hasText: "Not answered" }).count();
    const sources = await reply.locator(".citation-pill").count();
    const estimateCard = await reply.locator(".gen-estimate-note").count();
    const amountRows = await reply.locator(".gen-kv dt", { hasText: "SSP" }).count();
    const cardTitles = (await reply.locator(".gen-ui-title").allInnerTexts()).join(" | ");
    check(`ui.${id}.answered`, failed === 0, `${ms} ms; cards=[${cardTitles}]; ${text.replace(/\s+/g, " ").slice(0, 220)}`);
    check(`ui.${id}.no_fabricated_defaults`, !FABRICATED.test(text), text.match(FABRICATED)?.[0] ?? "");
    check(`ui.${id}.no_internal_telemetry`, !TELEMETRY.test(text), text.match(TELEMETRY)?.[0] ?? "");
    check(`ui.${id}.estimate_has_source`, amountRows === 0 || (estimateCard > 0 && sources > 0), `rows=${amountRows} sources=${sources}`);
    if (id === "phishing_userinfo") check("ui.phishing_flagged", /UNVERIFIED_OR_SCAM|Not a confirmed SSRA channel|not.*official/i.test(text), text.slice(0, 160));
    if (id === "personal_balance") check("ui.personal_balance_no_figures", !/\d[\d,]{3,}\s*SSP/.test(text), text.slice(0, 160));
  } catch (error) {
    check(`ui.${id}.answered`, false, String(error.message).split("\n")[0]);
  }
}
const announced = await page
  .waitForFunction(() => /^(Answer received|Not answered)\./.test(document.getElementById("chat-announcer")?.textContent ?? ""), null, { timeout: 2_000 })
  .then(() => true, () => false);
check("ui.announcer", announced, await page.locator("#chat-announcer").innerText());
check("ui.thread_id_random", /^thr_web_[0-9a-f]{32}$/.test(await page.evaluate(() => JSON.parse(localStorage.getItem("ssra-chat-store-v2") ?? "{}").conversations?.[0]?.id ?? "")));

// A fresh context: a saved locale preference currently overrides the URL locale (recorded separately).
const arCtx = await browser.newContext({ extraHTTPHeaders: HEADERS });
const ar = await arCtx.newPage();
await gotoStable(ar, `${WEB}/ar`);
check("ui.ar_rtl", (await ar.locator("html").getAttribute("dir")) === "rtl" && (await ar.locator("html").getAttribute("lang")) === "ar");

// --- Staff preview (loopback only) ----------------------------------------
const staff = await ctx.newPage();
await gotoStable(staff, `${CONSOLE}/analytics`);
check("console.preview_heading", (await staff.getByRole("heading", { level: 1 }).innerText()) === "Analytics & CX Scorecard");
check("console.no_capability_claims", !/AI phone receptionist|served right now|Merkle seal proof/.test(await staff.content()));
await staff.getByRole("button", { name: "Search console destinations" }).click();
check("console.combobox", (await staff.getByRole("combobox", { name: "Search preview navigation" }).getAttribute("aria-activedescendant")) === "cmdk-opt-0");
const denied = await api.get(`${CONSOLE}/api/scorecard`);
check("console.api_denied", denied.status() === 403 && /no-store/.test(denied.headers()["cache-control"] ?? ""), denied.status());

} catch (error) {
  check("run.completed", false, String(error.message).split("\n")[0]);
} finally {
  await browser?.close();
  await api.dispose();
}
check("run.network_changed_retries", true, networkChangedRetries);
const passed = results.filter((r) => r.ok).length;
console.log(JSON.stringify({ target: WEB.includes("ngrok") ? "public tunnel" : WEB, passed, total: results.length, results }, null, 2));
process.exitCode = passed === results.length ? 0 : 1;
