/**
 * Production Node.js HTTP & BFF Server for SSRA Assist Taxpayer Web PWA & Operations Console (`apps/web/server.js`).
 *
 * Implements the 2026 `chatv2` MainChat + Sidebar (`ConversationRail`, `ConversationSearch`, `AccountRail`, `SettingsDialog`)
 * and unified Operations Console (`/admin`, `/agent`, `/calls`, `/analytics`, `/ops`) inspired by `FinalYearProject` (`urabot`):
 * - Animated sovereign gradient mesh canvas (`#003087` Navy, `#00A88F` Nile Teal, `#F9C74F` Gold)
 * - `ConversationRail` sidebar with top-row Search (`🔍` / `⌘K`) & Collapse (`⟨`), recency-grouped (`Pinned` / `Today` / `Earlier`)
 *   1-line conversation rows with hover actions (`📌 Pin`, `✎ Rename`, `🗑 Delete`), and bottom `AccountRail` upward popover
 *   with Session Identity switcher, 5-tab `SettingsDialog`, and direct Operations Console links
 * - Floating `ChatHeader` strip with 8-language selector (`en`, `pga`, `ar` RTL, `din`, `nus`, `bfa`, `zne`, `shk`),
 *   Dark/Light/High-Contrast theme toggle, AI Call Receptionist (`CallScreen` & `CallOrb`), and `◈ Operations` shortcut
 * - Input-first `chatv2` landing state with 8 categorized `landing-chip` starter prompts & floating composer dock
 */

import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { isOpsDashboardPath, renderOpsDashboardHtml } from "../../packages/ui/ops-console.js";

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

