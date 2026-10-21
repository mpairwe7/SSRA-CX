/**
 * Production Node.js HTTP & BFF Server for the public SSRA Assist Taxpayer Web PWA (`apps/web/server.js`).
 *
 * Implements the October 2026 `chatv2` MainChat + Sidebar (`ConversationRail`, `ConversationSearch`, `AccountRail`, `SettingsDialog`),
 * and OWASP ASVS 5.0 / WCAG 2.2 AA / ADR-011 hardening:
 * - Republic of South Sudan & SSRA/NRA Natural Civic Palette (`#091310` Nile Dusk, `#F6F7F2` Savanna Cotton Paper, `#078930` Equatoria Green,
 *   `#0F47AF` White Nile Azure, `#F4C430` Guiding Star Gold, `#DA121A` Sovereign Crimson, and `.ssra-flag-ribbon`)
 * - Shared-device Zero-PII storage hygiene (`T0`-only persistence in `localStorage`, PII scrubbing, `SSRA_LOGOUT_PURGE` dispatch)
 * - W3C Trusted Types (`setSafeHtml`) + 6-char `escapeHtml` (`&`, `<`, `>`, `"`, `'`, `` ` ``)
 * - Deterministic Offline Statutory Resilience Pack (`Part-IV-Sec-18-PAYE`, WHT, `etax.nra.gov.ss` verifier, SSRA Office Directory)
 *   + Network Information API 2G `lowDataMode` auto-detection
 * - All 7 Generative UI Card renderers (`BalanceCard`, `FilingStatusTimeline`, `PaymentInstructionsCard`, `CalculatorForm`,
 *   `CitationList`, `ConfirmActionSheet`, `HandoffCard`) + 8-locale live UI dictionary (`en`, `pga`, `ar` RTL, `din`, `nus`, `bfa`, `zne`, `shk`)
 */

import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";
import { ICONS } from "../../packages/ui/icons.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number.parseInt(process.env.PORT ?? "3000", 10);
const HOSTNAME = process.env.HOSTNAME ?? "0.0.0.0";
const INTERNAL_API_URL = (process.env.INTERNAL_API_URL ?? "http://ssra-api:8000").replace(
  /\/$/,
  "",
);
const INTERNAL_RUNTIME_URL = (
  process.env.INTERNAL_RUNTIME_URL ?? "http://ssra-agent-runtime:8001"
).replace(/\/$/, "");

const SUPPORTED_LOCALES = new Set(["en", "pga", "ar", "din", "nus", "bfa", "zne", "shk"]);
const VALID_HOST_RE = /^[A-Za-z0-9.[\]:-]+$/;
const VALID_OPAQUE_HEADER_RE = /^[\x21-\x7e]{1,128}$/;
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "DELETE", "OPTIONS"]);

function createTraceparent(existing) {
  if (typeof existing === "string" && /^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$/.test(existing)) {
    return existing;
  }
  const traceId = crypto.randomBytes(16).toString("hex");
  const spanId = crypto.randomBytes(8).toString("hex");
  return `00-${traceId}-${spanId}-01`;
}

function negotiateAcceptLanguage(acceptLanguage) {
  if (!acceptLanguage || typeof acceptLanguage !== "string") return "en";
  const parts = acceptLanguage.split(",");
  let bestLocale = "en";
  let bestQ = -1;
  for (const part of parts) {
    const [tagRaw = "", ...params] = part.trim().toLowerCase().split(";");
    const primary = tagRaw.split("-")[0]?.trim() ?? "";
    if (!SUPPORTED_LOCALES.has(primary)) continue;
    let q = 1.0;
    for (const p of params) {
      const t = p.trim();
      if (t.startsWith("q=")) {
        const parsed = Number(t.slice(2));
        q = Number.isFinite(parsed) ? parsed : 0;
      }
    }
    if (q > 0 && q <= 1 && q > bestQ) {
      bestQ = q;
      bestLocale = primary;
    }
  }
  return bestLocale;
}

