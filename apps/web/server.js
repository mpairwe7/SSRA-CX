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
 *   `CitationList`, `ConfirmActionSheet`, `HandoffCard`) + reviewed UI strings for `en`, `pga`, and `ar` (RTL); the other
 *   roadmap locales (`din`, `nus`, `bfa`, `zne`, `shk`) show English with a notice until reviewed (OQ-008)
 */

import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";
import { ICONS } from "../../packages/ui/icons.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FONTS_DIR = path.resolve(__dirname, "../../packages/ui/fonts");
const ALLOWED_FONT_FILES = new Set([
  "IBMPlexSans-Regular.woff2",
  "IBMPlexSans-Medium.woff2",
  "IBMPlexSans-SemiBold.woff2",
  "IBMPlexMono-Light.woff2",
  "IBMPlexMono-Regular.woff2",
]);
const FONT_CACHE = new Map();
for (const fontName of ALLOWED_FONT_FILES) {
  const fontPath = path.join(FONTS_DIR, fontName);
  if (fs.existsSync(fontPath)) {
    const buffer = fs.readFileSync(fontPath);
    const etag = `"${crypto.createHash("sha256").update(buffer).digest("hex").slice(0, 32)}"`;
    FONT_CACHE.set(fontName, { buffer, etag, byteLength: String(buffer.byteLength) });
  }
}
const SW_PATH = path.join(__dirname, "public", "sw.js");
const SW_CONTENT = fs.existsSync(SW_PATH)
  ? fs.readFileSync(SW_PATH, "utf-8")
  : "self.addEventListener('install', () => self.skipWaiting());";
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
// Interface text exists only for the Phase 1 locales. Other locales show English until a
// qualified reviewer approves their strings (OQ-008), so the page language stays accurate.
const REVIEWED_UI_LOCALES = new Set(["en", "pga", "ar"]);
const VALID_HOST_RE = /^[A-Za-z0-9.[\]:-]+$/;
const VALID_OPAQUE_HEADER_RE = /^[\x21-\x7e]{1,128}$/;
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "DELETE", "OPTIONS"]);
// Mirrors the runtime's thread-id rule so malformed ids fail here with a 400.
const SAFE_THREAD_ID_RE = /^[A-Za-z0-9_:-]{1,128}$/;

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
    "Content-Security-Policy": `default-src 'self'; script-src 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; font-src 'self' data:; connect-src 'self'; img-src 'self' data:; worker-src 'self'; manifest-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; require-trusted-types-for 'script'; trusted-types ssra-web-html ssra-web-script-url`,
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
  const isHead = String(req.method ?? "GET").toUpperCase() === "HEAD";
  const acceptEnc = String(req.headers["accept-encoding"] ?? "");
  const buf = Buffer.from(bodyStr, "utf-8");
  if (buf.length > 512 && acceptsEncoding(acceptEnc, "br")) {
    const compressed = zlib.brotliCompressSync(buf, {
      // Quality 5 measured 6.8% smaller than quality 4 on this page for about 0.5 ms more CPU;
      // quality 4 was larger than gzip level 6.
      params: {
        [zlib.constants.BROTLI_PARAM_QUALITY]: 5,
        [zlib.constants.BROTLI_PARAM_SIZE_HINT]: buf.length,
      },
    });
    res.writeHead(statusCode, {
      ...headers,
      "Content-Encoding": "br",
      "Content-Length": String(compressed.byteLength),
      Vary: "Accept-Encoding",
    });
    res.end(isHead ? undefined : compressed);
    return;
  }
  if (buf.length > 512 && acceptsEncoding(acceptEnc, "gzip")) {
    const compressed = zlib.gzipSync(buf, { level: 6 });
    res.writeHead(statusCode, {
      ...headers,
      "Content-Encoding": "gzip",
      "Content-Length": String(compressed.byteLength),
      Vary: "Accept-Encoding",
    });
    res.end(isHead ? undefined : compressed);
    return;
  }
  res.writeHead(statusCode, {
    ...headers,
    "Content-Length": String(buf.byteLength),
  });
  res.end(isHead ? undefined : buf);
}