function buildSecurityHeaders(nonce) {
  return {
    "Content-Security-Policy": `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; connect-src 'self'; img-src 'self' data:; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
    "X-Nonce": nonce,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(self), camera=()",
    "Cache-Control": "private, no-cache, no-store, must-revalidate",
  };
}

function renderPwaShellHtml(locale, nonce) {
  const dir = locale === "ar" ? "rtl" : "ltr";
  return `<!DOCTYPE html>
<html lang="${locale}" dir="${dir}" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
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
      --text-3: #5B7065;
      --ssra-blue-bright: #0F47AF;
      --ssra-teal-light: #07792B;
      --ssra-gold: #9A6B00;
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

    /* App Shell Grid (chatv2) */
    .app-shell { display: grid; grid-template-columns: 288px minmax(0, 1fr); height: 100dvh; width: 100vw; transition: grid-template-columns 0.22s cubic-bezier(0.22, 1, 0.36, 1); }
    .app-shell[data-sidebar="collapsed"] { grid-template-columns: 0px minmax(0, 1fr); }
    @media (max-width: 960px) {
      .app-shell { grid-template-columns: minmax(0, 1fr); }
      .rail-wrap { position: fixed; inset: 0 auto 0 0; width: 292px; z-index: 50; transform: translateX(-100%); transition: transform 0.22s ease; }
      .app-shell[data-mobile-rail="open"] .rail-wrap { transform: translateX(0); }
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
      letter-spacing: 0.04em; box-shadow: 0 4px 12px rgba(0, 48, 135, 0.35);
    }
    .rail-top-actions { display: flex; align-items: center; gap: 4px; }
    .rail-icon-btn {
      width: 32px; height: 32px; border-radius: 8px; background: transparent;
      border: 1px solid transparent; color: var(--text-2); cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center; font-size: 0.86rem;
    }
    .rail-icon-btn:hover { background: var(--surface-2); color: var(--text-0); border-color: var(--border-1); }

    .rail-new-btn {
      margin: 0.75rem 0.85rem 0.45rem; padding: 0.62rem 0.9rem; border-radius: var(--radius-md);
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
      width: 24px; height: 24px; border-radius: 6px; border: none; background: transparent;
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
      width: 100%; padding: 0.5rem 0.6rem; border-radius: var(--radius-sm);
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
      padding: 6px 8px; border-radius: 7px; border: none; background: transparent;
      color: var(--text-1); font-size: 0.78rem; font-family: inherit; cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; text-decoration: none; text-align: start; width: 100%;
    }
    .acct-pop-item:hover { background: var(--surface-2); color: var(--text-0); }
    .acct-pop-item.active { color: var(--ssra-gold); font-weight: 600; }

    /* Main Column & Floating ChatHeader */
    .app-main-col { display: flex; flex-direction: column; height: 100dvh; overflow: hidden; position: relative; }
    .chat-header { display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 1.25rem; gap: 0.75rem; border-bottom: 1px solid var(--border-0); background: rgba(10, 10, 18, 0.45); backdrop-filter: blur(16px); z-index: 10; }
    :root[data-theme="light"] .chat-header { background: rgba(255, 255, 255, 0.72); }
    .header-left, .header-right { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
    .icon-btn { min-height: 36px; min-width: 36px; padding: 0.36rem 0.68rem; border-radius: var(--radius-sm); background: var(--surface-2); color: var(--text-0); border: 1px solid var(--border-1); cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; font-weight: 600; text-decoration: none; }
    .icon-btn:hover { background: var(--surface-3); border-color: var(--border-2); }
    .call-btn { background: linear-gradient(135deg, rgba(0, 168, 143, 0.22), rgba(0, 48, 135, 0.28)); border-color: rgba(46, 196, 168, 0.45); color: var(--text-0); }
    .ops-link-btn { border-color: rgba(249, 199, 79, 0.4); color: var(--ssra-gold); }
    .status-badge { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.28rem 0.65rem; border-radius: var(--radius-pill); background: rgba(52, 211, 153, 0.12); border: 1px solid rgba(52, 211, 153, 0.32); color: var(--success); font-size: 0.73rem; font-weight: 600; }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 8px var(--success); }

    /* Main Content Area */
    .app-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
    /* Landing View (chatv2 input-first hierarchy) */
    .landing { flex: 1; overflow-y: auto; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1.5rem 1.25rem 2.5rem; max-width: 820px; width: 100%; margin: 0 auto; gap: 1.35rem; }
    .landing-brand { text-align: center; max-width: 640px; }
    .eyebrow-pill { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.32rem 0.85rem; border-radius: var(--radius-pill); background: var(--surface-2); border: 1px solid var(--border-1); font-size: 0.76rem; font-weight: 600; color: var(--ssra-gold); margin-bottom: 0.75rem; }
    .ldv2-headline { font-size: clamp(1.65rem, 3.2vw, 2.35rem); font-weight: 800; color: var(--text-0); margin: 0 0 0.5rem; letter-spacing: -0.02em; line-height: 1.2; }
    .landing-sub { font-size: 0.96rem; color: var(--text-2); margin: 0; line-height: 1.5; }
    .landing-prompts { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.65rem; width: 100%; }
    .landing-chip { padding: 0.8rem 0.95rem; border-radius: var(--radius-md); background: var(--surface-1); border: 1px solid var(--border-1); color: var(--text-1); text-align: start; cursor: pointer; display: flex; flex-direction: column; gap: 0.28rem; transition: all 0.15s ease; }
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
    .bubble.user { background: var(--grad-user); border: 1px solid rgba(249, 199, 79, 0.32); color: var(--text-0); border-bottom-right-radius: 6px; }
    .bubble.assistant { background: var(--surface-2); border: 1px solid var(--border-1); color: var(--text-0); border-bottom-left-radius: 6px; box-shadow: var(--shadow-md); width: 100%; }
    .turn-meta-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; margin-bottom: 0.55rem; font-size: 0.74rem; color: var(--text-2); }
    .meta-pill { padding: 0.18rem 0.55rem; border-radius: var(--radius-pill); background: var(--surface-3); border: 1px solid var(--border-1); font-weight: 600; font-size: 0.71rem; }
    .meta-pill.tier { color: var(--ssra-gold); border-color: rgba(249, 199, 79, 0.35); }
    .meta-pill.verified { color: var(--success); border-color: rgba(52, 211, 153, 0.35); }
    .meta-pill.eq { color: var(--ssra-teal-light); }

    /* Generative UI Cards */
    .gen-ui-card { margin-top: 0.85rem; padding: 0.95rem 1.1rem; border-radius: var(--radius-md); background: var(--surface-1); border: 1px solid var(--border-2); }
    .gen-ui-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ssra-gold); margin-bottom: 0.55rem; display: flex; align-items: center; justify-content: space-between; }
    .ssra-guided-steps { margin: 0.4rem 0; padding-inline-start: 1.25rem; display: flex; flex-direction: column; gap: 0.4rem; font-size: 0.88rem; }
    .ssra-citation-badges { list-style: none; padding: 0; margin: 0.65rem 0 0; display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .citation-pill { padding: 0.25rem 0.65rem; border-radius: var(--radius-pill); background: rgba(0, 168, 143, 0.14); border: 1px solid rgba(46, 196, 168, 0.35); color: var(--ssra-teal-light); font-size: 0.74rem; font-weight: 600; }
    .confirm-btn { margin-top: 0.65rem; padding: 0.55rem 1rem; border-radius: var(--radius-sm); background: var(--grad-gold); color: #0A0A12; font-weight: 700; border: none; cursor: pointer; font-size: 0.84rem; }
    .turn-actions { display: flex; align-items: center; gap: 0.45rem; margin-top: 0.65rem; padding-top: 0.55rem; border-top: 1px solid var(--border-0); }
    .turn-act-btn { padding: 0.25rem 0.6rem; border-radius: 6px; background: var(--surface-1); border: 1px solid var(--border-0); color: var(--text-2); font-size: 0.74rem; cursor: pointer; }
    .turn-act-btn:hover { color: var(--text-0); border-color: var(--border-1); }

    /* Composer Dock */
    .composer-dock { width: 100%; max-width: 820px; margin: 0 auto; padding: 0.65rem 1rem max(0.85rem, env(safe-area-inset-bottom)); }
    .composer-box { background: var(--surface-2); backdrop-filter: blur(20px); border: 1px solid var(--border-2); border-radius: var(--radius-xl); padding: 0.65rem 0.85rem; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; gap: 0.45rem; transition: border-color 0.15s ease; }
    .composer-box:focus-within { border-color: var(--ssra-gold); }
    .composer-textarea { width: 100%; min-height: 46px; max-height: 140px; resize: none; border: none; background: transparent; color: var(--text-0); font: inherit; font-size: 0.95rem; outline: none; line-height: 1.45; }
    .composer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
    .composer-tools-left, .composer-tools-right { display: flex; align-items: center; gap: 0.45rem; }
    .send-btn { min-height: 38px; padding: 0 1rem; border-radius: var(--radius-pill); background: var(--grad-primary); color: #fff; border: none; font-weight: 700; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; }
    .send-btn:disabled { opacity: 0.48; cursor: not-allowed; }
    .composer-waveform { display: inline-flex; align-items: center; gap: 3px; height: 16px; }
    .composer-waveform span { width: 3px; height: 12px; border-radius: 2px; background: var(--ssra-gold); display: inline-block; }

    /* Modals: CallScreen, ConversationSearch (⌘K), SettingsDialog */
    .modal-backdrop { position: fixed; inset: 0; background: rgba(5, 6, 12, 0.76); backdrop-filter: blur(14px); z-index: 100; display: none; place-items: center; padding: 1rem; }
    .modal-backdrop.open { display: grid; }
    .call-modal { max-width: 440px; width: 100%; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-xl); padding: 1.75rem 1.5rem; text-align: center; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; align-items: center; gap: 1rem; }
    .call-orb { width: 108px; height: 108px; border-radius: 50%; background: radial-gradient(circle at 35% 30%, #2ECC71, #078930 55%, #0F47AF 95%); box-shadow: 0 0 40px rgba(7, 137, 48, 0.45); animation: orbPulse 2.2s ease-in-out infinite; display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 0.88rem; }
    @keyframes orbPulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.07); } }

    .search-modal { max-width: 540px; width: 100%; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow: hidden; }
    .search-input { width: 100%; padding: 14px 16px; border: none; border-bottom: 1px solid var(--border-1); background: transparent; color: var(--text-0); font: inherit; font-size: 0.95rem; outline: none; }
    .search-results { max-height: 320px; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 4px; }

    .settings-modal { max-width: 680px; width: 100%; min-height: 380px; background: var(--bg-1); border: 1px solid var(--border-2); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); display: grid; grid-template-columns: 180px 1fr; overflow: hidden; }
    @media (max-width: 640px) { .settings-modal { grid-template-columns: 1fr; } }
    .settings-tabs { background: var(--surface-1); border-inline-end: 1px solid var(--border-1); padding: 1rem 0.6rem; display: flex; flex-direction: column; gap: 4px; }
    .settings-tab-btn { padding: 8px 12px; border-radius: 8px; border: none; background: transparent; color: var(--text-2); font: inherit; font-size: 0.83rem; font-weight: 600; text-align: start; cursor: pointer; }
    .settings-tab-btn.active { background: var(--surface-3); color: var(--text-0); }
    .settings-pane { padding: 1.25rem 1.4rem; display: flex; flex-direction: column; gap: 0.85rem; }

    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
  </style>