function buildSecurityHeaders(nonce) {
  return {
    "Content-Security-Policy": `default-src 'self'; script-src 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; connect-src 'self'; img-src 'self' data:; worker-src 'self'; manifest-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
    "X-Nonce": nonce,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Permissions-Policy": "geolocation=(), microphone=(self), camera=(), payment=(), usb=()",
    "Cache-Control": "private, no-cache, no-store, must-revalidate",
  };
}

function compactHtmlAssetBlocks(html) {
  return html
    .replace(/<style([^>]*)>([\s\S]*?)<\/style>/g, (_, attrs, css) => {
      const minCss = css
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/\s+/g, " ")
        .replace(/\s*([{}:;,>~])\s*/g, "$1")
        .replace(/;}/g, "}")
        .trim();
      return `<style${attrs}>${minCss}</style>`;
    })
    .replace(/<script([^>]*)>([\s\S]*?)<\/script>/g, (_, attrs, js) => {
      const minJs = js
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0 && !line.startsWith("//"))
        .join("\n");
      return `<script${attrs}>${minJs}</script>`;
    });
}

function acceptsEncoding(acceptEncHeader, targetCoding) {
  let explicitQ = null;
  let wildcardQ = null;
  for (const part of String(acceptEncHeader ?? "").split(",")) {
    const [rawName, ...params] = part.trim().split(";");
    const name = rawName.trim().toLowerCase();
    if (!name) continue;
    let q = 1;
    for (const p of params) {
      const [k, v] = p.split("=");
      if (k && k.trim().toLowerCase() === "q" && v !== undefined) {
        const parsed = Number.parseFloat(v.trim());
        q = Number.isFinite(parsed) ? parsed : 0;
      }
    }
    if (name === targetCoding) {
      explicitQ = q;
    } else if (name === "*") {
      wildcardQ = q;
    }
  }
  if (explicitQ !== null) return explicitQ > 0;
  if (wildcardQ !== null) return wildcardQ > 0;
  return false;
}

function sendBodyWithCompression(req, res, statusCode, headers, bodyStr) {
  const acceptEnc = String(req.headers["accept-encoding"] ?? "");
  const buf = Buffer.from(bodyStr, "utf-8");
  if (buf.length > 512 && acceptsEncoding(acceptEnc, "br")) {
    const compressed = zlib.brotliCompressSync(buf, {
      params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 4 },
    });
    res.writeHead(statusCode, {
      ...headers,
      "Content-Encoding": "br",
      Vary: "Accept-Encoding",
    });
    res.end(compressed);
    return;
  }
  if (buf.length > 512 && acceptsEncoding(acceptEnc, "gzip")) {
    const compressed = zlib.gzipSync(buf, { level: 6 });
    res.writeHead(statusCode, {
      ...headers,
      "Content-Encoding": "gzip",
      Vary: "Accept-Encoding",
    });
    res.end(compressed);
    return;
  }
  res.writeHead(statusCode, headers);
  res.end(buf);
}

function renderPwaShellHtml(locale, nonce) {
  const dir = locale === "ar" ? "rtl" : "ltr";
  const rawHtml = `<!DOCTYPE html>
<html lang="${locale}" dir="${dir}" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="description" content="Official South Sudan Revenue Authority (SSRA / NRA) grounded AI tax assistant for TIN registration, PAYE, Withholding Tax, TCC, and customs guidance." />
  <title>SSRA Assist — South Sudan Revenue Authority Official AI Assistant</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <style nonce="${nonce}">
    :root {
      color-scheme: dark;
      --font-sans: "Aptos", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      --font-mono: "Cascadia Code", "SFMono-Regular", "IBM Plex Mono", monospace;
      --bg-0: #091310;
      --bg-1: #0E1C17;
      --bg-2: #142720;
      --surface-1: rgba(236, 245, 238, 0.04);
      --surface-2: rgba(236, 245, 238, 0.07);
      --surface-3: rgba(236, 245, 238, 0.11);
      --surface-ink: rgba(9, 19, 16, 0.88);
      --border-0: rgba(220, 235, 224, 0.075);
      --border-1: rgba(220, 235, 224, 0.13);
      --border-2: rgba(220, 235, 224, 0.22);
      --text-0: #F6F8F5;
      --text-1: #DCE4DD;
      --text-2: #9BB0A3;
      --text-3: #7E9688;
      --ssra-green: #078930;
      --ssra-blue: #0F47AF;
      --ssra-blue-bright: #3B82F6;
      --ssra-gold: #F4C430;
      --ssra-red: #DA121A;
      --ssra-teal: #078930;
      --ssra-teal-light: #2ECC71;
      --grad-primary: linear-gradient(135deg, #07792B 0%, #0D6E38 52%, #0F47AF 100%);
      --grad-gold: linear-gradient(135deg, #F4C430 0%, #D49B0B 100%);
      --grad-user: linear-gradient(135deg, rgba(7, 137, 48, 0.24), rgba(244, 196, 48, 0.12));
      --success: #34d399;
      --warning: #fbbf24;
      --danger: #fb7185;
      --shadow-md: 0 12px 32px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.04);
      --shadow-lg: 0 24px 60px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.06);
      --radius-sm: 10px;
      --radius-md: 14px;
      --radius-lg: 18px;
      --radius-xl: 24px;
      --radius-pill: 999px;
    }
    :root[data-theme="light"] {
      color-scheme: light;
      --bg-0: #F6F7F2;
      --bg-1: #FFFFFF;
      --bg-2: #EBF0E8;
      --surface-1: rgba(12, 28, 20, 0.032);
      --surface-2: rgba(12, 28, 20, 0.058);
      --surface-3: rgba(12, 28, 20, 0.092);
      --surface-ink: rgba(250, 251, 247, 0.94);
      --border-0: rgba(12, 28, 20, 0.08);
      --border-1: rgba(12, 28, 20, 0.14);
      --border-2: rgba(12, 28, 20, 0.23);
      --text-0: #0C1C14;
      --text-1: #1F3329;
      --text-2: #4A5E53;
      --text-3: #4E6358;
      --ssra-blue-bright: #0F47AF;
      --ssra-teal-light: #066926;
      --ssra-gold: #704B00;
      --success: #066926;
      --warning: #853A06;
      --danger: #B91C1C;
      --grad-user: linear-gradient(135deg, rgba(7, 137, 48, 0.14), rgba(212, 155, 11, 0.12));
      --shadow-md: 0 6px 20px rgba(12, 28, 20, 0.08), 0 0 0 1px rgba(12, 28, 20, 0.05);
      --shadow-lg: 0 16px 44px rgba(12, 28, 20, 0.12), 0 0 0 1px rgba(12, 28, 20, 0.06);
    }
    :root[data-theme="high-contrast"] {
      color-scheme: dark;
      --bg-0: #000000;
      --bg-1: #050505;
      --bg-2: #111111;
      --surface-1: #0D0D0D;
      --surface-2: #161616;
      --surface-3: #222222;
      --surface-ink: #000000;
      --border-1: #FFFFFF;
      --border-2: #FFD60A;
      --text-0: #FFFFFF;
      --text-1: #FFFFFF;
      --text-2: #E5E7EB;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; height: 100%; min-height: 100dvh; font-family: var(--font-sans); background: var(--bg-0); color: var(--text-1); overflow: hidden; }
    body::before {
      content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
      background:
        radial-gradient(ellipse 60% 50% at 18% 12%, rgba(7, 137, 48, 0.22), transparent 62%),
        radial-gradient(ellipse 50% 45% at 82% 28%, rgba(15, 71, 175, 0.18), transparent 56%),
        radial-gradient(ellipse 55% 40% at 50% 92%, rgba(244, 196, 48, 0.08), transparent 60%),
        linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 50%, var(--bg-0) 100%);
    }
    :root[data-theme="light"] body::before {
      background:
        radial-gradient(ellipse 60% 50% at 18% 12%, rgba(7, 137, 48, 0.07), transparent 62%),
        radial-gradient(ellipse 50% 45% at 82% 28%, rgba(15, 71, 175, 0.06), transparent 56%),
        linear-gradient(180deg, var(--bg-0) 0%, #ECEFE6 50%, var(--bg-0) 100%);
    }
    .ssra-flag-ribbon {
      position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 80; pointer-events: none;
      background: linear-gradient(90deg, #0F47AF 0%, #0F47AF 18%, #F4C430 18%, #F4C430 24%, #111815 24%, #111815 48%, #DA121A 48%, #DA121A 74%, #078930 74%, #078930 100%);
    }
    .skip-link {
      position: absolute; left: 12px; top: -48px; z-index: 95; padding: 8px 14px;
      background: var(--bg-1); color: var(--text-0); border: 2px solid var(--ssra-gold);
      border-radius: 8px; font-weight: 700; font-size: 0.84rem; text-decoration: none;
    }
    .skip-link:focus { top: 10px; }

    /* App Shell Grid (chatv2) */
    .app-shell { display: grid; grid-template-columns: 288px minmax(0, 1fr); height: 100dvh; width: 100%; transition: grid-template-columns 0.22s cubic-bezier(0.22, 1, 0.36, 1); }
    .app-shell[data-sidebar="collapsed"] { grid-template-columns: 0px minmax(0, 1fr); }
    @media (min-width: 961px) {
      .app-shell[data-sidebar="collapsed"] .rail-wrap { visibility: hidden; pointer-events: none; }
    }
    .rail-mobile-backdrop { display: none; position: fixed; inset: 0; background: rgba(5, 10, 8, 0.55); z-index: 45; }
    @media (max-width: 960px) {
      .app-shell { grid-template-columns: minmax(0, 1fr); }
      .rail-wrap { position: fixed; inset: 0 auto 0 0; width: min(292px, 86vw); z-index: 50; transform: translateX(-100%); visibility: hidden; transition: transform 0.22s ease, visibility 0.22s ease; }
      :root[dir="rtl"] .rail-wrap { inset: 0 0 0 auto; transform: translateX(100%); }
      .app-shell[data-mobile-rail="open"] .rail-wrap { transform: translateX(0); visibility: visible; }
      .app-shell[data-mobile-rail="open"] .rail-mobile-backdrop { display: block; }
    }
    @media (max-width: 640px) {
      .chat-header { padding: 0.55rem 0.75rem; gap: 0.45rem; }
      .status-badge { display: none; }
      .landing { padding: 1rem 0.85rem 1.5rem; gap: 0.9rem; justify-content: flex-start; }
      .landing-prompts { grid-template-columns: minmax(0, 1fr); }
      .composer-hint { display: none; }
    }

    /* ── chatv2 Sidebar (ConversationRail + AccountRail from FinalYearProject) ── */
    .rail-wrap {
      background: var(--surface-ink); backdrop-filter: blur(22px) saturate(145%);
      border-inline-end: 1px solid var(--border-1); display: flex; flex-direction: column;
      overflow: hidden; height: 100dvh; contain: paint;
    }
    .rail-top {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 0.85rem 0.6rem 1rem; border-bottom: 1px solid var(--border-0);
    }
    .rail-brand { display: flex; align-items: center; gap: 0.6rem; font-weight: 700; font-size: 0.92rem; color: var(--text-0); }
    .rail-mark {
      width: 30px; height: 30px; border-radius: 8px; background: var(--grad-primary);
      color: #fff; display: grid; place-items: center; font-weight: 800; font-size: 0.72rem;
      letter-spacing: 0.04em; box-shadow: 0 4px 12px rgba(7, 137, 48, 0.35);
    }
    .rail-top-actions { display: flex; align-items: center; gap: 4px; }
    .rail-icon-btn {
      width: 44px; height: 44px; border-radius: 8px; background: transparent;
      border: 1px solid transparent; color: var(--text-2); cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center; font-size: 0.86rem;
    }
    .rail-icon-btn:hover { background: var(--surface-2); color: var(--text-0); border-color: var(--border-1); }

    .rail-new-btn {
      margin: 0.75rem 0.85rem 0.45rem; padding: 0.62rem 0.9rem; border-radius: var(--radius-md);
      min-height: 44px;
      background: var(--grad-primary); color: #fff; border: 1px solid rgba(255,255,255,0.14);
      font-weight: 600; font-size: 0.86rem; cursor: pointer;
      display: flex; align-items: center; justify-content: space-between;
      box-shadow: var(--shadow-md); transition: transform 0.12s ease;
    }
    .rail-new-btn:hover { transform: translateY(-1px); }

    .rail-section-label {
      padding: 0.55rem 1rem 0.22rem; font-size: 0.68rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3);
    }
    .rail-list { flex: 1; overflow-y: auto; padding: 0.2rem 0.55rem; display: flex; flex-direction: column; gap: 2px; scrollbar-width: thin; }

    /* 1-line conversation row with hover actions (chatv2/sidebar.css pattern) */
    .rail-row {
      position: relative; display: flex; align-items: center; justify-content: space-between;
      border-radius: var(--radius-sm); border: 1px solid transparent;
      transition: background 0.12s ease;
    }
    .rail-row:hover { background: var(--surface-2); }
    .rail-row.active { background: var(--surface-3); border-color: var(--border-1); }
    .rail-item {
      flex: 1; min-width: 0; padding: 0.5rem 0.65rem; color: var(--text-1);
      font-size: 0.84rem; cursor: pointer; white-space: nowrap; overflow: hidden;
      text-overflow: ellipsis; border: none; background: transparent; text-align: start;
      font-family: inherit;
    }
    .rail-row.active .rail-item { color: var(--text-0); font-weight: 600; }
    .rail-row-actions {
      display: none; align-items: center; gap: 2px; padding-inline-end: 6px;
    }
    .rail-row:hover .rail-row-actions, .rail-row:focus-within .rail-row-actions { display: inline-flex; }
    .rail-act-mini {
      width: 44px; height: 44px; border-radius: 6px; border: none; background: transparent;
      color: var(--text-2); cursor: pointer; font-size: 0.74rem; display: inline-flex;
      align-items: center; justify-content: center;
    }
    .rail-act-mini:hover { background: var(--surface-3); color: var(--text-0); }

    /* AccountRail Footer & Upward Popover Menu (AccountRail.tsx pattern) */
    .rail-footer {
      padding: 0.65rem 0.75rem; border-top: 1px solid var(--border-1);
      background: var(--surface-1); position: relative; display: flex; flex-direction: column; gap: 0.45rem;
    }
    .acct-rail-trigger {
      width: 100%; min-height: 44px; padding: 0.5rem 0.6rem; border-radius: var(--radius-sm);
      background: var(--surface-2); border: 1px solid var(--border-1); color: var(--text-0);
      cursor: pointer; display: flex; align-items: center; gap: 0.6rem; text-align: start; font-family: inherit;
    }
    .acct-rail-trigger:hover { background: var(--surface-3); border-color: var(--border-2); }
    .acct-avatar {
      position: relative; width: 30px; height: 30px; border-radius: 8px;
      background: var(--grad-primary); color: #fff; font-weight: 800; font-size: 0.74rem;
      display: grid; place-items: center; flex: none;
    }
    .acct-dot {
      position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px;
      border-radius: 50%; background: var(--success); border: 2px solid var(--bg-0);
    }
    .acct-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .acct-name { font-size: 0.8rem; font-weight: 700; color: var(--text-0); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .acct-sub { font-size: 0.69rem; color: var(--text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .acct-popover {
      position: absolute; bottom: calc(100% + 8px); left: 0.65rem; right: 0.65rem;
      background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-md);
      box-shadow: var(--shadow-lg); padding: 0.55rem; display: none; flex-direction: column;
      gap: 3px; z-index: 60;
    }
    .acct-popover.open { display: flex; }
    .acct-pop-section { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); padding: 4px 8px 2px; }
    .acct-pop-item {
      min-height: 44px; padding: 8px; border-radius: 7px; border: none; background: transparent;
      color: var(--text-1); font-size: 0.78rem; font-family: inherit; cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; text-decoration: none; text-align: start; width: 100%;
    }
    .acct-pop-item:hover { background: var(--surface-2); color: var(--text-0); }
    .acct-pop-item.active { color: var(--ssra-gold); font-weight: 600; }

    /* Main Column & Floating ChatHeader */
    .app-main-col { display: flex; flex-direction: column; height: 100dvh; overflow: hidden; position: relative; }
    .chat-header { display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 1.25rem; gap: 0.75rem; border-bottom: 1px solid var(--border-0); background: rgba(9, 19, 16, 0.52); backdrop-filter: blur(16px); z-index: 10; }
    :root[data-theme="light"] .chat-header { background: rgba(246, 247, 242, 0.82); }
    .header-left, .header-right { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
    .icon-btn { min-height: 44px; min-width: 44px; padding: 0.36rem 0.68rem; border-radius: var(--radius-sm); background: var(--surface-2); color: var(--text-0); border: 1px solid var(--border-1); cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; font-weight: 600; text-decoration: none; }
    .icon-btn:hover { background: var(--surface-3); border-color: var(--border-2); }
    .call-btn { background: linear-gradient(135deg, rgba(7, 137, 48, 0.24), rgba(15, 71, 175, 0.28)); border-color: rgba(46, 204, 113, 0.45); color: var(--text-0); }
    .ops-link-btn { border-color: rgba(244, 196, 48, 0.45); color: var(--ssra-gold); }
    .status-badge { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.28rem 0.65rem; border-radius: var(--radius-pill); background: rgba(52, 211, 153, 0.12); border: 1px solid rgba(52, 211, 153, 0.32); color: var(--success); font-size: 0.73rem; font-weight: 600; }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 8px var(--success); }
    .status-badge[data-connection="offline"] { background: rgba(218, 18, 26, 0.12); border-color: rgba(218, 18, 26, 0.45); color: #ffb2b5; }
    .status-badge[data-connection="offline"] .status-dot { background: #ff6269; box-shadow: 0 0 8px #ff6269; }
    .status-badge[data-connection="low-data"] { background: rgba(244, 196, 48, 0.12); border-color: rgba(244, 196, 48, 0.45); color: var(--ssra-gold); }
    .status-badge[data-connection="low-data"] .status-dot { background: var(--ssra-gold); box-shadow: 0 0 8px var(--ssra-gold); }

    /* Main Content Area */
    .app-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
    .landing { flex: 1; overflow-y: auto; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1.5rem 1.25rem 2.5rem; max-width: 820px; width: 100%; margin: 0 auto; gap: 1.35rem; }
    .landing-brand { text-align: center; max-width: 640px; }
    .eyebrow-pill { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.32rem 0.85rem; border-radius: var(--radius-pill); background: var(--surface-2); border: 1px solid var(--border-1); font-size: 0.76rem; font-weight: 600; color: var(--ssra-gold); margin-bottom: 0.75rem; }
    .ldv2-headline { font-size: clamp(1.65rem, 3.2vw, 2.35rem); font-weight: 800; color: var(--text-0); margin: 0 0 0.5rem; letter-spacing: -0.02em; line-height: 1.2; }
    .landing-sub { font-size: 0.96rem; color: var(--text-2); margin: 0; line-height: 1.5; }
    .landing-prompts { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.65rem; width: 100%; }
    .landing-chip { min-height: 64px; padding: 0.8rem 0.95rem; border-radius: var(--radius-md); background: var(--surface-1); border: 1px solid var(--border-1); color: var(--text-1); text-align: start; cursor: pointer; display: flex; flex-direction: column; gap: 0.28rem; transition: all 0.15s ease; text-decoration: none; }
    .landing-chip:hover { background: var(--surface-2); border-color: var(--ssra-teal-light); transform: translateY(-2px); box-shadow: var(--shadow-md); }
    .ldv2-cat { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ssra-gold); }
    .landing-chip-text { font-size: 0.85rem; font-weight: 500; color: var(--text-0); line-height: 1.35; }

    /* Chat Stream Area */
    .chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .message-list { flex: 1; overflow-y: auto; padding: 1.25rem clamp(1rem, 4vw, 3rem); display: flex; flex-direction: column; gap: 1rem; max-width: 880px; width: 100%; margin: 0 auto; }
    .message-row { display: flex; flex-direction: column; gap: 0.35rem; animation: fadeIn 0.2s ease-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    .message-row-user { align-items: flex-end; }
    .message-row-assistant { align-items: flex-start; }
    .bubble { max-width: min(720px, 92%); padding: 0.95rem 1.15rem; border-radius: var(--radius-lg); line-height: 1.55; font-size: 0.94rem; }
    .bubble.user { background: var(--grad-user); border: 1px solid rgba(244, 196, 48, 0.35); color: var(--text-0); border-bottom-right-radius: 6px; }
    .bubble.assistant { background: var(--surface-2); border: 1px solid var(--border-1); color: var(--text-0); border-bottom-left-radius: 6px; box-shadow: var(--shadow-md); width: 100%; }
    .turn-meta-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; margin-bottom: 0.55rem; font-size: 0.74rem; color: var(--text-2); }
    .meta-pill { padding: 0.18rem 0.55rem; border-radius: var(--radius-pill); background: var(--surface-3); border: 1px solid var(--border-1); font-weight: 600; font-size: 0.71rem; }
    .meta-pill.tier { color: var(--ssra-gold); border-color: rgba(244, 196, 48, 0.35); }
    .meta-pill.verified { color: var(--success); border-color: rgba(52, 211, 153, 0.35); }
    .meta-pill.eq { color: var(--ssra-teal-light); }

    /* Generative UI Cards */
    .gen-ui-card { margin-top: 0.85rem; padding: 0.95rem 1.1rem; border-radius: var(--radius-md); background: var(--surface-1); border: 1px solid var(--border-2); }
    .gen-ui-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ssra-gold); margin-bottom: 0.55rem; display: flex; align-items: center; justify-content: space-between; }
    .ssra-guided-steps { margin: 0.4rem 0; padding-inline-start: 1.25rem; display: flex; flex-direction: column; gap: 0.4rem; font-size: 0.88rem; }
    .ssra-citation-badges { list-style: none; padding: 0; margin: 0.65rem 0 0; display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .citation-pill { padding: 0.25rem 0.65rem; border-radius: var(--radius-pill); background: rgba(7, 137, 48, 0.14); border: 1px solid rgba(46, 204, 113, 0.35); color: var(--ssra-teal-light); font-size: 0.74rem; font-weight: 600; }
    .confirm-btn { min-height: 44px; margin-top: 0.65rem; padding: 0.55rem 1rem; border-radius: var(--radius-sm); background: var(--grad-gold); color: #091310; font-weight: 700; border: none; cursor: pointer; font-size: 0.84rem; }
    .turn-actions { display: flex; align-items: center; gap: 0.45rem; margin-top: 0.65rem; padding-top: 0.55rem; border-top: 1px solid var(--border-0); }
    .turn-act-btn { min-height: 44px; padding: 0.25rem 0.75rem; border-radius: 6px; background: var(--surface-1); border: 1px solid var(--border-0); color: var(--text-2); font-size: 0.74rem; cursor: pointer; }
    .turn-act-btn:hover { color: var(--text-0); border-color: var(--border-1); }

    /* Composer Dock */
    .composer-dock { width: 100%; max-width: 820px; margin: 0 auto; padding: 0.65rem 1rem max(0.85rem, env(safe-area-inset-bottom)); }
    .composer-box { background: var(--surface-2); backdrop-filter: blur(20px); border: 1px solid var(--border-2); border-radius: var(--radius-xl); padding: 0.65rem 0.85rem; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; gap: 0.45rem; transition: border-color 0.15s ease; }
    .composer-box:focus-within { border-color: var(--ssra-gold); }
    .composer-textarea { width: 100%; min-height: 46px; max-height: 140px; resize: none; border: none; background: transparent; color: var(--text-0); font: inherit; font-size: 0.95rem; outline: none; line-height: 1.45; }
    .composer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
    .composer-tools-left, .composer-tools-right { display: flex; align-items: center; gap: 0.45rem; }
    .send-btn { min-height: 44px; padding: 0 1rem; border-radius: var(--radius-pill); background: var(--grad-primary); color: #fff; border: none; font-weight: 700; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; }
    .send-btn:disabled { opacity: 0.48; cursor: not-allowed; }
    .composer-waveform { display: inline-flex; align-items: center; gap: 3px; height: 16px; }
    .composer-waveform span { width: 3px; height: 12px; border-radius: 2px; background: var(--ssra-gold); display: inline-block; }

    /* Modals: CallScreen, ConversationSearch (⌘K), SettingsDialog */
    .modal-backdrop { position: fixed; inset: 0; background: rgba(5, 10, 8, 0.76); backdrop-filter: blur(14px); z-index: 100; display: none; place-items: center; padding: 1rem; }
    .modal-backdrop.open { display: grid; }
    .call-modal { max-width: 440px; width: 100%; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-xl); padding: 1.75rem 1.5rem; text-align: center; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; align-items: center; gap: 1rem; }
    .call-orb { width: 108px; height: 108px; border-radius: 50%; background: radial-gradient(circle at 35% 30%, #2ECC71, #078930 55%, #0F47AF 95%); box-shadow: 0 0 40px rgba(7, 137, 48, 0.45); animation: orbPulse 2.2s ease-in-out infinite; display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 0.88rem; }
    @keyframes orbPulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.07); } }

    .search-modal { max-width: 540px; width: 100%; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow: hidden; }
    .search-input { width: 100%; padding: 14px 16px; border: none; border-bottom: 1px solid var(--border-1); background: transparent; color: var(--text-0); font: inherit; font-size: 0.95rem; outline: none; }
    .search-results { max-height: 320px; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 4px; }

    .settings-modal { max-width: 680px; width: 100%; min-height: 380px; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); display: grid; grid-template-columns: 185px 1fr; overflow: hidden; }
    @media (max-width: 640px) { .settings-modal { grid-template-columns: 1fr; } }
    .settings-tabs { background: var(--surface-1); border-inline-end: 1px solid var(--border-1); padding: 1rem 0.6rem; display: flex; flex-direction: column; gap: 4px; }
    .settings-tab-btn { padding: 8px 12px; border-radius: 8px; border: none; background: transparent; color: var(--text-2); font: inherit; font-size: 0.83rem; font-weight: 600; text-align: start; cursor: pointer; }
    .settings-tab-btn.active { background: var(--surface-3); color: var(--text-0); }
    .settings-pane { padding: 1.25rem 1.4rem; display: flex; flex-direction: column; gap: 0.85rem; }

    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
    .is-hidden { display: none !important; }
    .rail-brand-sub { font-size: 0.68rem; color: var(--text-2); font-weight: 500; }
    .rail-kbd { font-size: 0.68rem; opacity: 0.8; font-family: var(--font-mono); }
    .acct-pop-hr { border: 0; border-top: 1px solid var(--border-0); margin: 3px 0; }
    .acct-chevron { color: var(--text-3); font-size: 0.75rem; }
    .active-conv-title { font-weight: 700; font-size: 0.9rem; color: var(--text-0); }
    .composer-hint { font-size: 0.75rem; color: var(--text-2); }
    .call-modal-title { margin: 0; color: var(--text-0); font-size: 1.25rem; }
    .call-transcript-live { margin: 0; font-size: 0.9rem; color: var(--text-1); min-height: 2.5rem; }
    .call-prompts-row { display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: center; }
    .call-actions-row { display: flex; gap: 0.65rem; margin-top: 0.5rem; }
    .danger-outline-btn { background: rgba(251, 113, 133, 0.2); border-color: var(--danger); color: var(--danger); }
    .danger-text-btn { color: var(--danger); }
    .settings-heading { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: var(--text-3); padding: 4px 12px; }
    .settings-pane-head { display: flex; justify-content: space-between; align-items: center; }
    .settings-pane-title { margin: 0; color: var(--text-0); font-size: 1.05rem; }
    .settings-pane-body { font-size: 0.86rem; color: var(--text-2); line-height: 1.55; }
    .settings-actions-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 8px; }
    .gen-resumable { margin-top: 0.45rem; font-size: 0.8rem; color: var(--ssra-gold); }
    .gen-summary-lg { font-size: 0.9rem; }
    .gen-summary-md { font-size: 0.86rem; }
    .gen-periods-list { margin: 0.4rem 0; padding-inline-start: 1.2rem; font-size: 0.85rem; }
    .gen-confirm-box { margin-top: 0.55rem; padding: 0.65rem; border-radius: 8px; background: rgba(244, 196, 48, 0.1); border: 1px solid rgba(244, 196, 48, 0.35); }
    .gen-confirm-title { font-size: 0.84rem; font-weight: 600; color: var(--ssra-gold); }
    .turn-content-text { white-space: pre-wrap; }
    .rail-empty-hint { padding: 0.75rem; font-size: 0.78rem; color: var(--text-3); }
    :focus-visible { outline: 3px solid var(--ssra-gold); outline-offset: 2px; }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
    }
    .jump-open-tag { font-size: 0.7rem; color: var(--text-3); }
  </style>
</head>
<body>
  <div class="ssra-flag-ribbon" aria-hidden="true"></div>
  <a class="skip-link" href="#main-content">Skip to main content</a>

  <div id="ssra-app-shell" class="app-shell chatv2" data-sidebar="open" data-mobile-rail="closed" data-locale="${locale}">
    <div id="rail-mobile-backdrop" class="rail-mobile-backdrop" aria-hidden="true"></div>
    <!-- Left Conversation Rail (ConversationRail.tsx + AccountRail.tsx pattern) -->
    <aside class="rail-wrap" id="conversation-rail" aria-label="Conversation history and account">
      <div class="rail-top">
        <div class="rail-brand">
          <div class="rail-mark" aria-hidden="true">${ICONS.ssraCrest}</div>
          <div>
            <div>SSRA Assist</div>
            <div class="rail-brand-sub">National Revenue Authority</div>
          </div>
        </div>
        <div class="rail-top-actions">
          <button type="button" id="rail-search-btn" class="rail-icon-btn" title="Search conversations (Ctrl+K)" aria-label="Search conversations">${ICONS.search}</button>
          <button type="button" id="rail-collapse-btn" class="rail-icon-btn" title="Collapse sidebar" aria-label="Collapse conversations sidebar" aria-controls="conversation-rail">${ICONS.panelLeft}</button>
        </div>
      </div>

      <button type="button" id="new-chat-btn" class="rail-new-btn">
        <span>${ICONS.plus} New Conversation</span>
        <kbd class="rail-kbd">Ctrl+N</kbd>
      </button>

      <div id="rail-conv-list" class="rail-list" role="list"></div>

      <!-- AccountRail Footer & Upward Popover Menu -->
      <div class="rail-footer">
        <div id="acct-popover" class="acct-popover" role="menu" aria-label="Account and privacy menu">
          <div class="acct-pop-section" role="presentation">Public conversation</div>
          <p class="acct-pop-item" role="presentation">Personal balances and filing records require secure sign-in.</p>
          <a href="https://etax.nra.gov.ss/" class="acct-pop-item" role="menuitem" rel="noopener noreferrer"><span>Open official e-Tax portal</span><span>${ICONS.arrowUpRight}</span></a>
          <hr class="acct-pop-hr" role="separator" />
          <button type="button" id="open-settings-btn" class="acct-pop-item" role="menuitem"><span>${ICONS.settings} Settings &amp; Privacy</span><span>Ctrl+,</span></button>
        </div>

        <button type="button" id="acct-rail-trigger" class="acct-rail-trigger" aria-expanded="false" aria-haspopup="menu" aria-controls="acct-popover">
          <div class="acct-avatar"><span id="acct-badge-text">PV</span><span class="acct-dot"></span></div>
          <div class="acct-meta">
            <span class="acct-name" id="acct-name-text">Public chat</span>
            <span class="acct-sub" id="acct-sub-text">No account details are shown here</span>
          </div>
          <span class="acct-chevron">${ICONS.chevronUpDown}</span>
        </button>

      </div>
    </aside>

    <!-- Main Column -->
    <div class="app-main-col">
      <header class="chat-header">
        <div class="header-left">
          <button type="button" id="header-rail-btn" class="icon-btn" aria-label="Open conversations" aria-expanded="false" aria-controls="conversation-rail">${ICONS.panelLeft}</button>
          <span id="active-conv-title" class="active-conv-title">New Conversation</span>
          <span id="net-status-badge" class="status-badge" role="status" aria-live="polite"><span class="status-dot" aria-hidden="true"></span><span id="net-status-text">Official sources cited per answer</span></span>
        </div>
        <div class="header-right">
          <button type="button" id="open-call-btn" class="icon-btn call-btn" aria-label="Open voice input options">${ICONS.mic} Voice input</button>
          <select id="locale-select" class="icon-btn" aria-label="Select language">
            <option value="en" ${locale === "en" ? "selected" : ""}>English (en)</option>
            <option value="pga" ${locale === "pga" ? "selected" : ""}>Juba Arabic (pga)</option>
            <option value="ar" ${locale === "ar" ? "selected" : ""}>العربية (ar)</option>
            <option value="din" ${locale === "din" ? "selected" : ""}>Thuɔŋjäŋ Dinka (din)</option>
            <option value="nus" ${locale === "nus" ? "selected" : ""}>Thok Naath Nuer (nus)</option>
            <option value="bfa" ${locale === "bfa" ? "selected" : ""}>Bari (bfa)</option>
            <option value="zne" ${locale === "zne" ? "selected" : ""}>Pazande (zne)</option>
            <option value="shk" ${locale === "shk" ? "selected" : ""}>Dhøg Cøllø Shilluk (shk)</option>
          </select>
          <button type="button" id="theme-toggle-btn" class="icon-btn" title="Switch color theme">${ICONS.moon} Dark</button>
          <button type="button" id="clear-chat-btn" class="icon-btn" aria-label="Delete all saved conversations on this device">${ICONS.trash} Clear all</button>
        </div>
      </header>

      <main id="main-content" class="app-content" tabindex="-1">
        <!-- Landing Hero State -->
        <div id="landing-view" class="landing">
          <div class="landing-brand">
            <div class="eyebrow-pill">${ICONS.ssraCrest} Republic of South Sudan · SSRA / NRA Grounded AI Assistant</div>
            <h1 id="landing-headline" class="ldv2-headline">How can I help with your South Sudan taxes today?</h1>
            <p id="landing-subtitle" class="landing-sub">Ask about TIN registration, PAYE, TCC, customs, or e-Tax. Answers cite approved sources when available. If a source cannot be confirmed, SSRA Assist will say so and offer staff help.</p>
          </div>

          <div class="landing-prompts" role="group" aria-label="Suggested tax questions">
            <button type="button" class="landing-chip" data-prompt="How do I register for a TIN step by step?">
              <span class="ldv2-cat">TIN Registration</span>
              <span class="landing-chip-text">How do I register for a TIN step by step?</span>
            </button>
            <button type="button" class="landing-chip" data-prompt="How much is PAYE salary tax on 250,000 SSP per month?">
              <span class="ldv2-cat">PAYE Calculator</span>
              <span class="landing-chip-text">How much is PAYE salary tax on 250,000 SSP per month?</span>
            </button>
            <button type="button" class="landing-chip" data-prompt="Please calculate withholding tax WHT on a contract invoice of 1,000,000 SSP">
              <span class="ldv2-cat">Withholding Tax (WHT)</span>
              <span class="landing-chip-text">Calculate WHT on a contract invoice of 1,000,000 SSP</span>
            </button>
            <button type="button" class="landing-chip" data-prompt="How do I apply for a Tax Compliance Certificate (TCC) on the SSRA e-Tax portal?">
              <span class="ldv2-cat">Compliance (TCC)</span>
              <span class="landing-chip-text">How do I apply for a Tax Compliance Certificate (TCC)?</span>
            </button>
            <button type="button" class="landing-chip" data-prompt="Is this really SSRA? Please verify account https://etax.nra.gov.ss/ before I pay.">
              <span class="ldv2-cat">Scam &amp; Channel Check</span>
              <span class="landing-chip-text">Is this really SSRA? Verify https://etax.nra.gov.ss/</span>
            </button>
            <button type="button" class="landing-chip" data-prompt="Waraga de Cuɔk de Wëu (TCC) në SSRA paguot?">
              <span class="ldv2-cat">Thuɔŋjäŋ (Dinka)</span>
              <span class="landing-chip-text">Waraga de Cuɔk de Wëu (TCC) në SSRA paguot?</span>
            </button>
            <button type="button" class="landing-chip" data-prompt="Kif ana aml tasjil ta TIN fi SSRA?">
              <span class="ldv2-cat">Juba Arabic (pga)</span>
              <span class="landing-chip-text">Kif ana aml tasjil ta TIN fi SSRA?</span>
            </button>
            <a class="landing-chip" href="https://etax.nra.gov.ss/" rel="noopener noreferrer">
              <span class="ldv2-cat">Personal e-Tax services</span>
              <span class="landing-chip-text">Sign in to check your own balance or filing status</span>
            </a>
          </div>
        </div>

        <!-- Active Conversation Message List -->
        <div id="chat-view" class="chat-area is-hidden" aria-label="Chat conversation">
          <div id="ssra-chat-messages" class="message-list" role="log" aria-live="polite"></div>
        </div>

        <!-- Floating Composer Dock -->
        <div class="composer-dock">
          <form id="ssra-chat-form" class="composer-box">
            <label for="ssra-chat-input" class="sr-only">Ask SSRA Assist</label>
            <textarea id="ssra-chat-input" class="composer-textarea" rows="1" required placeholder="Ask anything about SSRA taxes, TIN, PAYE, TCC, or customs in English, Arabic, Juba Arabic, or Dinka..."></textarea>
            <div class="composer-toolbar">
              <div class="composer-tools-left">
                <button type="button" id="voice-dictate-btn" class="icon-btn" title="Voice Dictation (Whisper-SALT / Speech API)" aria-label="Voice Dictation">
                  ${ICONS.mic} <span class="composer-waveform" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></span>
                </button>
                <span id="composer-hint" class="composer-hint" role="status" aria-live="polite">Enter to send · Shift+Enter for newline · Ctrl+K search</span>
              </div>
              <div class="composer-tools-right">
                <button type="submit" id="ssra-chat-submit" class="send-btn">${ICONS.send} Send</button>
              </div>
            </div>
          </form>
        </div>
      </main>
    </div>
  </div>

  <!-- AI Call Receptionist Modal (CallScreen & CallOrb) -->
  <div id="call-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="call-modal-title">
    <div class="call-modal">
    <div class="eyebrow-pill">${ICONS.mic} Browser voice input</div>
      <h2 id="call-modal-title" class="call-modal-title">Speak or choose a sample question</h2>
      <p id="call-transcript-live" class="call-transcript-live">Voice typing depends on your browser and is currently available only in English and Arabic. Your browser may process audio outside SSRA. Do not speak or type a TIN, balance, or other private account details in this public chat.</p>
      <div class="call-prompts-row">
        <button type="button" class="icon-btn call-sample-btn" data-voice-q="Where can I find general e-Tax filing guidance?">${ICONS.messageSquare} "General e-Tax guidance"</button>
        <button type="button" class="icon-btn call-sample-btn" data-voice-q="Where can I find general customs guidance?">${ICONS.messageSquare} "General customs guidance"</button>
      </div>
      <div class="call-actions-row">
        <button type="button" id="close-call-btn" class="icon-btn danger-outline-btn">${ICONS.close} Close</button>
      </div>
    </div>
  </div>

  <!-- ConversationSearch Modal (ConversationSearch.tsx pattern, Ctrl+K) -->
  <div id="search-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Search conversations">
    <div class="search-modal">
  <input id="conv-search-input" class="search-input" type="text" aria-label="Search saved conversations" placeholder="Search saved conversations… (Esc to close)" autocomplete="off" />
      <div id="conv-search-results" class="search-results" role="group" aria-label="Search results"></div>
    </div>
  </div>

  <!-- Tabbed SettingsDialog Modal (SettingsDialog.tsx pattern) -->
  <div id="settings-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Settings">
    <div class="settings-modal">
      <div class="settings-tabs" role="tablist" aria-label="Settings categories">
        <div class="settings-heading" role="presentation">Settings</div>
        <button type="button" class="settings-tab-btn active" role="tab" aria-selected="true" data-settings-tab="general">General &amp; Theme</button>
        <button type="button" class="settings-tab-btn" role="tab" aria-selected="false" data-settings-tab="voice">Voice &amp; Speech</button>
        <button type="button" class="settings-tab-btn" role="tab" aria-selected="false" data-settings-tab="profile">Taxpayer Profile</button>
        <button type="button" class="settings-tab-btn" role="tab" aria-selected="false" data-settings-tab="privacy">Privacy &amp; Erasure</button>
      </div>
      <div class="settings-pane" role="tabpanel">
        <div class="settings-pane-head">
          <h2 id="settings-pane-title" class="settings-pane-title">General &amp; Appearance</h2>
          <button type="button" id="close-settings-btn" class="icon-btn">${ICONS.close} Close</button>
        </div>
        <div id="settings-pane-body" class="settings-pane-body"></div>
      </div>
    </div>
  </div>

  <script nonce="${nonce}">
    (() => {
      const ICONS = ${JSON.stringify(ICONS)};
      if ("serviceWorker" in navigator) {
        caches?.keys?.().then((keys) => {
          keys.forEach((k) => {
            if (k !== "ssra-assist-public-shell-v2026.10.4") caches.delete(k);
          });
        }).catch(() => {});
        navigator.serviceWorker.register("/sw.js").catch(() => {});
      }

      // W3C Trusted Types & 6-character HTML Escaping (FE-G3)
      function escapeHtml(str) {
        return String(str ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;")
          .replace(/\x60/g, "&#96;");
      }
      const ttPolicy = window.trustedTypes?.createPolicy
        ? window.trustedTypes.createPolicy("ssra-web-html", { createHTML: (h) => h })
        : null;
      function setSafeHtml(el, htmlStr) {
        if (!el) return;
        el.innerHTML = ttPolicy ? ttPolicy.createHTML(htmlStr) : htmlStr;
      }

      // 8-Locale South Sudan UI Dictionary (FE-G5)
      const LOCALE_UI_STRINGS = {
        en: {
          headline: "How can I help with your South Sudan taxes today?",
          subtitle: "Ask about TIN registration, PAYE, TCC, customs, or e-Tax. Answers cite approved sources when available. If a source cannot be confirmed, SSRA Assist will say so and offer staff help.",
          placeholder: "Ask anything about SSRA taxes, TIN, PAYE, TCC, or customs in English, Arabic, Juba Arabic, or Dinka...",
        },
        pga: {
          headline: "Kif ana agdar asaidu inta fi darayib ta South Sudan al-yom?",
          subtitle: "Is'al an TIN, PAYE, TCC, Jamarik, aw e-Tax. Ijaba bitzkur maraji SSRA lama yisanduha. Iza al-masdar mish mu'akkad, SSRA Assist bitwaddeh da wa bitqaddim musaa'ada min الموظفين.",
          placeholder: "As'al ayi su'al ala TIN, PAYE, TCC, aw Jamarik bi Arabi Juba...",
        },
        ar: {
          headline: "كيف يمكنني مساعدتك في ضرائب جنوب السودان اليوم؟",
          subtitle: "اسأل عن تسجيل الرقم الضريبي أو PAYE أو شهادة الامتثال أو الجمارك أو e-Tax. تذكر الإجابات المصادر المعتمدة عند توفرها. إذا تعذر تأكيد المصدر، سنوضح ذلك ونقترح التواصل مع موظف.",
          placeholder: "اسأل عن الرقم الضريبي TIN أو ضريبة الدخل PAYE أو شهادة الامتثال TCC أو الجمارك...",
        },
        din: {
          headline: "Ba kony yin këdë në wëu ke ajuiɛɛr (SSRA / NRA) në Paguot Thudän akölë?",
          subtitle: "Wël ke lööŋ ke SSRA në gät de TIN, akuën de PAYE ku WHT, Waraga de Cuɔk de Wëu (TCC), ku ajuiɛɛr de الثغور (Nimule).",
          placeholder: "Thiëc në Thuɔŋjäŋ në wëu ke TIN, PAYE, TCC, tëdë ke Jamarik...",
        },
        nus: {
          headline: "Ba konyi ɛŋu kɛ luɔt SSRA / NRA kä Paguot Thudän walɛ?",
          subtitle: "Gör TIN, akuën PAYE kɛnɛ WHT, ku Waraga TCC kä etax.nra.gov.ss.",
          placeholder: "Thiëc kä Thok Naath (Nuer) kɛ TIN, PAYE, TCC...",
        },
        bfa: {
          headline: "Nan konyo iyesi ko SSRA / NRA pajak ti South Sudan?",
          subtitle: "TIN registration, PAYE & WHT calculators, ko Tax Compliance Certificate (TCC).",
          placeholder: "Tiya ko Bari نشت TIN, PAYE, TCC...",
        },
        zne: {
          headline: "Wai rengba mi ka undo ro na marã ngbii SSRA / NRA areme?",
          subtitle: "TIN, PAYE, WHT, na Waraga TCC rogo etax.nra.gov.ss.",
          placeholder: "Mo sanahe rogo Pazande tipa TIN, PAYE, TCC...",
        },
        shk: {
          headline: "A konyi yi ngo ki SSRA / NRA pajak pa Paguot Thudän?",
          subtitle: "TIN, PAYE, WHT, ki TCC e-Tax portal (etax.nra.gov.ss).",
          placeholder: "Peny ki Dhøg Cøllø (Shilluk)...",
        },
      };

      const shell = document.getElementById("ssra-app-shell");
      const landingView = document.getElementById("landing-view");
      const chatView = document.getElementById("chat-view");
      const msgList = document.getElementById("ssra-chat-messages");
      const form = document.getElementById("ssra-chat-form");
      const input = document.getElementById("ssra-chat-input");
      const submitBtn = document.getElementById("ssra-chat-submit");
      const localeSelect = document.getElementById("locale-select");
      const convListEl = document.getElementById("rail-conv-list");
      const activeTitleEl = document.getElementById("active-conv-title");
      const hintEl = document.getElementById("composer-hint");
      const acctTrigger = document.getElementById("acct-rail-trigger");
      const acctPopover = document.getElementById("acct-popover");

      // Detect 2G / Save-Data network condition (FE-G4)
      const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      const autoLowData = Boolean(
        conn && (conn.saveData || conn.effectiveType === "slow-2g" || conn.effectiveType === "2g")
      );

      const STORAGE_KEY = "ssra-chat-store-v2";
      let state = {
        locale: shell?.dataset.locale || "en",
        theme: "dark",
        lowDataMode: autoLowData,
        autoNarrate: false,
        settingsTab: "general",
        conversations: [],
        activeId: null,
      };
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
        if (saved && Array.isArray(saved.conversations)) {
          state = {
            ...state,
            theme: saved.theme || state.theme,
            locale: saved.locale || state.locale,
            lowDataMode: saved.lowDataMode ?? state.lowDataMode,
            autoNarrate: Boolean(saved.autoNarrate),
            conversations: saved.conversations.filter((c) => !c.isAuthenticated),
          };
        }
      } catch {}

      // FE-G1: Zero-PII Shared-Device Storage Hygiene — never persist non-T0 or TIN-bearing turns to localStorage
      function scrubPiiForStorage(text) {
        return String(text || "")
          .replace(/\\+?211\\d{9}\\b/g, "[REDACTED_PHONE]")
          .replace(/\\b\\d{9,12}\\b/g, "[REDACTED_TIN]");
      }
      function saveState() {
        try {
          const publicOnlyConvs = state.conversations
            .filter((c) => !c.isAuthenticated)
            .slice(0, 25)
            .map((c) => ({
              id: c.id,
              title: scrubPiiForStorage(c.title),
              pinned: Boolean(c.pinned),
              isAuthenticated: false,
              updatedAtMs: Number.isFinite(c.updatedAtMs) ? c.updatedAtMs : null,
              turns: (c.turns || [])
                .filter((t) => !t.meta?.tier || t.meta.tier === "T0")
                .map((t) => ({
                  role: t.role,
                  content: scrubPiiForStorage(t.content),
                  meta: t.meta,
                })),
            }));
          localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({
              locale: state.locale,
              theme: state.theme,
              lowDataMode: state.lowDataMode,
              autoNarrate: state.autoNarrate,
              conversations: publicOnlyConvs,
            }),
          );
        } catch {}
      }

      function dispatchSwLogoutPurge() {
        try {
          navigator.serviceWorker?.controller?.postMessage({ type: "SSRA_LOGOUT_PURGE" });
        } catch {}
      }

      function applyLocaleStrings(loc) {
        state.locale = SUPPORTED_LOCALE_SET.has(loc) ? loc : "en";
        document.documentElement.lang = state.locale;
        document.documentElement.dir = state.locale === "ar" ? "rtl" : "ltr";
        const dict = LOCALE_UI_STRINGS[state.locale] || LOCALE_UI_STRINGS.en;
        const hEl = document.getElementById("landing-headline");
        const sEl = document.getElementById("landing-subtitle");
        if (hEl) hEl.textContent = dict.headline;
        if (sEl) sEl.textContent = dict.subtitle;
        if (input) input.placeholder = dict.placeholder;
      }
      const SUPPORTED_LOCALE_SET = new Set(Object.keys(LOCALE_UI_STRINGS));
      applyLocaleStrings(state.locale);

      function applyTheme(t) {
        state.theme = t;
        document.documentElement.setAttribute("data-theme", t);
        const btn = document.getElementById("theme-toggle-btn");
        if (btn) {
          setSafeHtml(
            btn,
            t === "dark"
              ? ICONS.moon + " Dark"
              : t === "light"
                ? ICONS.sun + " Light"
                : ICONS.contrast + " Contrast",
          );
        }
        saveState();
      }
      applyTheme(state.theme || "dark");

      // Offline fallback abstains, preserves request uncertainty, and does not cite a snapshot.
      function computeOfflineResilienceAnswer(text) {
        const q = String(text || "").toLowerCase();
        const isCalcOrRate =
          q.includes("paye") || q.includes("salary") || q.includes("wht") || q.includes("withholding");
        return {
          content: isCalcOrRate
            ? "The connection was lost before SSRA Assist confirmed a response. I can’t tell whether your request completed. Check with SSRA staff before repeating a consequential request. I can’t calculate or confirm tax figures while offline. You can also visit the official SSRA / NRA e-Tax portal: https://etax.nra.gov.ss/."
            : "The connection was lost before SSRA Assist confirmed a response. I can’t tell whether your request completed. Check with SSRA staff before repeating a consequential request. Reconnect to continue, or visit the official SSRA / NRA e-Tax portal: https://etax.nra.gov.ss/.",
          meta: {
            tier: "T0",
            intent: isCalcOrRate ? "offline_calculator_abstention" : "offline_resilience_guidance",
            outcome_verified: false,
            citations: [],
          },
        };
      }

      // FE-G5: Render all 7 Generative UI Card types
      function renderGenerativeCard(ui, pendingConfirmation, threadId) {
        if (!ui && !pendingConfirmation) return "";
        const cardName = ui?.name || "ConfirmActionSheet";
        const props = ui?.props || {};
        let inner = "";

        if (Array.isArray(props.guided_steps) && props.guided_steps.length > 0) {
          inner += '<ol class="ssra-guided-steps">' + props.guided_steps.map((s) =>
            "<li><strong>" + escapeHtml(s.title || ("Step " + s.step_number)) + ":</strong> " + escapeHtml(s.instruction || s.detail || "") + "</li>"
          ).join("") + "</ol>";
        }
        if (props.resumable_workflow) {
          inner += '<div class="gen-resumable">' + ICONS.history + " Resumable Journey Paused: <strong>" + escapeHtml(props.resumable_workflow.journey_intent) + "</strong> (Step " + escapeHtml(props.resumable_workflow.current_step) + " of " + escapeHtml(props.resumable_workflow.total_steps) + ")</div>";
        }
        if (props.total_outstanding_ssp !== undefined) {
          inner += '<div class="gen-summary-lg"><strong>Outstanding Balance:</strong> ' + escapeHtml(props.total_outstanding_ssp) + " SSP · <strong>Filing Status:</strong> " + escapeHtml(props.filing_status || "COMPLIANT") + "</div>";
        }
        if (Array.isArray(props.periods) && props.periods.length > 0) {
          inner += '<ul class="gen-periods-list">' + props.periods.map((p) =>
            "<li><strong>" + escapeHtml(p.period || p.tax_type || "Period") + ":</strong> " + escapeHtml(p.status || "FILED") + " (Due: " + escapeHtml(p.due_date || "15th CAT") + ")</li>"
          ).join("") + "</ul>";
        }
        if (props.prn || props.approved_banks) {
          inner += '<div class="gen-summary-md"><strong>Payment Reference (PRN):</strong> <code>' + escapeHtml(props.prn || "PRN-PENDING") + "</code> · <strong>Cash-Free Policy:</strong> Pay only at approved commercial banks via https://etax.nra.gov.ss/</div>";
        }
        if (props.estimated_tax_ssp !== undefined || props.net_pay_ssp !== undefined || props.withholding_tax_ssp !== undefined) {
          inner += '<div class="gen-summary-lg"><strong>Estimated Tax:</strong> ' + escapeHtml(props.estimated_tax_ssp || props.withholding_tax_ssp || "") + " SSP" + (props.net_pay_ssp ? " · <strong>Net Pay:</strong> " + escapeHtml(props.net_pay_ssp) + " SSP" : "") + "</div>";
        }
        if (props.queue || props.reason || props.case_id) {
          inner += '<div class="gen-summary-md"><strong>SSRA Officer AssistanceQueue:</strong> ' + escapeHtml(props.queue || "Domestic Taxes Desk") + (props.case_id ? " · <strong>Case ID:</strong> <code>" + escapeHtml(props.case_id) + "</code>" : "") + " · <strong>Duty Hours:</strong> Mon–Fri 08:00–17:00 CAT (Africa/Juba)</div>";
        }
        if (pendingConfirmation && pendingConfirmation.token) {
          inner += '<div class="gen-confirm-box">' +
            '<div class="gen-confirm-title">Action Confirmation Required (T2): ' + escapeHtml(pendingConfirmation.summary_text) + "</div>" +
            '<button type="button" class="confirm-btn" data-confirm-token="' + escapeHtml(pendingConfirmation.token) + '" data-idem-key="' + escapeHtml(pendingConfirmation.idempotency_key) + '" data-thread-id="' + escapeHtml(threadId) + '">' + ICONS.check + " Confirm &amp; Execute " + escapeHtml(pendingConfirmation.tool) + "</button>" +
          "</div>";
        }
        return '<div class="gen-ui-card" role="region" aria-label="' + escapeHtml(cardName) + '">' +
          '<div class="gen-ui-title"><span>' + ICONS.sparkles + " " + escapeHtml(cardName) + "</span></div>" +
          inner +
        "</div>";
      }

      function renderTurnHtml(turn) {
        if (turn.role === "user") {
          return '<article class="message-row message-row-user"><div class="bubble user">' + escapeHtml(turn.content) + "</div></article>";
        }
        const meta = turn.meta || {};
        const pills = [];
        if (meta.tier) pills.push('<span class="meta-pill tier">Tier ' + escapeHtml(meta.tier) + "</span>");
        if (meta.intent) pills.push('<span class="meta-pill">' + escapeHtml(meta.intent) + "</span>");
        if (meta.outcome_verified) pills.push('<span class="meta-pill verified">' + ICONS.shieldCheck + " Provenance Verified</span>");
        if (meta.recommended_tone && meta.recommended_tone !== "standard_clear") {
          pills.push('<span class="meta-pill eq">EQ: ' + escapeHtml(meta.recommended_tone) + "</span>");
        }
        if (meta.elapsed_ms) pills.push("<span>Thought for " + escapeHtml(meta.elapsed_ms) + "ms</span>");

        const citationsHtml = Array.isArray(meta.citations) && meta.citations.length > 0
          ? '<ul class="ssra-citation-badges">' + meta.citations.map((c) =>
              '<li class="citation-pill">' + ICONS.bookOpen + " " + escapeHtml(c.section_anchor || c.doc_title || c.id || "Approved source") + (c.snapshot_version ? " (" + escapeHtml(c.snapshot_version) + ")" : "") + "</li>"
            ).join("") + "</ul>"
          : "";

        return '<article class="message-row message-row-assistant">' +
          '<div class="bubble assistant">' +
            (pills.length ? '<div class="turn-meta-bar">' + pills.join("") + "</div>" : "") +
            '<div class="turn-content-text">' + escapeHtml(turn.content) + "</div>" +
            renderGenerativeCard(meta.ui_component, meta.pending_confirmation, meta.thread_id) +
            citationsHtml +
            '<div class="turn-actions">' +
              '<button type="button" class="turn-act-btn" data-speak="' + escapeHtml(turn.content) + '">' + ICONS.speaker + " Listen</button>" +
              '<button type="button" class="turn-act-btn" data-copy="' + escapeHtml(turn.content) + '">' + ICONS.copy + " Copy</button>" +
              '<button type="button" class="turn-act-btn" data-csat="5" data-thread-id="' + escapeHtml(meta.thread_id || state.activeId || "thr_web") + '">' + ICONS.thumbUp + " Helpful</button>" +
              '<button type="button" class="turn-act-btn" data-csat="1" data-thread-id="' + escapeHtml(meta.thread_id || state.activeId || "thr_web") + '">' + ICONS.thumbDown + " Report</button>" +
            "</div>" +
          "</div>" +
        '</article>';
      }

      function renderConvRow(c) {
        const active = c.id === state.activeId ? " active" : "";
        return '<div class="rail-row' + active + '" role="listitem">' +
          '<button type="button" class="rail-item" data-conv-id="' + escapeHtml(c.id) + '" aria-label="Open conversation: ' + escapeHtml(c.title) + '"' + (active ? ' aria-current="true"' : "") + '>' +
            (c.pinned ? ICONS.pin + " " : ICONS.messageSquare + " ") + escapeHtml(c.title) +
          "</button>" +
          '<div class="rail-row-actions">' +
            '<button type="button" class="rail-act-mini" data-pin-conv="' + escapeHtml(c.id) + '" aria-label="' + (c.pinned ? "Unpin" : "Pin") + ' conversation: ' + escapeHtml(c.title) + '" title="' + (c.pinned ? "Unpin" : "Pin") + ' conversation">' + ICONS.pin + "</button>" +
            '<button type="button" class="rail-act-mini" data-rename-conv="' + escapeHtml(c.id) + '" aria-label="Rename conversation: ' + escapeHtml(c.title) + '" title="Rename conversation">' + ICONS.edit + "</button>" +
            '<button type="button" class="rail-act-mini" data-del-conv="' + escapeHtml(c.id) + '" aria-label="Delete conversation: ' + escapeHtml(c.title) + '" title="Delete conversation">' + ICONS.trash + "</button>" +
          "</div>" +
        "</div>";
      }

      function focusRailAction(attribute, conversationId) {
        const buttons = Array.from(convListEl?.querySelectorAll("[" + attribute + "]") || []);
        buttons.find((button) => button.getAttribute(attribute) === conversationId)?.focus();
      }

      function localDayOrdinal(timestamp) {
        const value = Number(timestamp);
        if (!Number.isFinite(value) || value <= 0) return null;
        const parts = new Intl.DateTimeFormat("en-CA", {
          timeZone: "Africa/Juba",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }).formatToParts(new Date(value));
        const part = (type) => parts.find((item) => item.type === type)?.value;
        const year = Number(part("year"));
        const month = Number(part("month"));
        const day = Number(part("day"));
        return Number.isInteger(year) && Number.isInteger(month) && Number.isInteger(day)
          ? Math.floor(Date.UTC(year, month - 1, day) / 86_400_000)
          : null;
      }

      function groupConversationRows(conversations) {
        const today = localDayOrdinal(Date.now());
        const groups = new Map([
          ["Pinned", []],
          ["Today", []],
          ["Yesterday", []],
          ["Previous 7 days", []],
          ["Older", []],
          ["Date unavailable", []],
        ]);
        const sorted = [...conversations].sort((a, b) => {
          const aTime = Number.isFinite(a.updatedAtMs) ? a.updatedAtMs : Number.NEGATIVE_INFINITY;
          const bTime = Number.isFinite(b.updatedAtMs) ? b.updatedAtMs : Number.NEGATIVE_INFINITY;
          return bTime - aTime || String(a.id).localeCompare(String(b.id));
        });
        for (const conversation of sorted) {
          const day = localDayOrdinal(conversation.updatedAtMs);
          const age = day === null || today === null ? null : today - day;
          const label = conversation.pinned
            ? "Pinned"
            : age === null || age < 0
              ? "Date unavailable"
              : age === 0
                ? "Today"
                : age === 1
                  ? "Yesterday"
                  : age <= 7
                    ? "Previous 7 days"
                    : "Older";
          groups.get(label)?.push(conversation);
        }
        return [...groups.entries()].filter(([, rows]) => rows.length > 0);
      }

      function renderApp() {
        const activeConv = state.conversations.find((c) => c.id === state.activeId) || null;
        if (convListEl) {
          if (state.conversations.length === 0) {
            setSafeHtml(
              convListEl,
              '<div class="rail-empty-hint" role="listitem">No saved conversations yet. Start a conversation to keep it on this device.</div>',
            );
          } else {
            const html = groupConversationRows(state.conversations).map(([label, rows]) =>
              '<h2 class="rail-section-label">' + escapeHtml(label) + "</h2>" + rows.map(renderConvRow).join("")
            ).join("");
            setSafeHtml(convListEl, html);
          }
        }
        if (!activeConv || activeConv.turns.length === 0) {
          landingView?.classList.remove("is-hidden");
          chatView?.classList.add("is-hidden");
          if (activeTitleEl) activeTitleEl.textContent = "New Conversation";
        } else {
          landingView?.classList.add("is-hidden");
          chatView?.classList.remove("is-hidden");
          if (activeTitleEl) activeTitleEl.textContent = activeConv.title;
          if (msgList) {
            setSafeHtml(msgList, activeConv.turns.map(renderTurnHtml).join(""));
            msgList.scrollTop = msgList.scrollHeight;
          }
        }
      }

      let activeTurnAbortController = null;

      function cleanTextForSpeech(raw) {
        return String(raw || "")
          .replace(/https?:\\/\\/\\S+/g, "web link")
          .replace(/[*_\\x60#~>-]+/g, " ")
          .replace(/\\s+/g, " ")
          .trim();
      }

      async function sendTurn(text, opts = {}) {
        if (activeTurnAbortController) return;
        const trimmed = String(text || "").trim();
        if (!trimmed) return;

        let conv = state.conversations.find((c) => c.id === state.activeId);
        if (!conv) {
          conv = {
            id: "thr_web_" + Date.now().toString(36),
            title: trimmed.slice(0, 48),
            pinned: false,
            isAuthenticated: false,
            updatedAtMs: Date.now(),
            turns: [],
          };
          state.conversations.unshift(conv);
          state.activeId = conv.id;
        }
        conv.updatedAtMs = Date.now();
        conv.turns.push({ role: "user", content: trimmed });
        conv.turns.push({ role: "assistant", content: "Searching SSRA statutory corpus & verifying numeric provenance..." });
        renderApp();

        const endpoint = "/api/turns";
        const headers = {
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true",
        };
        const payload = {
          message: trimmed,
          thread_id: opts.threadId || conv.id,
          locale: state.locale,
          channel: "web",
          low_data_mode: Boolean(state.lowDataMode),
          auth_level: "ANONYMOUS",
          subject_ref: null,
          confirmation_token: opts.confirmationToken || null,
          idempotency_key: opts.idempotencyKey || null,
        };

        const t0 = performance.now();
        activeTurnAbortController = new AbortController();
        if (submitBtn) {
          submitBtn.type = "button";
          setSafeHtml(submitBtn, ICONS.stop + " Stop");
        }
        try {
          const res = await fetch(endpoint, {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
            signal: activeTurnAbortController.signal,
          });
          const data = await res.json();
          const elapsed = Math.round(performance.now() - t0);
          const replyText = data?.answer?.segments?.map((s) => s.text).join(" ") || data?.detail || JSON.stringify(data);
          conv.turns[conv.turns.length - 1] = {
            role: "assistant",
            content: replyText,
            meta: {
              tier: data?.tier,
              intent: data?.intent?.intent,
              outcome_verified: data?.outcome_verified,
              recommended_tone: data?.affective_state?.recommended_tone,
              ui_component: data?.answer?.ui_component,
              pending_confirmation: data?.pending_confirmation,
              citations: data?.citations || data?.answer?.citations || [],
              thread_id: data?.thread_id || conv.id,
              elapsed_ms: elapsed,
            },
          };
          if (state.autoNarrate && "speechSynthesis" in window) {
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(new SpeechSynthesisUtterance(cleanTextForSpeech(replyText)));
          }
        } catch (err) {
          if (err && err.name === "AbortError") {
            conv.turns[conv.turns.length - 1] = {
              role: "assistant",
              content:
                "[Client request stopped. Server execution status is unknown; please check your status or recent activity before retrying any consequential action.]",
              meta: { tier: "T0", intent: "user_cancelled", outcome_verified: false },
            };
          } else {
            // The server may have received the request before the connection failed.
            const offlineAns = computeOfflineResilienceAnswer(trimmed);
            conv.turns[conv.turns.length - 1] = {
              role: "assistant",
              content: offlineAns.content,
              meta: offlineAns.meta,
            };
            if (input && !input.value.trim()) input.value = trimmed;
            if (hintEl) hintEl.textContent = "Connection interrupted. Draft restored; request completion may be unknown.";
          }
        } finally {
          activeTurnAbortController = null;
          if (submitBtn) {
            submitBtn.type = "submit";
            setSafeHtml(submitBtn, ICONS.send + " Send");
          }
          saveState();
          renderApp();
        }
      }

      submitBtn?.addEventListener("click", (e) => {
        if (activeTurnAbortController) {
          e.preventDefault();
          activeTurnAbortController.abort();
        }
      });

      form?.addEventListener("submit", (e) => {
        e.preventDefault();
        if (activeTurnAbortController) {
          activeTurnAbortController.abort();
          return;
        }
        const val = input.value;
        input.value = "";
        input.rows = 1;
        sendTurn(val);
      });

      input?.addEventListener("input", () => {
        const lines = String(input.value || "").split("\\n").length;
        input.rows = Math.min(5, Math.max(1, lines));
      });

      input?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          form?.requestSubmit();
        }
      });

      document.querySelectorAll(".landing-chip[data-prompt]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const prompt = btn.getAttribute("data-prompt");
          sendTurn(prompt);
        });
      });

      convListEl?.addEventListener("click", (e) => {
        const pinBtn = e.target.closest("[data-pin-conv]");
        if (pinBtn) {
          const cid = pinBtn.getAttribute("data-pin-conv");
          const c = state.conversations.find((x) => x.id === cid);
          if (c) c.pinned = !c.pinned;
          saveState();
          renderApp();
          focusRailAction("data-pin-conv", cid);
          return;
        }
        const renBtn = e.target.closest("[data-rename-conv]");
        if (renBtn) {
          const cid = renBtn.getAttribute("data-rename-conv");
          const c = state.conversations.find((x) => x.id === cid);
          if (c) {
            const nextTitle = window.prompt("Rename conversation:", c.title);
            if (nextTitle && nextTitle.trim()) {
              c.title = nextTitle.trim().slice(0, 64);
              saveState();
              renderApp();
              focusRailAction("data-rename-conv", cid);
            }
          }
          return;
        }
        const delBtn = e.target.closest("[data-del-conv]");
        if (delBtn) {
          const cid = delBtn.getAttribute("data-del-conv");
          if (!window.confirm("Delete this saved conversation from this device? This cannot be undone.")) return;
          state.conversations = state.conversations.filter((x) => x.id !== cid);
          if (state.activeId === cid) state.activeId = state.conversations[0]?.id || null;
          saveState();
          renderApp();
          const nextConversation = convListEl?.querySelector(".rail-item");
          if (nextConversation) nextConversation.focus();
          else document.getElementById("new-chat-btn")?.focus();
          return;
        }
        const btn = e.target.closest("[data-conv-id]");
        if (btn) {
          state.activeId = btn.getAttribute("data-conv-id");
          saveState();
          renderApp();
          if (window.matchMedia?.("(max-width: 960px)")?.matches) {
            shell?.setAttribute("data-mobile-rail", "closed");
            syncMobileRailA11y(false);
          }
          input?.focus();
        }
      });

      msgList?.addEventListener("click", (e) => {
        const confirmBtn = e.target.closest("[data-confirm-token]");
        if (confirmBtn) {
          const token = confirmBtn.getAttribute("data-confirm-token");
          const idem = confirmBtn.getAttribute("data-idem-key");
          const tid = confirmBtn.getAttribute("data-thread-id");
          sendTurn("Confirm action execution", {
            confirmationToken: token,
            idempotencyKey: idem,
            threadId: tid,
          });
          return;
        }
        const speakBtn = e.target.closest("[data-speak]");
        if (speakBtn && "speechSynthesis" in window) {
          if (window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
            setSafeHtml(speakBtn, ICONS.speaker + " Listen");
            return;
          }
          const u = new SpeechSynthesisUtterance(cleanTextForSpeech(speakBtn.getAttribute("data-speak") || ""));
          u.onend = () => { setSafeHtml(speakBtn, ICONS.speaker + " Listen"); };
          setSafeHtml(speakBtn, ICONS.stop + " Stop Audio");
          window.speechSynthesis.speak(u);
          return;
        }
        const copyBtn = e.target.closest("[data-copy]");
        if (copyBtn && navigator.clipboard) {
          navigator.clipboard.writeText(copyBtn.getAttribute("data-copy") || "");
          setSafeHtml(copyBtn, ICONS.check + " Copied");
          return;
        }
        const csatBtn = e.target.closest("[data-csat]");
        if (csatBtn) {
          const csatScore = Number(csatBtn.getAttribute("data-csat")) || 5;
          const convId = csatBtn.getAttribute("data-thread-id") || state.activeId || "thr_web";
          const reason = csatScore >= 4 ? "ACCURATE" : "MISSING_INFO";
          csatBtn.disabled = true;
          fetch("/v1/analytics/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
            body: JSON.stringify({
              conversation_id: convId,
              csat: csatScore,
              reason,
              locale: state.locale || "en",
            }),
          })
            .then((res) => {
              setSafeHtml(
                csatBtn,
                res.ok
                  ? csatScore >= 4
                    ? ICONS.check + " Helpful"
                    : ICONS.check + " Flagged for Audit"
                  : ICONS.alertTriangle + " Retry",
              );
            })
            .catch(() => {
              setSafeHtml(csatBtn, ICONS.alertTriangle + " Retry");
            })
            .finally(() => {
              csatBtn.disabled = false;
            });
        }
      });

      document.getElementById("new-chat-btn")?.addEventListener("click", () => {
        state.activeId = null;
        saveState();
        renderApp();
        if (window.matchMedia?.("(max-width: 960px)")?.matches) {
          shell?.setAttribute("data-mobile-rail", "closed");
          syncMobileRailA11y(false);
        }
        input?.focus();
      });

      document.getElementById("clear-chat-btn")?.addEventListener("click", () => {
        if (!window.confirm("Delete all saved conversations from this device? This cannot be undone.")) return;
        state.conversations = [];
        state.activeId = null;
        dispatchSwLogoutPurge();
        saveState();
        renderApp();
        input?.focus();
      });

      const railAsideEl = document.querySelector(".rail-wrap");
      const syncMobileRailA11y = (moveFocus = false) => {
        const isMobileViewport = window.matchMedia?.("(max-width: 960px)")?.matches ?? false;
        if (!isMobileViewport) shell?.setAttribute("data-mobile-rail", "closed");
        const isMobOpen = shell?.getAttribute("data-mobile-rail") === "open";
        const isDesktopCollapsed = shell?.getAttribute("data-sidebar") === "collapsed";
        const isHidden = isMobileViewport ? !isMobOpen : isDesktopCollapsed;
        if (railAsideEl) {
          railAsideEl.toggleAttribute("inert", Boolean(isHidden));
        }
        document.querySelector(".app-main-col")?.toggleAttribute("inert", Boolean(isMobileViewport && isMobOpen));
        const headerRailBtn = document.getElementById("header-rail-btn");
        headerRailBtn?.setAttribute("aria-expanded", String(!isHidden));
        headerRailBtn?.setAttribute("aria-label", isHidden ? "Open conversations" : "Close conversations");
        document.getElementById("rail-collapse-btn")?.setAttribute(
          "aria-label",
          isMobileViewport ? "Close conversations sidebar" : "Collapse conversations sidebar",
        );
        if (moveFocus && isHidden) {
          headerRailBtn?.focus();
        } else if (moveFocus && !isHidden) {
          document.getElementById("new-chat-btn")?.focus();
        }
      };
      const toggleSidebar = () => {
        const isMobileViewport = window.matchMedia?.("(max-width: 960px)")?.matches ?? false;
        if (isMobileViewport) {
          const mob = shell?.getAttribute("data-mobile-rail");
          shell?.setAttribute("data-mobile-rail", mob === "open" ? "closed" : "open");
        } else {
          const cur = shell?.getAttribute("data-sidebar");
          shell?.setAttribute("data-sidebar", cur === "collapsed" ? "open" : "collapsed");
        }
        syncMobileRailA11y(true);
      };
      document.getElementById("rail-collapse-btn")?.addEventListener("click", toggleSidebar);
      document.getElementById("header-rail-btn")?.addEventListener("click", toggleSidebar);
      document.getElementById("rail-mobile-backdrop")?.addEventListener("click", () => {
        shell?.setAttribute("data-mobile-rail", "closed");
        syncMobileRailA11y(true);
      });
      window.addEventListener("resize", () => syncMobileRailA11y(false));
      syncMobileRailA11y(false);

      document.getElementById("theme-toggle-btn")?.addEventListener("click", () => {
        const next = state.theme === "dark" ? "light" : state.theme === "light" ? "high-contrast" : "dark";
        applyTheme(next);
      });

      localeSelect?.addEventListener("change", () => {
        applyLocaleStrings(localeSelect.value);
        saveState();
      });

      // Online / Offline Network Indicator (FE-G4)
      function syncNetworkStatusBadge() {
        const txt = document.getElementById("net-status-text");
        const badge = document.getElementById("net-status-badge");
        if (!txt || !badge) return;
        const offline = navigator.onLine === false;
        const lowData = !offline && state.lowDataMode;
        badge.setAttribute("data-connection", offline ? "offline" : lowData ? "low-data" : "available");
        txt.textContent = offline
          ? "Offline · reconnect to get current guidance"
          : lowData
            ? "Low-data mode · network available"
            : "Network available · citations shown with answers";
      }
      window.addEventListener("online", syncNetworkStatusBadge);
      window.addEventListener("offline", syncNetworkStatusBadge);
      syncNetworkStatusBadge();

      // AccountRail Popover
      acctTrigger?.addEventListener("click", (e) => {
        e.stopPropagation();
        const open = acctPopover?.classList.toggle("open");
        acctTrigger.setAttribute("aria-expanded", String(Boolean(open)));
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".rail-footer")) {
          acctPopover?.classList.remove("open");
          acctTrigger?.setAttribute("aria-expanded", "false");
        }
      });
      // Modal focus restoration (FE-G6)
      let modalReturnFocusEl = null;
      function closeAllModals() {
        document.getElementById("search-modal-backdrop")?.classList.remove("open");
        document.getElementById("settings-modal-backdrop")?.classList.remove("open");
        document.getElementById("call-modal-backdrop")?.classList.remove("open");
        if (modalReturnFocusEl && typeof modalReturnFocusEl.focus === "function") {
          modalReturnFocusEl.focus();
          modalReturnFocusEl = null;
        }
      }

      // ConversationSearch Modal (Ctrl+K)
      const searchBackdrop = document.getElementById("search-modal-backdrop");
      const searchInput = document.getElementById("conv-search-input");
      const searchResults = document.getElementById("conv-search-results");
      function renderSearchModalList() {
        const q = (searchInput?.value || "").trim().toLocaleLowerCase();
        const matches = state.conversations.filter((c) => !q || c.title.toLocaleLowerCase().includes(q));
        let html = matches.map((c) =>
          '<button type="button" class="acct-pop-item" data-jump-conv="' + escapeHtml(c.id) + '"><span>' + ICONS.messageSquare + " " + escapeHtml(c.title) + '</span><span class="jump-open-tag">Open</span></button>'
        ).join("");
        if (!matches.length && q) {
          html = '<p class="rail-empty-hint" role="status">No saved conversations match this search.</p>';
        } else if (!matches.length) {
          html = '<p class="rail-empty-hint" role="status">No saved conversations yet.</p>';
        }
        setSafeHtml(searchResults, html);
      }
      function openSearchModal() {
        modalReturnFocusEl = document.activeElement;
        searchBackdrop?.classList.add("open");
        if (searchInput) {
          searchInput.value = "";
          renderSearchModalList();
          searchInput.focus();
        }
      }
      document.getElementById("rail-search-btn")?.addEventListener("click", openSearchModal);
      searchBackdrop?.addEventListener("click", (e) => {
        if (e.target === searchBackdrop) closeAllModals();
      });
      searchInput?.addEventListener("input", renderSearchModalList);
      searchResults?.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-jump-conv]");
        if (btn) {
          state.activeId = btn.getAttribute("data-jump-conv");
          closeAllModals();
          renderApp();
          if (window.matchMedia?.("(max-width: 960px)")?.matches) {
            shell?.setAttribute("data-mobile-rail", "closed");
            syncMobileRailA11y(false);
          }
          input?.focus();
          input?.focus();
        }
      });

      // FE-G6: Interactive 5-Tab SettingsDialog Modal
      const settingsBackdrop = document.getElementById("settings-modal-backdrop");
      const settingsTitleEl = document.getElementById("settings-pane-title");
      const settingsBodyEl = document.getElementById("settings-pane-body");

      function renderSettingsTabContent(tabId) {
        state.settingsTab = tabId || "general";
        document.querySelectorAll("[data-settings-tab]").forEach((btn) => {
          const isAct = btn.getAttribute("data-settings-tab") === state.settingsTab;
          btn.classList.toggle("active", isAct);
          btn.setAttribute("aria-selected", String(isAct));
        });
        if (state.settingsTab === "voice") {
          if (settingsTitleEl) settingsTitleEl.textContent = "Voice typing & reading";
          setSafeHtml(
            settingsBodyEl,
            "<p>Voice typing uses your browser's speech recognition when available and currently supports English and Arabic only. Your browser may process audio outside SSRA. Auto-narration uses browser speech synthesis; available voices vary by device.</p>" +
            '<div class="settings-actions-row">' +
              '<button type="button" class="icon-btn" id="toggle-narrate-btn">' + (state.autoNarrate ? ICONS.speaker + " Auto-Narrate Replies: ON" : ICONS.speakerOff + " Auto-Narrate Replies: OFF") + "</button>" +
            "</div>"
          );
        } else if (state.settingsTab === "profile") {
          if (settingsTitleEl) settingsTitleEl.textContent = "Personal e-Tax services";
          setSafeHtml(
            settingsBodyEl,
            "<p>This public chat does not show personal balances, filing records, or taxpayer identity details.</p>" +
            '<p><a href="https://etax.nra.gov.ss/" rel="noopener noreferrer">Sign in through the official e-Tax portal</a> for personal services.</p>'
          );
        } else if (state.settingsTab === "privacy") {
          if (settingsTitleEl) settingsTitleEl.textContent = "Privacy, Shared-Device Hygiene & Right to Erasure";
          setSafeHtml(
            settingsBodyEl,
            "<p><strong>Shared-Device Protection:</strong> Only anonymous <code>T0</code> public turns are saved locally; <code>T1</code>/<code>T2</code> turns and TINs are scrubbed automatically.</p>" +
            '<div class="settings-actions-row">' +
              '<button type="button" id="purge-local-btn" class="icon-btn danger-text-btn">' + ICONS.trash + " Clear saved conversations on this device</button>" +
            "</div>"
          );
        } else {
          if (settingsTitleEl) settingsTitleEl.textContent = "General, Theme & 2G Low-Data Mode";
          setSafeHtml(
            settingsBodyEl,
            "<p><strong>Republic of South Sudan Civic Palette:</strong> Nile Dusk (Dark), Savanna Cotton Paper (Light), and WCAG AAA High Contrast.</p>" +
            '<div class="settings-actions-row">' +
              '<button type="button" class="icon-btn" id="toggle-lowdata-btn">' + ICONS.wifi + (state.lowDataMode ? " 2G Low-Data Mode: ON" : " 2G Low-Data Mode: OFF") + "</button>" +
            "</div>"
          );
        }
      }

      document.getElementById("open-settings-btn")?.addEventListener("click", () => {
        modalReturnFocusEl = acctTrigger;
        acctPopover?.classList.remove("open");
        renderSettingsTabContent("general");
        settingsBackdrop?.classList.add("open");
        settingsBackdrop?.querySelector('[data-settings-tab][aria-selected="true"]')?.focus();
      });
      document.getElementById("close-settings-btn")?.addEventListener("click", closeAllModals);
      settingsBackdrop?.addEventListener("click", (e) => {
        if (e.target === settingsBackdrop) {
          closeAllModals();
          return;
        }
        const tabBtn = e.target.closest("[data-settings-tab]");
        if (tabBtn) {
          renderSettingsTabContent(tabBtn.getAttribute("data-settings-tab"));
          return;
        }
        if (e.target.closest("#toggle-lowdata-btn")) {
          state.lowDataMode = !state.lowDataMode;
          saveState();
          syncNetworkStatusBadge();
          renderSettingsTabContent("general");
          return;
        }
        if (e.target.closest("#toggle-narrate-btn")) {
          state.autoNarrate = !state.autoNarrate;
          saveState();
          renderSettingsTabContent("voice");
          return;
        }
        if (e.target.closest("#purge-local-btn")) {
          state.conversations = [];
          state.activeId = null;
          dispatchSwLogoutPurge();
          saveState();
          renderApp();
          closeAllModals();
        }
      });

      function trapModalTabFocus(e, containerEl) {
        if (!containerEl || e.key !== "Tab") return;
        const focusables = Array.from(
          containerEl.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }

      window.addEventListener("keydown", (e) => {
        const openModals = document.querySelectorAll(".modal-backdrop.open");
        const openModal = openModals.length > 0 ? openModals[openModals.length - 1] : null;
        if (openModal && e.key === "Tab") {
          trapModalTabFocus(e, openModal);
          return;
        }
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          if (searchBackdrop?.classList.contains("open")) closeAllModals();
          else openSearchModal();
        } else if (e.key === "Escape") {
          if (openModal) {
            closeAllModals();
          } else if (shell?.getAttribute("data-mobile-rail") === "open") {
            shell.setAttribute("data-mobile-rail", "closed");
            syncMobileRailA11y(true);
          }
        }
      });

      // Voice Dictation (Web Speech API)
      document.getElementById("voice-dictate-btn")?.addEventListener("click", () => {
        const speechLocale = state.locale === "ar" ? "ar-SS" : state.locale === "en" ? "en-US" : null;
        if (!speechLocale) {
          if (hintEl) hintEl.textContent = "Voice typing is unavailable for this selected language. Type your question instead.";
          return;
        }
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
          if (hintEl) hintEl.textContent = "Voice typing is unavailable in this browser. Type your question instead.";
          modalReturnFocusEl = document.getElementById("voice-dictate-btn");
          document.getElementById("call-modal-backdrop")?.classList.add("open");
          document.getElementById("close-call-btn")?.focus();
          return;
        }
        const rec = new SR();
        rec.lang = speechLocale;
        if (hintEl) hintEl.textContent = "Listening... speak your tax question";
        rec.onresult = (ev) => {
          const transcript = ev.results?.[0]?.[0]?.transcript || "";
          if (transcript && input) {
            input.value = (input.value ? input.value + " " : "") + transcript;
          }
          if (hintEl) hintEl.textContent = "Enter to send · Shift+Enter for newline · Ctrl+K search";
        };
        rec.onerror = () => {
          if (hintEl) hintEl.textContent = "Enter to send · Shift+Enter for newline · Ctrl+K search";
        };
        rec.start();
      });

      // AI Call Receptionist Modal
      const callBackdrop = document.getElementById("call-modal-backdrop");
      document.getElementById("open-call-btn")?.addEventListener("click", (e) => {
        modalReturnFocusEl = e.currentTarget;
        callBackdrop?.classList.add("open");
        document.getElementById("close-call-btn")?.focus();
      });
      document.getElementById("close-call-btn")?.addEventListener("click", closeAllModals);
      document.querySelectorAll(".call-sample-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const q = btn.getAttribute("data-voice-q");
          closeAllModals();
          sendTurn(q);
        });
      });

    })();
  </script>