function renderPwaShellHtml(locale, nonce) {
  const uiLocale = REVIEWED_UI_LOCALES.has(locale) ? locale : "en";
  const dir = uiLocale === "ar" ? "rtl" : "ltr";
  const rawHtml = `<!DOCTYPE html>
<html lang="${uiLocale}" dir="${dir}" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content" />
  <meta name="theme-color" content="#091310" media="(prefers-color-scheme: dark)" />
  <meta name="theme-color" content="#F6F7F2" media="(prefers-color-scheme: light)" />
  <meta name="description" content="Official South Sudan Revenue Authority (SSRA / NRA) grounded AI tax assistant for TIN registration, PAYE, Withholding Tax, TCC, and customs guidance." />
  <title>SSRA Assist — South Sudan Revenue Authority Official AI Assistant</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <style nonce="${nonce}">
    @font-face {
      font-family: "IBM Plex Sans";
      src: url("/fonts/IBMPlexSans-Regular.woff2") format("woff2");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "IBM Plex Sans";
      src: url("/fonts/IBMPlexSans-Medium.woff2") format("woff2");
      font-weight: 500;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "IBM Plex Sans";
      src: url("/fonts/IBMPlexSans-SemiBold.woff2") format("woff2");
      font-weight: 600;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "IBM Plex Mono";
      src: url("/fonts/IBMPlexMono-Light.woff2") format("woff2");
      font-weight: 300;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "IBM Plex Mono";
      src: url("/fonts/IBMPlexMono-Regular.woff2") format("woff2");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }
    :root {
      color-scheme: dark;
      --font-geist-sans: "Aptos", "Avenir Next", "Trebuchet MS", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, system-ui, sans-serif;
      --font-geist-mono: "IBM Plex Mono", "Cascadia Code", "SFMono-Regular", "Fira Code", monospace;
      --font-sans: var(--font-geist-sans);
      --font-mono: var(--font-geist-mono);
      --bg-0: #091310;
      --bg-1: #0E1C17;
      --bg-2: #142720;
      --surface-1: rgba(236, 245, 238, 0.04);
      --surface-2: rgba(236, 245, 238, 0.07);
      --surface-3: rgba(236, 245, 238, 0.11);
      --surface-4: rgba(236, 245, 238, 0.15);
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
      --cv2-rail: 300px;
      --cv2-top-h: calc(60px + env(safe-area-inset-top, 0px));
      --cv2-spring: cubic-bezier(0.34, 1.35, 0.64, 1);
      --cv2-tap: 140ms;
      --cv2-accent: #078930;
      --cv2-accent-contrast: #FFFFFF;
      --cv2-accent-hover: #056A24;
      --cv2-accent-soft: rgba(7, 137, 48, 0.18);
      --cv2-user-bubble: rgba(7, 137, 48, 0.20);
      --cv2-user-bubble-border: rgba(244, 196, 48, 0.35);
      --cv2-focus: #F4C430;
      --success: #34d399;
      --warning: #fbbf24;
      --danger: #fb7185;
      --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.35);
      --shadow-md: 0 12px 32px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.04);
      --shadow-lg: 0 24px 60px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.06);
      --radius-xs: 6px;
      --radius-sm: 10px;
      --radius-md: 14px;
      --radius-lg: 18px;
      --radius-xl: 24px;
      --radius-2xl: 32px;
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
      --surface-4: rgba(12, 28, 20, 0.13);
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
      --cv2-accent: #07792B;
      --cv2-accent-contrast: #FFFFFF;
      --cv2-accent-hover: #055E21;
      --cv2-accent-soft: rgba(7, 137, 48, 0.10);
      --cv2-user-bubble: #EAF4EC;
      --cv2-user-bubble-border: rgba(7, 137, 48, 0.28);
      --cv2-focus: #704B00;
      --success: #066926;
      --warning: #853A06;
      --danger: #B91C1C;
      --grad-user: linear-gradient(135deg, rgba(7, 137, 48, 0.14), rgba(212, 155, 11, 0.12));
      --shadow-sm: 0 1px 2px rgba(12, 28, 20, 0.08), 0 2px 6px rgba(12, 28, 20, 0.05);
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
      --surface-4: #2E2E2E;
      --surface-ink: #000000;
      --border-1: #FFFFFF;
      --border-2: #FFD60A;
      --text-0: #FFFFFF;
      --text-1: #FFFFFF;
      --text-2: #E5E7EB;
      --cv2-user-bubble: #111111;
      --cv2-user-bubble-border: #FFD60A;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; height: 100%; min-height: 100dvh;
      font-family: var(--font-sans); font-feature-settings: "cv11", "ss01";
      -webkit-text-size-adjust: 100%; text-size-adjust: 100%;
      background: var(--bg-0); color: var(--text-1); overflow: hidden;
    }
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

    /* App Shell Grid & Hover-Peek (chatv2/shell.css pattern) */
    .app-shell { display: grid; grid-template-columns: var(--cv2-rail, 300px) minmax(0, 1fr); height: 100dvh; width: 100%; transition: grid-template-columns 0.22s cubic-bezier(0.22, 1, 0.36, 1); }
    .rail-hotzone { display: none; }
    @media (min-width: 961px) {
      .app-shell[data-sidebar="collapsed"] { --cv2-rail: 0px; grid-template-columns: 0px minmax(0, 1fr); }
      .app-shell[data-sidebar="collapsed"]:not([data-rail-peek="true"]) .rail-wrap { visibility: hidden; pointer-events: none; border-inline-end-width: 0; }
    }
    @media (min-width: 961px) and (hover: hover) {
      .app-shell[data-sidebar="collapsed"] .rail-hotzone {
        display: block; position: fixed; inset-block: 0; inset-inline-start: 0; width: 16px; z-index: 54;
      }
      .app-shell[data-sidebar="collapsed"][data-rail-peek="true"] .rail-wrap {
        position: fixed; inset: 0 auto 0 0; width: 300px; z-index: 55; visibility: visible; pointer-events: auto;
        box-shadow: 0 18px 48px rgba(0, 0, 0, 0.32); animation: railPeekIn 0.2s cubic-bezier(0.22, 1, 0.36, 1);
      }
      :root[dir="rtl"] .app-shell[data-sidebar="collapsed"][data-rail-peek="true"] .rail-wrap {
        inset: 0 0 0 auto; animation: railPeekInRtl 0.2s cubic-bezier(0.22, 1, 0.36, 1);
      }
    }
    @keyframes railPeekIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }
    @keyframes railPeekInRtl { from { transform: translateX(100%); } to { transform: translateX(0); } }
    .rail-mobile-backdrop { display: none; position: fixed; inset: 0; background: rgba(5, 10, 8, 0.55); z-index: 45; }
    @media (max-width: 960px) {
      .app-shell, .app-shell[data-sidebar="collapsed"] { grid-template-columns: minmax(0, 1fr); }
      .rail-wrap { position: fixed; inset: 0 auto 0 0; width: min(300px, 86vw); z-index: 50; transform: translateX(-100%); visibility: hidden; transition: transform 0.22s ease, visibility 0s linear 0.22s; }
      :root[dir="rtl"] .rail-wrap { inset: 0 0 0 auto; transform: translateX(100%); }
      .app-shell[data-mobile-rail="open"] .rail-wrap { transform: translateX(0); visibility: visible; transition: transform 0.22s ease, visibility 0s; }
      .app-shell[data-mobile-rail="open"] .rail-mobile-backdrop { display: block; }
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
      padding: 0.55rem 1rem 0.22rem; font-size: 0.75rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3);
    }
    .rail-list { flex: 1; overflow-y: auto; padding: 0.2rem 0.55rem; display: flex; flex-direction: column; gap: 2px; scrollbar-width: thin; }

    /* 1-line conversation row with status dot & hover actions (chatv2/sidebar.css pattern) */
    .rail-group { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
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
      font-family: inherit; display: inline-flex; align-items: center; gap: 8px;
    }
    .rail-row.active .rail-item { color: var(--text-0); font-weight: 600; }
    .rail-item-dot {
      width: 5px; height: 5px; border-radius: 50%; border: 1px solid var(--text-3); flex-shrink: 0;
    }
    .rail-row.active .rail-item-dot { background: var(--cv2-accent); border-color: var(--cv2-accent); }
    .rail-item-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .rail-row-actions {
      display: none; align-items: center; gap: 2px; padding-inline-end: 6px;
    }
    .rail-row:hover .rail-row-actions, .rail-row:focus-within .rail-row-actions { display: inline-flex; }
    @media (hover: none) { .rail-row-actions { display: inline-flex; } }
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
    .acct-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .acct-name { font-size: 0.8rem; font-weight: 700; color: var(--text-0); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .acct-sub { font-size: 0.75rem; color: var(--text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .acct-popover {
      position: absolute; bottom: calc(100% + 8px); left: 0.65rem; right: 0.65rem;
      background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-md);
      box-shadow: var(--shadow-lg); padding: 0.55rem; display: none; flex-direction: column;
      gap: 3px; z-index: 60;
    }
    .acct-popover.open { display: flex; }
    .acct-pop-section { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); padding: 4px 8px 2px; }
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
    :root[data-theme="light"] .status-badge[data-connection="offline"] { color: #991B1B; }
    :root[data-theme="light"] .status-badge[data-connection="offline"] .status-dot { background: #991B1B; box-shadow: none; }
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
    .ldv2-cat { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ssra-gold); }
    .landing-chip-text { font-size: 0.85rem; font-weight: 500; color: var(--text-0); line-height: 1.35; }

    /* Chat Stream Area (chatv2/messages.css & loading.css pattern) */
    .chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .message-list { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 1.25rem clamp(1rem, 4vw, 3rem); display: flex; flex-direction: column; gap: 1.15rem; max-width: 880px; width: 100%; margin: 0 auto; container-type: inline-size; }
    .message-row { display: flex; flex-direction: column; gap: 0.35rem; animation: fadeIn 0.22s var(--cv2-spring) both; content-visibility: auto; contain-intrinsic-size: auto 160px; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    .message-row-user { align-items: flex-end; }
    .message-row-assistant { display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 12px; align-items: flex-start; }
    .avatar.assistant {
      width: 32px; height: 32px; border-radius: 8px; background: var(--grad-primary);
      color: #fff; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
      margin-top: 2px; box-shadow: var(--shadow-sm);
    }
    @media (max-width: 720px) {
      .message-row-assistant { display: flex; flex-direction: column; }
      .avatar.assistant { display: none; }
    }
    .bubble { max-width: min(720px, 92%); padding: 0.95rem 1.15rem; border-radius: var(--radius-lg); line-height: 1.62; font-size: 0.94rem; }
    .bubble.user { background: var(--cv2-user-bubble); border: 1px solid var(--cv2-user-bubble-border); color: var(--text-0); border-radius: 16px; border-bottom-right-radius: 6px; max-width: min(78%, 640px); }
    .bubble.assistant { background: var(--surface-2); border: 1px solid var(--border-1); color: var(--text-0); border-bottom-left-radius: 6px; box-shadow: var(--shadow-md); width: 100%; }
    .lds { display: inline-flex; align-items: center; gap: 10px; }
    .lds-grid { display: grid; grid-template-columns: repeat(3, 4px); gap: 1.5px; flex-shrink: 0; }
    .lds-cell { width: 4px; height: 4px; border-radius: 1px; background: var(--text-0); animation: pixelOn 1.2s ease-in-out infinite; }
    .lds-cell:nth-child(2), .lds-cell:nth-child(6) { animation-delay: 0.15s; }
    .lds-cell:nth-child(3), .lds-cell:nth-child(7) { animation-delay: 0.3s; }
    .lds-cell:nth-child(4), .lds-cell:nth-child(8) { animation-delay: 0.45s; }
    .lds-cell:nth-child(5), .lds-cell:nth-child(9) { animation-delay: 0.6s; }
    @keyframes pixelOn { 0%, 100% { opacity: 0.18; } 50% { opacity: 1; } }
    .turn-meta-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; margin-bottom: 0.55rem; font-size: 0.74rem; color: var(--text-2); }
    .meta-pill { padding: 0.18rem 0.55rem; border-radius: var(--radius-pill); background: var(--surface-3); border: 1px solid var(--border-1); font-weight: 600; font-size: 0.75rem; }
    .meta-pill.verified { color: var(--success); border-color: rgba(52, 211, 153, 0.35); }
    .meta-pill.caution { color: var(--warning); border-color: rgba(251, 191, 36, 0.45); }

    /* Generative UI Cards */
    .gen-ui-card { margin-top: 0.85rem; padding: 0.95rem 1.1rem; border-radius: var(--radius-md); background: var(--surface-1); border: 1px solid var(--border-2); }
    .gen-ui-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ssra-gold); margin-bottom: 0.55rem; display: flex; align-items: center; justify-content: space-between; }
    .ssra-guided-steps { margin: 0.4rem 0; padding-inline-start: 1.25rem; display: flex; flex-direction: column; gap: 0.4rem; font-size: 0.88rem; }
    .ssra-citation-badges { list-style: none; padding: 0; margin: 0.65rem 0 0; display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .citation-pill { padding: 0.25rem 0.65rem; border-radius: var(--radius-pill); background: rgba(7, 137, 48, 0.14); border: 1px solid rgba(46, 204, 113, 0.35); color: var(--ssra-teal-light); font-size: 0.78rem; font-weight: 600; }
    .citation-link { color: inherit; text-underline-offset: 2px; }
    .gen-ui-card.is-warning { border-color: rgba(251, 191, 36, 0.55); }
    .gen-ui-card p { margin: 0.35rem 0 0; font-size: 0.88rem; line-height: 1.5; }
    .gen-kv { margin: 0.45rem 0 0; display: grid; gap: 0.3rem; }
    .gen-kv > div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.25rem 0.75rem; padding: 0.3rem 0; border-bottom: 1px solid var(--border-0); font-size: 0.88rem; }
    .gen-kv dt { color: var(--text-2); }
    .gen-kv dd { margin: 0; font-weight: 700; color: var(--text-0); font-variant-numeric: tabular-nums; }
    .gen-estimate-note { font-weight: 600; color: var(--warning); }
    .turn-actions { display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; margin-top: 0.65rem; padding-top: 0.55rem; border-top: 1px solid var(--border-0); opacity: 0.45; transition: opacity 0.16s ease; }
    .message-list > article:last-of-type .turn-actions,
    .message-row:hover .turn-actions,
    .message-row:focus-within .turn-actions { opacity: 1; }
    @media (hover: none) { .turn-actions { opacity: 1; } }
    .turn-act-btn { min-height: 44px; padding: 0.25rem 0.75rem; border-radius: 8px; background: var(--surface-1); border: 1px solid var(--border-0); color: var(--text-2); font-size: 0.74rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.35rem; }
    .turn-act-btn:hover { background: var(--surface-3); color: var(--text-0); border-color: var(--border-1); }

    /* Two-Row Composer Dock (chatv2/composer.css, NarrationBar.tsx & interactions.css pattern) */
    .chatv2 button, .chatv2 [role="button"], .chatv2 .landing-chip { -webkit-tap-highlight-color: transparent; touch-action: manipulation; }
    .composer-dock { width: 100%; max-width: 820px; margin: 0 auto; padding: 0.65rem 1rem max(0.85rem, env(safe-area-inset-bottom)); }
    .narration-bar { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.45rem; padding: 0.4rem 0.75rem; border-radius: 12px; background: var(--surface-2); border: 1px solid var(--border-2); color: var(--text-0); font-size: 0.8rem; }
    .narration-text { display: flex; align-items: center; gap: 0.5rem; min-width: 0; flex: 1; overflow: hidden; }
    .narration-label { font-weight: 700; color: var(--ssra-gold); white-space: nowrap; }
    .narration-sentence { color: var(--text-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .narration-actions { display: inline-flex; align-items: center; gap: 0.35rem; flex-shrink: 0; }
    .narration-btn { min-width: 36px; min-height: 36px; padding: 0 0.5rem; border-radius: 8px; border: 1px solid var(--border-1); background: var(--surface-1); color: var(--text-0); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
    .composer-box { background: var(--surface-2); backdrop-filter: blur(20px); border: 1px solid var(--border-2); border-radius: 16px; padding: 0.65rem 0.85rem; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; gap: 0.45rem; transition: border-color 0.15s ease, box-shadow 0.15s ease; }
    .composer-box:focus-within { border-color: var(--ssra-gold); }
    .composer-box.is-recording { border-color: var(--danger); }
    .composer-active-recording { display: flex; align-items: center; justify-content: space-between; gap: 0.65rem; min-height: 48px; padding: 0.25rem 0.35rem; border-radius: 12px; background: rgba(251, 113, 133, 0.08); border: 1px solid rgba(251, 113, 133, 0.35); }
    .composer-rec-label { display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.84rem; font-weight: 600; color: var(--text-0); }
    .composer-rec-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--danger); animation: callDotPulse 1.4s ease-in-out infinite; }
    .composer-rec-controls { display: inline-flex; align-items: center; gap: 0.4rem; }
    .composer-rec-cancel, .composer-rec-confirm { width: 38px; height: 38px; border-radius: 50%; border: 1px solid var(--border-1); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
    .composer-rec-cancel { background: var(--surface-1); color: var(--danger); }
    .composer-rec-confirm { background: var(--grad-primary); color: #fff; border-color: transparent; }
    .composer-textarea { width: 100%; min-height: 46px; max-height: 140px; resize: none; border: none; background: transparent; color: var(--text-0); font: inherit; font-size: 0.95rem; outline: none; line-height: 1.45; }
    .composer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
    .composer-tools-left, .composer-tools-right { display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; }
    .add-circle-btn { width: 38px; height: 38px; border-radius: 50%; background: var(--surface-1); border: 1px solid var(--border-2); color: var(--text-0); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
    .add-circle-btn:hover { background: var(--surface-3); }
    .composer-attachments { display: flex; flex-wrap: wrap; gap: 0.45rem; padding-bottom: 0.25rem; }
    .attachment-chip { display: inline-flex; align-items: center; gap: 0.4rem; max-width: 100%; padding: 0.3rem 0.55rem; border-radius: 10px; background: var(--surface-1); border: 1px solid var(--border-1); font-size: 0.78rem; color: var(--text-0); }
    .attachment-chip-error { border-color: var(--danger); background: rgba(251, 113, 133, 0.1); }
    .attachment-thumb { width: 28px; height: 28px; border-radius: 6px; object-fit: cover; flex-shrink: 0; }
    .attachment-name { font-weight: 600; max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .attachment-meta { color: var(--text-2); font-size: 0.72rem; white-space: nowrap; }
    .attachment-act-btn { min-width: 28px; min-height: 28px; padding: 0 0.3rem; border-radius: 6px; border: 1px solid var(--border-1); background: var(--surface-2); color: var(--text-0); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
    .composer-attachment-privacy { margin: 0; font-size: 0.72rem; color: var(--text-2); line-height: 1.35; }
    .addmenu-modal, .doc-modal, .camera-modal { max-width: 520px; width: 100%; max-height: min(86vh, 700px); background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-xl); padding: 1.15rem 1.25rem; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; gap: 0.75rem; overflow-y: auto; text-align: start; }
    .addmenu-list { display: flex; flex-direction: column; gap: 0.45rem; }
    .addmenu-opt { display: flex; align-items: center; gap: 0.7rem; width: 100%; min-height: 48px; padding: 0.55rem 0.75rem; border-radius: 12px; border: 1px solid var(--border-1); background: var(--surface-1); color: var(--text-0); font: inherit; cursor: pointer; text-align: start; }
    .addmenu-opt:hover { background: var(--surface-2); border-color: var(--ssra-gold); }
    .addmenu-opt-copy { display: flex; flex-direction: column; gap: 0.1rem; }
    .addmenu-opt-title { font-weight: 700; font-size: 0.86rem; color: var(--text-0); }
    .addmenu-opt-desc { font-size: 0.76rem; color: var(--text-2); }
    .doc-modal-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.65rem; padding-bottom: 0.6rem; border-bottom: 1px solid var(--border-1); }
    .doc-modal-badges { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.3rem; }
    .doc-modal-badge { font-size: 0.72rem; font-weight: 600; padding: 0.15rem 0.5rem; border-radius: 999px; background: var(--surface-2); color: var(--text-1); border: 1px solid var(--border-1); }
    .doc-modal-section { display: flex; flex-direction: column; gap: 0.35rem; padding: 0.65rem 0.75rem; border-radius: 10px; background: var(--surface-1); border: 1px solid var(--border-1); font-size: 0.82rem; color: var(--text-1); line-height: 1.45; }
    .doc-modal-section-title { margin: 0; font-size: 0.78rem; font-weight: 700; text-transform: uppercase; color: var(--text-0); }
    .doc-modal-prompts-list { display: flex; flex-direction: column; gap: 0.35rem; }
    .doc-modal-prompt-btn { display: inline-flex; align-items: center; gap: 0.45rem; width: 100%; min-height: 40px; padding: 0.4rem 0.65rem; border-radius: 8px; border: 1px solid var(--border-1); background: var(--surface-2); color: var(--text-0); font: inherit; font-size: 0.8rem; cursor: pointer; text-align: start; }
    .doc-modal-footer { display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem; flex-wrap: wrap; padding-top: 0.4rem; border-top: 1px solid var(--border-1); }
    .camera-video { width: 100%; max-height: 280px; border-radius: 10px; background: #000; object-fit: cover; }
    .voicemode-circle-btn { width: 42px; height: 42px; border-radius: 50%; background: var(--surface-1); border: 1px solid var(--border-2); color: var(--text-0); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
    .voicemode-circle-btn.is-active { background: rgba(7, 137, 48, 0.22); border-color: #2ECC71; box-shadow: 0 0 0 3px rgba(46, 204, 113, 0.28); color: #2ECC71; }
    .voice-dock { --vd-floor: var(--border-1); display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; flex-wrap: wrap; padding: 0.5rem 0.75rem; margin-bottom: 0.45rem; background: var(--bg-1); border: 1px solid var(--vd-floor); border-radius: 14px; box-shadow: var(--shadow-md); }
    .voice-dock[data-floor="listening"] { --vd-floor: #2ECC71; }
    .voice-dock[data-floor="thinking"] { --vd-floor: #FCDD09; }
    .voice-dock[data-floor="speaking"] { --vd-floor: #0F3A6D; }
    .voice-dock-status { display: flex; align-items: center; gap: 0.55rem; min-width: 0; flex: 1 1 180px; }
    .voice-dock-orb-wrap { width: 34px; height: 34px; flex: none; display: grid; place-items: center; }
    .voice-dock-orb-wrap .call-orb { width: 30px; height: 30px; }
    .voice-dock-text { min-width: 0; flex: 1; text-align: start; }
    .voice-dock-label { margin: 0; font-size: 0.82rem; font-weight: 700; color: var(--text-0); line-height: 1.25; }
    .voice-dock-detail { margin: 1px 0 0; font-size: 0.76rem; color: var(--text-2); line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .voice-dock-controls { display: inline-flex; align-items: center; gap: 0.35rem; flex: none; }
    .voice-dock-end { min-height: 36px; padding: 0 0.7rem; border-radius: 999px; border: 1px solid var(--border-1); background: transparent; color: var(--text-1); font: inherit; font-size: 0.78rem; font-weight: 600; cursor: pointer; }
    .voice-dock-btn { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--border-1); background: var(--surface-2); color: var(--text-0); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
    .voice-dock-primary { background: var(--grad-primary); color: #fff; border: none; }
    .voice-dock-primary[data-action="send"] { background: #078930; }
    .voice-dock-primary[data-action="stop"] { background: var(--danger); }
    .setv2-segmented { display: inline-flex; align-items: center; gap: 4px; padding: 3px; border-radius: 10px; background: var(--surface-1); border: 1px solid var(--border-1); flex-wrap: wrap; }
    .setv2-seg-btn { min-height: 34px; padding: 0 0.65rem; border-radius: 7px; border: none; background: transparent; color: var(--text-1); font: inherit; font-size: 0.78rem; font-weight: 600; cursor: pointer; }
    .setv2-seg-btn[aria-checked="true"] { background: var(--surface-3); color: var(--text-0); }
    .send-btn { min-height: 44px; padding: 0 1rem; border-radius: var(--radius-pill); background: var(--grad-primary); color: #fff; border: none; font-weight: 700; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; }
    .send-btn:disabled { opacity: 0.48; cursor: not-allowed; }
    .composer-waveform { display: inline-flex; align-items: center; gap: 3px; height: 16px; }
    .composer-waveform span { width: 3px; height: 12px; border-radius: 2px; background: var(--ssra-gold); display: inline-block; }

    /* Modals: CallScreen & CallOrb (FinalYearProject call.css pattern), ConversationSearch (⌘K), SettingsDialog */
    .modal-backdrop { position: fixed; inset: 0; background: rgba(5, 10, 8, 0.76); backdrop-filter: blur(14px); z-index: 100; display: none; place-items: center; padding: 1rem; }
    .modal-backdrop.open { display: grid; }
    .call-modal { max-width: 540px; width: 100%; max-height: min(86vh, 720px); background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-xl); padding: 1.15rem 1.25rem; text-align: center; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; align-items: stretch; gap: 0.75rem; overflow: hidden; }
    .call-header { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; padding-bottom: 0.6rem; border-bottom: 1px solid var(--border-1); }
    .call-header-meta { display: inline-flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; }
    .call-status-pill { display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.78rem; font-weight: 600; padding: 0.25rem 0.7rem; border-radius: 999px; background: var(--surface-2); color: var(--text-1); border: 1px solid var(--border-1); }
    .call-status-pill[data-status="ai"] { background: rgba(7, 137, 48, 0.18); color: #2ECC71; border-color: rgba(46, 204, 113, 0.4); }
    .call-status-pill[data-status="transferring"] { background: rgba(251, 191, 36, 0.16); color: var(--warning); border-color: rgba(251, 191, 36, 0.4); }
    .call-status-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
    .call-status-pill[data-status="ai"] .call-status-dot { animation: callDotPulse 1.6s infinite; }
    @keyframes callDotPulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.45; transform: scale(1.3); } }
    .call-lang { position: relative; }
    .call-lang-chip { display: inline-flex; align-items: center; gap: 0.3rem; font: inherit; font-size: 0.75rem; font-weight: 600; min-height: 34px; padding: 0.2rem 0.55rem; border-radius: 8px; background: var(--surface-2); color: var(--text-0); border: 1px solid var(--border-1); cursor: pointer; }
    .call-lang-menu { position: absolute; top: calc(100% + 0.35rem); inset-inline-end: 0; z-index: 10; min-width: 11rem; padding: 0.35rem; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: 12px; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; gap: 2px; }
    .call-lang-option { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 38px; padding: 0.4rem 0.6rem; font: inherit; font-size: 0.82rem; color: var(--text-0); background: transparent; border: none; border-radius: 8px; cursor: pointer; text-align: start; }
    .call-lang-option[aria-pressed="true"], .call-lang-option:hover { background: var(--surface-2); }
    .call-timer { font-size: 0.8rem; font-weight: 700; color: var(--text-1); font-variant-numeric: tabular-nums; }
    .call-thread-wrap { position: relative; min-height: 96px; max-height: 180px; flex: 1; display: flex; flex-direction: column; border-radius: 12px; background: var(--surface-1); border: 1px solid var(--border-1); overflow: hidden; }
    .call-thread { flex: 1; overflow-y: auto; padding: 0.75rem 0.85rem; display: flex; flex-direction: column; gap: 0.65rem; text-align: start; }
    .call-turn { display: flex; flex-direction: column; gap: 0.2rem; max-width: 100%; }
    .call-turn--caller { align-self: flex-end; align-items: flex-end; max-width: 85%; }
    .call-turn--agent { align-self: stretch; align-items: flex-start; }
    .call-bubble { padding: 0.45rem 0.75rem; border-radius: 14px; border-bottom-right-radius: 5px; background: var(--cv2-user-bubble); border: 1px solid var(--cv2-user-bubble-border); color: var(--text-0); font-size: 0.86rem; line-height: 1.4; }
    .call-say { font-size: 0.9rem; line-height: 1.5; color: var(--text-0); }
    .call-system-note { align-self: center; margin: 0; font-size: 0.75rem; color: var(--text-2); text-align: center; }
    .call-jump { position: absolute; inset-inline-start: 50%; bottom: 0.45rem; transform: translateX(-50%); display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.3rem 0.65rem; border-radius: 999px; font-size: 0.74rem; font-weight: 600; color: var(--text-0); background: var(--bg-1); border: 1px solid var(--border-2); cursor: pointer; }
    .call-dock { display: flex; align-items: center; justify-content: space-between; gap: 0.65rem; padding-top: 0.45rem; border-top: 1px solid var(--border-1); }
    .call-dock-side { display: inline-flex; align-items: center; gap: 0.45rem; }
    .call-ctl { width: 44px; height: 44px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-0); background: var(--surface-2); border: 1px solid var(--border-1); }
    .call-ctl--muted { background: rgba(251, 191, 36, 0.2); border-color: var(--warning); color: var(--warning); }
    .call-ctl--hangup { background: rgba(251, 113, 133, 0.2); border-color: var(--danger); color: var(--danger); }
    .call-orb-wrap { width: 76px; height: 60px; display: flex; align-items: center; justify-content: center; flex: none; }
    .call-orb { position: relative; width: 54px; height: 54px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: transform 0.08s linear; }
    .call-orb-core { position: absolute; inset: 0; border-radius: 50%; background: radial-gradient(circle at 32% 28%, rgba(249, 199, 79, 0.55), transparent 42%), radial-gradient(circle at 60% 65%, #0F47AF, #078930 78%); box-shadow: inset 0 0 12px rgba(255, 255, 255, 0.18); }
    .call-orb-halo { position: absolute; inset: -12px; border-radius: 50%; background: radial-gradient(circle, rgba(15, 71, 175, 0.42), transparent 68%); opacity: 0.25; pointer-events: none; transition: opacity 0.08s linear; }
    .call-orb[data-mode="listening"] .call-orb-core { background: radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.5), transparent 42%), radial-gradient(circle at 60% 65%, #2ECC71, #078930 74%); }
    .call-orb[data-mode="listening"] .call-orb-halo { background: radial-gradient(circle, rgba(46, 204, 113, 0.45), transparent 68%); opacity: 0.65; }
    .call-orb[data-mode="thinking"] .call-orb-core { background: radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.45), transparent 42%), radial-gradient(circle at 60% 65%, #FCDD09, #D97706 76%); }
    .call-orb[data-mode="thinking"] .call-orb-halo { background: radial-gradient(circle, rgba(252, 221, 9, 0.48), transparent 68%); opacity: 0.72; }
    .call-orb[data-mode="speaking"] { transform: scale(1.1); }
    .call-orb[data-mode="speaking"] .call-orb-halo { opacity: 0.85; }
    .call-orb[data-mode="idle"], .call-orb[data-mode="thinking"] { animation: orbPulse 2.8s ease-in-out infinite; }
    .call-controls-strip { display: flex; align-items: center; justify-content: center; gap: 0.4rem; flex-wrap: wrap; }
    .call-chip-btn { display: inline-flex; align-items: center; gap: 0.3rem; min-height: 34px; padding: 0.25rem 0.65rem; border-radius: 999px; font: inherit; font-size: 0.76rem; font-weight: 600; background: var(--surface-2); color: var(--text-0); border: 1px solid var(--border-1); cursor: pointer; }
    .call-chip-btn.is-active { background: rgba(7, 137, 48, 0.22); border-color: #2ECC71; color: #2ECC71; }
    .call-text-form { display: flex; align-items: center; gap: 0.45rem; width: 100%; }
    .call-text-input { flex: 1; min-width: 0; min-height: 38px; padding: 0.35rem 0.65rem; border-radius: 10px; border: 1px solid var(--border-2); background: var(--surface-1); color: var(--text-0); font: inherit; font-size: 0.84rem; }
    .call-text-send { min-height: 38px; padding: 0 0.85rem; border-radius: 10px; border: none; background: var(--grad-primary); color: #fff; font: inherit; font-size: 0.82rem; font-weight: 700; cursor: pointer; }
    @keyframes orbPulse { 0%, 100% { transform: scale(0.97); } 50% { transform: scale(1.03); } }
    @media (prefers-reduced-motion: reduce) {
      .call-orb, .call-orb[data-mode="idle"], .call-orb[data-mode="thinking"], .call-orb[data-mode="speaking"], .call-status-pill[data-status="ai"] .call-status-dot, .composer-rec-dot { animation: none; transform: none; transition: none; }
    }

    .search-modal { max-width: 540px; width: 100%; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow: hidden; }
    .search-input { width: 100%; padding: 14px 16px; border: none; border-bottom: 1px solid var(--border-1); background: transparent; color: var(--text-0); font: inherit; font-size: 0.95rem; outline: none; }
    .search-results { max-height: 320px; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 4px; }

    .settings-modal { max-width: 680px; width: 100%; min-height: 380px; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); display: grid; grid-template-columns: 185px 1fr; overflow: hidden; }
    @media (max-width: 640px) { .settings-modal { grid-template-columns: 1fr; } }
    .settings-tabs { background: var(--surface-1); border-inline-end: 1px solid var(--border-1); padding: 1rem 0.6rem; display: flex; flex-direction: column; gap: 4px; }
    .settings-tablist { display: flex; flex-direction: column; gap: 4px; }
    .settings-tab-btn { min-height: 44px; padding: 8px 12px; border-radius: 8px; border: none; background: transparent; color: var(--text-2); font: inherit; font-size: 0.83rem; font-weight: 600; text-align: start; cursor: pointer; }
    .settings-tab-btn.active { background: var(--surface-3); color: var(--text-0); }
    .settings-pane { padding: 1.25rem 1.4rem; display: flex; flex-direction: column; gap: 0.85rem; }

    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
    .is-hidden { display: none !important; }
    .rail-brand-sub { font-size: 0.68rem; color: var(--text-2); font-weight: 500; }
    .acct-pop-hr { border: 0; border-top: 1px solid var(--border-0); margin: 3px 0; }
    .acct-chevron { color: var(--text-3); font-size: 0.75rem; }
    .active-conv-title { font-weight: 700; font-size: 0.9rem; color: var(--text-0); }
    .composer-hint { flex: 1; min-width: 0; font-size: 0.8rem; color: var(--text-1); }
    .composer-hint:empty { display: none; }
    .composer-keys { font-size: 0.75rem; color: var(--text-2); }
    .composer-disclosure { margin: 0.45rem 0.4rem 0; font-size: 0.75rem; line-height: 1.45; color: var(--text-2); text-align: center; }
    .rail-device-note { margin: 0 0.85rem 0.35rem; font-size: 0.75rem; line-height: 1.4; color: var(--text-2); }
    .locale-notice { margin: 0.75rem auto 0; max-width: 820px; width: calc(100% - 2rem); padding: 0.6rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid rgba(251, 191, 36, 0.45); background: var(--surface-2); color: var(--text-0); font-size: 0.84rem; line-height: 1.45; }
    .noscript-note { position: fixed; inset: auto 1rem 1rem 1rem; z-index: 200; margin: 0; padding: 1rem; border: 2px solid var(--ssra-gold); border-radius: var(--radius-md); background: var(--bg-1); color: var(--text-0); }
    .acct-pop-note { margin: 0; padding: 4px 8px; font-size: 0.78rem; color: var(--text-2); line-height: 1.45; }
    .confirm-modal { max-width: 440px; width: 100%; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); padding: 1.25rem 1.4rem; display: flex; flex-direction: column; gap: 0.75rem; }
    .confirm-modal-field { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.86rem; color: var(--text-1); }
    .confirm-modal-input { min-height: 44px; padding: 0.5rem 0.7rem; border-radius: var(--radius-sm); border: 1px solid var(--border-2); background: var(--surface-1); color: var(--text-0); font: inherit; }
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
    .turn-content-text { white-space: pre-wrap; }
    .bubble, .landing-chip-text, .citation-pill, .gen-ui-card p, .gen-kv dd, .locale-notice, .composer-disclosure { overflow-wrap: anywhere; }
    .rail-empty-hint { padding: 0.75rem; font-size: 0.78rem; color: var(--text-3); }
    :focus-visible { outline: 3px solid var(--ssra-gold); outline-offset: 2px; }
    .composer-textarea:focus-visible, .search-input:focus-visible { outline: 3px solid var(--ssra-gold) !important; outline-offset: 2px; box-shadow: 0 0 0 3px var(--ssra-gold); }
    /* Responsive overrides come after the base rules so they take effect. */
    @media (max-width: 640px) {
      .chat-header {
        display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; gap: 0.35rem 0.4rem;
        grid-template-areas: "rail title voice theme" "status status status locale"; padding: 0.4rem 0.6rem;
      }
      .header-left, .header-right { display: contents; }
      #header-rail-btn { grid-area: rail; }
      #active-conv-title { grid-area: title; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      #open-call-btn { grid-area: voice; }
      #theme-toggle-btn { grid-area: theme; }
      #net-status-badge { grid-area: status; justify-self: start; min-width: 0; }
      #locale-select { grid-area: locale; max-width: 9.5rem; }
      .chat-header .btn-label { display: none; }
      .landing { padding: 1rem 0.85rem 1.5rem; gap: 0.9rem; justify-content: flex-start; }
      .landing-prompts { grid-template-columns: minmax(0, 1fr); }
      .composer-keys { display: none; }
      .composer-dock { padding: 0.45rem 0.6rem max(0.55rem, env(safe-area-inset-bottom)); }
    }
    /* Short screens (landscape phones): scroll the whole column so the conversation keeps its space. */
    @media (max-height: 500px) {
      .app-main-col { overflow-y: auto; }
      .app-content, .chat-area, .message-list, .landing { flex: none; overflow: visible; }
      .landing { justify-content: flex-start; }
      .composer-keys { display: none; }
      .composer-dock { padding-block: 0.35rem max(0.45rem, env(safe-area-inset-bottom)); }
    }
    /* Low-data mode and reduced transparency drop blur, decorative backgrounds, shadows and motion. */
    :root[data-low-data="true"] body::before { background: var(--bg-0); }
    :root[data-low-data="true"] *, :root[data-low-data="true"] *::before, :root[data-low-data="true"] *::after {
      backdrop-filter: none !important; box-shadow: none !important; animation: none !important; transition: none !important;
    }
    @media (prefers-reduced-transparency: reduce) {
      body::before { background: var(--bg-0); }
      *, *::before, *::after { backdrop-filter: none !important; }
    }
    @media (forced-colors: active) {
      .send-btn, .rail-new-btn, .icon-btn, .turn-act-btn, .landing-chip, .bubble, .gen-ui-card, .meta-pill, .citation-pill, .status-badge, .composer-box { border: 1px solid CanvasText; }
      .status-dot { forced-color-adjust: none; background: CanvasText; box-shadow: none; }
      :focus-visible { outline-color: Highlight; }
    }
    @media (prefers-reduced-motion: reduce) {
      .rail-wrap { transition: none !important; }
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
    }
    .jump-open-tag { font-size: 0.7rem; color: var(--text-3); }
  </style>
</head>
<body>
  <div class="ssra-flag-ribbon" aria-hidden="true"></div>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <noscript><p class="noscript-note">SSRA Assist needs JavaScript to answer questions. For SSRA tax services, use the official e-Tax portal: https://etax.nra.gov.ss/</p></noscript>

  <div id="ssra-app-shell" class="app-shell chatv2" data-sidebar="open" data-mobile-rail="closed" data-locale="${locale}">
    <div id="rail-hotzone" class="rail-hotzone" aria-hidden="true"></div>
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
      </button>

      <p id="rail-device-note" class="rail-device-note">Conversations are saved on this device only.</p>
      <nav id="rail-conv-list" class="rail-list" aria-label="Saved conversations"></nav>

      <!-- AccountRail Footer & Upward Popover Menu -->
      <div class="rail-footer">
        <div id="acct-popover" class="acct-popover">
          <div class="acct-pop-section">Public conversation</div>
          <p class="acct-pop-note">Personal balances and filing records require secure sign-in.</p>
          <a href="https://etax.nra.gov.ss/" class="acct-pop-item" rel="noopener noreferrer"><span>Open official e-Tax portal</span><span>${ICONS.arrowUpRight}</span></a>
          <hr class="acct-pop-hr" />
          <button type="button" id="open-settings-btn" class="acct-pop-item"><span>${ICONS.settings} Settings &amp; Privacy</span></button>
        </div>

        <button type="button" id="acct-rail-trigger" class="acct-rail-trigger" aria-expanded="false" aria-controls="acct-popover">
          <div class="acct-avatar"><span id="acct-badge-text">PV</span></div>
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
          <button type="button" id="open-call-btn" class="icon-btn call-btn" aria-label="Open voice input options">${ICONS.mic}<span class="btn-label">Voice input</span></button>
          <select id="locale-select" class="icon-btn" aria-label="Language">
            <optgroup label="Available">
              <option value="en" ${locale === "en" ? "selected" : ""}>English (en)</option>
              <option value="pga" ${locale === "pga" ? "selected" : ""}>Juba Arabic (pga)</option>
              <option value="ar" ${locale === "ar" ? "selected" : ""}>العربية (ar)</option>
            </optgroup>
            <optgroup label="Not yet reviewed (interface in English)">
              <option value="din" ${locale === "din" ? "selected" : ""}>Thuɔŋjäŋ Dinka (din)</option>
              <option value="nus" ${locale === "nus" ? "selected" : ""}>Thok Naath Nuer (nus)</option>
              <option value="bfa" ${locale === "bfa" ? "selected" : ""}>Bari (bfa)</option>
              <option value="zne" ${locale === "zne" ? "selected" : ""}>Pazande (zne)</option>
              <option value="shk" ${locale === "shk" ? "selected" : ""}>Dhøg Cøllø Shilluk (shk)</option>
            </optgroup>
          </select>
          <button type="button" id="theme-toggle-btn" class="icon-btn">${ICONS.moon}<span class="btn-label">Dark</span></button>
        </div>
      </header>

      <main id="main-content" class="app-content" tabindex="-1">
        <p id="locale-notice" class="locale-notice is-hidden" role="status"></p>
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
          <div id="ssra-chat-messages" class="message-list" aria-label="Conversation messages"></div>
        </div>
        <div id="chat-announcer" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>

        <!-- Floating Composer Dock -->
        <div class="composer-dock">
          <!-- WCAG 2.2 SC 1.4.2 NarrationBar (NarrationBar.tsx pattern) -->
          <div id="narration-bar" class="narration-bar is-hidden" role="region" aria-label="Read-aloud controls" data-testid="narration-bar">
            <div class="narration-text">
              <span id="narration-label" class="narration-label" aria-live="polite">Reading aloud</span>
              <span id="narration-sentence" class="narration-sentence" aria-hidden="true"></span>
            </div>
            <div class="narration-actions">
              <button type="button" id="narration-pause-btn" class="narration-btn" aria-label="Pause reading">${ICONS.pause}</button>
              <button type="button" id="narration-stop-btn" class="narration-btn" aria-label="Stop reading" aria-keyshortcuts="Escape">${ICONS.stop}</button>
            </div>
          </div>
          <!-- Main Chat VoiceModeDock (VoiceModeDock.tsx & voice-dock.css pattern) -->
          <section id="voice-mode-dock" class="voice-dock is-hidden" data-phase="idle" data-floor="idle" aria-label="Voice conversation controls" data-testid="voice-dock">
            <div class="voice-dock-status">
              <div class="voice-dock-orb-wrap" aria-hidden="true">
                <div id="voice-dock-orb" class="call-orb" data-mode="idle">
                  <span class="call-orb-core"></span>
                  <span class="call-orb-halo"></span>
                </div>
              </div>
              <div class="voice-dock-text">
                <p id="voice-dock-label" class="voice-dock-label" data-testid="voice-dock-label">Listening…</p>
                <p id="voice-dock-detail" class="voice-dock-detail" data-testid="voice-dock-detail">Speak your question — pauses send automatically.</p>
              </div>
            </div>
            <div class="voice-dock-controls">
              <button type="button" id="voice-dock-end" class="voice-dock-end" data-testid="voice-dock-end" aria-label="Exit voice mode">End</button>
              <button type="button" id="voice-dock-mic-off" class="voice-dock-btn" data-testid="voice-dock-mic-off" aria-label="Cancel microphone listening" aria-keyshortcuts="Escape">${ICONS.micOff}</button>
              <button type="button" id="voice-dock-pause" class="voice-dock-btn is-hidden" data-testid="voice-dock-pause" aria-label="Pause reading">${ICONS.pause}</button>
              <button type="button" id="voice-dock-primary" class="voice-dock-btn voice-dock-primary" data-testid="voice-dock-primary" data-action="send" aria-label="Send voice turn now">${ICONS.check}</button>
            </div>
          </section>
          <form id="ssra-chat-form" class="composer-box">
            <!-- Composer Attachment Chips & Privacy Note (ChatInput.tsx pattern) -->
            <div id="composer-attachments" class="composer-attachments is-hidden" aria-label="Attached documents"></div>
            <p id="composer-attachment-privacy" class="composer-attachment-privacy is-hidden" role="note">Files are checked locally for format safety. Server-side OCR and malware scanning remain disabled under OQ-017; do not attach confidential taxpayer records in public chat.</p>
            <input id="composer-file-input" type="file" multiple accept=".pdf,.docx,.xlsx,.csv,.txt,image/*" class="sr-only" aria-hidden="true" tabindex="-1" />
            <input id="composer-camera-input" type="file" accept="image/*" capture="environment" class="sr-only" aria-hidden="true" tabindex="-1" />
            <label for="ssra-chat-input" class="sr-only">Ask SSRA Assist</label>
            <textarea id="ssra-chat-input" class="composer-textarea" rows="1" required placeholder="Ask about SSRA taxes, TIN, PAYE, TCC, or customs in English, Arabic, or Juba Arabic…"></textarea>
            <!-- In-Composer Active Recording Panel (ChatInput.tsx composer-active-recording pattern) -->
            <div id="composer-recording-bar" class="composer-active-recording is-hidden" data-testid="composer-active-recording">
              <div class="composer-rec-label">
                <span class="composer-rec-dot" aria-hidden="true"></span>
                <span id="composer-rec-text">Listening…</span>
              </div>
              <div class="composer-rec-controls">
                <span class="composer-waveform" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></span>
                <button type="button" id="composer-rec-cancel" class="composer-rec-cancel" data-testid="composer-rec-cancel" aria-label="Cancel voice recording">${ICONS.close}</button>
                <button type="button" id="composer-rec-confirm" class="composer-rec-confirm" data-testid="composer-rec-confirm" aria-label="Confirm voice recording">${ICONS.check}</button>
              </div>
            </div>
            <div class="composer-toolbar">
              <div class="composer-tools-left">
                <button type="button" id="composer-add-btn" class="add-circle-btn" data-testid="composer-add-btn" aria-haspopup="dialog" aria-expanded="false" aria-label="Add file or photo" title="Add file, screenshot, or photo">${ICONS.plus}</button>
                <button type="button" id="voice-dictate-btn" class="icon-btn" title="Voice typing uses your browser's speech recognition" aria-label="Voice typing">
                  ${ICONS.mic} <span class="composer-waveform" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></span>
                </button>
                <span id="composer-hint" class="composer-hint" role="status" aria-live="polite"></span>
                <span class="composer-keys">Enter to send · Shift+Enter for a new line · Ctrl+K to search</span>
              </div>
              <div class="composer-tools-right">
                <button type="button" id="composer-voicemode-btn" class="voicemode-circle-btn" data-testid="composer-voicemode" aria-pressed="false" aria-label="Enter voice conversation mode" title="Toggle hands-free voice conversation">${ICONS.voiceWave}</button>
                <button type="submit" id="ssra-chat-submit" class="send-btn">${ICONS.send} Send</button>
              </div>
            </div>
          </form>
          <p class="composer-disclosure" lang="en">SSRA Assist is an automated AI assistant and can make mistakes. Check answers against the cited sources. Don’t enter your TIN, phone number, or passwords in this public chat.</p>
        </div>
      </main>
    </div>
  </div>

  <!-- AI Call Receptionist Modal (CallScreen.tsx & CallOrb.tsx pattern) -->
  <div id="call-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="call-modal-title">
    <div class="call-modal call-card--live">
      <header class="call-header">
        <div id="call-status-pill" class="call-status-pill" data-status="consent">
          <span class="call-status-dot" aria-hidden="true"></span>
          <span id="call-status-label">AI Receptionist · Automated</span>
        </div>
        <div class="call-header-meta">
          <div class="call-lang">
            <button type="button" id="call-lang-chip" class="call-lang-chip" aria-expanded="false" aria-controls="call-lang-menu" aria-label="Call language: English · auto">
              ${ICONS.globe}
              <span id="call-lang-chip-text">English · auto</span>
              ${ICONS.chevronDown}
            </button>
            <div id="call-lang-menu" class="call-lang-menu is-hidden" role="group" aria-label="Call language">
              <button type="button" aria-pressed="true" class="call-lang-option" data-call-lang="en"><span>English</span></button>
              <button type="button" aria-pressed="false" class="call-lang-option" data-call-lang="ar"><span>العربية</span></button>
            </div>
          </div>
          <span id="call-timer" class="call-timer">00:00</span>
        </div>
      </header>
      <div class="eyebrow-pill">${ICONS.mic} Browser voice input</div>
      <h2 id="call-modal-title" class="call-modal-title">Speak or choose a sample question</h2>
      <p id="call-transcript-live" class="call-transcript-live">Voice typing depends on your browser and is currently available only in English and Arabic. Your browser may process audio outside SSRA. Do not speak or type a TIN, balance, or other private account details in this public chat.</p>
      <p id="call-voice-status" class="call-transcript-live" role="status" aria-live="polite">Ready. Tap Start voice conversation for hands-free back-and-forth, or choose a sample question.</p>
      <div class="call-thread-wrap">
        <div id="call-thread" class="call-thread" role="log" aria-label="Call transcript">
          <p class="call-system-note">You are speaking with SSRA Assist, an automated AI assistant. It can make mistakes.</p>
        </div>
        <button type="button" id="call-jump-btn" class="call-jump is-hidden">${ICONS.chevronDown} Jump to latest</button>
      </div>
      <div class="call-prompts-row">
        <button type="button" class="icon-btn call-sample-btn" data-voice-q="Where can I find general e-Tax filing guidance?">${ICONS.messageSquare} "General e-Tax guidance"</button>
        <button type="button" class="icon-btn call-sample-btn" data-voice-q="Where can I find general customs guidance?">${ICONS.messageSquare} "General customs guidance"</button>
      </div>
      <!-- In-Call Receptionist Controls Strip & Typed Turn Form (CallScreen.tsx lines 393-498 parity) -->
      <div class="call-controls-strip" role="toolbar" aria-label="Call receptionist controls">
        <button type="button" id="call-repeat-btn" class="call-chip-btn is-hidden" data-testid="call-repeat-btn">${ICONS.refresh} Repeat last</button>
        <button type="button" id="call-more-detail-btn" class="call-chip-btn is-hidden" data-testid="call-more-detail-btn">More detail</button>
        <button type="button" id="call-pace-btn" class="call-chip-btn" data-testid="call-pace-btn" aria-pressed="false">Slower pace</button>
        <button type="button" id="call-type-toggle-btn" class="call-chip-btn" data-testid="call-type-toggle-btn" aria-expanded="false" aria-controls="call-text-form">Type a question</button>
      </div>
      <form id="call-text-form" class="call-text-form is-hidden" data-testid="call-text-form">
        <input id="call-text-input" class="call-text-input" data-testid="call-text-input" type="text" maxlength="500" aria-label="Type your question" placeholder="Type your question for SSRA Assist…" autocomplete="off" />
        <button type="submit" id="call-text-send" class="call-text-send" data-testid="call-text-send">Send</button>
      </form>
      <footer class="call-dock">
        <div class="call-dock-side">
          <button type="button" id="call-mute-btn" class="call-ctl" aria-pressed="false" aria-label="Mute microphone" title="Mute microphone">${ICONS.mic}</button>
        </div>
        <div class="call-orb-wrap" aria-hidden="true">
          <div id="call-orb" class="call-orb" data-mode="idle">
            <span class="call-orb-core"></span>
            <span class="call-orb-halo"></span>
          </div>
        </div>
        <div class="call-dock-side">
          <button type="button" id="call-officer-btn" class="call-ctl" aria-label="Request an SSRA officer" title="Request an SSRA officer">${ICONS.user}</button>
          <button type="button" id="call-hangup-btn" class="call-ctl call-ctl--hangup" aria-label="End call" title="End call">${ICONS.phoneOff}</button>
        </div>
      </footer>
      <div class="call-actions-row">
        <button type="button" id="call-listen-btn" class="icon-btn">${ICONS.mic} Start voice conversation</button>
        <button type="button" id="call-interrupt-btn" class="icon-btn">${ICONS.stop} Interrupt &amp; speak</button>
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
      <div class="settings-tabs">
        <div class="settings-heading">Settings</div>
        <div class="settings-tablist" role="tablist" aria-label="Settings categories" aria-orientation="vertical">
          <button type="button" id="settings-tab-general" class="settings-tab-btn active" role="tab" aria-selected="true" aria-controls="settings-pane" tabindex="0" data-settings-tab="general">General &amp; Theme</button>
          <button type="button" id="settings-tab-voice" class="settings-tab-btn" role="tab" aria-selected="false" aria-controls="settings-pane" tabindex="-1" data-settings-tab="voice">Voice &amp; Speech</button>
          <button type="button" id="settings-tab-profile" class="settings-tab-btn" role="tab" aria-selected="false" aria-controls="settings-pane" tabindex="-1" data-settings-tab="profile">Taxpayer Profile</button>
          <button type="button" id="settings-tab-privacy" class="settings-tab-btn" role="tab" aria-selected="false" aria-controls="settings-pane" tabindex="-1" data-settings-tab="privacy">Privacy &amp; Erasure</button>
        </div>
      </div>
      <div id="settings-pane" class="settings-pane" role="tabpanel" aria-labelledby="settings-tab-general">
        <div class="settings-pane-head">
          <h2 id="settings-pane-title" class="settings-pane-title">General &amp; Appearance</h2>
          <button type="button" id="close-settings-btn" class="icon-btn">${ICONS.close} Close</button>
        </div>
        <div id="settings-pane-body" class="settings-pane-body"></div>
      </div>
    </div>
  </div>

  <!-- In-page confirmation and rename dialog (replaces window.prompt / window.confirm) -->
  <div id="confirm-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title" aria-describedby="confirm-modal-message">
    <form id="confirm-modal-form" class="confirm-modal">
      <h2 id="confirm-modal-title" class="settings-pane-title"></h2>
      <p id="confirm-modal-message" class="settings-pane-body"></p>
      <label id="confirm-modal-field" class="confirm-modal-field is-hidden">
        <span>Conversation name</span>
        <input id="confirm-modal-input" class="confirm-modal-input" type="text" maxlength="64" autocomplete="off" />
      </label>
      <div class="settings-actions-row">
        <button type="button" id="confirm-modal-cancel" class="icon-btn">Cancel</button>
        <button type="submit" id="confirm-modal-ok" class="icon-btn"></button>
      </div>
    </form>
  </div>

  <!-- Composer Add-Attachment Modal (ChatInput.tsx addmenu-dialog pattern) -->
  <div id="addmenu-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="composer-attach-title">
    <div class="addmenu-modal">
      <div class="settings-pane-head">
        <h2 id="composer-attach-title" class="settings-pane-title">${ICONS.plus} Add to conversation</h2>
        <button type="button" id="close-addmenu-btn" class="icon-btn" aria-label="Close attachment options">${ICONS.close} Close</button>
      </div>
      <div class="addmenu-list" role="group" aria-label="Attachment options">
        <button type="button" id="addmenu-upload-btn" class="addmenu-opt">
          <span aria-hidden="true">${ICONS.file}</span>
          <span class="addmenu-opt-copy">
            <span class="addmenu-opt-title">Upload a file or screenshot</span>
            <span class="addmenu-opt-desc">PDF, DOCX, XLSX, CSV, TXT, or image (max 3 files, 40 MB)</span>
          </span>
        </button>
        <button type="button" id="addmenu-camera-btn" class="addmenu-opt">
          <span aria-hidden="true">${ICONS.camera}</span>
          <span class="addmenu-opt-copy">
            <span class="addmenu-opt-title">Take a photo</span>
            <span class="addmenu-opt-desc">Scan a tax notice, receipt, or portal screen with your camera</span>
          </span>
        </button>
      </div>
    </div>
  </div>

  <!-- Document & Screenshot Inspection Modal (DocumentInspectionModal.tsx pattern, OQ-017 truthful state) -->
  <div id="doc-inspect-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="doc-modal-title">
    <div class="doc-modal">
      <header class="doc-modal-header">
        <div>
          <h2 id="doc-modal-title" class="settings-pane-title" tabindex="-1">Document inspection</h2>
          <div id="doc-modal-badges" class="doc-modal-badges"></div>
        </div>
        <button type="button" id="close-doc-modal-btn" class="icon-btn" aria-label="Close document inspection">${ICONS.close}</button>
      </header>
      <section class="doc-modal-section" aria-label="Client security preflight">
        <h3 class="doc-modal-section-title">Client-Side Security Preflight</h3>
        <p id="doc-modal-preflight-note" class="composer-attachment-privacy"></p>
      </section>
      <section class="doc-modal-section" aria-label="Analysis status">
        <h3 class="doc-modal-section-title">Analysis &amp; Reconciliation Status (OQ-017)</h3>
        <p id="doc-modal-oq017-note" class="composer-attachment-privacy">Automated OCR extraction, malware scanning, and tax figure reconciliation are unavailable until SSRA approves OQ-017 providers and legal snapshot rules. Do not upload confidential taxpayer records in public chat.</p>
      </section>
      <section class="doc-modal-section" aria-label="Suggested public questions">
        <h3 class="doc-modal-section-title">Suggested Public Questions</h3>
        <div id="doc-modal-prompts" class="doc-modal-prompts-list"></div>
      </section>
      <footer class="doc-modal-footer">
        <button type="button" id="doc-modal-report-btn" class="icon-btn">${ICONS.download} Download inspection receipt</button>
        <button type="button" id="doc-modal-close-secondary-btn" class="icon-btn">${ICONS.close} Close</button>
      </footer>
    </div>
  </div>

  <!-- CameraCapture Modal (CameraCapture.tsx pattern) -->
  <div id="camera-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="camera-modal-title">
    <div class="camera-modal">
      <div class="settings-pane-head">
        <h2 id="camera-modal-title" class="settings-pane-title">${ICONS.camera} Scan Document</h2>
        <button type="button" id="close-camera-btn" class="icon-btn" aria-label="Close camera">${ICONS.close} Close</button>
      </div>
      <p id="camera-error" class="composer-attachment-privacy" role="status">Rear-camera access is disabled under this public chat's Permissions-Policy (camera=()). Use Choose photo below or Upload a file.</p>
      <video id="camera-video" class="camera-video is-hidden" autoplay playsinline muted></video>
      <canvas id="camera-canvas" class="is-hidden"></canvas>
      <div class="doc-modal-footer">
        <button type="button" id="camera-fallback-file-btn" class="icon-btn">${ICONS.camera} Choose photo or image</button>
        <button type="button" id="camera-capture-btn" class="icon-btn" disabled>${ICONS.check} Capture</button>
      </div>
    </div>
  </div>

  <script nonce="${nonce}">
    (() => {
      const ICONS = ${JSON.stringify(ICONS)};
      // Trusted Types: the only script URL this page may load is its own service worker.
      const scriptUrlPolicy = window.trustedTypes?.createPolicy
        ? window.trustedTypes.createPolicy("ssra-web-script-url", {
            createScriptURL: (url) => {
              if (url !== "/sw.js") throw new TypeError("Script URL not allowed: " + url);
              return url;
            },
          })
        : null;
      if ("serviceWorker" in navigator) {
        caches?.keys?.().then((keys) => {
          keys.forEach((k) => {
            if (k !== "ssra-assist-public-shell-v2026.10.4") caches.delete(k);
          });
        }).catch(() => {});
        navigator.serviceWorker.register(scriptUrlPolicy ? scriptUrlPolicy.createScriptURL("/sw.js") : "/sw.js").catch(() => {});
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

      // FE-G5: reviewed Phase 1 interface strings only (OQ-008). Other locales fall back to English.
      const LOCALE_UI_STRINGS = {
        en: {
          headline: "How can I help with your South Sudan taxes today?",
          subtitle: "Ask about TIN registration, PAYE, TCC, customs, or e-Tax. Answers cite approved sources when available. If a source cannot be confirmed, SSRA Assist will say so and offer staff help.",
          placeholder: "Ask about SSRA taxes, TIN, PAYE, TCC, or customs in English, Arabic, or Juba Arabic…",
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
      const SELECTABLE_LOCALES = new Set(Array.from(localeSelect?.options || [], (option) => option.value));

      // Detect 2G / Save-Data network condition (FE-G4)
      const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      const autoLowData = Boolean(
        conn && (conn.saveData || conn.effectiveType === "slow-2g" || conn.effectiveType === "2g")
      );

      const STORAGE_KEY = "ssra-chat-store-v2";
      function systemTheme() {
        if (window.matchMedia?.("(prefers-contrast: more)")?.matches) return "high-contrast";
        return window.matchMedia?.("(prefers-color-scheme: light)")?.matches ? "light" : "dark";
      }
      let state = {
        locale: shell?.dataset.locale || "en",
        theme: systemTheme(),
        themeChosen: false,
        lowDataMode: autoLowData,
        autoNarrate: false,
        saveHistory: true,
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
            themeChosen: Boolean(saved.theme),
            locale: saved.locale || state.locale,
            lowDataMode: saved.lowDataMode ?? state.lowDataMode,
            autoNarrate: Boolean(saved.autoNarrate),
            saveHistory: saved.saveHistory !== false,
            conversations: saved.conversations.filter((c) => !c.isAuthenticated),
          };
        }
      } catch {}

      // FE-G1: Zero-PII Shared-Device Storage Hygiene — never persist non-T0 or TIN-bearing turns to localStorage
      function scrubPiiForStorage(text) {
        return String(text || "")
          .replace(/[\\u0660-\\u0669\\u06f0-\\u06f9]/g, (c) => String(c.charCodeAt(0) & 15))
          .replace(/\\+?211[\\s-]?9\\d(?:[\\s-]?\\d){7}\\b|\\b09[12578](?:[\\s-]?\\d){7}\\b/g, "[REDACTED_PHONE]")
          .replace(/\\b(?:\\d{9,12}|\\d{3}[\\s-]\\d{3}[\\s-]?\\d{4})\\b/g, "[REDACTED_TIN]")
          .replace(/\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b/g, (m) =>
            m.toLowerCase() === "support@nra.gov.ss" ? m : "[REDACTED_EMAIL]",
          );
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
                .filter((t) => (!t.meta?.tier || t.meta.tier === "T0") && t.meta?.kind !== "pending")
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
              theme: state.themeChosen ? state.theme : null,
              lowDataMode: state.lowDataMode,
              autoNarrate: state.autoNarrate,
              saveHistory: state.saveHistory,
              conversations: state.saveHistory ? publicOnlyConvs : [],
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
        state.locale = SELECTABLE_LOCALES.has(loc) ? loc : "en";
        const uiLocale = LOCALE_UI_STRINGS[state.locale] ? state.locale : "en";
        document.documentElement.lang = uiLocale;
        document.documentElement.dir = uiLocale === "ar" ? "rtl" : "ltr";
        if (localeSelect) localeSelect.value = state.locale;
        const notice = document.getElementById("locale-notice");
        if (notice) {
          const name = localeSelect?.selectedOptions?.[0]?.textContent || state.locale;
          notice.textContent = uiLocale === state.locale
            ? ""
            : "Interface text in " + name + " hasn’t been reviewed yet, so it is shown in English. SSRA Assist hasn’t been tested in this language; for checked answers, ask in English, Arabic, or Juba Arabic.";
          notice.classList.toggle("is-hidden", uiLocale === state.locale);
        }
        const dict = LOCALE_UI_STRINGS[uiLocale];
        const hEl = document.getElementById("landing-headline");
        const sEl = document.getElementById("landing-subtitle");
        if (hEl) hEl.textContent = dict.headline;
        if (sEl) sEl.textContent = dict.subtitle;
        if (input) input.placeholder = dict.placeholder;
      }
      applyLocaleStrings(state.locale);

      const THEME_COLORS = { dark: "#091310", light: "#F6F7F2", "high-contrast": "#000000" };
      function applyTheme(t) {
        state.theme = t;
        document.documentElement.setAttribute("data-theme", t);
        const btn = document.getElementById("theme-toggle-btn");
        if (btn) {
          const label = t === "dark" ? "Dark" : t === "light" ? "Light" : "High contrast";
          setSafeHtml(btn, (t === "dark" ? ICONS.moon : t === "light" ? ICONS.sun : ICONS.contrast) + '<span class="btn-label">' + label + "</span>");
          document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => meta.setAttribute("content", THEME_COLORS[t]));
          btn.setAttribute("aria-label", "Colour theme: " + label + ". Change theme");
        }
        saveState();
      }
      applyTheme(state.theme);
      // Until the user picks a theme, follow later system colour or contrast changes.
      ["(prefers-color-scheme: light)", "(prefers-contrast: more)"].forEach((query) => {
        window.matchMedia?.(query)?.addEventListener?.("change", () => {
          if (!state.themeChosen) applyTheme(systemTheme());
        });
      });

      // Offline fallback abstains, says whether the question was sent, and never cites a source.
      function computeOfflineResilienceAnswer(text, opts = {}) {
        const q = String(text || "").toLowerCase();
        const isCalcOrRate =
          q.includes("paye") ||
          q.includes("salary") ||
          q.includes("wht") ||
          q.includes("withholding") ||
          q.includes("customs") ||
          q.includes("duty") ||
          q.includes("tariff") ||
          q.includes("cif");
        const status = opts.sent
          ? "The connection dropped before SSRA Assist replied, so your question may not have been answered."
          : "You’re offline, so your question wasn’t sent.";
        return {
          content:
            status +
            " You can send it again when you’re connected." +
            (isCalcOrRate ? " I can’t calculate or confirm tax figures while offline." : ""),
          meta: {
            tier: "T0",
            kind: "failure",
            outcome_verified: false,
            citations: [],
            retry_text: String(text || "").trim(),
          },
        };
      }

      // Public chat is anonymous (T0), so it renders only the public Generative UI
      // components. Every displayed prop is checked; a missing value is never filled in.
      const PUBLIC_UI_COMPONENTS = new Set(["CitationList", "CalculatorForm", "PaymentInstructionsCard", "HandoffCard"]);
      const SIGN_IN_UI_COMPONENTS = new Set(["BalanceCard", "FilingStatusTimeline", "ConfirmActionSheet"]);
      const OFFICIAL_PORTAL = "https://etax.nra.gov.ss/";
      const SIGN_IN_NOTICE = "Personal tax records and account actions aren’t available in this public chat. Sign in through the official e-Tax portal: " + OFFICIAL_PORTAL;

      function isFilledText(value) {
        return typeof value === "string" && value.trim().length > 0;
      }

      function cardHtml(title, body, tone) {
        return '<div class="gen-ui-card' + (tone ? " is-" + tone : "") + '" role="group" aria-label="' + escapeHtml(title) + '">' +
          '<div class="gen-ui-title">' + escapeHtml(title) + "</div>" + body + "</div>";
      }

      function definitionRows(rows) {
        const filled = rows.filter(([, value]) => isFilledText(value));
        return filled.length
          ? '<dl class="gen-kv">' + filled.map(([label, value]) => "<div><dt>" + escapeHtml(label) + "</dt><dd>" + escapeHtml(value) + "</dd></div>").join("") + "</dl>"
          : "";
      }

      function renderGuidedSteps(steps) {
        if (!Array.isArray(steps) || steps.length === 0) return "";
        const valid = steps.every(
          (s) => s && Number.isInteger(s.step_number) && s.step_number >= 1 && isFilledText(s.title) && isFilledText(s.instruction),
        );
        if (!valid) return "";
        return '<ol class="ssra-guided-steps">' + steps.map((s) =>
          "<li><strong>" + escapeHtml(s.title) + ":</strong> " + escapeHtml(s.instruction) + "</li>"
        ).join("") + "</ol>";
      }

      function renderCalculatorCard(p, citationCount) {
        const hasPaye = p.estimated_tax_ssp !== undefined;
        const hasWht = p.withholding_tax_ssp !== undefined;
        const type = hasWht ? "WHT" : hasPaye ? "PAYE" : null;
        if (p.is_estimate !== true || !type || (hasPaye && hasWht)) return "";
        if (p.calculator_type !== undefined && p.calculator_type !== type) return "";
        if (!isFilledText(type === "WHT" ? p.withholding_tax_ssp : p.estimated_tax_ssp)) return "";
        if (citationCount < 1) {
          return cardHtml("Estimate unavailable", "<p>An estimate can’t be shown because no approved source came with it.</p>", "warning");
        }
        const rows = type === "WHT"
          ? [["Gross payment (SSP)", p.gross_amount_ssp], ["Rate (%)", p.rate_percent], ["Withholding tax (SSP)", p.withholding_tax_ssp], ["Net payable (SSP)", p.net_payable_ssp]]
          : [["Gross monthly pay (SSP)", p.gross_monthly_ssp], ["Estimated PAYE (SSP)", p.estimated_tax_ssp], ["Net monthly pay (SSP)", p.net_monthly_ssp]];
        return cardHtml(
          type === "WHT" ? "Withholding tax estimate" : "PAYE estimate",
          '<p class="gen-estimate-note">Estimate only. It is not an official assessment.</p>' + definitionRows(rows),
        );
      }

      function renderPaymentCheckCard(p) {
        const official = p.status === "OFFICIAL_VERIFIED";
        if ((!official && p.status !== "UNVERIFIED_OR_SCAM") || !isFilledText(p.identifier) || !isFilledText(p.guidance) || p.official_portal !== OFFICIAL_PORTAL) {
          return "";
        }
        return cardHtml(
          official ? "Official SSRA channel" : "Not a confirmed SSRA channel",
          definitionRows([["Checked", p.identifier]]) + "<p>" + escapeHtml(p.guidance) + "</p><p>Official e-Tax portal: " + OFFICIAL_PORTAL + "</p>",
          official ? "" : "warning",
        );
      }

      function renderPublicCard(ui, citationCount) {
        if (!ui || typeof ui.name !== "string") return "";
        if (SIGN_IN_UI_COMPONENTS.has(ui.name)) return cardHtml("Secure sign-in needed", "<p>" + escapeHtml(SIGN_IN_NOTICE) + "</p>");
        const p = ui.props && typeof ui.props === "object" ? ui.props : null;
        if (!PUBLIC_UI_COMPONENTS.has(ui.name) || !p) return "";
        if (ui.name === "CitationList") {
          const steps = renderGuidedSteps(p.guided_steps);
          return steps ? cardHtml("Steps", steps) : "";
        }
        if (ui.name === "CalculatorForm") return renderCalculatorCard(p, citationCount);
        if (ui.name === "PaymentInstructionsCard") return renderPaymentCheckCard(p);
        if (!isFilledText(p.reason)) return "";
        return cardHtml(
          "SSRA staff help",
          "<p>An SSRA officer needs to answer this question. SSRA Assist can’t confirm officer availability or contact hours here.</p>" +
            "<p>For SSRA contact information, use the official e-Tax portal: " + OFFICIAL_PORTAL + "</p>",
        );
      }

      function renderCitations(citations) {
        if (!Array.isArray(citations) || citations.length === 0) return "";
        return '<ul class="ssra-citation-badges" aria-label="Approved sources">' + citations.map((c) => {
          const label = [c?.doc_title, c?.section_anchor].filter(isFilledText).join(" · ") || "Source";
          const detail = [
            isFilledText(c?.effective_from) ? "effective from " + c.effective_from : "",
            isFilledText(c?.snapshot_version) ? "version " + c.snapshot_version : "",
          ].filter(Boolean).join(", ");
          const text = ICONS.bookOpen + " " + escapeHtml(label) + (detail ? " (" + escapeHtml(detail) + ")" : "");
          const href = typeof c?.url === "string" && c.url.startsWith("https://") ? c.url : "";
          return '<li class="citation-pill">' + (href ? '<a class="citation-link" href="' + escapeHtml(href) + '" rel="noopener noreferrer">' + text + "</a>" : text) + "</li>";
        }).join("") + "</ul>";
      }

      function renderTrustPills(meta) {
        if (meta.kind === "failure") return '<div class="turn-meta-bar"><span class="meta-pill caution">' + ICONS.alertTriangle + " Not answered</span></div>";
        const count = Array.isArray(meta.citations) ? meta.citations.length : 0;
        const pills = [
          count > 0
            ? '<span class="meta-pill verified">' + ICONS.bookOpen + " " + count + (count === 1 ? " approved source" : " approved sources") + "</span>"
            : '<span class="meta-pill caution">No source cited</span>',
        ];
        if (meta.outcome_verified === false) pills.push('<span class="meta-pill caution">Not fully verified</span>');
        if (meta.is_estimate === true) pills.push('<span class="meta-pill">Estimate</span>');
        return '<div class="turn-meta-bar">' + pills.join("") + "</div>";
      }

      function renderTurnHtml(turn, index) {
        if (turn.role === "user") {
          return '<article class="message-row message-row-user"><div class="bubble user">' + escapeHtml(turn.content) + "</div></article>";
        }
        const meta = turn.meta || {};
        if (meta.kind === "pending") {
          const grid = '<span class="lds-grid" aria-hidden="true">' + '<span class="lds-cell"></span>'.repeat(9) + "</span>";
          return '<article class="message-row message-row-assistant" aria-busy="true"><div class="avatar assistant" aria-hidden="true">' + ICONS.ssraCrest + '</div><div class="bubble assistant"><div class="lds">' + grid + '<div class="turn-content-text">' + escapeHtml(turn.content) + "</div></div></div></article>";
        }
        const citationCount = Array.isArray(meta.citations) ? meta.citations.length : 0;
        const actions = meta.kind === "failure"
          ? (isFilledText(meta.retry_text) ? '<button type="button" class="turn-act-btn" data-retry-turn="' + index + '">' + ICONS.refresh + " Try again</button>" : "")
          : '<button type="button" class="turn-act-btn" data-speak="' + escapeHtml(turn.content) + '">' + ICONS.speaker + " Listen</button>" +
            '<button type="button" class="turn-act-btn" data-copy="' + escapeHtml(turn.content) + '">' + ICONS.copy + " Copy</button>" +
            (isFilledText(meta.thread_id)
              ? '<button type="button" class="turn-act-btn" data-csat="5" data-thread-id="' + escapeHtml(meta.thread_id) + '">' + ICONS.thumbUp + " Helpful</button>" +
                '<button type="button" class="turn-act-btn" data-csat="1" data-thread-id="' + escapeHtml(meta.thread_id) + '">' + ICONS.thumbDown + " Not helpful</button>"
              : "");

        return '<article class="message-row message-row-assistant">' +
          '<div class="avatar assistant" aria-hidden="true">' + ICONS.ssraCrest + "</div>" +
          '<div class="bubble assistant">' +
            renderTrustPills(meta) +
            '<div class="turn-content-text">' + escapeHtml(turn.content) + "</div>" +
            (meta.kind === "failure" ? "" : renderPublicCard(meta.ui_component, citationCount)) +
            (meta.needs_sign_in || meta.pending_confirmation ? cardHtml("Secure sign-in needed", "<p>" + escapeHtml(SIGN_IN_NOTICE) + "</p>") : "") +
            renderCitations(meta.citations) +
            (actions ? '<div class="turn-actions">' + actions + "</div>" : "") +
          "</div>" +
        "</article>";
      }

      function renderConvRow(c) {
        const active = c.id === state.activeId ? " active" : "";
        return '<li class="rail-row' + active + '">' +
          '<button type="button" class="rail-item" data-conv-id="' + escapeHtml(c.id) + '" aria-label="Open conversation: ' + escapeHtml(c.title) + '"' + (active ? ' aria-current="true"' : "") + '>' +
            '<span class="rail-item-dot" aria-hidden="true"></span>' +
            '<span class="rail-item-title">' + (c.pinned ? ICONS.pin + " " : "") + escapeHtml(c.title) + "</span>" +
          "</button>" +
          '<div class="rail-row-actions">' +
            '<button type="button" class="rail-act-mini" data-pin-conv="' + escapeHtml(c.id) + '" aria-label="' + (c.pinned ? "Unpin" : "Pin") + ' conversation: ' + escapeHtml(c.title) + '" title="' + (c.pinned ? "Unpin" : "Pin") + ' conversation">' + ICONS.pin + "</button>" +
            '<button type="button" class="rail-act-mini" data-rename-conv="' + escapeHtml(c.id) + '" aria-label="Rename conversation: ' + escapeHtml(c.title) + '" title="Rename conversation">' + ICONS.edit + "</button>" +
            '<button type="button" class="rail-act-mini" data-del-conv="' + escapeHtml(c.id) + '" aria-label="Delete conversation: ' + escapeHtml(c.title) + '" title="Delete conversation">' + ICONS.trash + "</button>" +
          "</div>" +
        "</li>";
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

      // Rebuild only the turns that changed, and open long conversations progressively: rewriting
      // a long transcript on every update made 80-turn interactions exceed 200 ms (AUD-029).
      const FIRST_PAINT_TURNS = 30;
      const PREPEND_CHUNK_TURNS = 20;
      let renderedTranscript = { convId: null, turnHtml: [], offset: 0 };
      let prependTimer = 0;

      function appendTurnHtml(htmlList, prepend) {
        const holder = document.createElement("div");
        setSafeHtml(holder, htmlList.join(""));
        if (prepend) msgList.prepend(...holder.children);
        else msgList.append(...holder.children);
      }

      function prependEarlierTurns(convId) {
        const rt = renderedTranscript;
        if (rt.convId !== convId || rt.offset === 0) return;
        const start = Math.max(0, rt.offset - PREPEND_CHUNK_TURNS);
        const scroller = msgList.scrollHeight > msgList.clientHeight + 1 ? msgList : document.querySelector(".app-main-col");
        const anchor = msgList.lastElementChild;
        const anchorTop = anchor ? anchor.getBoundingClientRect().top : 0;
        appendTurnHtml(rt.turnHtml.slice(start, rt.offset), true);
        // Keep the latest turn where it was; a no-op where the browser's scroll anchoring already did.
        if (scroller && anchor) scroller.scrollTop += anchor.getBoundingClientRect().top - anchorTop;
        renderedTranscript = { ...rt, offset: start };
        if (start > 0) prependTimer = window.setTimeout(() => prependEarlierTurns(convId), 0);
      }

      function renderTranscript(conv) {
        const turnHtml = conv.turns.map(renderTurnHtml);
        const prev = renderedTranscript;
        const domMatches = prev.convId === conv.id && msgList.children.length === prev.turnHtml.length - prev.offset;
        const unchangedBeforeOffset = domMatches && prev.turnHtml.slice(0, prev.offset).every((h, i) => h === turnHtml[i]);
        if (unchangedBeforeOffset) {
          let first = prev.offset;
          while (first < turnHtml.length && turnHtml[first] === prev.turnHtml[first]) first += 1;
          while (msgList.children.length > first - prev.offset) msgList.lastElementChild.remove();
          if (first < turnHtml.length) appendTurnHtml(turnHtml.slice(first), false);
          renderedTranscript = { convId: conv.id, turnHtml, offset: prev.offset };
          return;
        }
        window.clearTimeout(prependTimer);
        const offset = Math.max(0, turnHtml.length - FIRST_PAINT_TURNS);
        setSafeHtml(msgList, turnHtml.slice(offset).join(""));
        renderedTranscript = { convId: conv.id, turnHtml, offset };
        if (offset > 0) prependTimer = window.setTimeout(() => prependEarlierTurns(conv.id), 0);
      }

      let renderedRailHtml = null;
      function renderApp() {
        const activeConv = state.conversations.find((c) => c.id === state.activeId) || null;
        const deviceNote = document.getElementById("rail-device-note");
        if (deviceNote) {
          deviceNote.textContent = state.saveHistory
            ? "Conversations are saved on this device only. On a shared device, delete them in Settings."
            : "Conversations are not saved. They disappear when you close or reload this page.";
        }
        if (convListEl) {
          const railHtml = state.conversations.length === 0
            ? '<p class="rail-empty-hint">No saved conversations yet. Start a conversation to keep it on this device.</p>'
            : groupConversationRows(state.conversations).map(([label, rows]) =>
                '<h2 class="rail-section-label">' + escapeHtml(label) + '</h2><ul class="rail-group">' + rows.map(renderConvRow).join("") + "</ul>"
              ).join("");
          if (railHtml !== renderedRailHtml) {
            setSafeHtml(convListEl, railHtml);
            renderedRailHtml = railHtml;
          }
        }
        if (!activeConv || activeConv.turns.length === 0) {
          landingView?.classList.remove("is-hidden");
          chatView?.classList.add("is-hidden");
          if (activeTitleEl) activeTitleEl.textContent = "New Conversation";
          window.clearTimeout(prependTimer);
          renderedTranscript = { convId: null, turnHtml: [], offset: 0 };
        } else {
          landingView?.classList.add("is-hidden");
          chatView?.classList.remove("is-hidden");
          if (activeTitleEl) activeTitleEl.textContent = activeConv.title;
          if (msgList) {
            renderTranscript(activeConv);
            const lastTurn = msgList.lastElementChild;
            const visibleHeight = Math.min(msgList.clientHeight, window.innerHeight);
            lastTurn?.scrollIntoView({ block: lastTurn.offsetHeight > visibleHeight ? "start" : "end" });
          }
        }
      }

      let activeTurnAbortController = null;
      const TURN_TIMEOUT_MS = 30000;

      const SPEECH_LANGS = { en: "en", ar: "ar" };
      const POST_TTS_ECHO_COOLDOWN_MS = 450;
      const MAX_VOICE_EMPTY_RETRIES = 3;
      const VOICE_BACKCHANNELS = new Set(["mm", "mmm", "mm hm", "mmhm", "uh huh", "okay", "ok", "i see", "right", "got it", "نعم", "تمام", "ايوه", "أيوة"]);
      let activeSpeechRec = null;
      let activeUtterance = null;
      let voiceContinuousActive = false;
      let voiceConsecutiveEmptyRetries = 0;
      let lastSpokenAssistantText = "";
      let lastTtsEndedAtMs = 0;
      let ttsKeepAliveTimer = null;
      let postTtsResumeTimer = null;
      let assistantCurrentlySpeaking = false;
      let callSpeechRateSlow = false;
      let voiceSilenceTimeoutMs = 1200;
      let lastHeardVoiceTranscript = "";

      function speechUtterance(text) {
        const utterance = new SpeechSynthesisUtterance(cleanTextForSpeech(text));
        if (SPEECH_LANGS[state.locale]) utterance.lang = SPEECH_LANGS[state.locale];
        utterance.rate = callSpeechRateSlow ? 0.82 : 1.0;
        return utterance;
      }

      function cleanTextForSpeech(raw) {
        return String(raw || "")
          .replace(/\\s*\\[\\d+(?:\\s*[,;]\\s*\\d+)*\\](?!\\()/g, "")
          .replace(/\\[([^\\]]+)\\]\\([^\\)]+\\)/g, "$1")
          .replace(/https?:\\/\\/etax\\.nra\\.gov\\.ss\\/?/gi, "e-tax dot n r a dot gov dot s s")
          .replace(/https?:\\/\\/\\S+/g, "web link")
          .replace(/••••(\\d{4})/g, (_, d) => "T I N ending in " + d.split("").join(" "))
          .replace(/\\bSec\\.\\s*(\\d+[A-Za-z]?)\\b/g, "Section $1")
          .replace(/\\bArt\\.\\s*(\\d+[A-Za-z]?)\\b/g, "Article $1")
          .replace(/[*_\\x60#~>-]+/g, " ")
          .replace(/\\s+/g, " ")
          .trim();
      }

      function normalizeSpeechTokens(text) {
        const matches = String(text || "").toLowerCase().match(/[\\p{L}\\p{N}]+/gu);
        return matches ? matches.filter(Boolean) : [];
      }

      function isBackchannelUtterance(text) {
        const tokens = normalizeSpeechTokens(text);
        return tokens.length > 0 && tokens.length <= 2 && VOICE_BACKCHANNELS.has(tokens.join(" "));
      }

      function isLikelyAssistantEcho(transcript, lastAssistantText, elapsedMs) {
        const callerTokens = normalizeSpeechTokens(transcript);
        const assistantTokens = normalizeSpeechTokens(lastAssistantText);
        if (!callerTokens.length || !assistantTokens.length) return false;
        const callerJoined = callerTokens.join(" ");
        const assistantJoined = assistantTokens.join(" ");
        const callerPadded = " " + callerJoined + " ";
        const assistantPadded = " " + assistantJoined + " ";
        const assistantSet = new Set(assistantTokens);
        const matched = callerTokens.filter((t) => assistantSet.has(t)).length;
        const overlap = matched / callerTokens.length;
        const inTail = typeof elapsedMs === "number" && Number.isFinite(elapsedMs) && elapsedMs <= POST_TTS_ECHO_COOLDOWN_MS;
        if (inTail && (assistantPadded.includes(callerPadded) || (callerTokens.length >= 2 && overlap >= 0.75))) {
          return true;
        }
        return callerTokens.length >= 4 && (assistantPadded.includes(callerPadded) || overlap >= 0.85);
      }

      function stopActiveSpeechRecognition() {
        if (postTtsResumeTimer) {
          window.clearTimeout(postTtsResumeTimer);
          postTtsResumeTimer = null;
        }
        if (activeSpeechRec) {
          const rec = activeSpeechRec;
          activeSpeechRec = null;
          rec.onresult = null;
          rec.onerror = null;
          rec.onend = null;
          try {
            rec.stop();
          } catch {}
        }
      }

      function stopAssistantSpeechPlayback() {
        if (ttsKeepAliveTimer) {
          window.clearInterval(ttsKeepAliveTimer);
          ttsKeepAliveTimer = null;
        }
        activeUtterance = null;
        assistantCurrentlySpeaking = false;
        if ("speechSynthesis" in window) {
          window.speechSynthesis.cancel();
        }
        document.querySelectorAll("[data-speak]").forEach((btn) => {
          setSafeHtml(btn, ICONS.speaker + " Listen");
        });
      }

      function newThreadId() {
        const bytes = new Uint8Array(16);
        crypto.getRandomValues(bytes);
        return "thr_web_" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      }

      function failureTurn(content, retryText) {
        return {
          role: "assistant",
          content,
          meta: { tier: "T0", kind: "failure", outcome_verified: false, citations: [], retry_text: retryText },
        };
      }

      // Describe only what the HTTP status tells us; never show a raw error body.
      function describeHttpFailure(status, retryAfter) {
        if (status === 429) {
          const seconds = Number.parseInt(String(retryAfter || ""), 10);
          return "Too many questions were sent in a short time, so this one wasn’t answered. " +
            (Number.isFinite(seconds) && seconds > 0 ? "Wait " + seconds + " seconds, then try again." : "Wait a moment, then try again.");
        }
        if (status === 413) return "Your message is too long to send. Shorten it and try again.";
        if (status === 400 || status === 422) return "SSRA Assist couldn’t read this request, so it wasn’t answered. Edit your message and try again.";
        if (status === 401 || status === 403) return "This request isn’t available in public chat. " + SIGN_IN_NOTICE;
        if (status === 503) return "SSRA Assist isn’t available right now, so your question wasn’t answered. Try again later, or use the official e-Tax portal: " + OFFICIAL_PORTAL;
        if (status === 502 || status === 504) return "SSRA Assist didn’t reply in time, so your question may not have been answered. You can try again.";
        return "Something went wrong at SSRA Assist, so your question wasn’t answered. You can try again.";
      }

      const announcer = document.getElementById("chat-announcer");
      function announce(message) {
        if (!announcer) return;
        announcer.textContent = "";
        window.setTimeout(() => {
          announcer.textContent = message;
        }, 60);
      }
      function announceReply(reply) {
        const text = String(reply.content || "");
        const summary = text.length > 280 ? text.slice(0, 277) + "…" : text;
        announce((reply.meta?.kind === "failure" ? "Not answered. " : "Answer received. ") + summary);
      }

      function restoreDraft(text) {
        if (!input || input.value.trim()) return false;
        input.value = text;
        return true;
      }

      async function sendTurn(text, opts) {
        if (activeTurnAbortController) return;
        const trimmed = String(text || "").trim();
        if (!trimmed) return;
        const fromVoiceLoop = Boolean(opts && opts.fromVoiceLoop);

        let conv = state.conversations.find((c) => c.id === state.activeId);
        if (!conv) {
          conv = {
            id: newThreadId(),
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
        if (fromVoiceLoop || voiceContinuousActive || callBackdrop?.classList.contains("open")) {
          appendCallCaption("caller", trimmed);
        }

        if (navigator.onLine === false) {
          const offline = computeOfflineResilienceAnswer(trimmed);
          const offlineReply = { role: "assistant", content: offline.content, meta: offline.meta };
          conv.turns.push(offlineReply);
          if (fromVoiceLoop || voiceContinuousActive || callBackdrop?.classList.contains("open")) {
            appendCallCaption("assistant", offline.content);
          }
          restoreDraft(trimmed);
          saveState();
          renderApp();
          announceReply(offlineReply);
          if (voiceContinuousActive && !assistantCurrentlySpeaking && !activeSpeechRec) {
            setVoiceStatus("Listening for your next question…");
            scheduleNextVoiceTurnListen();
          }
          return;
        }

        conv.turns.push({ role: "assistant", content: "Preparing an answer…", meta: { tier: "T0", kind: "pending" } });
        renderApp();
        announce("Preparing an answer.");

        const payload = {
          message: trimmed,
          thread_id: conv.id,
          locale: state.locale,
          channel: "web",
          low_data_mode: Boolean(state.lowDataMode),
          auth_level: "ANONYMOUS",
          subject_ref: null,
        };

        const controller = new AbortController();
        activeTurnAbortController = controller;
        let timedOut = false;
        const timeoutId = window.setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, TURN_TIMEOUT_MS);
        if (submitBtn) {
          submitBtn.type = "button";
          setSafeHtml(submitBtn, ICONS.stop + " Stop");
        }
        let reply;
        try {
          const res = await fetch("/api/turns", {
            method: "POST",
            headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
            body: JSON.stringify(payload),
            signal: controller.signal,
          });
          let data = null;
          if ((res.headers.get("content-type") || "").includes("json")) {
            try {
              data = await res.json();
            } catch {
              data = null;
            }
          }
          const segments = Array.isArray(data?.answer?.segments) ? data.answer.segments : [];
          const replyText = segments.map((s) => (typeof s?.text === "string" ? s.text : "")).join(" ").trim();
          if (!res.ok) {
            reply = failureTurn(describeHttpFailure(res.status, res.headers.get("retry-after")), trimmed);
          } else if (!replyText) {
            reply = failureTurn("SSRA Assist sent a reply it couldn’t display, so your question wasn’t answered. You can try again.", trimmed);
          } else {
            const answerCitations = Array.isArray(data.answer.citations) ? data.answer.citations : [];
            reply = {
              role: "assistant",
              content: replyText,
              meta: {
                tier: typeof data.tier === "string" ? data.tier : "T0",
                kind: "answer",
                outcome_verified: typeof data.outcome_verified === "boolean" ? data.outcome_verified : null,
                is_estimate: data.answer.is_estimate === true,
                ui_component: data.answer.ui_component || null,
                needs_sign_in: Boolean(data.pending_confirmation),
                citations: answerCitations.length > 0 ? answerCitations : Array.isArray(data.citations) ? data.citations : [],
                thread_id: typeof data.thread_id === "string" ? data.thread_id : conv.id,
              },
            };
            if ((state.autoNarrate || fromVoiceLoop || voiceContinuousActive) && "speechSynthesis" in window) {
              speakAssistantReply(replyText);
            }
          }
        } catch (err) {
          if (err && err.name === "AbortError" && !timedOut) {
            reply = failureTurn("You stopped this answer before it arrived.", trimmed);
          } else if (timedOut) {
            reply = failureTurn(describeHttpFailure(504), trimmed);
          } else {
            const offline = computeOfflineResilienceAnswer(trimmed, { sent: true });
            reply = { role: "assistant", content: offline.content, meta: offline.meta };
          }
        } finally {
          window.clearTimeout(timeoutId);
          activeTurnAbortController = null;
          if (submitBtn) {
            submitBtn.type = "submit";
            setSafeHtml(submitBtn, ICONS.send + " Send");
          }
        }
        conv.turns[conv.turns.length - 1] = reply;
        if (fromVoiceLoop || voiceContinuousActive || callBackdrop?.classList.contains("open")) {
          lastSpokenAssistantText = cleanTextForSpeech(reply.content);
          document.getElementById("call-repeat-btn")?.classList.remove("is-hidden");
          document.getElementById("call-more-detail-btn")?.classList.remove("is-hidden");
          appendCallCaption("assistant", reply.content);
        }
        if (reply.meta?.kind === "failure" && hintEl) {
          hintEl.textContent = restoreDraft(trimmed)
            ? "Not answered. Your message is back in the box."
            : "Not answered.";
        }
        saveState();
        renderApp();
        announceReply(reply);
        if (voiceContinuousActive && !assistantCurrentlySpeaking && !activeSpeechRec) {
          setVoiceStatus("Listening for your next question…");
          scheduleNextVoiceTurnListen();
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
          if (!c) return;
          askInPage({
            title: "Rename conversation",
            message: "Conversation names are saved only on this device.",
            confirmLabel: "Save name",
            value: c.title,
          }).then((nextTitle) => {
            if (typeof nextTitle !== "string" || !nextTitle.trim()) return;
            c.title = nextTitle.trim().slice(0, 64);
            saveState();
            renderApp();
            focusRailAction("data-rename-conv", cid);
          });
          return;
        }
        const delBtn = e.target.closest("[data-del-conv]");
        if (delBtn) {
          const cid = delBtn.getAttribute("data-del-conv");
          askInPage({
            title: "Delete this conversation?",
            message: "It will be removed from this device. This cannot be undone.",
            confirmLabel: "Delete conversation",
            destructive: true,
          }).then((confirmed) => {
            if (confirmed !== true) return;
            state.conversations = state.conversations.filter((x) => x.id !== cid);
            if (state.activeId === cid) state.activeId = state.conversations[0]?.id || null;
            saveState();
            renderApp();
            const nextConversation = convListEl?.querySelector(".rail-item");
            if (nextConversation) nextConversation.focus();
            else document.getElementById("new-chat-btn")?.focus();
          });
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
        const retryBtn = e.target.closest("[data-retry-turn]");
        if (retryBtn) {
          const conv = state.conversations.find((c) => c.id === state.activeId);
          const index = Number(retryBtn.getAttribute("data-retry-turn"));
          const retryText = conv?.turns[index]?.meta?.retry_text;
          if (!conv || !retryText || activeTurnAbortController || conv.turns[index - 1]?.role !== "user") return;
          conv.turns.splice(index - 1, 2);
          if (input && input.value.trim() === retryText) input.value = "";
          input?.focus();
          sendTurn(retryText);
          return;
        }
        const speakBtn = e.target.closest("[data-speak]");
        if (speakBtn && "speechSynthesis" in window) {
          if (assistantCurrentlySpeaking || window.speechSynthesis.speaking) {
            stopAssistantSpeechPlayback();
            syncNarrationBar(false, "");
            syncComposerRecordingUi();
            return;
          }
          setSafeHtml(speakBtn, ICONS.stop + " Stop Audio");
          speakAssistantReply(speakBtn.getAttribute("data-speak") || "");
          return;
        }
        const copyBtn = e.target.closest("[data-copy]");
        if (copyBtn) {
          const showCopyResult = (copied) =>
            setSafeHtml(copyBtn, copied ? ICONS.check + " Copied" : ICONS.alertTriangle + " Copy failed");
          if (!navigator.clipboard?.writeText) {
            showCopyResult(false);
            return;
          }
          navigator.clipboard.writeText(copyBtn.getAttribute("data-copy") || "").then(
            () => showCopyResult(true),
            () => showCopyResult(false),
          );
          return;
        }
        const csatBtn = e.target.closest("[data-csat]");
        if (csatBtn) {
          const csatScore = Number(csatBtn.getAttribute("data-csat")) || 5;
          const convId = csatBtn.getAttribute("data-thread-id");
          if (!convId) return;
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
                  ? ICONS.check + " Feedback sent"
                  : ICONS.alertTriangle + " Not sent · try again",
              );
            })
            .catch(() => {
              setSafeHtml(csatBtn, ICONS.alertTriangle + " Not sent · try again");
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

      const railAsideEl = document.querySelector(".rail-wrap");
      const focusAfterRailStateSync = (target) => {
        if (!target || typeof target.focus !== "function") return;
        const activeBeforeSync = document.activeElement;
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            const focusWasMovedByAnotherInteraction =
              document.activeElement !== activeBeforeSync && document.activeElement !== document.body;
            if (!focusWasMovedByAnotherInteraction && target.isConnected && !target.closest("[inert]")) {
              target.focus({ preventScroll: true });
            }
          });
        });
      };
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
          focusAfterRailStateSync(headerRailBtn);
        } else if (moveFocus && !isHidden) {
          focusAfterRailStateSync(document.getElementById("new-chat-btn"));
        }
      };
      const toggleSidebar = () => {
        const isMobileViewport = window.matchMedia?.("(max-width: 960px)")?.matches ?? false;
        shell?.removeAttribute("data-rail-peek");
        if (isMobileViewport) {
          const mob = shell?.getAttribute("data-mobile-rail");
          shell?.setAttribute("data-mobile-rail", mob === "open" ? "closed" : "open");
        } else {
          const cur = shell?.getAttribute("data-sidebar");
          shell?.setAttribute("data-sidebar", cur === "collapsed" ? "open" : "collapsed");
        }
        syncMobileRailA11y(true);
      };
      const setRailPeek = (peek) => {
        const isMobileViewport = window.matchMedia?.("(max-width: 960px)")?.matches ?? false;
        if (isMobileViewport || shell?.getAttribute("data-sidebar") !== "collapsed") {
          shell?.removeAttribute("data-rail-peek");
          return;
        }
        if (peek) {
          shell?.setAttribute("data-rail-peek", "true");
          railAsideEl?.removeAttribute("inert");
        } else {
          shell?.removeAttribute("data-rail-peek");
          railAsideEl?.setAttribute("inert", "");
        }
      };
      document.getElementById("rail-hotzone")?.addEventListener("mouseenter", () => setRailPeek(true));
      railAsideEl?.addEventListener("mouseleave", () => {
        if (shell?.getAttribute("data-rail-peek") === "true") setRailPeek(false);
      });
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
        state.themeChosen = true;
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
        document.documentElement.setAttribute("data-low-data", String(Boolean(state.lowDataMode)));
        badge.setAttribute("data-connection", offline ? "offline" : lowData ? "low-data" : "available");
        txt.textContent = offline
          ? "Offline · reconnect to get current guidance"
          : lowData
            ? "Low-data mode · online"
            : "Online";
      }
      window.addEventListener("online", syncNetworkStatusBadge);
      window.addEventListener("offline", syncNetworkStatusBadge);
      syncNetworkStatusBadge();

      // AccountRail disclosure: Escape or leaving the footer closes it.
      function setAcctPopover(open, returnFocus) {
        acctPopover?.classList.toggle("open", open);
        acctTrigger?.setAttribute("aria-expanded", String(open));
        if (!open && returnFocus) acctTrigger?.focus();
      }
      acctTrigger?.addEventListener("click", (e) => {
        e.stopPropagation();
        setAcctPopover(!acctPopover?.classList.contains("open"), false);
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".rail-footer")) setAcctPopover(false, false);
      });
      document.querySelector(".rail-footer")?.addEventListener("focusout", (e) => {
        if (!(e.relatedTarget instanceof Node) || !e.currentTarget.contains(e.relatedTarget)) setAcctPopover(false, false);
      });

      // Modal stack (FE-G6): the page behind an open dialog is inert, Escape closes the
      // top dialog, and focus returns to the control that opened it.
      const modalStack = [];
      function syncModalInert() {
        shell?.toggleAttribute("inert", modalStack.length > 0);
        modalStack.forEach((entry, i) => entry.backdrop.toggleAttribute("inert", i < modalStack.length - 1));
      }
      function openModal(backdrop, focusTarget, returnFocusEl) {
        if (!backdrop || modalStack.some((entry) => entry.backdrop === backdrop)) return;
        modalStack.push({ backdrop, returnFocusEl: returnFocusEl || document.activeElement, onClose: null });
        backdrop.classList.add("open");
        syncModalInert();
        focusTarget?.focus();
      }
      function closeTopModal() {
        const entry = modalStack.pop();
        if (!entry) return;
        entry.backdrop.classList.remove("open");
        entry.backdrop.removeAttribute("inert");
        syncModalInert();
        entry.onClose?.();
        if (entry.returnFocusEl?.isConnected && !entry.returnFocusEl.closest("[inert]")) entry.returnFocusEl.focus();
      }
      function closeAllModals() {
        while (modalStack.length > 0) closeTopModal();
      }

      // In-page confirmation and rename dialog. Resolves true, the entered text, or null.
      const confirmBackdrop = document.getElementById("confirm-modal-backdrop");
      const confirmField = document.getElementById("confirm-modal-field");
      const confirmInput = document.getElementById("confirm-modal-input");
      const confirmOk = document.getElementById("confirm-modal-ok");
      let resolveConfirm = null;
      function askInPage({ title, message, confirmLabel, value, destructive }) {
        return new Promise((resolve) => {
          const wantsText = typeof value === "string";
          document.getElementById("confirm-modal-title").textContent = title;
          document.getElementById("confirm-modal-message").textContent = message;
          if (confirmOk) {
            confirmOk.textContent = confirmLabel;
            confirmOk.classList.toggle("danger-outline-btn", Boolean(destructive));
          }
          confirmField?.classList.toggle("is-hidden", !wantsText);
          if (confirmInput) confirmInput.value = wantsText ? value : "";
          resolveConfirm = resolve;
          openModal(confirmBackdrop, wantsText ? confirmInput : document.getElementById("confirm-modal-cancel"));
          const entry = modalStack[modalStack.length - 1];
          if (entry?.backdrop === confirmBackdrop) {
            entry.onClose = () => {
              const pending = resolveConfirm;
              resolveConfirm = null;
              pending?.(null);
            };
          }
          if (wantsText) confirmInput?.select();
        });
      }
      document.getElementById("confirm-modal-form")?.addEventListener("submit", (e) => {
        e.preventDefault();
        const pending = resolveConfirm;
        resolveConfirm = null;
        const result = confirmField?.classList.contains("is-hidden") ? true : confirmInput?.value || "";
        closeTopModal();
        pending?.(result);
      });
      document.getElementById("confirm-modal-cancel")?.addEventListener("click", closeTopModal);
      confirmBackdrop?.addEventListener("click", (e) => {
        if (e.target === confirmBackdrop) closeTopModal();
      });

      // ConversationSearch Modal (Ctrl+K — ConversationSearch.tsx pattern)
      const searchBackdrop = document.getElementById("search-modal-backdrop");
      const searchInput = document.getElementById("conv-search-input");
      const searchResults = document.getElementById("conv-search-results");
      let searchActiveIdx = 0;
      function getSearchMatches() {
        const q = (searchInput?.value || "").trim().toLocaleLowerCase();
        return state.conversations.filter((c) => !q || c.title.toLocaleLowerCase().includes(q));
      }
      function selectSearchConversation(convId) {
        if (!convId) return;
        state.activeId = convId;
        closeAllModals();
        renderApp();
        if (window.matchMedia?.("(max-width: 960px)")?.matches) {
          shell?.setAttribute("data-mobile-rail", "closed");
          syncMobileRailA11y(false);
        }
        input?.focus();
      }
      function renderSearchModalList() {
        const q = (searchInput?.value || "").trim().toLocaleLowerCase();
        const matches = getSearchMatches();
        if (searchActiveIdx >= matches.length) searchActiveIdx = 0;
        let html = matches.map((c, idx) =>
          '<button type="button" class="acct-pop-item' + (idx === searchActiveIdx ? " active" : "") + '" data-jump-conv="' + escapeHtml(c.id) + '" data-active="' + (idx === searchActiveIdx) + '"><span>' + ICONS.messageSquare + " " + escapeHtml(c.title) + '</span><span class="jump-open-tag">Open</span></button>'
        ).join("");
        if (!matches.length && q) {
          html = '<p class="rail-empty-hint" role="status">No saved conversations match this search.</p>';
        } else if (!matches.length) {
          html = '<p class="rail-empty-hint" role="status">No saved conversations yet.</p>';
        }
        setSafeHtml(searchResults, html);
        searchResults?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
      }
      function openSearchModal() {
        if (searchInput) searchInput.value = "";
        searchActiveIdx = 0;
        renderSearchModalList();
        openModal(searchBackdrop, searchInput);
      }
      document.getElementById("rail-search-btn")?.addEventListener("click", openSearchModal);
      searchBackdrop?.addEventListener("click", (e) => {
        if (e.target === searchBackdrop) closeAllModals();
      });
      searchInput?.addEventListener("input", () => {
        searchActiveIdx = 0;
        renderSearchModalList();
      });
      searchInput?.addEventListener("keydown", (e) => {
        const matches = getSearchMatches();
        if (!matches.length) return;
        if (e.key === "ArrowDown") {
          e.preventDefault();
          searchActiveIdx = (searchActiveIdx + 1) % matches.length;
          renderSearchModalList();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          searchActiveIdx = (searchActiveIdx - 1 + matches.length) % matches.length;
          renderSearchModalList();
        } else if (e.key === "Home") {
          e.preventDefault();
          searchActiveIdx = 0;
          renderSearchModalList();
        } else if (e.key === "End") {
          e.preventDefault();
          searchActiveIdx = matches.length - 1;
          renderSearchModalList();
        } else if (e.key === "Enter") {
          e.preventDefault();
          selectSearchConversation(matches[searchActiveIdx]?.id);
        }
      });
      searchResults?.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-jump-conv]");
        if (btn) selectSearchConversation(btn.getAttribute("data-jump-conv"));
      });

      // FE-G6: Interactive 5-Tab SettingsDialog Modal
      const settingsBackdrop = document.getElementById("settings-modal-backdrop");
      const settingsTitleEl = document.getElementById("settings-pane-title");
      const settingsBodyEl = document.getElementById("settings-pane-body");
      const settingsPaneEl = document.getElementById("settings-pane");

      function renderSettingsTabContent(tabId) {
        state.settingsTab = tabId || "general";
        document.querySelectorAll("[data-settings-tab]").forEach((btn) => {
          const isAct = btn.getAttribute("data-settings-tab") === state.settingsTab;
          btn.classList.toggle("active", isAct);
          btn.setAttribute("aria-selected", String(isAct));
          btn.tabIndex = isAct ? 0 : -1;
          if (isAct) settingsPaneEl?.setAttribute("aria-labelledby", btn.id);
        });
        if (state.settingsTab === "voice") {
          if (settingsTitleEl) settingsTitleEl.textContent = "Voice typing & reading";
          const pauseOpts = [
            { value: 0, label: "Off" },
            { value: 800, label: "0.8 s" },
            { value: 1200, label: "1.2 s" },
            { value: 2000, label: "2 s" },
          ];
          const pauseButtonsHtml = pauseOpts
            .map(
              (opt) =>
                '<button type="button" role="radio" class="setv2-seg-btn" data-voice-pause="' +
                opt.value +
                '" aria-checked="' +
                String(voiceSilenceTimeoutMs === opt.value) +
                '">' +
                opt.label +
                "</button>",
            )
            .join("");
          setSafeHtml(
            settingsBodyEl,
            "<p>Voice typing uses your browser's speech recognition when available and currently supports English and Arabic only. Your browser may process audio outside SSRA. Auto-narration uses browser speech synthesis; available voices vary by device.</p>" +
              '<div class="settings-actions-row">' +
                '<button type="button" class="icon-btn" id="toggle-narrate-btn">' +
                  (state.autoNarrate ? ICONS.speaker + " Auto-Narrate Replies: ON" : ICONS.speakerOff + " Auto-Narrate Replies: OFF") +
                "</button>" +
                '<button type="button" class="icon-btn" id="settings-voice-pace-btn" aria-pressed="' +
                  String(callSpeechRateSlow) +
                '">' +
                  (callSpeechRateSlow ? "Speech pace: Slower (0.82x)" : "Speech pace: Normal (1.0x)") +
                "</button>" +
                '<button type="button" class="icon-btn" id="settings-voice-preview-btn">' +
                  ICONS.play +
                  " Preview voice sample" +
                "</button>" +
              "</div>" +
              '<div class="settings-actions-row" role="radiogroup" aria-label="Send after a pause">' +
                "<span>Send after a pause:</span>" +
                '<div class="setv2-segmented">' +
                  pauseButtonsHtml +
                "</div>" +
              "</div>",
          );
        } else if (state.settingsTab === "profile") {
          if (settingsTitleEl) settingsTitleEl.textContent = "Personal e-Tax services";
          setSafeHtml(
            settingsBodyEl,
            "<p>This public chat does not show personal balances, filing records, or taxpayer identity details.</p>" +
            '<p><a href="https://etax.nra.gov.ss/" rel="noopener noreferrer">Sign in through the official e-Tax portal</a> for personal services.</p>'
          );
        } else if (state.settingsTab === "privacy") {
          if (settingsTitleEl) settingsTitleEl.textContent = "Privacy on this device";
          setSafeHtml(
            settingsBodyEl,
            "<p>Only public questions and answers are saved, and only on this device. Numbers that look like a TIN or phone number are hidden before saving.</p>" +
            '<div class="settings-actions-row">' +
              '<button type="button" id="toggle-history-btn" class="icon-btn">' + ICONS.history + (state.saveHistory ? " Save conversations on this device: ON" : " Save conversations on this device: OFF") + "</button>" +
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
        setAcctPopover(false, false);
        renderSettingsTabContent("general");
        openModal(settingsBackdrop, settingsBackdrop?.querySelector('[data-settings-tab][aria-selected="true"]'), acctTrigger);
      });
      document.getElementById("close-settings-btn")?.addEventListener("click", closeAllModals);
      // APG tabs: arrow keys, Home and End move and select; only the selected tab is in the Tab order.
      document.querySelector(".settings-tablist")?.addEventListener("keydown", (e) => {
        const tabs = Array.from(document.querySelectorAll("[data-settings-tab]"));
        const current = tabs.indexOf(document.activeElement);
        if (current < 0) return;
        const forward = e.key === "ArrowDown" || e.key === "ArrowRight";
        const backward = e.key === "ArrowUp" || e.key === "ArrowLeft";
        const next = forward
          ? (current + 1) % tabs.length
          : backward
            ? (current - 1 + tabs.length) % tabs.length
            : e.key === "Home"
              ? 0
              : e.key === "End"
                ? tabs.length - 1
                : -1;
        if (next < 0) return;
        e.preventDefault();
        renderSettingsTabContent(tabs[next].getAttribute("data-settings-tab"));
        tabs[next].focus();
      });
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
          document.getElementById("toggle-lowdata-btn")?.focus();
          return;
        }
        if (e.target.closest("#toggle-history-btn")) {
          state.saveHistory = !state.saveHistory;
          saveState();
          renderApp();
          renderSettingsTabContent("privacy");
          document.getElementById("toggle-history-btn")?.focus();
          return;
        }
        if (e.target.closest("#toggle-narrate-btn")) {
          state.autoNarrate = !state.autoNarrate;
          if (!state.autoNarrate) {
            voiceContinuousActive = false;
            stopActiveSpeechRecognition();
            stopAssistantSpeechPlayback();
            syncNarrationBar(false, "");
          }
          saveState();
          syncVoiceModalButtons();
          renderSettingsTabContent("voice");
          document.getElementById("toggle-narrate-btn")?.focus();
          return;
        }
        const pauseBtn = e.target.closest("[data-voice-pause]");
        if (pauseBtn) {
          voiceSilenceTimeoutMs = Number.parseInt(pauseBtn.getAttribute("data-voice-pause") || "1200", 10);
          renderSettingsTabContent("voice");
          settingsBackdrop?.querySelector('[data-voice-pause="' + voiceSilenceTimeoutMs + '"]')?.focus();
          return;
        }
        if (e.target.closest("#settings-voice-pace-btn")) {
          callSpeechRateSlow = !callSpeechRateSlow;
          const paceBtn = document.getElementById("call-pace-btn");
          if (paceBtn) {
            paceBtn.classList.toggle("is-active", callSpeechRateSlow);
            paceBtn.setAttribute("aria-pressed", String(callSpeechRateSlow));
            paceBtn.textContent = callSpeechRateSlow ? "Normal pace" : "Slower pace";
          }
          renderSettingsTabContent("voice");
          document.getElementById("settings-voice-pace-btn")?.focus();
          return;
        }
        if (e.target.closest("#settings-voice-preview-btn")) {
          const sample =
            state.locale === "ar"
              ? "مرحبا، أنا مساعد هيئة الإيرادات في جنوب السودان."
              : "Hello, I am SSRA Assist. I can read tax answers aloud.";
          speakAssistantReply(sample);
          return;
        }
        if (e.target.closest("#purge-local-btn")) {
          askInPage({
            title: "Delete all saved conversations?",
            message: "Every conversation saved on this device will be removed. This cannot be undone.",
            confirmLabel: "Delete all",
            destructive: true,
          }).then((confirmed) => {
            if (confirmed !== true) return;
            state.conversations = [];
            state.activeId = null;
            dispatchSwLogoutPurge();
            saveState();
            renderApp();
            closeAllModals();
            input?.focus();
          });
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
        const openModal = modalStack[modalStack.length - 1]?.backdrop || null;
        if (openModal && e.key === "Tab") {
          trapModalTabFocus(e, openModal);
          return;
        }
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          if (searchBackdrop?.classList.contains("open")) closeAllModals();
          else if (!openModal) openSearchModal();
        } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b" && !openModal) {
          e.preventDefault();
          toggleSidebar();
        } else if (e.key === "Escape") {
          if (openModal) {
            closeTopModal();
          } else if (acctPopover?.classList.contains("open")) {
            setAcctPopover(false, true);
          } else if (shell?.getAttribute("data-mobile-rail") === "open") {
            shell.setAttribute("data-mobile-rail", "closed");
            syncMobileRailA11y(true);
          } else if (activeSpeechRec || voiceContinuousActive) {
            e.preventDefault();
            voiceContinuousActive = false;
            stopActiveSpeechRecognition();
            syncVoiceModalButtons();
            setVoiceStatus("Voice recording cancelled.");
          } else if (assistantCurrentlySpeaking || !narrationBarEl?.classList.contains("is-hidden")) {
            e.preventDefault();
            stopAssistantSpeechPlayback();
            syncNarrationBar(false, "");
            syncComposerRecordingUi();
          }
        }
      });

      const callBackdrop = document.getElementById("call-modal-backdrop");
      const callVoiceStatusEl = document.getElementById("call-voice-status");
      const callListenBtn = document.getElementById("call-listen-btn");
      const callInterruptBtn = document.getElementById("call-interrupt-btn");
      const callStatusPillEl = document.getElementById("call-status-pill");
      const callStatusLabelEl = document.getElementById("call-status-label");
      const callLangChipBtn = document.getElementById("call-lang-chip");
      const callLangChipTextEl = document.getElementById("call-lang-chip-text");
      const callLangMenuEl = document.getElementById("call-lang-menu");
      const callTimerEl = document.getElementById("call-timer");
      const callThreadEl = document.getElementById("call-thread");
      const callJumpBtn = document.getElementById("call-jump-btn");
      const callMuteBtn = document.getElementById("call-mute-btn");
      const callOrbEl = document.getElementById("call-orb");
      const callOfficerBtn = document.getElementById("call-officer-btn");
      const narrationBarEl = document.getElementById("narration-bar");
      const narrationLabelEl = document.getElementById("narration-label");
      const narrationSentenceEl = document.getElementById("narration-sentence");
      const narrationPauseBtn = document.getElementById("narration-pause-btn");
      const narrationStopBtn = document.getElementById("narration-stop-btn");
      const composerRecBarEl = document.getElementById("composer-recording-bar");
      const composerRecCancelBtn = document.getElementById("composer-rec-cancel");
      const composerRecConfirmBtn = document.getElementById("composer-rec-confirm");
      const composerVoiceModeBtn = document.getElementById("composer-voicemode-btn");
      let callMuted = false;
      let callDurationSec = 0;
      let callDurationTimer = null;
      let callPinnedToBottom = true;
      let callLangSource = "auto";
      let narrationPaused = false;

      function formatMmSs(sec) {
        const s = Math.max(0, Math.floor(sec || 0));
        return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
      }

      function syncCallLanguageChipUi() {
        const langName = state.locale === "ar" ? "العربية" : "English";
        const suffix = callLangSource === "chosen" ? " · chosen" : " · auto";
        const label = langName + suffix;
        if (callLangChipTextEl) callLangChipTextEl.textContent = label;
        callLangChipBtn?.setAttribute("aria-label", "Call language: " + label);
        document.querySelectorAll(".call-lang-option[data-call-lang]").forEach((opt) => {
          const isChosen = opt.getAttribute("data-call-lang") === (state.locale === "ar" ? "ar" : "en");
          opt.setAttribute("aria-pressed", String(isChosen));
        });
      }

      function appendCallCaption(speaker, text) {
        if (!callThreadEl || !text) return;
        const row = document.createElement("div");
        if (speaker === "caller") {
          row.className = "call-turn call-turn--caller";
          const b = document.createElement("div");
          b.className = "call-bubble";
          b.textContent = text;
          row.appendChild(b);
        } else if (speaker === "system") {
          const p = document.createElement("p");
          p.className = "call-system-note";
          p.textContent = text;
          callThreadEl.appendChild(p);
        } else {
          row.className = "call-turn call-turn--agent";
          const s = document.createElement("div");
          s.className = "call-say";
          s.textContent = text;
          row.appendChild(s);
        }
        if (speaker !== "system") callThreadEl.appendChild(row);
        if (callPinnedToBottom) {
          callThreadEl.scrollTop = callThreadEl.scrollHeight;
          callJumpBtn?.classList.add("is-hidden");
        } else {
          callJumpBtn?.classList.remove("is-hidden");
        }
      }

      callThreadEl?.addEventListener("scroll", () => {
        if (!callThreadEl) return;
        const dist = callThreadEl.scrollHeight - callThreadEl.scrollTop - callThreadEl.clientHeight;
        callPinnedToBottom = dist < 48;
        callJumpBtn?.classList.toggle("is-hidden", callPinnedToBottom);
      });
      callJumpBtn?.addEventListener("click", () => {
        if (!callThreadEl) return;
        callPinnedToBottom = true;
        callThreadEl.scrollTop = callThreadEl.scrollHeight;
        callJumpBtn.classList.add("is-hidden");
      });

      function syncNarrationBar(active, sentenceText) {
        if (!narrationBarEl) return;
        narrationBarEl.classList.toggle("is-hidden", !active);
        if (!active) {
          narrationPaused = false;
          return;
        }
        if (narrationLabelEl) narrationLabelEl.textContent = narrationPaused ? "Paused" : "Reading aloud";
        if (narrationSentenceEl && typeof sentenceText === "string") narrationSentenceEl.textContent = sentenceText;
        if (narrationPauseBtn) {
          narrationPauseBtn.setAttribute("aria-label", narrationPaused ? "Resume reading" : "Pause reading");
          setSafeHtml(narrationPauseBtn, narrationPaused ? ICONS.play : ICONS.pause);
        }
      }

      function syncComposerRecordingUi() {
        const isListening = Boolean(activeSpeechRec) && !callMuted;
        composerRecBarEl?.classList.toggle("is-hidden", !isListening);
        form?.classList.toggle("is-recording", isListening);
        if (composerRecConfirmBtn) {
          composerRecConfirmBtn.setAttribute(
            "aria-label",
            voiceContinuousActive ? "Send voice recording" : "Stop and insert voice text",
          );
        }
        if (composerVoiceModeBtn) {
          const vmOn = Boolean(voiceContinuousActive);
          composerVoiceModeBtn.classList.toggle("is-active", vmOn);
          composerVoiceModeBtn.setAttribute("aria-pressed", String(vmOn));
          composerVoiceModeBtn.setAttribute(
            "aria-label",
            vmOn ? "Exit voice conversation mode" : "Enter voice conversation mode",
          );
        }
        const isThinking = Boolean(activeTurnAbortController);
        const orbMode = assistantCurrentlySpeaking
          ? "speaking"
          : isThinking
            ? "thinking"
            : isListening
              ? "listening"
              : "idle";
        if (callOrbEl) {
          // Playback (speaking) wins ties over thinking and listening so speaker echo never flickers the orb.
          callOrbEl.setAttribute("data-mode", orbMode);
        }
        const voiceDockEl = document.getElementById("voice-mode-dock");
        const voiceDockOrbEl = document.getElementById("voice-dock-orb");
        const voiceDockLabelEl = document.getElementById("voice-dock-label");
        const voiceDockDetailEl = document.getElementById("voice-dock-detail");
        const voiceDockPauseBtn = document.getElementById("voice-dock-pause");
        const voiceDockMicOffBtn = document.getElementById("voice-dock-mic-off");
        const voiceDockPrimaryBtn = document.getElementById("voice-dock-primary");
        if (voiceDockEl) {
          const showDock = Boolean(voiceContinuousActive) && !callBackdrop?.classList.contains("open");
          voiceDockEl.classList.toggle("is-hidden", !showDock);
          const dockPhase = assistantCurrentlySpeaking
            ? narrationPaused
              ? "paused"
              : "speaking"
            : isThinking
              ? "thinking"
              : isListening
                ? "listening"
                : "idle";
          voiceDockEl.setAttribute("data-phase", dockPhase);
          voiceDockEl.setAttribute("data-floor", orbMode);
          if (voiceDockOrbEl) voiceDockOrbEl.setAttribute("data-mode", orbMode);
          if (voiceDockLabelEl) {
            voiceDockLabelEl.textContent =
              dockPhase === "paused"
                ? "Paused"
                : dockPhase === "speaking"
                  ? "Speaking…"
                  : dockPhase === "thinking"
                    ? "Working on your answer…"
                    : dockPhase === "listening"
                      ? "Listening…"
                      : "Voice mode ready";
          }
          if (voiceDockDetailEl) {
            voiceDockDetailEl.textContent =
              dockPhase === "speaking" || dockPhase === "paused"
                ? lastSpokenAssistantText || "Tap the microphone to interrupt and ask a follow-up."
                : dockPhase === "thinking" && lastHeardVoiceTranscript
                  ? 'You said: "' + lastHeardVoiceTranscript + '"'
                  : voiceSilenceTimeoutMs > 0
                    ? "Speak your question — pauses send automatically."
                    : "Speak your question, then tap Send.";
          }
          voiceDockMicOffBtn?.classList.toggle("is-hidden", dockPhase !== "listening");
          if (voiceDockPauseBtn) {
            const canPause = dockPhase === "speaking" || dockPhase === "paused";
            voiceDockPauseBtn.classList.toggle("is-hidden", !canPause);
            voiceDockPauseBtn.setAttribute("aria-label", narrationPaused ? "Resume reading" : "Pause reading");
            setSafeHtml(voiceDockPauseBtn, narrationPaused ? ICONS.play : ICONS.pause);
          }
          if (voiceDockPrimaryBtn) {
            const action =
              dockPhase === "listening"
                ? "send"
                : dockPhase === "thinking"
                  ? "stop"
                  : dockPhase === "speaking" || dockPhase === "paused"
                    ? "interrupt"
                    : "talk";
            voiceDockPrimaryBtn.setAttribute("data-action", action);
            voiceDockPrimaryBtn.setAttribute(
              "aria-label",
              action === "send"
                ? "Send voice turn now"
                : action === "stop"
                  ? "Stop answer generation"
                  : action === "interrupt"
                    ? "Interrupt and speak"
                    : "Start speaking",
            );
            setSafeHtml(
              voiceDockPrimaryBtn,
              action === "send" ? ICONS.check : action === "stop" ? ICONS.stop : ICONS.mic,
            );
          }
        }
        if (callStatusPillEl && callStatusLabelEl) {
          const curStatus = callStatusPillEl.getAttribute("data-status");
          if (voiceContinuousActive || assistantCurrentlySpeaking || isThinking || isListening) {
            if (curStatus !== "transferring") {
              callStatusPillEl.setAttribute("data-status", "ai");
              callStatusLabelEl.textContent = assistantCurrentlySpeaking
                ? "Speaking · Automated AI"
                : isThinking
                  ? "Thinking · Automated AI"
                  : isListening
                    ? "Listening · Automated AI"
                    : "Connected · Automated AI";
            }
          } else if (curStatus !== "transferring" && curStatus !== "ended") {
            callStatusPillEl.setAttribute("data-status", "consent");
            callStatusLabelEl.textContent = "AI Receptionist · Automated";
          }
        }
      }

      function setVoiceStatus(message) {
        if (callVoiceStatusEl) callVoiceStatusEl.textContent = message;
        if (hintEl) hintEl.textContent = message;
        syncComposerRecordingUi();
      }

      function syncVoiceModalButtons() {
        syncCallLanguageChipUi();
        syncComposerRecordingUi();
        if (voiceContinuousActive && !callDurationTimer) {
          callDurationSec = 0;
          if (callTimerEl) callTimerEl.textContent = "00:00";
          callDurationTimer = window.setInterval(() => {
            callDurationSec += 1;
            if (callTimerEl) callTimerEl.textContent = formatMmSs(callDurationSec);
          }, 1000);
        } else if (!voiceContinuousActive && callDurationTimer) {
          window.clearInterval(callDurationTimer);
          callDurationTimer = null;
        }
        if (!callListenBtn) return;
        if (voiceContinuousActive) {
          callListenBtn.setAttribute("aria-pressed", "true");
          setSafeHtml(callListenBtn, ICONS.stop + " Stop voice conversation");
        } else {
          callListenBtn.setAttribute("aria-pressed", "false");
          setSafeHtml(callListenBtn, ICONS.mic + " Start voice conversation");
        }
      }

      function scheduleNextVoiceTurnListen() {
        if (!voiceContinuousActive || callMuted) return;
        if (postTtsResumeTimer) window.clearTimeout(postTtsResumeTimer);
        postTtsResumeTimer = window.setTimeout(() => {
          postTtsResumeTimer = null;
          if (voiceContinuousActive && !callMuted && !assistantCurrentlySpeaking && !activeTurnAbortController) {
            startVoiceRecognition({ continuousLoop: true });
          }
        }, POST_TTS_ECHO_COOLDOWN_MS);
      }

      function speakAssistantReply(replyText) {
        if (!("speechSynthesis" in window)) return;
        // Pause SpeechRecognition before TTS begins so the mic never records the assistant's own voice.
        stopActiveSpeechRecognition();
        stopAssistantSpeechPlayback();
        const u = speechUtterance(replyText);
        activeUtterance = u;
        lastSpokenAssistantText = cleanTextForSpeech(replyText);
        assistantCurrentlySpeaking = true;
        narrationPaused = false;
        syncNarrationBar(true, lastSpokenAssistantText);
        syncComposerRecordingUi();
        if (voiceContinuousActive) {
          setVoiceStatus("Speaking answer… tap Interrupt & speak at any time to ask a follow-up.");
        }
        // Keep Chromium speechSynthesis awake across long answers (>15s).
        u.onstart = () => {
          if (activeUtterance !== u) return;
          if (ttsKeepAliveTimer) window.clearInterval(ttsKeepAliveTimer);
          ttsKeepAliveTimer = window.setInterval(() => {
            if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
              window.speechSynthesis.pause();
              window.speechSynthesis.resume();
            }
          }, 10000);
        };
        const onSpeechDone = () => {
          if (activeUtterance !== u) return;
          activeUtterance = null;
          if (ttsKeepAliveTimer) {
            window.clearInterval(ttsKeepAliveTimer);
            ttsKeepAliveTimer = null;
          }
          assistantCurrentlySpeaking = false;
          lastTtsEndedAtMs = Date.now();
          document.querySelectorAll("[data-speak]").forEach((btn) => {
            setSafeHtml(btn, ICONS.speaker + " Listen");
          });
          syncNarrationBar(false, "");
          syncComposerRecordingUi();
          if (voiceContinuousActive && !callMuted) {
            setVoiceStatus("Answer finished. Listening for your next question…");
            scheduleNextVoiceTurnListen();
          }
        };
        u.onend = onSpeechDone;
        u.onerror = onSpeechDone;
        window.speechSynthesis.speak(u);
      }

      narrationPauseBtn?.addEventListener("click", () => {
        if (!("speechSynthesis" in window) || !assistantCurrentlySpeaking) return;
        if (narrationPaused) {
          window.speechSynthesis.resume();
          narrationPaused = false;
        } else {
          window.speechSynthesis.pause();
          narrationPaused = true;
        }
        syncNarrationBar(true, lastSpokenAssistantText);
      });
      narrationStopBtn?.addEventListener("click", () => {
        stopAssistantSpeechPlayback();
        syncNarrationBar(false, "");
        syncComposerRecordingUi();
      });

      composerRecCancelBtn?.addEventListener("click", () => {
        voiceContinuousActive = false;
        stopActiveSpeechRecognition();
        syncVoiceModalButtons();
        setVoiceStatus("Voice recording cancelled.");
      });
      composerRecConfirmBtn?.addEventListener("click", () => {
        if (activeSpeechRec) {
          stopActiveSpeechRecognition();
        }
        syncComposerRecordingUi();
        if (input && input.value.trim()) {
          const val = input.value;
          input.value = "";
          input.rows = 1;
          sendTurn(val, { fromVoiceLoop: voiceContinuousActive });
        }
      });
      composerVoiceModeBtn?.addEventListener("click", () => {
        const nextMode = !voiceContinuousActive;
        state.autoNarrate = nextMode;
        saveState();
        if (!nextMode) {
          voiceContinuousActive = false;
          if (activeTurnAbortController) activeTurnAbortController.abort();
          stopActiveSpeechRecognition();
          stopAssistantSpeechPlayback();
          syncNarrationBar(false, "");
          syncVoiceModalButtons();
          setVoiceStatus("Voice conversation mode off.");
          return;
        }
        voiceConsecutiveEmptyRetries = 0;
        startVoiceRecognition({ continuousLoop: true });
      });

      document.getElementById("voice-dock-end")?.addEventListener("click", () => {
        voiceContinuousActive = false;
        state.autoNarrate = false;
        saveState();
        if (activeTurnAbortController) activeTurnAbortController.abort();
        stopActiveSpeechRecognition();
        stopAssistantSpeechPlayback();
        syncNarrationBar(false, "");
        syncVoiceModalButtons();
        setVoiceStatus("Voice conversation mode off.");
      });
      document.getElementById("voice-dock-mic-off")?.addEventListener("click", () => {
        composerRecCancelBtn?.click();
      });
      document.getElementById("voice-dock-pause")?.addEventListener("click", () => {
        narrationPauseBtn?.click();
        syncComposerRecordingUi();
      });
      document.getElementById("voice-dock-primary")?.addEventListener("click", () => {
        const act = document.getElementById("voice-dock-primary")?.getAttribute("data-action");
        if (act === "send") {
          composerRecConfirmBtn?.click();
        } else if (act === "stop") {
          if (activeTurnAbortController) activeTurnAbortController.abort();
          syncComposerRecordingUi();
        } else {
          stopAssistantSpeechPlayback();
          startVoiceRecognition({ continuousLoop: true });
        }
      });

      callLangChipBtn?.addEventListener("click", () => {
        const isOpen = !callLangMenuEl?.classList.contains("is-hidden");
        callLangMenuEl?.classList.toggle("is-hidden", isOpen);
        callLangChipBtn.setAttribute("aria-expanded", String(!isOpen));
      });
      document.querySelectorAll(".call-lang-option[data-call-lang]").forEach((opt) => {
        opt.addEventListener("click", () => {
          const chosenLang = opt.getAttribute("data-call-lang") || "en";
          callLangSource = "chosen";
          if (localeSelect) localeSelect.value = chosenLang;
          applyLocaleStrings(chosenLang);
          saveState();
          callLangMenuEl?.classList.add("is-hidden");
          callLangChipBtn?.setAttribute("aria-expanded", "false");
          syncCallLanguageChipUi();
        });
      });

      callMuteBtn?.addEventListener("click", () => {
        callMuted = !callMuted;
        callMuteBtn.classList.toggle("call-ctl--muted", callMuted);
        callMuteBtn.setAttribute("aria-pressed", String(callMuted));
        callMuteBtn.setAttribute("aria-label", callMuted ? "Unmute microphone" : "Mute microphone");
        setSafeHtml(callMuteBtn, callMuted ? ICONS.micOff : ICONS.mic);
        if (callMuted) {
          stopActiveSpeechRecognition();
          setVoiceStatus("Microphone muted. Tap Unmute microphone to continue speaking.");
        } else if (voiceContinuousActive && !assistantCurrentlySpeaking) {
          startVoiceRecognition({ continuousLoop: true });
        } else {
          syncComposerRecordingUi();
        }
      });

      const callHangupBtn = document.getElementById("call-hangup-btn");

      function resetOfficerBtnUi() {
        if (!callOfficerBtn) return;
        callOfficerBtn.setAttribute("aria-label", "Request an SSRA officer");
        callOfficerBtn.setAttribute("title", "Request an SSRA officer");
        setSafeHtml(callOfficerBtn, ICONS.user);
      }

      callOfficerBtn?.addEventListener("click", () => {
        const curStatus = callStatusPillEl?.getAttribute("data-status");
        if (curStatus === "transferring") {
          // CallScreen.tsx requestCallback parity: one button changes its job when the wait starts.
          resetOfficerBtnUi();
          if (callStatusPillEl) callStatusPillEl.setAttribute("data-status", "ended");
          if (callStatusLabelEl) callStatusLabelEl.textContent = "Call ended · Callback guidance";
          appendCallCaption(
            "system",
            "Callback guidance requested. Use the official SSRA contact details in the chat transcript to schedule a call.",
          );
          return;
        }
        if (callStatusPillEl) callStatusPillEl.setAttribute("data-status", "transferring");
        if (callStatusLabelEl) callStatusLabelEl.textContent = "Transferring · Officer handoff";
        callOfficerBtn.setAttribute("aria-label", "Request a callback instead");
        callOfficerBtn.setAttribute("title", "Request a callback instead");
        setSafeHtml(callOfficerBtn, ICONS.phone);
        appendCallCaption(
          "system",
          "Requesting an SSRA tax officer. No live telephony trunk is connected in this public browser session; preparing official contact and callback guidance.",
        );
        sendTurn("I would like to speak with an SSRA tax officer", { fromVoiceLoop: voiceContinuousActive });
      });

      callHangupBtn?.addEventListener("click", () => {
        voiceContinuousActive = false;
        if (activeTurnAbortController) activeTurnAbortController.abort();
        stopActiveSpeechRecognition();
        stopAssistantSpeechPlayback();
        syncNarrationBar(false, "");
        resetOfficerBtnUi();
        document.getElementById("call-text-form")?.classList.add("is-hidden");
        const toggleBtn = document.getElementById("call-type-toggle-btn");
        toggleBtn?.classList.remove("is-active");
        toggleBtn?.setAttribute("aria-expanded", "false");
        if (callStatusPillEl) callStatusPillEl.setAttribute("data-status", "ended");
        if (callStatusLabelEl) callStatusLabelEl.textContent = "Call ended";
        appendCallCaption("system", "Thank you for calling SSRA Assist.");
        syncVoiceModalButtons();
        setVoiceStatus("Call ended. Tap Start voice conversation to begin a new session.");
      });

      const callRepeatBtn = document.getElementById("call-repeat-btn");
      const callMoreDetailBtn = document.getElementById("call-more-detail-btn");
      const callPaceBtn = document.getElementById("call-pace-btn");
      const callTypeToggleBtn = document.getElementById("call-type-toggle-btn");
      const callTextForm = document.getElementById("call-text-form");
      const callTextInput = document.getElementById("call-text-input");

      callRepeatBtn?.addEventListener("click", () => {
        if (!lastSpokenAssistantText || callStatusPillEl?.getAttribute("data-status") === "ended") return;
        appendCallCaption("system", "Repeating last answer…");
        speakAssistantReply(lastSpokenAssistantText);
      });

      callMoreDetailBtn?.addEventListener("click", () => {
        if (callStatusPillEl?.getAttribute("data-status") === "ended") return;
        sendTurn("Please provide more detail on the previous answer.", {
          fromVoiceLoop: voiceContinuousActive,
        });
      });

      callPaceBtn?.addEventListener("click", () => {
        callSpeechRateSlow = !callSpeechRateSlow;
        callPaceBtn.classList.toggle("is-active", callSpeechRateSlow);
        callPaceBtn.setAttribute("aria-pressed", String(callSpeechRateSlow));
        callPaceBtn.textContent = callSpeechRateSlow ? "Normal pace" : "Slower pace";
        setVoiceStatus(
          callSpeechRateSlow
            ? "Speech pace set to slower (0.82x)."
            : "Speech pace set to normal (1.0x).",
        );
      });

      callTypeToggleBtn?.addEventListener("click", () => {
        const isOpen = !callTextForm?.classList.contains("is-hidden");
        callTextForm?.classList.toggle("is-hidden", isOpen);
        callTypeToggleBtn.classList.toggle("is-active", !isOpen);
        callTypeToggleBtn.setAttribute("aria-expanded", String(!isOpen));
        if (!isOpen) {
          callTextInput?.focus();
        }
      });

      callTextForm?.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          e.preventDefault();
          callTextForm.classList.add("is-hidden");
          callTypeToggleBtn?.classList.remove("is-active");
          callTypeToggleBtn?.setAttribute("aria-expanded", "false");
          callTypeToggleBtn?.focus();
        }
      });

      callTextForm?.addEventListener("submit", (e) => {
        e.preventDefault();
        const val = (callTextInput?.value || "").trim();
        if (!val) return;
        if (callTextInput) callTextInput.value = "";
        callTextForm.classList.add("is-hidden");
        callTypeToggleBtn?.classList.remove("is-active");
        callTypeToggleBtn?.setAttribute("aria-expanded", "false");
        sendTurn(val, { fromVoiceLoop: true });
      });

      const SPOKEN_REPEAT_RE = /\\b(?:repeat\\s+that|say\\s+that\\s+again|could\\s+you\\s+repeat|pardon\\s+me|what\\s+did\\s+you\\s+say|أعد\\s+ذلك|ممكن\\s+تعيد)\\b/i;
      const SPOKEN_SLOW_RE = /\\b(?:speak\\s+slower|more\\s+slowly|talk\\s+slower|slow\\s+down|تحدث\\s+ببطء|تكلم\\s+ببطء)\\b/i;
      const SPOKEN_NORMAL_RE = /\\b(?:speak\\s+(?:normally|faster)|normal\\s+(?:speed|pace)|regular\\s+(?:speed|pace)|talk\\s+faster|سرعة\\s+عادية)\\b/i;
      const SPOKEN_MORE_RE = /\\b(?:tell\\s+me\\s+more|more\\s+detail|تفاصيل\\s+أكثر)\\b/i;
      const SPOKEN_HANGUP_RE = /\\b(?:hang\\s+up|end\\s+(?:the\\s+)?call|disconnect|good[\\s-]?bye|مع\\s+السلامة|أنهي\\s+المكالمة)\\b/i;
      const SPOKEN_DONE_RE = /^[\\s,!.?]*(?:(?:ok|okay|thanks|thank\\s+you|alright|great|no)[\\s,!.?]+)?(?:that'?s\\s+all|that\\s+is\\s+all|good[\\s-]?bye|bye\\s+bye|bye|i'?m\\s+done)(?:[\\s,!.?]+(?:for\\s+(?:now|today)|thank\\s+you|thanks|bye))?[\\s,!.?]*$/i;

      function handleSpokenCallControl(transcript) {
        const clean = String(transcript || "").trim();
        if (!clean) return false;
        const wordCount = clean.split(/\\s+/).filter(Boolean).length;
        if (SPOKEN_DONE_RE.test(clean) || (wordCount <= 8 && SPOKEN_HANGUP_RE.test(clean))) {
          appendCallCaption("caller", clean);
          callHangupBtn?.click();
          return true;
        }
        if (wordCount > 8) return false;
        if (SPOKEN_REPEAT_RE.test(clean) && lastSpokenAssistantText) {
          appendCallCaption("caller", clean);
          callRepeatBtn?.click();
          return true;
        }
        if (SPOKEN_MORE_RE.test(clean) && lastSpokenAssistantText) {
          appendCallCaption("caller", clean);
          callMoreDetailBtn?.click();
          return true;
        }
        if (SPOKEN_SLOW_RE.test(clean)) {
          appendCallCaption("caller", clean);
          if (!callSpeechRateSlow) callPaceBtn?.click();
          speakAssistantReply("Okay, I will speak more slowly.");
          return true;
        }
        if (SPOKEN_NORMAL_RE.test(clean)) {
          appendCallCaption("caller", clean);
          if (callSpeechRateSlow) callPaceBtn?.click();
          speakAssistantReply("Okay, I will speak at a normal pace.");
          return true;
        }
        return false;
      }

      window.addEventListener("pagehide", () => {
        voiceContinuousActive = false;
        stopActiveSpeechRecognition();
        stopAssistantSpeechPlayback();
      });

      function startVoiceRecognition(options) {
        const continuousLoop = Boolean(options && options.continuousLoop);
        const speechLocale = state.locale === "ar" ? "ar-SS" : state.locale === "en" ? "en-US" : null;
        if (!speechLocale) {
          voiceContinuousActive = false;
          syncVoiceModalButtons();
          setVoiceStatus("Voice typing is unavailable for this selected language. Type your question instead.");
          return;
        }
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
          voiceContinuousActive = false;
          syncVoiceModalButtons();
          setVoiceStatus("Voice typing is unavailable in this browser. Type your question instead.");
          if (!callBackdrop?.classList.contains("open")) {
            openModal(callBackdrop, document.getElementById("close-call-btn"));
          }
          return;
        }
        stopActiveSpeechRecognition();
        stopAssistantSpeechPlayback();
        if (callStatusPillEl?.getAttribute("data-status") === "ended") {
          resetOfficerBtnUi();
          callStatusPillEl.setAttribute("data-status", "ai");
        }
        voiceContinuousActive = continuousLoop || Boolean(state.autoNarrate);
        syncVoiceModalButtons();

        const rec = new SR();
        activeSpeechRec = rec;
        rec.lang = speechLocale;
        rec.continuous = false;
        rec.interimResults = false;
        let receivedTranscript = false;
        let hadError = false;
        setVoiceStatus(
          voiceContinuousActive
            ? "Listening… speak your question for hands-free conversation."
            : "Listening… speak your question.",
        );
        rec.onresult = (ev) => {
          const transcript = String(ev.results?.[0]?.[0]?.transcript || "").trim();
          if (!transcript) return;
          const elapsedSinceTts = assistantCurrentlySpeaking ? 0 : Date.now() - lastTtsEndedAtMs;
          if (isLikelyAssistantEcho(transcript, lastSpokenAssistantText, elapsedSinceTts)) {
            setVoiceStatus("Ignored speaker echo. Listening for your question…");
            return;
          }
          if (assistantCurrentlySpeaking && isBackchannelUtterance(transcript)) {
            return;
          }
          receivedTranscript = true;
          voiceConsecutiveEmptyRetries = 0;
          lastHeardVoiceTranscript = transcript;
          if (voiceContinuousActive) {
            if (handleSpokenCallControl(transcript)) {
              return;
            }
            setVoiceStatus('Heard: "' + transcript + '" — preparing answer…');
            sendTurn(transcript, { fromVoiceLoop: true });
          } else {
            if (input) {
              input.value = (input.value ? input.value + " " : "") + transcript;
            }
            setVoiceStatus("Voice text added. Check it before you send.");
          }
        };
        rec.onerror = (ev) => {
          hadError = true;
          if (activeSpeechRec === rec) activeSpeechRec = null;
          const errCode = String(ev?.error || "");
          const isFatal = errCode === "not-allowed" || errCode === "service-not-allowed" || errCode === "audio-capture";
          if (!isFatal && voiceContinuousActive) {
            voiceConsecutiveEmptyRetries += 1;
            if (voiceConsecutiveEmptyRetries <= MAX_VOICE_EMPTY_RETRIES) {
              scheduleNextVoiceTurnListen();
              return;
            }
            voiceContinuousActive = false;
            syncVoiceModalButtons();
            setVoiceStatus("Voice conversation paused after silence. Tap Start voice conversation to continue.");
            return;
          }
          voiceContinuousActive = false;
          syncVoiceModalButtons();
          setVoiceStatus("Voice typing stopped. Type your question instead.");
        };
        rec.onend = () => {
          if (activeSpeechRec === rec) {
            activeSpeechRec = null;
          }
          syncComposerRecordingUi();
          if (!hadError && !receivedTranscript && voiceContinuousActive && !callMuted && !assistantCurrentlySpeaking && !activeTurnAbortController) {
            voiceConsecutiveEmptyRetries += 1;
            if (voiceConsecutiveEmptyRetries <= MAX_VOICE_EMPTY_RETRIES) {
              scheduleNextVoiceTurnListen();
            } else {
              voiceContinuousActive = false;
              syncVoiceModalButtons();
              setVoiceStatus("Voice conversation paused after silence. Tap Start voice conversation to continue.");
            }
          }
        };
        try {
          rec.start();
        } catch {
          activeSpeechRec = null;
          voiceContinuousActive = false;
          syncVoiceModalButtons();
          setVoiceStatus("Voice typing stopped. Type your question instead.");
        }
      }

      // Voice Dictation (Web Speech API)
      document.getElementById("voice-dictate-btn")?.addEventListener("click", () => {
        if (assistantCurrentlySpeaking || activeTurnAbortController) {
          stopAssistantSpeechPlayback();
          if (activeTurnAbortController) activeTurnAbortController.abort();
          startVoiceRecognition({ continuousLoop: true });
          return;
        }
        startVoiceRecognition({ continuousLoop: Boolean(state.autoNarrate) });
      });

      callListenBtn?.addEventListener("click", () => {
        if (voiceContinuousActive) {
          voiceContinuousActive = false;
          if (activeTurnAbortController) activeTurnAbortController.abort();
          stopActiveSpeechRecognition();
          stopAssistantSpeechPlayback();
          syncVoiceModalButtons();
          setVoiceStatus("Voice conversation stopped. Tap Start voice conversation when ready.");
          return;
        }
        voiceConsecutiveEmptyRetries = 0;
        startVoiceRecognition({ continuousLoop: true });
      });

      callInterruptBtn?.addEventListener("click", () => {
        stopAssistantSpeechPlayback();
        if (activeTurnAbortController) {
          activeTurnAbortController.abort();
        }
        voiceConsecutiveEmptyRetries = 0;
        startVoiceRecognition({ continuousLoop: true });
      });

      // Voice input options dialog
      document.getElementById("open-call-btn")?.addEventListener("click", (e) => {
        syncVoiceModalButtons();
        openModal(callBackdrop, document.getElementById("close-call-btn"), e.currentTarget);
      });
      document.getElementById("close-call-btn")?.addEventListener("click", () => {
        voiceContinuousActive = false;
        if (activeTurnAbortController) activeTurnAbortController.abort();
        stopActiveSpeechRecognition();
        stopAssistantSpeechPlayback();
        syncVoiceModalButtons();
        closeAllModals();
      });
      callBackdrop?.addEventListener("click", (e) => {
        if (e.target === callBackdrop) {
          voiceContinuousActive = false;
          if (activeTurnAbortController) activeTurnAbortController.abort();
          stopActiveSpeechRecognition();
          stopAssistantSpeechPlayback();
          syncVoiceModalButtons();
          closeAllModals();
        }
      });
      document.querySelectorAll(".call-sample-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const q = btn.getAttribute("data-voice-q");
          closeAllModals();
          sendTurn(q, { fromVoiceLoop: voiceContinuousActive });
        });
      });

      // Document & Screenshot Attachment Intake, Security Preflight & Inspection Modal (ChatInput.tsx & DocumentInspectionModal.tsx parity, OQ-017 truthful state)
      const MAX_ATTACHMENTS = 3;
      const MAX_ATTACHMENT_BYTES = 40 * 1024 * 1024;
      const addMenuBackdrop = document.getElementById("addmenu-modal-backdrop");
      const docModalBackdrop = document.getElementById("doc-inspect-modal-backdrop");
      const cameraModalBackdrop = document.getElementById("camera-modal-backdrop");
      const composerAddBtn = document.getElementById("composer-add-btn");
      const composerFileInput = document.getElementById("composer-file-input");
      const composerCameraInput = document.getElementById("composer-camera-input");
      const composerAttachmentsEl = document.getElementById("composer-attachments");
      const composerAttachPrivacyEl = document.getElementById("composer-attachment-privacy");
      const docModalTitleEl = document.getElementById("doc-modal-title");
      const docModalBadgesEl = document.getElementById("doc-modal-badges");
      const docModalPreflightEl = document.getElementById("doc-modal-preflight-note");
      const docModalPromptsEl = document.getElementById("doc-modal-prompts");
      const docModalReportBtn = document.getElementById("doc-modal-report-btn");
      let pendingAttachments = [];
      let inspectingAttachmentId = null;

      function sanitizeAttachmentName(rawName) {
        const stripped = Array.from(String(rawName || "document"))
          .filter((ch) => {
            const code = ch.charCodeAt(0);
            return (
              code >= 32 &&
              code !== 127 &&
              !(code >= 0x200b && code <= 0x200f) &&
              !(code >= 0x202a && code <= 0x202e) &&
              !(code >= 0x2066 && code <= 0x2069) &&
              code !== 0xfeff
            );
          })
          .join("")
          .split("\\\\")
          .join("/");
        const base = stripped.split("/").pop() || "document";
        const safeChars = base.replace(/[^\\p{L}\\p{N}.\\- ()[\\]_]+/gu, "_");
        let sIdx = 0;
        let eIdx = safeChars.length;
        while (sIdx < eIdx && (safeChars[sIdx] === "." || safeChars[sIdx] === " ")) sIdx += 1;
        while (eIdx > sIdx && (safeChars[eIdx - 1] === "." || safeChars[eIdx - 1] === " ")) eIdx -= 1;
        return safeChars.slice(sIdx, eIdx).slice(0, 120) || "document";
      }

      function formatBytes(bytes) {
        const n = Number(bytes) || 0;
        if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
        if (n >= 1024) return Math.round(n / 1024) + " KB";
        return Math.round(n) + " B";
      }

      const DOC_LABELS = {
        en: {
          receipt: "Payment Receipt",
          tin_card: "TIN Certificate",
          assessment: "Tax Assessment Notice",
          customs_declaration: "TANCIS++ Customs Declaration",
          invoice: "Sales Tax Invoice",
          portal_screenshot: "SSRA e-Tax Portal Screenshot",
          generic: "Document",
        },
        ar: {
          receipt: "إيصال دفع",
          tin_card: "شهادة الرقم الضريبي TIN",
          assessment: "إشعار ربط ضريبي",
          customs_declaration: "بيان جمركي TANCIS++",
          invoice: "فاتورة ضريبية",
          portal_screenshot: "لقطة شاشة بوابة الضرائب e-Tax",
          generic: "مستند",
        },
        pga: {
          receipt: "Isal ta Dafa",
          tin_card: "Shahada ta TIN",
          assessment: "Rabit ta Dariba",
          customs_declaration: "Bayan ta Jamarik",
          invoice: "Fatura ta Dariba",
          portal_screenshot: "Sura ta Mawqi SSRA e-Tax",
          generic: "Waraga",
        },
      };

      function formatDocCategory(docType) {
        const dict = DOC_LABELS[state.locale] || DOC_LABELS.en;
        return dict[docType] || DOC_LABELS.en[docType] || dict.generic;
      }

      function classifyAttachmentName(safeName) {
        const lower = safeName.toLowerCase();
        if (/(?:screenshot|screen|portal|etax|error|capture|snip)/.test(lower)) {
          return {
            docType: "portal_screenshot",
            prompts: [
              "Where can I find general e-Tax filing guidance?",
              "Is https://etax.nra.gov.ss/ an official SSRA payment portal?",
            ],
          };
        }
        if (/(?:customs|declaration|tancis|asycuda|nimule)/.test(lower)) {
          return {
            docType: "customs_declaration",
            prompts: [
              "Where can I find general customs guidance?",
              "What is the customs tariff rate for HS 8703.23?",
            ],
          };
        }
        if (/(?:tin|registration|certificate)/.test(lower)) {
          return {
            docType: "tin_card",
            prompts: [
              "How do I register for a TIN on e-Tax?",
              "Where can I find general e-Tax filing guidance?",
            ],
          };
        }
        if (/(?:receipt|payment|bank|remittance)/.test(lower)) {
          return {
            docType: "receipt",
            prompts: [
              "Verify account TSA-ETAX-BANK for tax payment",
              "How do I file and pay my tax return on e-Tax?",
            ],
          };
        }
        if (/(?:invoice|wht|withholding)/.test(lower)) {
          return {
            docType: "invoice",
            prompts: [
              "Calculate withholding tax on 1,000,000 SSP for rent",
              "Where can I find general e-Tax filing guidance?",
            ],
          };
        }
        if (/(?:assessment|demand|notice)/.test(lower)) {
          return {
            docType: "assessment",
            prompts: [
              "How do I file and pay my tax return on e-Tax?",
              "I would like to speak with an SSRA tax officer",
            ],
          };
        }
        return {
          docType: "generic",
          prompts: [
            "Where can I find general e-Tax filing guidance?",
            "How do I register for a TIN on e-Tax?",
          ],
        };
      }

      function inspectPdfPreflight(uint8) {
        if (!uint8 || !uint8.byteLength) return { ok: false, findings: ["Empty PDF file."] };
        let off = 0;
        while (off < Math.min(uint8.byteLength, 8) && (uint8[off] === 0x20 || uint8[off] === 0x09 || uint8[off] === 0x0d || uint8[off] === 0x0a)) {
          off += 1;
        }
        const magicOk =
          uint8.byteLength >= off + 5 &&
          uint8[off] === 0x25 &&
          uint8[off + 1] === 0x50 &&
          uint8[off + 2] === 0x44 &&
          uint8[off + 3] === 0x46 &&
          uint8[off + 4] === 0x2d;
        if (!magicOk) {
          return { ok: false, findings: ["File content does not match the .pdf header (%PDF- required)."] };
        }
        const sample = new TextDecoder("latin1").decode(uint8.subarray(0, Math.min(uint8.byteLength, 256 * 1024)));
        const findings = [];
        if (new RegExp("/Encrypt\\\\b").test(sample)) {
          findings.push("Encrypted or password-protected PDF documents are not accepted.");
        }
        const badTokens = sample.match(
          new RegExp("/(?:JavaScript|JS|Launch|SubmitForm|ImportData|GoToR|RichMedia|EmbeddedFiles|XFA)\\\\b", "g"),
        );
        if (badTokens && badTokens.length) {
          findings.push("PDF contains active or embedded content (" + Array.from(new Set(badTokens)).join(", ") + ").");
        }
        return { ok: findings.length === 0, findings };
      }

      function renderComposerAttachments() {
        if (!composerAttachmentsEl) return;
        const hasAny = pendingAttachments.length > 0;
        composerAttachmentsEl.classList.toggle("is-hidden", !hasAny);
        composerAttachPrivacyEl?.classList.toggle("is-hidden", !hasAny);
        if (!hasAny) {
          setSafeHtml(composerAttachmentsEl, "");
          return;
        }
        const chipsHtml = pendingAttachments
          .map((att) => {
            const metaText =
              att.status === "error"
                ? escapeHtml(att.error || "Rejected")
                : escapeHtml(formatDocCategory(att.docType) + " · " + formatBytes(att.sizeBytes));
            const inspectBtn =
              '<button type="button" class="attachment-act-btn" data-inspect-att="' +
              escapeHtml(att.id) +
              '" aria-label="Inspect ' +
              escapeHtml(att.name) +
              '" title="Inspect document">' +
              ICONS.eye +
              "</button>" +
              (att.status === "ready"
                ? '<button type="button" class="attachment-act-btn" data-report-att="' +
                  escapeHtml(att.id) +
                  '" aria-label="Download inspection receipt for ' +
                  escapeHtml(att.name) +
                  '" title="Download inspection receipt">' +
                  ICONS.download +
                  "</button>"
                : "");
            return (
              '<div class="attachment-chip' +
              (att.status === "error" ? " attachment-chip-error" : "") +
              '" data-testid="attachment-chip">' +
              '<span aria-hidden="true">' +
              ICONS.file +
              "</span>" +
              '<span class="attachment-name" title="' +
              escapeHtml(att.name) +
              '">' +
              escapeHtml(att.name) +
              "</span>" +
              '<span class="attachment-meta">' +
              metaText +
              "</span>" +
              inspectBtn +
              '<button type="button" class="attachment-act-btn" data-remove-att="' +
              escapeHtml(att.id) +
              '" aria-label="Remove ' +
              escapeHtml(att.name) +
              '" title="Remove attachment">' +
              ICONS.close +
              "</button>" +
              "</div>"
            );
          })
          .join("");
        setSafeHtml(composerAttachmentsEl, chipsHtml);
      }

      async function handleAttachFiles(fileList) {
        if (!fileList || !fileList.length) return;
        const files = Array.from(fileList);
        for (const f of files) {
          if (pendingAttachments.length >= MAX_ATTACHMENTS) {
            if (hintEl) hintEl.textContent = "Up to 3 attachments allowed per turn.";
            break;
          }
          const safeName = sanitizeAttachmentName(f.name);
          const lower = safeName.toLowerCase();
          const attId = "att_" + Math.random().toString(36).slice(2, 10);
          if (f.size > MAX_ATTACHMENT_BYTES) {
            pendingAttachments.push({
              id: attId,
              name: safeName,
              sizeBytes: f.size,
              docType: "generic",
              status: "error",
              error: "Exceeds 40 MB limit",
              findings: ["File exceeds the 40 MB attachment limit."],
              prompts: [],
            });
            continue;
          }
          if (lower.endsWith(".xlsm") || lower.endsWith(".docm") || lower.endsWith(".pptm") || lower.endsWith(".xls")) {
            pendingAttachments.push({
              id: attId,
              name: safeName,
              sizeBytes: f.size,
              docType: "generic",
              status: "error",
              error: "Macros / legacy .xls blocked",
              findings: ["Macro-enabled or legacy binary Office files are blocked. Re-save as .xlsx or .docx."],
              prompts: [],
            });
            continue;
          }
          let shaHex = "local_preflight";
          let findings = [];
          let status = "ready";
          let errText = "";
          try {
            const buf = await f.arrayBuffer();
            const uint8 = new Uint8Array(buf);
            if (window.crypto?.subtle?.digest) {
              const digestBuf = await window.crypto.subtle.digest("SHA-256", buf);
              shaHex = Array.from(new Uint8Array(digestBuf), (b) => b.toString(16).padStart(2, "0")).join("");
            }
            if (lower.endsWith(".pdf") || f.type === "application/pdf") {
              const pdfCheck = inspectPdfPreflight(uint8);
              if (!pdfCheck.ok) {
                status = "error";
                errText = "Blocked by PDF security guard";
                findings = pdfCheck.findings;
              }
            }
          } catch {
            findings = ["Could not read file bytes for local preflight."];
          }
          const cls = classifyAttachmentName(safeName);
          pendingAttachments.push({
            id: attId,
            name: safeName,
            sizeBytes: f.size,
            docType: cls.docType,
            sha256Hex: shaHex,
            status,
            error: errText,
            findings,
            prompts: cls.prompts,
          });
        }
        renderComposerAttachments();
      }

      function buildInspectionReceiptText(att) {
        const lines = [
          "========================================================================",
          "SOUTH SUDAN REVENUE AUTHORITY (SSRA) — ATTACHMENT PREFLIGHT RECEIPT",
          "========================================================================",
          "Attachment ID     : " + att.id,
          "File Name         : " + att.name,
          "Detected Category : " + formatDocCategory(att.docType) + " (" + att.docType + ")",
          "File Size         : " + formatBytes(att.sizeBytes) + " (" + att.sizeBytes + " bytes)",
          "SHA-256 Digest    : " + (att.sha256Hex || "local_preflight"),
          "Client Preflight  : " + (att.status === "ready" ? "PASSED" : "BLOCKED"),
          "Preflight Notes   : " + (att.findings && att.findings.length ? att.findings.join("; ") : "Client-side extension and header preflight passed."),
          "------------------------------------------------------------------------",
          "GOVERNANCE & TRUTHFULNESS NOTICE (OQ-017):",
          "Server-side OCR extraction, malware scanning, and automated tax figure",
          "reconciliation are disabled until SSRA approves OQ-017 providers.",
          "Official e-Tax portal: https://etax.nra.gov.ss/",
          "========================================================================",
        ];
        return lines.join("\\n");
      }

      function openDocInspectionModal(attId, triggerEl) {
        const att = pendingAttachments.find((a) => a.id === attId);
        if (!att || !docModalBackdrop) return;
        inspectingAttachmentId = att.id;
        if (docModalTitleEl) docModalTitleEl.textContent = att.name;
        if (docModalBadgesEl) {
          setSafeHtml(
            docModalBadgesEl,
            '<span class="doc-modal-badge">' +
              escapeHtml(formatDocCategory(att.docType)) +
              "</span>" +
              '<span class="doc-modal-badge">' +
              escapeHtml(formatBytes(att.sizeBytes)) +
              "</span>" +
              '<span class="doc-modal-badge">' +
              escapeHtml("SHA-256: " + String(att.sha256Hex || "local").slice(0, 12) + "…") +
              "</span>",
          );
        }
        if (docModalPreflightEl) {
          docModalPreflightEl.textContent =
            att.findings && att.findings.length
              ? att.findings.join(" ")
              : "Client-side extension, filename BiDi, and header preflight passed.";
        }
        if (docModalPromptsEl) {
          const promptsHtml = (att.prompts || [])
            .map(
              (p) =>
                '<button type="button" class="doc-modal-prompt-btn" data-doc-prompt="' +
                escapeHtml(p) +
                '">' +
                ICONS.sparkles +
                " <span>" +
                escapeHtml(p) +
                "</span></button>",
            )
            .join("");
          setSafeHtml(docModalPromptsEl, promptsHtml);
        }
        openModal(docModalBackdrop, document.getElementById("close-doc-modal-btn"), triggerEl || composerAddBtn);
      }

      function downloadAttachmentReceipt(attId) {
        const att = pendingAttachments.find((a) => a.id === attId);
        if (!att) return;
        const receipt = buildInspectionReceiptText(att);
        try {
          const blob = new Blob([receipt], { type: "text/plain;charset=utf-8" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "ssra_inspection_" + att.name.replace(/\\.[^.]+$/, "") + ".txt";
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        } catch {}
        if (hintEl) hintEl.textContent = "Inspection receipt downloaded for " + att.name + ".";
      }

      composerAddBtn?.addEventListener("click", (e) => {
        openModal(addMenuBackdrop, document.getElementById("addmenu-upload-btn"), e.currentTarget);
      });
      document.getElementById("close-addmenu-btn")?.addEventListener("click", closeAllModals);
      addMenuBackdrop?.addEventListener("click", (e) => {
        if (e.target === addMenuBackdrop) closeAllModals();
      });
      document.getElementById("addmenu-upload-btn")?.addEventListener("click", () => {
        closeAllModals();
        composerFileInput?.click();
      });
      document.getElementById("addmenu-camera-btn")?.addEventListener("click", () => {
        closeAllModals();
        openModal(cameraModalBackdrop, document.getElementById("camera-fallback-file-btn"), composerAddBtn);
      });
      document.getElementById("close-camera-btn")?.addEventListener("click", closeAllModals);
      cameraModalBackdrop?.addEventListener("click", (e) => {
        if (e.target === cameraModalBackdrop) closeAllModals();
      });
      document.getElementById("camera-fallback-file-btn")?.addEventListener("click", () => {
        closeAllModals();
        composerCameraInput?.click();
      });
      composerFileInput?.addEventListener("change", (e) => {
        if (e.target.files?.length) handleAttachFiles(e.target.files);
        e.target.value = "";
      });
      composerCameraInput?.addEventListener("change", (e) => {
        if (e.target.files?.length) handleAttachFiles(e.target.files);
        e.target.value = "";
      });
      composerAttachmentsEl?.addEventListener("click", (e) => {
        const inspectBtn = e.target.closest("[data-inspect-att]");
        if (inspectBtn) {
          openDocInspectionModal(inspectBtn.getAttribute("data-inspect-att"), inspectBtn);
          return;
        }
        const reportBtn = e.target.closest("[data-report-att]");
        if (reportBtn) {
          downloadAttachmentReceipt(reportBtn.getAttribute("data-report-att"));
          return;
        }
        const removeBtn = e.target.closest("[data-remove-att]");
        if (removeBtn) {
          const rid = removeBtn.getAttribute("data-remove-att");
          pendingAttachments = pendingAttachments.filter((a) => a.id !== rid);
          renderComposerAttachments();
          composerAddBtn?.focus();
        }
      });
      document.getElementById("close-doc-modal-btn")?.addEventListener("click", closeAllModals);
      document.getElementById("doc-modal-close-secondary-btn")?.addEventListener("click", closeAllModals);
      docModalBackdrop?.addEventListener("click", (e) => {
        if (e.target === docModalBackdrop) {
          closeAllModals();
          return;
        }
        const promptBtn = e.target.closest("[data-doc-prompt]");
        if (promptBtn) {
          const q = promptBtn.getAttribute("data-doc-prompt");
          closeAllModals();
          if (q) sendTurn(q);
        }
      });
      docModalReportBtn?.addEventListener("click", () => {
        if (inspectingAttachmentId) downloadAttachmentReceipt(inspectingAttachmentId);
      });

      // Show saved conversations (or the empty state) as soon as the page loads.
      renderApp();
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

class InvalidTurnRequestError extends Error {}

// Pass through only the content type and a delta-seconds Retry-After from upstream.
function upstreamResponseHeaders(upstream, fallbackContentType) {
  const headers = { "Content-Type": upstream.headers.get("content-type") ?? fallbackContentType };
  const retryAfter = upstream.headers.get("retry-after")?.trim();
  if (retryAfter && /^\d{1,6}$/.test(retryAfter)) headers["Retry-After"] = retryAfter;
  return headers;
}

function sanitizeBrowserTurnBody(rawBodyStr) {
  const parsed = JSON.parse(rawBodyStr);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new InvalidTurnRequestError("INVALID_TURN_BODY");
  }
  if (
    parsed.thread_id !== undefined &&
    parsed.thread_id !== null &&
    (typeof parsed.thread_id !== "string" || !SAFE_THREAD_ID_RE.test(parsed.thread_id))
  ) {
    throw new InvalidTurnRequestError("INVALID_THREAD_ID");
  }
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

  if (isGetOrHead && pathname.startsWith("/fonts/")) {
    const fontName = pathname.slice("/fonts/".length);
    const cached = FONT_CACHE.get(fontName);
    if (cached) {
      const fontHeaders = {
        ...secHeaders,
        "Content-Type": "font/woff2",
        "Cache-Control": "public, max-age=31536000, immutable",
        ETag: cached.etag,
      };
      if (req.headers["if-none-match"] === cached.etag) {
        res.writeHead(304, fontHeaders);
        res.end();
        return;
      }
      res.writeHead(200, {
        ...fontHeaders,
        "Content-Length": cached.byteLength,
      });
      res.end(method === "HEAD" ? undefined : cached.buffer);
      return;
    }
    res.writeHead(404, { "Content-Type": "application/json", ...secHeaders });
    res.end(method === "HEAD" ? undefined : JSON.stringify({ error: "FONT_NOT_FOUND" }));
    return;
  }

  if (isGetOrHead && (pathname === "/healthz" || pathname === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json", ...secHeaders });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "ssra-web",
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
        description: "Public AI assistant for general South Sudan Revenue Authority tax guidance.",
        id: "/",
        lang: "en",
        dir: "ltr",
        scope: "/",
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
    res.writeHead(200, {
      "Content-Type": "application/javascript; charset=utf-8",
      "Clear-Site-Data": '"cache"',
      ...secHeaders,
    });
    res.end(method === "HEAD" ? undefined : SW_CONTENT);
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
        ...upstreamResponseHeaders(upstream, "application/json"),
        ...secHeaders,
      });
      res.end(text);
    } catch (err) {
      const code =
        err instanceof Error && err.message === "PAYLOAD_TOO_LARGE"
          ? 413
          : err instanceof SyntaxError || err instanceof InvalidTurnRequestError
            ? 400
            : 502;
      res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: "BFF_TURN_PROXY_ERROR" }));
    }
    return;
  }

  if (method === "POST" && pathname === "/api/chat/stream") {
    const ac = new AbortController();
    let inactivityTimer = setTimeout(() => ac.abort(), 15_000);
    const resetInactivityTimeout = () => {
      clearTimeout(inactivityTimer);
      inactivityTimer = setTimeout(() => ac.abort(), 15_000);
    };
    res.on("close", () => {
      clearTimeout(inactivityTimer);
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
      resetInactivityTimeout();
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "text/event-stream",
        "X-Accel-Buffering": "no",
        ...secHeaders,
      });
      if (upstream.body) {
        for await (const chunk of upstream.body) {
          resetInactivityTimeout();
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
            : err instanceof SyntaxError || err instanceof InvalidTurnRequestError
              ? 400
              : 502;
        res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
        res.end(JSON.stringify({ error: "BFF_STREAM_PROXY_ERROR" }));
      } else {
        res.end();
      }
    } finally {
      clearTimeout(inactivityTimer);
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