</head>
<body>
  <div class="ssra-flag-ribbon" aria-hidden="true"></div>
  <div id="ssra-app-shell" class="app-shell chatv2" data-sidebar="open" data-locale="${locale}">
    <!-- Left Conversation Rail (ConversationRail.tsx + AccountRail.tsx pattern) -->
    <aside class="rail-wrap" aria-label="Conversation history and account">
      <div class="rail-top">
        <div class="rail-brand">
          <div class="rail-mark" aria-hidden="true">SSRA</div>
          <div>
            <div>SSRA Assist</div>
            <div style="font-size:0.68rem;color:var(--text-2);font-weight:500;">National Revenue Authority</div>
          </div>
        </div>
        <div class="rail-top-actions">
          <button type="button" id="rail-search-btn" class="rail-icon-btn" title="Search conversations (⌘K)" aria-label="Search conversations">🔍</button>
          <button type="button" id="rail-collapse-btn" class="rail-icon-btn" title="Collapse sidebar" aria-label="Toggle sidebar">⟨</button>
        </div>
      </div>

      <button type="button" id="new-chat-btn" class="rail-new-btn">
        <span>+ New Conversation</span>
        <kbd style="font-size:0.68rem;opacity:0.8;font-family:var(--font-mono);">⌘N</kbd>
      </button>

      <div id="rail-conv-list" class="rail-list" role="list"></div>

      <!-- AccountRail Footer & Upward Popover Menu -->
      <div class="rail-footer">
        <div id="acct-popover" class="acct-popover" role="menu" aria-label="Account, Identity &amp; Operations Menu">
          <div class="acct-pop-section">Taxpayer Session Identity</div>
          <button type="button" class="acct-pop-item" data-select-identity="ANONYMOUS"><span>Public Visitor (T0 Anonymous)</span><span id="chk-anon">✓</span></button>
          <button type="button" class="acct-pop-item" data-select-identity="sub_taxpayer_amina_01"><span>Amina M. — TIN ••••1234 (T1/T2)</span><span id="chk-amina"></span></button>
          <button type="button" class="acct-pop-item" data-select-identity="sub_taxpayer_deng_02"><span>Deng Trading — TIN ••••5678 (T1/T2)</span><span id="chk-deng"></span></button>
          <hr style="border:0;border-top:1px solid var(--border-0);margin:3px 0;" />
          <div class="acct-pop-section">SSRA Operations Console (Staff / Admin / Audit)</div>
          <a href="/admin" class="acct-pop-item"><span>◈ Operations Overview</span><span>↗</span></a>
          <a href="/agent" class="acct-pop-item"><span>📥 Agent Queue &amp; Copilot</span><span>↗</span></a>
          <a href="/calls" class="acct-pop-item"><span>📞 AI Phone Call Desk</span><span>↗</span></a>
          <a href="/analytics" class="acct-pop-item"><span>📈 Analytics &amp; CX Scorecard</span><span>↗</span></a>
          <a href="/admin/flags" class="acct-pop-item"><span>⚑ Flags &amp; Knowledge Release</span><span>↗</span></a>
          <a href="/admin/audit" class="acct-pop-item"><span>🛡 WORM Audit &amp; Forensic Replay</span><span>↗</span></a>
          <hr style="border:0;border-top:1px solid var(--border-0);margin:3px 0;" />
          <button type="button" id="open-settings-btn" class="acct-pop-item"><span>⚙ Settings &amp; Privacy</span><span>⌘,</span></button>
        </div>

        <button type="button" id="acct-rail-trigger" class="acct-rail-trigger" aria-expanded="false" aria-haspopup="menu">
          <div class="acct-avatar"><span id="acct-badge-text">PV</span><span class="acct-dot"></span></div>
          <div class="acct-meta">
            <span class="acct-name" id="acct-name-text">Public Visitor</span>
            <span class="acct-sub" id="acct-sub-text">Tier T0 · Click to switch TIN or open Ops</span>
          </div>
          <span style="color:var(--text-3);font-size:0.75rem;">⇅</span>
        </button>

        <!-- Hidden select preserved for programmatic compatibility -->
        <select id="ssra-identity-select" class="sr-only" aria-label="Select taxpayer identity mode">
          <option value="ANONYMOUS">Public Visitor (T0 Anonymous)</option>
          <option value="sub_taxpayer_amina_01">Amina M. — Compliant TIN ••••1234 (T1/T2)</option>
          <option value="sub_taxpayer_deng_02">Deng Trading Co. — Overdue TIN ••••5678 (T1/T2)</option>
        </select>
      </div>
    </aside>

    <!-- Main Column -->
    <div class="app-main-col">
      <header class="chat-header">
        <div class="header-left">
          <button type="button" id="header-rail-btn" class="icon-btn" aria-label="Open conversations">☰</button>
          <span id="active-conv-title" style="font-weight:700;font-size:0.9rem;color:var(--text-0);">New Conversation</span>
          <span class="status-badge" title="Governed Knowledge Snapshot 2026.10.1"><span class="status-dot"></span>Snapshot 2026.10.1</span>
        </div>
        <div class="header-right">
          <a href="/admin" class="icon-btn ops-link-btn" title="Open SSRA Staff, Admin &amp; Auditor Operations Console">◈ Operations</a>
          <button type="button" id="open-call-btn" class="icon-btn call-btn" aria-label="Call SSRA AI Receptionist">📞 Call SSRA</button>
          <select id="locale-select" class="icon-btn" aria-label="Select language">
            <option value="en" ${locale === "en" ? "selected" : ""}>🇬🇧 English (en)</option>
            <option value="pga" ${locale === "pga" ? "selected" : ""}>🇸🇸 Juba Arabic (pga)</option>
            <option value="ar" ${locale === "ar" ? "selected" : ""}>🇸🇸 العربية (ar)</option>
            <option value="din" ${locale === "din" ? "selected" : ""}>🇸🇸 Thuɔŋjäŋ Dinka (din)</option>
            <option value="nus" ${locale === "nus" ? "selected" : ""}>🇸🇸 Thok Naath Nuer (nus)</option>
            <option value="bfa" ${locale === "bfa" ? "selected" : ""}>🇸🇸 Bari (bfa)</option>
            <option value="zne" ${locale === "zne" ? "selected" : ""}>🇸🇸 Pazande (zne)</option>
            <option value="shk" ${locale === "shk" ? "selected" : ""}>🇸🇸 Dhøg Cøllø Shilluk (shk)</option>
          </select>
          <button type="button" id="theme-toggle-btn" class="icon-btn" aria-label="Switch color theme">🌙 Dark</button>
          <button type="button" id="clear-chat-btn" class="icon-btn" aria-label="Clear conversation">Clear</button>
        </div>
      </header>

      <main id="main-content" class="app-content" tabindex="-1">
        <!-- Landing Hero State -->
        <div id="landing-view" class="landing">
          <div class="landing-brand">
            <div class="eyebrow-pill">🇸🇸 South Sudan Revenue Authority (SSRA / NRA) · Grounded AI Assistant</div>
            <h1 id="landing-headline" class="ldv2-headline">How can I help with your South Sudan taxes today?</h1>
            <p id="landing-subtitle" class="landing-sub">Instant, statute-grounded guidance on TIN registration, PAYE &amp; Withholding Tax calculators, Tax Compliance Certificates (TCC), customs duties, and e-Tax bank payments.</p>
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
            <button type="button" class="landing-chip" data-prompt="Check my tax balance and check my TCC status and open a support case" data-demo-subject="sub_taxpayer_amina_01">
              <span class="ldv2-cat">Authenticated Self-Service (T1/T2)</span>
              <span class="landing-chip-text">Check my tax balance, TCC status &amp; open a support case</span>
            </button>
          </div>
        </div>

        <!-- Active Conversation Message List -->
        <div id="chat-view" class="chat-area" style="display:none;" aria-label="Chat conversation">
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
                  🎤 <span class="composer-waveform" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></span>
                </button>
                <span id="composer-hint" style="font-size:0.75rem;color:var(--text-2);">Enter to send · Shift+Enter for newline · ⌘K search</span>
              </div>
              <div class="composer-tools-right">
                <button type="submit" id="ssra-chat-submit" class="send-btn">Send ↗</button>
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
      <div class="eyebrow-pill">SSRA Toll-Free AI Voice Receptionist</div>
      <h2 id="call-modal-title" style="margin:0;color:var(--text-0);font-size:1.25rem;">SSRA Voice Assistant</h2>
      <div id="call-orb" class="call-orb">LISTENING</div>
      <p id="call-transcript-live" style="margin:0;font-size:0.9rem;color:var(--text-1);min-height:2.5rem;">Speak in English, Juba Arabic, Arabic, or Dinka — or tap a quick voice prompt below.</p>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;justify-content:center;">
        <button type="button" class="icon-btn call-sample-btn" data-voice-q="How much is PAYE on 350,000 SSP per month?">🎙️ "PAYE on 350,000 SSP"</button>
        <button type="button" class="icon-btn call-sample-btn" data-voice-q="My goods are held at Nimule border and e-Tax is not working!">🎙️ "Nimule Customs Urgent Help"</button>
      </div>
      <div style="display:flex;gap:0.65rem;margin-top:0.5rem;">
        <button type="button" id="close-call-btn" class="icon-btn" style="background:rgba(251,113,133,0.2);border-color:var(--danger);color:var(--danger);">End Call ✕</button>
      </div>
    </div>
  </div>

  <!-- ConversationSearch Modal (ConversationSearch.tsx pattern, ⌘K) -->
  <div id="search-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Search conversations">
    <div class="search-modal">
      <input id="conv-search-input" class="search-input" type="text" placeholder="Search saved tax conversations or jump to Operations… (Esc to close)" autocomplete="off" />
      <div id="conv-search-results" class="search-results" role="listbox"></div>
    </div>
  </div>

  <!-- Tabbed SettingsDialog Modal (SettingsDialog.tsx pattern) -->
  <div id="settings-modal-backdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Settings">
    <div class="settings-modal">
      <div class="settings-tabs" role="tablist">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;color:var(--text-3);padding:4px 12px;">Settings</div>
        <button type="button" class="settings-tab-btn active" data-settings-tab="general">General &amp; Theme</button>
        <button type="button" class="settings-tab-btn" data-settings-tab="voice">Voice &amp; Speech</button>
        <button type="button" class="settings-tab-btn" data-settings-tab="profile">Taxpayer Profile</button>
        <button type="button" class="settings-tab-btn" data-settings-tab="privacy">Privacy &amp; Erasure</button>
        <button type="button" class="settings-tab-btn" data-settings-tab="ops">Operations Console</button>
      </div>
      <div class="settings-pane">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h3 id="settings-pane-title" style="margin:0;color:var(--text-0);font-size:1.05rem;">General &amp; Appearance</h3>
          <button type="button" id="close-settings-btn" class="icon-btn">Close ✕</button>
        </div>
        <div id="settings-pane-body" style="font-size:0.86rem;color:var(--text-2);line-height:1.55;">
          <p><strong>Theme:</strong> Switch between Dark Sovereign Mesh, Light Paper, and WCAG AAA High Contrast.</p>
          <p><strong>Language Hysteresis:</strong> Automatic 2-turn language stability across all 8 South Sudan BCP-47 languages (<code>en</code>, <code>pga</code>, <code>ar</code>, <code>din</code>, <code>nus</code>, <code>bfa</code>, <code>zne</code>, <code>shk</code>).</p>
          <p><strong>Right to Erasure (GDPR / Data Protection):</strong> Purge local conversation history and Qdrant episodic vectors at any time.</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
            <a href="/admin" class="icon-btn ops-link-btn">◈ Open SSRA Operations Console</a>
            <button type="button" id="purge-local-btn" class="icon-btn" style="color:var(--danger);">🗑 Purge All Local Data</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script nonce="${nonce}">
    (() => {
      if ("serviceWorker" in navigator) {
        caches?.keys?.().then((keys) => {
          keys.forEach((k) => {
            if (k !== "ssra-assist-public-shell-v2026.10.4") caches.delete(k);
          });
        }).catch(() => {});
        navigator.serviceWorker.register("/sw.js").catch(() => {});
      }

      const shell = document.getElementById("ssra-app-shell");
      const landingView = document.getElementById("landing-view");
      const chatView = document.getElementById("chat-view");
      const msgList = document.getElementById("ssra-chat-messages");
      const form = document.getElementById("ssra-chat-form");
      const input = document.getElementById("ssra-chat-input");
      const submitBtn = document.getElementById("ssra-chat-submit");
      const localeSelect = document.getElementById("locale-select");
      const identitySelect = document.getElementById("ssra-identity-select");
      const convListEl = document.getElementById("rail-conv-list");
      const activeTitleEl = document.getElementById("active-conv-title");
      const hintEl = document.getElementById("composer-hint");
      const acctTrigger = document.getElementById("acct-rail-trigger");
      const acctPopover = document.getElementById("acct-popover");

      const IDENTITY_META = {
        ANONYMOUS: { badge: "PV", name: "Public Visitor", sub: "Tier T0 · Click to switch TIN or open Ops" },
        sub_taxpayer_amina_01: { badge: "AM", name: "Amina M. (TIN ••••1234)", sub: "Tier T1/T2 Verified · Compliant" },
        sub_taxpayer_deng_02: { badge: "DT", name: "Deng Trading (TIN ••••5678)", sub: "Tier T1/T2 Verified · Overdue BPT" },
      };

      const STORAGE_KEY = "ssra-chat-store-v2";
      let state = {
        locale: shell?.dataset.locale || "en",
        theme: "dark",
        identity: "ANONYMOUS",
        conversations: [],
        activeId: null,
      };
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
        if (saved && Array.isArray(saved.conversations)) {
          state = { ...state, ...saved };
        }
      } catch {}

      function saveState() {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch {}
      }

      function applyTheme(t) {
        state.theme = t;
        document.documentElement.setAttribute("data-theme", t);
        const btn = document.getElementById("theme-toggle-btn");
        if (btn) btn.textContent = t === "dark" ? "🌙 Dark" : t === "light" ? "☀️ Light" : "◐ Contrast";
        saveState();
      }
      applyTheme(state.theme || "dark");

      function applyIdentity(idVal) {
        state.identity = idVal || "ANONYMOUS";
        if (identitySelect) identitySelect.value = state.identity;
        const meta = IDENTITY_META[state.identity] || IDENTITY_META.ANONYMOUS;
        const bEl = document.getElementById("acct-badge-text");
        const nEl = document.getElementById("acct-name-text");
        const sEl = document.getElementById("acct-sub-text");
        if (bEl) bEl.textContent = meta.badge;
        if (nEl) nEl.textContent = meta.name;
        if (sEl) sEl.textContent = meta.sub;
        const cAnon = document.getElementById("chk-anon");
        const cAmina = document.getElementById("chk-amina");
        const cDeng = document.getElementById("chk-deng");
        if (cAnon) cAnon.textContent = state.identity === "ANONYMOUS" ? "✓" : "";
        if (cAmina) cAmina.textContent = state.identity === "sub_taxpayer_amina_01" ? "✓" : "";
        if (cDeng) cDeng.textContent = state.identity === "sub_taxpayer_deng_02" ? "✓" : "";
        saveState();
      }
      applyIdentity(state.identity || "ANONYMOUS");

      function escapeHtml(str) {
        return String(str ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
      }

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
          inner += '<div style="margin-top:0.45rem;font-size:0.8rem;color:var(--ssra-gold);">↺ Resumable Journey Paused: <strong>' + escapeHtml(props.resumable_workflow.journey_intent) + "</strong> (Step " + escapeHtml(props.resumable_workflow.current_step) + " of " + escapeHtml(props.resumable_workflow.total_steps) + ")</div>";
        }
        if (props.total_outstanding_ssp !== undefined) {
          inner += '<div style="font-size:0.9rem;"><strong>Outstanding Balance:</strong> ' + escapeHtml(props.total_outstanding_ssp) + " SSP · <strong>Filing Status:</strong> " + escapeHtml(props.filing_status || "COMPLIANT") + "</div>";
        }
        if (props.estimated_tax_ssp !== undefined || props.net_pay_ssp !== undefined) {
          inner += '<div style="font-size:0.9rem;"><strong>Estimated Tax:</strong> ' + escapeHtml(props.estimated_tax_ssp || props.withholding_tax_ssp || "") + " SSP</div>";
        }
        if (pendingConfirmation && pendingConfirmation.token) {
          inner += '<div style="margin-top:0.55rem;padding:0.65rem;border-radius:8px;background:rgba(249,199,79,0.1);border:1px solid rgba(249,199,79,0.35);">' +
            '<div style="font-size:0.84rem;font-weight:600;color:var(--ssra-gold);">Action Confirmation Required (T2): ' + escapeHtml(pendingConfirmation.summary_text) + "</div>" +
            '<button type="button" class="confirm-btn" data-confirm-token="' + escapeHtml(pendingConfirmation.token) + '" data-idem-key="' + escapeHtml(pendingConfirmation.idempotency_key) + '" data-thread-id="' + escapeHtml(threadId) + '">✓ Confirm &amp; Execute ' + escapeHtml(pendingConfirmation.tool) + "</button>" +
          "</div>";
        }
        return '<div class="gen-ui-card" role="region" aria-label="' + escapeHtml(cardName) + '">' +
          '<div class="gen-ui-title"><span>✦ ' + escapeHtml(cardName) + "</span></div>" +
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
        if (meta.outcome_verified) pills.push('<span class="meta-pill verified">✓ Provenance Verified</span>');
        if (meta.recommended_tone && meta.recommended_tone !== "standard_clear") {
          pills.push('<span class="meta-pill eq">EQ: ' + escapeHtml(meta.recommended_tone) + "</span>");
        }
        if (meta.elapsed_ms) pills.push("<span>Thought for " + escapeHtml(meta.elapsed_ms) + "ms</span>");

        const citationsHtml = Array.isArray(meta.citations) && meta.citations.length > 0
          ? '<ul class="ssra-citation-badges">' + meta.citations.map((c) =>
              '<li class="citation-pill">📜 ' + escapeHtml(c.section_anchor || c.doc_title || c.id) + " (" + escapeHtml(c.snapshot_version || "2026.10.1") + ")</li>"
            ).join("") + "</ul>"
          : "";

        return '<article class="message-row message-row-assistant">' +
          '<div class="bubble assistant">' +
            (pills.length ? '<div class="turn-meta-bar">' + pills.join("") + "</div>" : "") +
            '<div style="white-space:pre-wrap;">' + escapeHtml(turn.content) + "</div>" +
            renderGenerativeCard(meta.ui_component, meta.pending_confirmation, meta.thread_id) +
            citationsHtml +
            '<div class="turn-actions">' +
              '<button type="button" class="turn-act-btn" data-speak="' + escapeHtml(turn.content) + '">🔊 Listen</button>' +
              '<button type="button" class="turn-act-btn" data-copy="' + escapeHtml(turn.content) + '">📋 Copy</button>' +
            "</div>" +
          "</div>" +
        "</article>";
      }

      function renderConvRow(c) {
        const active = c.id === state.activeId ? " active" : "";
        return '<div class="rail-row' + active + '">' +
          '<button type="button" class="rail-item" data-conv-id="' + escapeHtml(c.id) + '">' +
            (c.pinned ? "📌 " : "💬 ") + escapeHtml(c.title) +
          "</button>" +
          '<div class="rail-row-actions">' +
            '<button type="button" class="rail-act-mini" data-pin-conv="' + escapeHtml(c.id) + '" title="Pin conversation">📌</button>' +
            '<button type="button" class="rail-act-mini" data-del-conv="' + escapeHtml(c.id) + '" title="Delete conversation">🗑</button>' +
          "</div>" +
        "</div>";
      }

      function renderApp() {
        const activeConv = state.conversations.find((c) => c.id === state.activeId) || null;
        if (convListEl) {
          if (state.conversations.length === 0) {
            convListEl.innerHTML = '<div style="padding:0.75rem;font-size:0.78rem;color:var(--text-3);">Your tax conversations will appear here, grouped by Pinned &amp; Recent.</div>';
          } else {
            const pinned = state.conversations.filter((c) => c.pinned);
            const recent = state.conversations.filter((c) => !c.pinned);
            let html = "";
            if (pinned.length) {
              html += '<div class="rail-section-label">Pinned</div>' + pinned.map(renderConvRow).join("");
            }
            if (recent.length) {
              html += '<div class="rail-section-label">Today</div>' + recent.map(renderConvRow).join("");
            }
            convListEl.innerHTML = html;
          }
        }
        if (!activeConv || activeConv.turns.length === 0) {
          if (landingView) landingView.style.display = "flex";
          if (chatView) chatView.style.display = "none";
          if (activeTitleEl) activeTitleEl.textContent = "New Conversation";
        } else {
          if (landingView) landingView.style.display = "none";
          if (chatView) chatView.style.display = "flex";
          if (activeTitleEl) activeTitleEl.textContent = activeConv.title;
          if (msgList) {
            msgList.innerHTML = activeConv.turns.map(renderTurnHtml).join("");
            msgList.scrollTop = msgList.scrollHeight;
          }
        }
      }

      async function sendTurn(text, opts = {}) {
        const trimmed = String(text || "").trim();
        if (!trimmed) return;
        let conv = state.conversations.find((c) => c.id === state.activeId);
        if (!conv) {
          conv = {
            id: "thr_web_" + Date.now().toString(36),
            title: trimmed.slice(0, 48),
            pinned: false,
            turns: [],
          };
          state.conversations.unshift(conv);
          state.activeId = conv.id;
        }
        conv.turns.push({ role: "user", content: trimmed });
        conv.turns.push({ role: "assistant", content: "Searching SSRA statutory corpus & verifying numeric provenance..." });
        renderApp();

        if (opts.forceIdentity) {
          applyIdentity(opts.forceIdentity);
        }
        const selectedIdentity = state.identity || "ANONYMOUS";
        const isSignedIn = selectedIdentity !== "ANONYMOUS";
        const endpoint = isSignedIn ? "/v1/turns" : "/api/turns";
        const headers = {
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true",
        };
        if (isSignedIn) {
          headers["X-SSRA-Subject-Ref"] = selectedIdentity;
        }
        const payload = {
          message: trimmed,
          thread_id: opts.threadId || conv.id,
          locale: state.locale,
          channel: "web",
          auth_level: isSignedIn ? "T1_TIN_BOUND" : "ANONYMOUS",
          subject_ref: isSignedIn ? selectedIdentity : null,
          confirmation_token: opts.confirmationToken || null,
          idempotency_key: opts.idempotencyKey || null,
        };

        const t0 = performance.now();
        if (submitBtn) submitBtn.disabled = true;
        try {
          const res = await fetch(endpoint, {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
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
        } catch {
          conv.turns[conv.turns.length - 1] = {
            role: "assistant",
            content: "Offline or connection interrupted. You can still use SSRA Assist or visit https://etax.nra.gov.ss/.",
          };
        } finally {
          if (submitBtn) submitBtn.disabled = false;
          saveState();
          renderApp();
        }
      }

      form?.addEventListener("submit", (e) => {
        e.preventDefault();
        const val = input.value;
        input.value = "";
        sendTurn(val);
      });

      input?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          form?.requestSubmit();
        }
      });

      document.querySelectorAll(".landing-chip").forEach((btn) => {
        btn.addEventListener("click", () => {
          const prompt = btn.getAttribute("data-prompt");
          const reqSub = btn.getAttribute("data-demo-subject");
          sendTurn(prompt, { forceIdentity: reqSub || undefined });
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
          return;
        }
        const delBtn = e.target.closest("[data-del-conv]");
        if (delBtn) {
          const cid = delBtn.getAttribute("data-del-conv");
          state.conversations = state.conversations.filter((x) => x.id !== cid);
          if (state.activeId === cid) state.activeId = state.conversations[0]?.id || null;
          saveState();
          renderApp();
          return;
        }
        const btn = e.target.closest("[data-conv-id]");
        if (btn) {
          state.activeId = btn.getAttribute("data-conv-id");
          saveState();
          renderApp();
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
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(speakBtn.getAttribute("data-speak") || "");
          window.speechSynthesis.speak(u);
          return;
        }
        const copyBtn = e.target.closest("[data-copy]");
        if (copyBtn && navigator.clipboard) {
          navigator.clipboard.writeText(copyBtn.getAttribute("data-copy") || "");
          copyBtn.textContent = "✓ Copied";
        }
      });

      document.getElementById("new-chat-btn")?.addEventListener("click", () => {
        state.activeId = null;
        saveState();
        renderApp();
      });

      document.getElementById("clear-chat-btn")?.addEventListener("click", () => {
        state.conversations = [];
        state.activeId = null;
        saveState();
        renderApp();
      });

      const toggleSidebar = () => {
        const cur = shell?.getAttribute("data-sidebar");
        shell?.setAttribute("data-sidebar", cur === "collapsed" ? "open" : "collapsed");
        const mob = shell?.getAttribute("data-mobile-rail");
        shell?.setAttribute("data-mobile-rail", mob === "open" ? "closed" : "open");
      };
      document.getElementById("rail-collapse-btn")?.addEventListener("click", toggleSidebar);
      document.getElementById("header-rail-btn")?.addEventListener("click", toggleSidebar);

      document.getElementById("theme-toggle-btn")?.addEventListener("click", () => {
        const next = state.theme === "dark" ? "light" : state.theme === "light" ? "high-contrast" : "dark";
        applyTheme(next);
      });

      localeSelect?.addEventListener("change", () => {
        state.locale = localeSelect.value;
        document.documentElement.lang = state.locale;
        document.documentElement.dir = state.locale === "ar" ? "rtl" : "ltr";
        saveState();
      });

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
      acctPopover?.addEventListener("click", (e) => {
        const idBtn = e.target.closest("[data-select-identity]");
        if (idBtn) {
          applyIdentity(idBtn.getAttribute("data-select-identity"));
          acctPopover.classList.remove("open");
        }
      });

      // ConversationSearch Modal (⌘K)
      const searchBackdrop = document.getElementById("search-modal-backdrop");
      const searchInput = document.getElementById("conv-search-input");
      const searchResults = document.getElementById("conv-search-results");
      function renderSearchModalList() {
        const q = (searchInput?.value || "").trim().toLowerCase();
        const matches = state.conversations.filter((c) => !q || c.title.toLowerCase().includes(q));
        let html = matches.map((c) =>
          '<button type="button" class="acct-pop-item" data-jump-conv="' + escapeHtml(c.id) + '"><span>💬 ' + escapeHtml(c.title) + '</span><span style="font-size:0.7rem;color:var(--text-3);">Open</span></button>'
        ).join("");
        html += '<a href="/admin" class="acct-pop-item"><span>◈ Jump to SSRA Operations Overview (/admin)</span><span>↗</span></a>';
        html += '<a href="/agent" class="acct-pop-item"><span>📥 Jump to Agent Queue &amp; Copilot (/agent)</span><span>↗</span></a>';
        html += '<a href="/analytics" class="acct-pop-item"><span>📈 Jump to CX Analytics &amp; Scorecard (/analytics)</span><span>↗</span></a>';
        if (searchResults) searchResults.innerHTML = html;
      }
      function openSearchModal() {
        searchBackdrop?.classList.add("open");
        if (searchInput) {
          searchInput.value = "";
          renderSearchModalList();
          searchInput.focus();
        }
      }
      document.getElementById("rail-search-btn")?.addEventListener("click", openSearchModal);
      searchBackdrop?.addEventListener("click", (e) => {
        if (e.target === searchBackdrop) searchBackdrop.classList.remove("open");
      });
      searchInput?.addEventListener("input", renderSearchModalList);
      searchResults?.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-jump-conv]");
        if (btn) {
          state.activeId = btn.getAttribute("data-jump-conv");
          searchBackdrop?.classList.remove("open");
          renderApp();
        }
      });

      // SettingsDialog Modal
      const settingsBackdrop = document.getElementById("settings-modal-backdrop");
      document.getElementById("open-settings-btn")?.addEventListener("click", () => {
        acctPopover?.classList.remove("open");
        settingsBackdrop?.classList.add("open");
      });
      document.getElementById("close-settings-btn")?.addEventListener("click", () => {
        settingsBackdrop?.classList.remove("open");
      });
      settingsBackdrop?.addEventListener("click", (e) => {
        if (e.target === settingsBackdrop) settingsBackdrop.classList.remove("open");
      });
      document.getElementById("purge-local-btn")?.addEventListener("click", () => {
        state.conversations = [];
        state.activeId = null;
        saveState();
        renderApp();
        settingsBackdrop?.classList.remove("open");
      });

      window.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          if (searchBackdrop?.classList.contains("open")) searchBackdrop.classList.remove("open");
          else openSearchModal();
        } else if (e.key === "Escape") {
          searchBackdrop?.classList.remove("open");
          settingsBackdrop?.classList.remove("open");
          document.getElementById("call-modal-backdrop")?.classList.remove("open");
        }
      });

      // Voice Dictation (Web Speech API)
      document.getElementById("voice-dictate-btn")?.addEventListener("click", () => {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
          if (hintEl) hintEl.textContent = "Voice dictation active via Call SSRA modal";
          document.getElementById("call-modal-backdrop")?.classList.add("open");
          return;
        }
        const rec = new SR();
        rec.lang = state.locale === "ar" ? "ar-SS" : "en-US";
        if (hintEl) hintEl.textContent = "🎙️ Listening... speak your tax question";
        rec.onresult = (ev) => {
          const transcript = ev.results?.[0]?.[0]?.transcript || "";
          if (transcript && input) {
            input.value = (input.value ? input.value + " " : "") + transcript;
          }
          if (hintEl) hintEl.textContent = "Enter to send · Shift+Enter for newline · ⌘K search";
        };
        rec.onerror = () => {
          if (hintEl) hintEl.textContent = "Enter to send · Shift+Enter for newline · ⌘K search";
        };
        rec.start();
      });

      // AI Call Receptionist Modal
      const callBackdrop = document.getElementById("call-modal-backdrop");
      document.getElementById("open-call-btn")?.addEventListener("click", () => {
        callBackdrop?.classList.add("open");
      });
      document.getElementById("close-call-btn")?.addEventListener("click", () => {
        callBackdrop?.classList.remove("open");
      });
      document.querySelectorAll(".call-sample-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const q = btn.getAttribute("data-voice-q");
          callBackdrop?.classList.remove("open");
          sendTurn(q);
        });
      });

      renderApp();
    })();
  </script>