</body>
</html>`;
  return compactHtmlAssetBlocks(rawHtml);
}

async function readRequestBody(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > 1_048_576) {
      throw new Error("PAYLOAD_TOO_LARGE");
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8");
}

function sanitizeBrowserTurnBody(rawBodyStr) {
  const parsed = JSON.parse(rawBodyStr);
  return JSON.stringify({
    message: typeof parsed.message === "string" ? parsed.message : "",
    locale: typeof parsed.locale === "string" ? parsed.locale : "en",
    channel: "web",
    thread_id: typeof parsed.thread_id === "string" ? parsed.thread_id : null,
    low_data_mode: Boolean(parsed.low_data_mode),
    auth_level: "ANONYMOUS",
    subject_ref: null,
  });
}

const server = http.createServer(async (req, res) => {
  const nonce = crypto.randomBytes(16).toString("base64");
  const secHeaders = buildSecurityHeaders(nonce);
  const method = String(req.method ?? "GET").toUpperCase();
  if (!ALLOWED_METHODS.has(method)) {
    res.writeHead(405, {
      "Content-Type": "application/json",
      Allow: "GET, HEAD, POST, DELETE, OPTIONS",
      ...secHeaders,
    });
    res.end(JSON.stringify({ error: "METHOD_NOT_ALLOWED" }));
    return;
  }

  const hostHeader = String(req.headers.host ?? "localhost");
  if (!VALID_HOST_RE.test(hostHeader)) {
    res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "INVALID_HOST_HEADER" }));
    return;
  }

  let pathname = "/";
  try {
    const rawTarget = req.url ?? "/";
    const lowerTarget = rawTarget.toLowerCase();
    if (
      !rawTarget.startsWith("/") ||
      rawTarget.includes("..") ||
      lowerTarget.includes("%2e") ||
      lowerTarget.includes("%2f") ||
      lowerTarget.includes("%5c")
    ) {
      throw new Error("INVALID_TARGET");
    }
    const decodedPath = decodeURIComponent(new URL(rawTarget, "http://127.0.0.1").pathname);
    pathname = path.posix.normalize(decodedPath);
    if (!pathname.startsWith("/") || pathname.includes("..")) {
      throw new Error("INVALID_TARGET");
    }
  } catch {
    res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "INVALID_REQUEST_TARGET" }));
    return;
  }

  const isGetOrHead = method === "GET" || method === "HEAD";
  const traceparent = createTraceparent(req.headers.traceparent);

  if (isGetOrHead && pathname === "/robots.txt") {
    res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8", ...secHeaders });
    res.end("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /v1/\n");
    return;
  }

  if (isGetOrHead && (pathname === "/healthz" || pathname === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json", ...secHeaders });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "ssra-web",
        internal_api_url: INTERNAL_API_URL,
        internal_runtime_url: INTERNAL_RUNTIME_URL,
      }),
    );
    return;
  }

  if (isGetOrHead && pathname === "/manifest.webmanifest") {
    res.writeHead(200, { "Content-Type": "application/manifest+json", ...secHeaders });
    res.end(
      JSON.stringify({
        name: "SSRA Assist — South Sudan Revenue Authority",
        short_name: "SSRA Assist",
        start_url: "/en",
        display: "standalone",
        background_color: "#091310",
        theme_color: "#078930",
      }),
    );
    return;
  }

  if (/^\/(?:admin|agent|calls|analytics|queue|auditor|ops)(?:\/|$)/.test(pathname)) {
    res.writeHead(404, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      ...secHeaders,
    });
    res.end(JSON.stringify({ error: "NOT_FOUND" }));
    return;
  }

  if (isGetOrHead && pathname === "/sw.js") {
    const swPath = path.join(__dirname, "public", "sw.js");
    const swContent = fs.existsSync(swPath)
      ? fs.readFileSync(swPath, "utf-8")
      : "self.addEventListener('install', () => self.skipWaiting());";
    res.writeHead(200, {
      "Content-Type": "application/javascript; charset=utf-8",
      "Clear-Site-Data": '"cache"',
      ...secHeaders,
    });
    res.end(swContent);
    return;
  }

  if (isGetOrHead && pathname === "/api/status") {
    try {
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/admin/public-status`, {
        headers: { Accept: "application/json", traceparent },
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "degraded", service: "ssra-web" }));
    }
    return;
  }

  if (pathname === "/api/scorecard") {
    res.writeHead(403, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "STAFF_CONSOLE_REQUIRED" }));
    return;
  }

  if (pathname === "/api/flags" || pathname === "/api/kill-switches") {
    res.writeHead(403, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "STAFF_CONSOLE_REQUIRED" }));
    return;
  }

  if (method === "POST" && pathname === "/api/auth/backchannel-logout") {
    try {
      const rawBody = await readRequestBody(req);
      const tokenParam = rawBody.startsWith("{")
        ? String(JSON.parse(rawBody).logout_token ?? "")
        : String(new URLSearchParams(rawBody).get("logout_token") ?? "");
      const parts = tokenParam.trim().split(".");
      if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) {
        res.writeHead(400, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
          ...secHeaders,
        });
        res.end(JSON.stringify({ error: "UNSIGNED_OR_MALFORMED_LOGOUT_JWT" }));
        return;
      }
      const hdr = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf-8"));
      const pld = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"));
      const verifyKey = process.env.KEYCLOAK_LOGOUT_VERIFY_KEY ?? "";
      const expectedSig = verifyKey
        ? crypto.createHmac("sha256", verifyKey).update(`${parts[0]}.${parts[1]}`).digest()
        : Buffer.alloc(0);
      const actualSig = Buffer.from(parts[2], "base64url");
      const sigOk =
        Boolean(verifyKey) &&
        expectedSig.length === actualSig.length &&
        crypto.timingSafeEqual(expectedSig, actualSig);
      const nowSec = Math.floor(Date.now() / 1000);
      if (
        !sigOk ||
        !["ES256", "RS256", "PS256", "EdDSA"].includes(hdr?.alg) ||
        pld?.iss !== "https://sso.ssra.gov.ss/realms/ssra" ||
        pld?.aud !== "ssra-web-bff" ||
        pld?.nonce !== undefined ||
        typeof pld?.jti !== "string" ||
        typeof pld?.iat !== "number" ||
        typeof pld?.exp !== "number" ||
        nowSec > pld.exp ||
        Math.abs(nowSec - pld.iat) > 120 ||
        !pld?.events?.["http://schemas.openid.net/event/backchannel-logout"] ||
        (!pld?.sid && !pld?.sub)
      ) {
        res.writeHead(400, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
          ...secHeaders,
        });
        res.end(JSON.stringify({ error: "INVALID_BACKCHANNEL_LOGOUT_CLAIMS" }));
        return;
      }
      res.writeHead(200, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "Clear-Site-Data": '"cache", "cookies", "storage"',
        ...secHeaders,
      });
      res.end(JSON.stringify({ status: "logged_out", client_id: "ssra-web-bff" }));
    } catch {
      res.writeHead(400, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        ...secHeaders,
      });
      res.end(JSON.stringify({ error: "INVALID_BACKCHANNEL_LOGOUT_REQUEST" }));
    }
    return;
  }

  if (method === "POST" && pathname === "/api/turns") {
    try {
      const safeBody = sanitizeBrowserTurnBody(await readRequestBody(req));
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/turns`, {
        method: "POST",
        headers: { "Content-Type": "application/json", traceparent },
        body: safeBody,
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        ...secHeaders,
      });
      res.end(text);
    } catch (err) {
      const code =
        err instanceof Error && err.message === "PAYLOAD_TOO_LARGE"
          ? 413
          : err instanceof SyntaxError
            ? 400
            : 502;
      res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: "BFF_TURN_PROXY_ERROR" }));
    }
    return;
  }

  if (method === "POST" && pathname === "/api/chat/stream") {
    const ac = new AbortController();
    res.on("close", () => {
      if (!res.writableEnded) {
        ac.abort();
      }
    });
    try {
      const safeBody = sanitizeBrowserTurnBody(await readRequestBody(req));
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/agui/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream", traceparent },
        body: safeBody,
        signal: ac.signal,
      });
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "text/event-stream",
        "X-Accel-Buffering": "no",
        ...secHeaders,
      });
      if (upstream.body) {
        for await (const chunk of upstream.body) {
          if (res.destroyed) {
            break;
          }
          res.write(chunk);
        }
      }
      res.end();
    } catch (err) {
      if (!res.headersSent) {
        const code =
          err instanceof Error && err.message === "PAYLOAD_TOO_LARGE"
            ? 413
            : err instanceof SyntaxError
              ? 400
              : 502;
        res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
        res.end(JSON.stringify({ error: "BFF_STREAM_PROXY_ERROR" }));
      } else {
        res.end();
      }
    }
    return;
  }

  if (pathname.startsWith("/v1/")) {
    // The public browser may submit feedback only. Chat requests go through the
    // subject-stripping /api/turns BFF; other runtime and staff paths are private.
    if (pathname !== "/v1/analytics/feedback" || method !== "POST") {
      res.writeHead(403, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        ...secHeaders,
      });
      res.end(JSON.stringify({ error: "PUBLIC_BFF_ROUTE_NOT_ALLOWED" }));
      return;
    }
    const upstreamBase = INTERNAL_API_URL;
    try {
      const hasBody = method === "POST";
      const bodyStr = hasBody ? await readRequestBody(req) : undefined;
      const fwdHeaders = { Accept: req.headers.accept ?? "application/json", traceparent };
      if (hasBody) {
        fwdHeaders["Content-Type"] = "application/json";
      }
      for (const hName of ["last-event-id", "idempotency-key"]) {
        if (req.headers[hName]) {
          const rawVal = String(req.headers[hName]).trim();
          if (!VALID_OPAQUE_HEADER_RE.test(rawVal)) {
            res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
            res.end(JSON.stringify({ error: "INVALID_HEADER_VALUE" }));
            return;
          }
          fwdHeaders[hName] = rawVal;
        }
      }
      const upstream = await fetch(`${upstreamBase}${pathname}`, {
        method,
        headers: fwdHeaders,
        body: bodyStr,
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        ...secHeaders,
      });
      res.end(text);
    } catch (err) {
      const code = err instanceof Error && err.message === "PAYLOAD_TOO_LARGE" ? 413 : 502;
      res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: "UPSTREAM_V1_PROXY_ERROR" }));
    }
    return;
  }

  const seg = pathname.split("/").filter(Boolean)[0] ?? "";
  const locale = SUPPORTED_LOCALES.has(seg)
    ? seg
    : negotiateAcceptLanguage(req.headers["accept-language"]);
  sendBodyWithCompression(
    req,
    res,
    200,
    { "Content-Type": "text/html; charset=utf-8", ...secHeaders },
    renderPwaShellHtml(locale, nonce),
  );
});

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-web listening on http://${HOSTNAME}:${PORT}\n`);
});