</body>
</html>`;
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
  const hostHeader = String(req.headers.host ?? "localhost");
  if (!VALID_HOST_RE.test(hostHeader)) {
    res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "INVALID_HOST_HEADER" }));
    return;
  }

  let pathname = "/";
  try {
    const rawTarget = req.url ?? "/";
    if (!rawTarget.startsWith("/")) {
      throw new Error("INVALID_TARGET");
    }
    pathname = new URL(rawTarget, "http://127.0.0.1").pathname;
  } catch {
    res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "INVALID_REQUEST_TARGET" }));
    return;
  }

  const isGetOrHead = req.method === "GET" || req.method === "HEAD";

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
        headers: { Accept: "application/json" },
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

  if (isGetOrHead && pathname === "/api/scorecard") {
    try {
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/analytics/cx-scorecard`, {
        headers: { Accept: "application/json" },
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "unavailable", service: "ssra-web" }));
    }
    return;
  }

  if (isGetOrHead && isOpsDashboardPath(pathname)) {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...secHeaders });
    res.end(renderOpsDashboardHtml(pathname, nonce));
    return;
  }

  if (req.method === "POST" && pathname === "/api/turns") {
    try {
      const safeBody = sanitizeBrowserTurnBody(await readRequestBody(req));
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/turns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: safeBody,
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

  if (req.method === "POST" && pathname === "/api/chat/stream") {
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
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
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
    const isRuntimeRoute =
      pathname.startsWith("/v1/turns") ||
      pathname.startsWith("/v1/agui/") ||
      pathname.startsWith("/v1/memory/") ||
      pathname.startsWith("/v1/runtime/") ||
      pathname.startsWith("/v1/field-officer/");
    const upstreamBase = isRuntimeRoute ? INTERNAL_RUNTIME_URL : INTERNAL_API_URL;
    try {
      const hasBody = req.method === "POST" || req.method === "PUT" || req.method === "PATCH";
      const bodyStr = hasBody ? await readRequestBody(req) : undefined;
      const fwdHeaders = { Accept: req.headers.accept ?? "application/json" };
      if (hasBody) {
        fwdHeaders["Content-Type"] = "application/json";
      }
      for (const hName of [
        "x-ssra-subject-ref",
        "x-ssra-staff-id",
        "authorization",
        "last-event-id",
        "traceparent",
        "idempotency-key",
      ]) {
        if (req.headers[hName]) {
          fwdHeaders[hName] = String(req.headers[hName]);
        }
      }
      const upstream = await fetch(`${upstreamBase}${pathname}`, {
        method: req.method ?? "GET",
        headers: fwdHeaders,
        body: bodyStr,
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

  const seg = pathname.split("/").filter(Boolean)[0] ?? "en";
  const locale = SUPPORTED_LOCALES.has(seg) ? seg : "en";
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...secHeaders });
  res.end(renderPwaShellHtml(locale, nonce));
});

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-web listening on http://${HOSTNAME}:${PORT}\n`);
});
