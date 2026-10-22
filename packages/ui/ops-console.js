/**
 * SSRA Assist Operations Console Preview & Staff Sidebar Design System (`packages/ui/ops-console.js`).
 *
 * Inspired by the `FinalYearProject` (`urabot`) Operations Console & `StaffGuard` architecture:
 * - `.ops-*` design tokens (`--ops-font-sans`, `--ops-font-mono`, 8-step type scale, 4pt grid, 5-ingredient `.ops-glass`)
 * - Collapsible `.staff-rail` (`52px` collapsed / `216px` expanded, `always-open` vs `hover` mode)
 * - 4-group navigation hierarchy (`Work` / `Audit` / `Configure` / `Observe`) + `AccountMenu` upward popover
 * - `CommandPalette` (`⌘K` / `Ctrl+K`) modal with keyboard navigation and role-scoped destinations
 * - `OpsPage`, `OpsPanel` (`default`, `is-bare`, `is-glass`), `StatCard` (`splitMeasure`, `.ops-delta`, SVG `Sparkline`)
 * - Explicit non-operational preview until authenticated staff sessions and provenance-bearing data are available
 */

import { ICONS } from "./icons.js";

const OPS_ROUTE_PREFIXES = [
  "/admin",
  "/agent",
  "/calls",
  "/analytics",
  "/queue",
  "/auditor",
  "/ops",
];

export function isOpsDashboardPath(pathname) {
  if (!pathname || pathname === "/") return false;
  return OPS_ROUTE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function normalizeOpsRoute(pathname) {
  if (!pathname || pathname === "/" || pathname === "/ops") return "/admin";
  if (pathname === "/queue") return "/agent";
  if (pathname === "/auditor") return "/admin/audit";
  return pathname;
}

function compactOpsHtmlAssetBlocks(html) {
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

export function renderOpsDashboardHtml(rawPathname, nonce) {
  const currentPath = normalizeOpsRoute(rawPathname);
  const rawHtml = `<!DOCTYPE html>
<html lang="en" data-theme="dark" data-rail-mode="always-open">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="description" content="Non-operational preview of SSRA Assist staff navigation. No live taxpayer data, service telemetry, or staff actions." />
  <title>SSRA Operations Console Preview — South Sudan Revenue Authority</title>
  <style nonce="${nonce}">
    :root {
      color-scheme: dark;
      --ops-font-sans: "IBM Plex Sans", "Segoe UI", "Aptos", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      --ops-font-mono: "IBM Plex Mono", "Cascadia Code", "SFMono-Regular", "Fira Code", monospace;
      --ops-text-2xs: 11px;
      --ops-text-xs: 12px;
      --ops-text-sm: 13px;
      --ops-text-base: 14px;
      --ops-text-md: 16px;
      --ops-text-lg: 20px;
      --ops-text-xl: 26px;
      --ops-text-2xl: 34px;
      --ops-lh-tight: 1.2;
      --ops-lh-snug: 1.4;
      --ops-lh-normal: 1.55;
      --ops-weight-light: 300;
      --ops-weight-normal: 400;
      --ops-weight-medium: 500;
      --ops-weight-semi: 600;
      --ops-weight-bold: 700;
      --ops-space-1: 4px;
      --ops-space-2: 8px;
      --ops-space-3: 12px;
      --ops-space-4: 16px;
      --ops-space-5: 20px;
      --ops-space-6: 24px;
      --ops-space-8: 32px;
      --ops-space-10: 40px;
      --ops-space-12: 48px;
      --ops-gutter: var(--ops-space-5);
      --ops-band: var(--ops-space-8);
      --ops-radius-xs: 6px;
      --ops-radius-sm: 8px;
      --ops-radius-md: 12px;
      --ops-radius-lg: 16px;
      --ops-radius-pill: 999px;
      --ops-nav-h: 52px;
      --ops-max-w: 1380px;
      --ops-dur-fast: 140ms;
      --ops-dur-base: 200ms;
      --ops-ease: cubic-bezier(0.22, 1, 0.36, 1);

      --bg-0: #091310;
      --bg-1: #0E1C17;
      --bg-2: #142720;
      --surface-1: rgba(236, 245, 238, 0.038);
      --surface-2: rgba(236, 245, 238, 0.068);
      --surface-3: rgba(236, 245, 238, 0.105);
      --surface-ink: #0B1713;
      --border-0: rgba(220, 235, 224, 0.075);
      --border-1: rgba(220, 235, 224, 0.13);
      --border-2: rgba(220, 235, 224, 0.22);
      --text-0: #F6F8F5;
      --text-1: #DCE4DD;
      --text-2: #9BB0A3;
      --text-3: #7E9688;
      --accent: #F4C430;
      --ssra-green: #078930;
      --ssra-green-light: #2ECC71;
      --ssra-blue: #0F47AF;
      --ssra-red: #DA121A;
      --ssra-teal: #078930;
      --ssra-teal-light: #2ECC71;

      --ops-panel: var(--surface-ink);
      --ops-panel-inset: var(--surface-1);
      --ops-row: var(--surface-1);
      --ops-row-hover: var(--surface-2);
      --ops-row-active: var(--surface-3);
      --ops-hairline: var(--border-0);
      --ops-line: var(--border-1);
      --ops-line-strong: var(--border-2);
      --ops-glass-bg: linear-gradient(180deg, rgba(18, 36, 29, 0.86) 0%, rgba(10, 21, 17, 0.90) 100%);
      --ops-glass-line: rgba(220, 235, 224, 0.13);
      --ops-glass-blur: blur(20px) saturate(145%);
      --ops-glass-spec: inset 0 1px 0 rgba(255, 255, 255, 0.09);
      --ops-glass-cast: 0 12px 32px rgba(0, 0, 0, 0.44);
      --ops-elev-3: 0 24px 60px rgba(0, 0, 0, 0.56);

      --ops-good-ink: #34D399;
      --ops-warn-ink: #FBBF24;
      --ops-bad-ink: #FB7185;
      --ops-info-ink: #60A5FA;
      --ops-focus: #F4C430;
      --ops-focus-ring: 2px;
      --ops-focus-gap: 2px;
    }

    :root[data-theme="light"] {
      color-scheme: light;
      --bg-0: #F6F7F2;
      --bg-1: #FFFFFF;
      --bg-2: #EBF0E8;
      --surface-1: rgba(12, 28, 20, 0.032);
      --surface-2: rgba(12, 28, 20, 0.058);
      --surface-3: rgba(12, 28, 20, 0.092);
      --surface-ink: #FFFFFF;
      --border-0: rgba(12, 28, 20, 0.08);
      --border-1: rgba(12, 28, 20, 0.14);
      --border-2: rgba(12, 28, 20, 0.23);
      --text-0: #0C1C14;
      --text-1: #1F3329;
      --text-2: #4A5E53;
      --text-3: #4E6358;
      --accent: #704B00;
      --ops-glass-bg: linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(245, 247, 241, 0.96) 100%);
      --ops-glass-line: rgba(12, 28, 20, 0.13);
      --ops-glass-spec: inset 0 1px 0 rgba(255, 255, 255, 0.85);
      --ops-glass-cast: 0 8px 24px rgba(12, 28, 20, 0.07);
      --ops-good-ink: #066926;
      --ops-warn-ink: #853A06;
      --ops-bad-ink: #B91C1C;
      --ops-info-ink: #0F47AF;
      --ops-focus: #078930;
    }

    :root[data-theme="high-contrast"] {
      color-scheme: dark;
      --bg-0: #000000;
      --bg-1: #050505;
      --surface-ink: #000000;
      --surface-1: #0D0D0D;
      --surface-2: #171717;
      --surface-3: #242424;
      --border-0: #737373;
      --border-1: #FFFFFF;
      --border-2: #FFD60A;
      --text-0: #FFFFFF;
      --text-1: #FFFFFF;
      --text-2: #E5E7EB;
      --text-3: #D1D5DB;
      --ops-glass-bg: #050505;
      --ops-glass-line: #FFFFFF;
    }

    *, *::before, *::after { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; min-height: 100dvh;
      font-family: var(--ops-font-sans);
      font-variant-numeric: tabular-nums;
      background: var(--bg-0); color: var(--text-1);
    }
    body::before {
      content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
      background:
        radial-gradient(ellipse 58% 48% at 16% 12%, rgba(7, 137, 48, 0.22), transparent 62%),
        radial-gradient(ellipse 48% 42% at 84% 24%, rgba(15, 71, 175, 0.18), transparent 58%),
        radial-gradient(ellipse 52% 38% at 50% 92%, rgba(244, 196, 48, 0.08), transparent 60%),
        linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 55%, var(--bg-0) 100%);
    }
    :root[data-theme="light"] body::before {
      background:
        radial-gradient(ellipse 58% 48% at 16% 12%, rgba(7, 137, 48, 0.07), transparent 62%),
        radial-gradient(ellipse 48% 42% at 84% 24%, rgba(15, 71, 175, 0.06), transparent 58%),
        linear-gradient(180deg, var(--bg-0) 0%, #ECEFE6 55%, var(--bg-0) 100%);
    }
    .ssra-flag-ribbon {
      position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 60; pointer-events: none;
      background: linear-gradient(90deg, #0F47AF 0%, #0F47AF 18%, #F4C430 18%, #F4C430 24%, #111815 24%, #111815 48%, #DA121A 48%, #DA121A 74%, #078930 74%, #078930 100%);
    }

    .ops-sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); border: 0;
    }

    .staff-skip {
      position: absolute; left: var(--ops-space-3); top: -44px; z-index: 50;
      padding: var(--ops-space-2) var(--ops-space-3); background: var(--ops-panel);
      color: var(--text-0); border: 1px solid var(--ops-line-strong); border-radius: var(--ops-radius-sm);
      font-size: var(--ops-text-sm); font-weight: var(--ops-weight-semi); text-decoration: none;
    }
    .staff-skip:focus { top: var(--ops-space-2); }
    :where(a, button, input, select, textarea, [tabindex]):focus-visible {
      outline: var(--ops-focus-ring) solid var(--ops-focus);
      outline-offset: var(--ops-focus-gap);
    }

    /* ── Staff Shell & Collapsible Vertical Rail (staffGuard.css pattern) ── */
    .staff-shell {
      --rail-w-collapsed: 56px;
      --rail-w-expanded: 224px;
      --rail-w: var(--rail-w-collapsed);
      min-height: 100dvh;
    }
    .staff-shell:has(.staff-rail.is-expanded),
    :root[data-rail-mode="always-open"] .staff-shell {
      --rail-w: var(--rail-w-expanded);
    }
    .staff-shell-content {
      margin-inline-start: var(--rail-w);
      transition: margin-inline-start var(--ops-dur-base) var(--ops-ease);
      min-height: 100dvh; display: flex; flex-direction: column;
    }

    .staff-rail {
      position: fixed; inset: 0 auto 0 0; z-index: 30;
      display: flex; flex-direction: column;
      width: var(--rail-w-collapsed);
      background: var(--ops-glass-bg);
      border-inline-end: 1px solid var(--ops-glass-line);
      box-shadow: var(--ops-glass-spec);
      -webkit-backdrop-filter: var(--ops-glass-blur);
      backdrop-filter: var(--ops-glass-blur);
      overflow: hidden; contain: paint;
      transition: width var(--ops-dur-base) var(--ops-ease);
    }
    .staff-rail.is-expanded,
    :root[data-rail-mode="always-open"] .staff-rail {
      width: var(--rail-w-expanded);
      box-shadow: var(--ops-elev-3);
    }

    .staff-rail-head {
      display: flex; align-items: center; justify-content: space-between;
      gap: var(--ops-space-1); min-height: var(--ops-nav-h);
      padding: var(--ops-space-2) var(--ops-space-3); flex: none;
    }
    .staff-brand {
      display: flex; align-items: center; gap: var(--ops-space-2);
      min-width: 0; color: var(--text-0); text-decoration: none; white-space: nowrap;
    }
    .staff-brand-mark {
      display: inline-flex; align-items: center; justify-content: center; flex: none;
      width: 30px; height: 30px; border-radius: var(--ops-radius-sm);
      background: var(--accent); color: #0B1220;
      font-size: 10px; font-weight: var(--ops-weight-bold); letter-spacing: 0.03em;
    }
    .staff-brand-text {
      display: flex; flex-direction: column; min-width: 0;
      line-height: var(--ops-lh-tight); font-size: var(--ops-text-sm);
      font-weight: var(--ops-weight-semi); opacity: 0;
      transition: opacity var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail.is-expanded .staff-brand-text { opacity: 1; }
    .staff-brand-sub {
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-normal);
      color: var(--text-3); overflow: hidden; text-overflow: ellipsis;
    }
    .staff-rail-pin {
      flex: none; width: 28px; height: 28px; border-radius: var(--ops-radius-xs);
      background: transparent; border: 1px solid transparent; color: var(--text-2);
      cursor: pointer; display: inline-flex; align-items: center; justify-content: center;
    }
    .staff-rail-pin:hover { background: var(--ops-row-hover); color: var(--text-0); }
    .staff-rail.is-collapsed .staff-rail-pin { display: none; }
    .staff-rail-pin.is-on { color: var(--accent); border-color: var(--ops-line); }

    .staff-rail-search {
      flex: none; padding: 0 var(--ops-space-2) var(--ops-space-2);
      border-bottom: 1px solid var(--ops-line);
    }
    .ops-cmdk-trigger {
      width: 100%; min-height: 34px; padding: 0 var(--ops-space-2);
      border-radius: var(--ops-radius-sm); background: var(--ops-row);
      border: 1px solid var(--ops-line); color: var(--text-2);
      font-family: inherit; font-size: var(--ops-text-xs); cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; gap: var(--ops-space-2);
    }
    .ops-cmdk-trigger:hover { background: var(--ops-row-hover); color: var(--text-0); border-color: var(--ops-line-strong); }
    .staff-rail.is-collapsed .ops-cmdk-trigger-text,
    .staff-rail.is-collapsed .ops-cmdk-kbd { display: none; }
    .ops-kbd {
      font-family: var(--ops-font-mono); font-size: 10px; padding: 1px 5px;
      border-radius: 4px; background: var(--ops-row-active); border: 1px solid var(--ops-line);
      color: var(--text-2);
    }

    .staff-rail-scroll {
      flex: 1; overflow-y: auto; overflow-x: hidden;
      padding: var(--ops-space-3) 0; scrollbar-width: thin;
    }
    .staff-rail-group + .staff-rail-group {
      margin-top: var(--ops-space-3); padding-top: var(--ops-space-3);
      border-top: 1px solid var(--ops-hairline);
    }
    .staff-rail-group-label {
      margin: 0 0 var(--ops-space-1); padding: 0 var(--ops-space-3);
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-semi);
      letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-3);
      white-space: nowrap; opacity: 0; height: 0; overflow: hidden;
    }
    .staff-rail.is-expanded .staff-rail-group-label {
      opacity: 1; height: auto; margin-bottom: var(--ops-space-1);
    }
    .staff-rail ul {
      list-style: none; margin: 0; padding: 0 var(--ops-space-2);
      display: flex; flex-direction: column; gap: 2px;
    }
    .staff-rail a.nav-item {
      position: relative; display: flex; align-items: center; gap: var(--ops-space-2);
      padding: 8px 10px; border-radius: var(--ops-radius-sm);
      font-size: var(--ops-text-sm); font-weight: var(--ops-weight-medium);
      color: var(--text-2); text-decoration: none; white-space: nowrap;
      transition: background var(--ops-dur-fast) var(--ops-ease), color var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail a.nav-item:hover { background: var(--ops-row-hover); color: var(--text-0); }
    .staff-rail a.nav-item.active {
      color: var(--text-0); font-weight: var(--ops-weight-semi);
      background: var(--ops-row-active); border: 1px solid var(--ops-line);
    }
    .staff-rail-icon { display: inline-flex; flex: none; width: 20px; justify-content: center; font-size: 14px; }
    .staff-rail-label { opacity: 0; transition: opacity var(--ops-dur-fast) var(--ops-ease); }
    .staff-rail.is-expanded .staff-rail-label { opacity: 1; }

    /* AccountMenu Footer & Upward Popover */
    .staff-rail-foot {
      flex: none; padding: var(--ops-space-2); border-top: 1px solid var(--ops-line);
      position: relative;
    }
    .staff-acct-trigger {
      width: 100%; display: flex; align-items: center; gap: var(--ops-space-2);
      padding: 6px 8px; border-radius: var(--ops-radius-sm);
      background: transparent; border: 1px solid transparent; color: var(--text-0);
      cursor: pointer; text-align: start; font-family: inherit;
    }
    .staff-acct-trigger:hover { background: var(--ops-row-hover); border-color: var(--ops-line); }
    .staff-acct-avatar {
      position: relative; width: 28px; height: 28px; border-radius: var(--ops-radius-sm);
      background: linear-gradient(135deg, #078930, #0F47AF); color: #fff;
      font-size: 11px; font-weight: var(--ops-weight-bold);
      display: inline-flex; align-items: center; justify-content: center; flex: none;
    }
    .staff-acct-dot {
      position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px;
      border-radius: 50%; background: var(--ops-good-ink); border: 2px solid var(--bg-0);
    }
    .staff-acct-meta {
      display: flex; flex-direction: column; min-width: 0; flex: 1;
      opacity: 0; transition: opacity var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail.is-expanded .staff-acct-meta { opacity: 1; }
    .staff-acct-name { font-size: var(--ops-text-xs); font-weight: var(--ops-weight-semi); color: var(--text-0); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .staff-acct-role { font-size: var(--ops-text-2xs); color: var(--text-3); white-space: nowrap; }
    .staff-acct-menu {
      position: absolute; bottom: calc(100% + 6px); left: var(--ops-space-2); right: var(--ops-space-2);
      background: var(--ops-panel); border: 1px solid var(--ops-line-strong);
      border-radius: var(--ops-radius-md); box-shadow: var(--ops-elev-3);
      padding: var(--ops-space-2); display: none; flex-direction: column; gap: 4px; z-index: 45;
    }
    .staff-acct-menu.open { display: flex; }
    .staff-acct-item {
      padding: 6px 8px; border-radius: var(--ops-radius-xs); background: transparent;
      border: none; color: var(--text-1); font-size: var(--ops-text-xs); font-family: inherit;
      cursor: pointer; display: flex; align-items: center; justify-content: space-between;
      text-decoration: none; width: 100%; text-align: start;
    }
    .staff-acct-item:hover { background: var(--ops-row-hover); color: var(--text-0); }
    .staff-acct-item.active { color: var(--accent); font-weight: var(--ops-weight-semi); }

    /* ── Sticky CallConsoleBar (StaffCallLayer pattern) ── */
    .call-console-bar {
      display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
      gap: var(--ops-space-3); padding: 8px var(--ops-space-5);
      background: var(--ops-glass-bg); border-bottom: 1px solid var(--ops-line);
      -webkit-backdrop-filter: var(--ops-glass-blur); backdrop-filter: var(--ops-glass-blur);
      font-size: var(--ops-text-xs);
    }
    .call-bar-left, .call-bar-right { display: flex; align-items: center; gap: var(--ops-space-3); flex-wrap: wrap; }
    .presence-pill {
      display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
      border-radius: var(--ops-radius-pill); background: rgba(52, 211, 153, 0.12);
      border: 1px solid rgba(52, 211, 153, 0.35); color: var(--ops-good-ink); font-weight: var(--ops-weight-semi);
    }

    /* ── OpsPage, OpsPanel & StatCard (ops.css + admin.css pattern) ── */
    .ops-page {
      max-width: var(--ops-max-w); width: 100%; margin: 0 auto;
      padding: var(--ops-space-6) var(--ops-space-5) var(--ops-space-12);
      color: var(--text-1);
    }
    .ops-page-head {
      display: flex; align-items: flex-end; justify-content: space-between;
      gap: var(--ops-space-4); flex-wrap: wrap; margin-bottom: var(--ops-space-5);
    }
    .ops-eyebrow {
      display: block; margin-bottom: var(--ops-space-1);
      font-family: var(--ops-font-mono); font-size: var(--ops-text-2xs);
      letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent);
    }
    .ops-page-head h1 {
      margin: 0; font-size: var(--ops-text-xl); line-height: var(--ops-lh-tight);
      font-weight: var(--ops-weight-semi); letter-spacing: -0.01em; color: var(--text-0);
    }
    .ops-page-desc {
      margin: var(--ops-space-2) 0 0; max-width: 70ch;
      font-size: var(--ops-text-sm); line-height: var(--ops-lh-normal); color: var(--text-2);
    }
    .ops-page-actions { display: flex; align-items: center; gap: var(--ops-space-2); flex-wrap: wrap; }

    .ops-segmented {
      display: inline-flex; padding: 2px; border-radius: var(--ops-radius-sm);
      background: var(--ops-row); border: 1px solid var(--ops-line);
    }
    .ops-seg-btn {
      min-height: 28px; min-width: 36px; padding: 5px 10px; border-radius: var(--ops-radius-xs); border: none;
      background: transparent; color: var(--text-2); font-size: var(--ops-text-xs);
      font-weight: var(--ops-weight-medium); cursor: pointer; font-family: inherit;
      display: inline-flex; align-items: center; justify-content: center;
    }
    .ops-seg-btn.active { background: var(--ops-row-active); color: var(--text-0); font-weight: var(--ops-weight-semi); }

    .ops-btn {
      min-height: 32px; padding: 0 12px; border-radius: var(--ops-radius-sm);
      background: var(--ops-row); border: 1px solid var(--ops-line); color: var(--text-0);
      font-size: var(--ops-text-xs); font-weight: var(--ops-weight-medium);
      cursor: pointer; display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
    }
    .ops-btn:hover { background: var(--ops-row-hover); border-color: var(--ops-line-strong); }
    .ops-btn.primary { background: linear-gradient(135deg, #07792B 0%, #0D6E38 50%, #0F47AF 100%); color: #fff; border-color: rgba(255,255,255,0.18); }
    .ops-btn.gold { background: var(--accent); color: #0B1220; border-color: transparent; font-weight: var(--ops-weight-bold); }
    :root[data-theme="light"] .ops-btn.gold { color: #FFFFFF; }

    /* StatCard Grid */
    .ops-stat-grid {
      display: grid;
      grid-template-columns: repeat(var(--ops-stat-cols, 3), minmax(0, 1fr));
      gap: var(--ops-space-3); margin-bottom: var(--ops-band);
    }
    @media (max-width: 1024px) { .ops-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 600px) { .ops-stat-grid { grid-template-columns: minmax(0, 1fr); } }

    .ops-stat {
      position: relative; display: flex; flex-direction: column; gap: var(--ops-space-1);
      padding: var(--ops-space-4) var(--ops-space-5); border-radius: var(--ops-radius-md);
      background: var(--ops-glass-bg); border: 1px solid var(--ops-glass-line);
      box-shadow: var(--ops-glass-spec), var(--ops-glass-cast);
      -webkit-backdrop-filter: var(--ops-glass-blur); backdrop-filter: var(--ops-glass-blur);
      contain: paint; text-decoration: none; color: inherit;
      transition: border-color var(--ops-dur-fast) var(--ops-ease), background var(--ops-dur-fast) var(--ops-ease);
    }
    .ops-stat:hover { border-color: var(--ops-line-strong); }
    .ops-stat-label {
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-semi);
      letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-3);
    }
    .ops-stat-row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--ops-space-2); margin-top: 2px; }
    .ops-stat-value {
      font-size: var(--ops-text-xl); line-height: var(--ops-lh-tight);
      font-weight: var(--ops-weight-semi); color: var(--text-0);
    }
    .ops-stat-unit { font-size: var(--ops-text-sm); font-weight: var(--ops-weight-normal); color: var(--text-2); }
    .ops-delta {
      font-family: var(--ops-font-mono); font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-semi);
      padding: 2px 6px; border-radius: var(--ops-radius-xs); background: var(--ops-row); color: var(--text-2);
    }
    .ops-delta.is-good { color: var(--ops-good-ink); background: rgba(52, 211, 153, 0.12); }
    .ops-delta.is-bad { color: var(--ops-bad-ink); background: rgba(251, 113, 133, 0.12); }
    .ops-stat-hint { font-size: var(--ops-text-xs); color: var(--text-2); line-height: var(--ops-lh-snug); }
    .ops-sparkline { width: 100%; height: 28px; margin-top: 4px; overflow: visible; }

    /* OpsPanel & Two-Column Layouts */
    .ov-cols { display: grid; grid-template-columns: 1.45fr 1fr; gap: var(--ops-band); align-items: start; }
    @media (max-width: 980px) { .ov-cols { grid-template-columns: minmax(0, 1fr); } }
    .ov-side { display: grid; gap: var(--ops-band); }

    .ops-panel {
      background: var(--ops-panel); border: 1px solid var(--ops-line);
      border-radius: var(--ops-radius-md); overflow: hidden;
    }
    .ops-panel.is-bare { background: none; border: 0; border-radius: 0; }
    .ops-panel.is-glass {
      background: var(--ops-glass-bg); border-color: var(--ops-glass-line);
      box-shadow: var(--ops-glass-spec), var(--ops-glass-cast);
      -webkit-backdrop-filter: var(--ops-glass-blur); backdrop-filter: var(--ops-glass-blur);
    }
    .ops-panel-head {
      display: flex; align-items: center; justify-content: space-between; gap: var(--ops-space-2);
      padding: var(--ops-space-3) var(--ops-space-4); border-bottom: 1px solid var(--ops-hairline);
    }
    .ops-panel.is-bare .ops-panel-head { padding: 0 0 var(--ops-space-2); border-bottom: 1px solid var(--ops-line); }
    .ops-panel-head h2 { margin: 0; font-size: var(--ops-text-base); font-weight: var(--ops-weight-semi); color: var(--text-0); }
    .ops-panel.is-bare .ops-panel-head h2 { font-size: var(--ops-text-lg); }
    .ops-panel-body { padding: var(--ops-space-4); overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .ops-panel.is-bare .ops-panel-body { padding: var(--ops-space-4) 0 0; }

    /* Lists, Tables & Chips */
    .ov-review-list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--ops-space-2); }
    .ov-review-item {
      display: grid; gap: 4px; padding: var(--ops-space-3) var(--ops-space-4);
      border: 1px solid var(--ops-hairline); border-radius: var(--ops-radius-sm); background: var(--ops-row);
    }
    .ov-review-top { display: flex; align-items: center; justify-content: space-between; gap: var(--ops-space-2); }
    .ops-chip {
      display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px;
      border-radius: var(--ops-radius-pill); font-size: var(--ops-text-2xs);
      font-weight: var(--ops-weight-semi); background: var(--ops-row-active); border: 1px solid var(--ops-line);
    }
    .ops-chip.good { color: var(--ops-good-ink); border-color: rgba(52, 211, 153, 0.35); background: rgba(52, 211, 153, 0.1); }
    .ops-chip.warn { color: var(--ops-warn-ink); border-color: rgba(251, 191, 36, 0.35); background: rgba(251, 191, 36, 0.1); }
    .ops-chip.bad { color: var(--ops-bad-ink); border-color: rgba(251, 113, 133, 0.35); background: rgba(251, 113, 133, 0.1); }
    .ops-chip.info { color: var(--ops-info-ink); border-color: rgba(96, 165, 250, 0.35); background: rgba(96, 165, 250, 0.1); }

    .ops-table { width: 100%; border-collapse: collapse; font-size: var(--ops-text-xs); }
    .ops-table th, .ops-table td {
      padding: 10px 12px; text-align: start; border-bottom: 1px solid var(--ops-hairline);
    }
    .ops-table th {
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-semi);
      text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3);
    }
    .ops-table tr:hover td { background: var(--ops-row-hover); }

    .ov-kv { margin: 0; display: grid; gap: var(--ops-space-2); }
    .ov-kv > div { display: flex; align-items: center; justify-content: space-between; gap: var(--ops-space-3); padding: 4px 0; border-bottom: 1px solid var(--ops-hairline); }
    .ov-kv dt { font-size: var(--ops-text-xs); color: var(--text-3); }
    .ov-kv dd { margin: 0; font-size: var(--ops-text-xs); font-weight: var(--ops-weight-semi); color: var(--text-0); }

    /* Command Palette Modal (CommandPalette.tsx pattern) */
    .ops-cmdk-backdrop {
      position: fixed; inset: 0; z-index: 90; background: rgba(5, 7, 14, 0.72);
      backdrop-filter: blur(10px); display: none; place-items: start center; padding-top: 12vh;
    }
    .ops-cmdk-backdrop.open { display: grid; }
    .ops-cmdk-dialog {
      width: min(560px, 92vw); background: var(--ops-panel); border: 1px solid var(--ops-line-strong);
      border-radius: var(--ops-radius-lg); box-shadow: var(--ops-elev-3); overflow: hidden;
    }
    .ops-cmdk-input {
      width: 100%; padding: 14px 16px; border: none; border-bottom: 1px solid var(--ops-line);
      background: transparent; color: var(--text-0); font-family: inherit; font-size: var(--ops-text-base); outline: none;
    }
    .ops-cmdk-list { list-style: none; margin: 0; padding: 8px; max-height: 340px; overflow-y: auto; }
    .ops-cmdk-item {
      padding: 9px 12px; border-radius: var(--ops-radius-sm); cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      color: var(--text-1); font-size: var(--ops-text-sm);
    }
    .ops-cmdk-item:hover, .ops-cmdk-item[data-active="true"] { background: var(--ops-row-active); color: var(--text-0); }
    .ops-cmdk-foot {
      padding: 8px 14px; border-top: 1px solid var(--ops-hairline);
      font-size: var(--ops-text-2xs); color: var(--text-3); display: flex; justify-content: space-between;
    }

    .mobile-nav-btn { display: none; }
    .ops-mobile-backdrop { display: none; position: fixed; inset: 0; background: rgba(5, 10, 8, 0.55); z-index: 25; }
    @media (max-width: 820px) {
      .staff-shell { --rail-w: 0px !important; }
      .staff-rail { transform: translateX(-100%); visibility: hidden; width: min(240px, 84vw) !important; transition: transform var(--ops-dur-base) var(--ops-ease), visibility 0s linear var(--ops-dur-base); }
      .staff-rail.is-drawer-open { transform: translateX(0); visibility: visible; transition: transform var(--ops-dur-base) var(--ops-ease), visibility 0s; }
      .ops-mobile-backdrop.open { display: block; }
      .mobile-nav-btn { display: inline-flex; }
      .ops-page { padding: var(--ops-space-4) var(--ops-space-3) var(--ops-space-8); }
      .call-console-bar { padding: 8px var(--ops-space-3); }
    }
    .staff-acct-heading { padding: 4px 8px; font-size: 10px; text-transform: uppercase; color: var(--text-3); font-weight: 700; }
    .staff-acct-hr { border: 0; border-top: 1px solid var(--ops-hairline); margin: 4px 0; }
    .staff-acct-chevron { color: var(--text-3); font-size: 11px; }
    .ops-stat-grid.cols-3 { --ops-stat-cols: 3; }
    .ops-stat-grid.cols-4 { --ops-stat-cols: 4; }
    .ops-meta-xs { font-size: 11px; color: var(--text-3); }
    .ops-review-link { color: var(--text-0); font-weight: 600; text-decoration: none; }
    .ops-review-quote { margin: 0; font-size: 12px; color: var(--text-2); }
    .ops-duty-lead { margin: 0 0 12px; font-size: 13px; color: var(--text-2); }
    .ov-review-item.is-clickable { cursor: pointer; }
    .ov-review-item.is-selected { border-color: var(--accent); }
    .ops-ticket-title { font-weight: 600; color: var(--text-0); font-size: 13px; }
    .ops-msg-box { padding: 10px 12px; border-radius: 8px; background: var(--ops-row); border: 1px solid var(--ops-line); margin-bottom: 12px; }
    .ops-msg-head { font-size: 11px; color: var(--text-3); margin-bottom: 4px; }
    .ops-msg-body { font-size: 13px; color: var(--text-0); }
    .ops-draft-wrap { margin-bottom: 10px; }
    .ops-draft-label { display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--accent); margin-bottom: 6px; }
    .ops-draft-textarea { width: 100%; padding: 10px; border-radius: 8px; background: var(--ops-panel); color: var(--text-0); border: 1px solid var(--ops-line-strong); font-family: inherit; font-size: 13px; }
    .ops-chips-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
    .ops-actions-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .ops-actions-row-mt { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
    .ops-status-msg { margin-top: 10px; font-size: 12px; color: var(--ops-good-ink); }
    .ops-degrade-bar { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--ops-hairline); }
    .ops-degrade-label { font-size: 12px; font-weight: 600; color: var(--text-0); }
    .ops-release-steps { margin: 0; padding-inline-start: 18px; display: grid; gap: 8px; font-size: 13px; }
    .ops-panel-mt { margin-top: 24px; }
    .ops-preview-banner { margin: 14px 20px 0; padding: 14px 16px; border: 2px solid #F4C430; border-radius: var(--ops-radius-md); background: rgba(244, 196, 48, 0.12); color: var(--text-0); line-height: 1.5; }
    .ops-preview-banner strong { display: block; margin-bottom: 3px; color: #F4C430; }
    .ops-preview-card { max-width: 760px; margin: 28px auto; padding: 24px; }
    .ops-preview-card h1 { margin: 8px 0; }
    .ops-preview-card p, .ops-preview-card li { line-height: 1.6; }
    .ops-preview-card ul { padding-inline-start: 1.25rem; }
    .ops-preview-chip { display: inline-block; padding: 4px 9px; border: 1px solid #F4C430; border-radius: 999px; color: #F4C430; font-weight: 700; }
    @media (prefers-reduced-motion: reduce) {
      .staff-rail { transition: none !important; }
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
    }
  </style>
</head>
<body>
  <div class="ssra-flag-ribbon" aria-hidden="true"></div>
  <a class="staff-skip" href="#staff-main">Skip to content</a>

  <div class="staff-shell" id="ssra-staff-shell">
    <div id="ops-mobile-backdrop" class="ops-mobile-backdrop" aria-hidden="true"></div>
    <!-- Left Vertical Operations Rail (StaffGuard.tsx pattern) -->
    <nav id="staff-rail" class="staff-rail is-expanded" aria-label="Staff console preview navigation">
      <div class="staff-rail-head">
        <a class="staff-brand" href="/admin" aria-label="SSRA Operations Console preview">
          <span class="staff-brand-mark" aria-hidden="true">${ICONS.ssraCrest}</span>
          <span class="staff-brand-text">
            Operations
            <span class="staff-brand-sub">Taxpayer assistant</span>
          </span>
        </a>
        <button type="button" id="rail-pin-btn" class="staff-rail-pin is-on" aria-label="Toggle preview navigation width" aria-pressed="true" title="Toggle preview navigation width">${ICONS.chevronsLeft}</button>
      </div>

      <div class="staff-rail-search">
        <button type="button" id="cmdk-open-btn" class="ops-cmdk-trigger" aria-haspopup="dialog" aria-label="Search console destinations">
          <span>${ICONS.search} <span class="ops-cmdk-trigger-text">Search console…</span></span>
          <kbd class="ops-kbd ops-cmdk-kbd">Ctrl+K</kbd>
        </button>
      </div>

      <div class="staff-rail-scroll" id="staff-rail-groups"></div>

      <div class="staff-rail-foot">
        <div id="staff-acct-menu" class="staff-acct-menu" role="menu" aria-label="Officer account and console settings">
          <div class="staff-acct-heading" role="presentation">Preview persona · not access control</div>
          <button type="button" class="staff-acct-item" data-set-role="ssra_admin" role="menuitemradio" aria-checked="true"><span>Administrator view (preview)</span><span>${ICONS.check}</span></button>
          <button type="button" class="staff-acct-item" data-set-role="ssra_staff" role="menuitemradio" aria-checked="false"><span>Tax agent view (preview)</span><span></span></button>
          <button type="button" class="staff-acct-item" data-set-role="ssra_auditor" role="menuitemradio" aria-checked="false"><span>Auditor view (preview)</span><span></span></button>
          <hr class="staff-acct-hr" role="separator" />
          <div class="staff-acct-heading" role="presentation">Appearance</div>
          <button type="button" class="staff-acct-item" data-set-theme="dark" role="menuitemradio" aria-checked="true"><span>${ICONS.moon} Dark Mesh</span></button>
          <button type="button" class="staff-acct-item" data-set-theme="light" role="menuitemradio" aria-checked="false"><span>${ICONS.sun} Light Paper</span></button>
          <button type="button" class="staff-acct-item" data-set-theme="high-contrast" role="menuitemradio" aria-checked="false"><span>${ICONS.contrast} High Contrast (WCAG AAA)</span></button>
          <hr class="staff-acct-hr" role="separator" />
          <a href="/en" class="staff-acct-item" role="menuitem"><span>${ICONS.messageSquare} Return to Taxpayer MainChat</span><span>${ICONS.arrowUpRight}</span></a>
        </div>
        <button type="button" id="staff-acct-trigger" class="staff-acct-trigger" aria-label="Preview persona menu; not signed in" aria-expanded="false" aria-haspopup="menu">
          <span class="staff-acct-avatar"><span id="acct-initials">P</span></span>
          <span class="staff-acct-meta">
            <span class="staff-acct-name" id="acct-display-name">Preview persona</span>
            <span class="staff-acct-role" id="acct-role-label">Not signed in · preview only</span>
          </span>
          <span class="staff-acct-chevron">${ICONS.chevronUpDown}</span>
        </button>
      </div>
    </nav>

    <!-- Main Operations Content Column -->
    <div class="staff-shell-content">
      <!-- Preview status: operational data is hidden until an authenticated staff session is configured. -->
      <div class="call-console-bar" id="call-console-bar" role="note" aria-label="Staff console preview status">
        <div class="call-bar-left">
          <button type="button" id="mobile-ops-nav-btn" class="ops-btn mobile-nav-btn" aria-label="Open preview navigation" aria-expanded="false" aria-controls="staff-rail">${ICONS.panelLeft} Menu</button>
          <span class="presence-pill">Preview only · no authenticated staff session</span>
          <span>No live calls, taxpayer records, or service telemetry are shown.</span>
        </div>
        <div class="call-bar-right">
          <a href="/en" class="ops-btn primary">${ICONS.messageSquare} Taxpayer MainChat</a>
        </div>
      </div>

      <main id="staff-main" class="ops-page" data-route="${currentPath}" tabindex="-1">
        <!-- Populated dynamically by route renderer below -->
      </main>
    </div>
  </div>

  <!-- Command Palette Dialog (⌘K / Ctrl+K) -->
  <div id="cmdk-backdrop" class="ops-cmdk-backdrop" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="ops-cmdk-dialog">
      <input id="cmdk-input" class="ops-cmdk-input" type="text" aria-label="Search preview navigation" placeholder="Search preview pages… (type to filter)" autocomplete="off" />
      <ul id="cmdk-list" class="ops-cmdk-list" role="listbox" aria-label="Available commands"></ul>
      <div class="ops-cmdk-foot">
        <span>↑↓ to navigate · Enter to open · Esc to close</span>
        <span>Preview only · no staff session</span>
      </div>
    </div>
  </div>

  <script nonce="${nonce}">
    (() => {
      const ICONS = ${JSON.stringify(ICONS)};
      const DESTINATIONS = [
        { href: "/admin", label: "Operations overview", navLabel: "Overview", group: "Work", icon: ICONS.gauge, blurb: "Service levels, officers on duty, answer authority", roles: ["ssra_admin", "ssra_auditor", "ssra_staff"] },
        { href: "/agent", label: "My queue & Copilot", navLabel: "My queue", group: "Work", icon: ICONS.inbox, blurb: "Claim a case, review AI cited draft, and reply", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/admin/tickets", label: "All tickets", navLabel: "All tickets", group: "Work", icon: ICONS.list, blurb: "Every escalation, every status, every team", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/calls", label: "Phone calls desk", navLabel: "Calls", group: "Work", icon: ICONS.phone, blurb: "AI phone receptionist: live calls, transfers & takeover", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/admin/quality", label: "Service quality audit", navLabel: "Quality audit", group: "Audit", icon: ICONS.clipboardCheck, blurb: "Where answers went wrong, from taxpayers' ratings", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/audit", label: "WORM Audit trail", navLabel: "Audit trail", group: "Audit", icon: ICONS.shieldCheck, blurb: "Who changed or read what, and Merkle seal proof", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/replay", label: "Forensic turn replay", navLabel: "Forensic replay", group: "Audit", icon: ICONS.history, blurb: "Turn-by-turn redacted replay & numeric provenance", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/flags", label: "Flags & kill switches", navLabel: "Flags", group: "Configure", icon: ICONS.flag, blurb: "Degradation ladder and feature flags served right now", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/discrepancies", label: "Knowledge & Bug Reports", navLabel: "Bug Reports", group: "Configure", icon: ICONS.alertTriangle, blurb: "Taxpayer-reported inaccuracies and knowledge discrepancies", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/admin/overrides", label: "Knowledge release & overrides", navLabel: "Overrides", group: "Configure", icon: ICONS.sliders, blurb: "6-step KnowledgeSnapshot pipeline & verified staff replies", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/outbox", label: "Notification outbox", navLabel: "Outbox", group: "Configure", icon: ICONS.send, blurb: "Queued SMS, WhatsApp, and email rows", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/connectors", label: "MCP System connectors", navLabel: "Connectors", group: "Configure", icon: ICONS.plug, blurb: "Health and circuit-breaker state for 11 MCP servers", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/analytics", label: "Analytics & CX Scorecard", navLabel: "Analytics", group: "Observe", icon: ICONS.chart, blurb: "Service levels, topics, retrieval and satisfaction", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/analytics/evaluation", label: "Answer evaluation", navLabel: "Evaluation", group: "Observe", icon: ICONS.beaker, blurb: "RAG & numeric provenance metrics against thresholds", roles: ["ssra_admin", "ssra_auditor"] },
      ];

      const ROLE_META = {
        ssra_admin: { initials: "P", name: "Preview persona", label: "Not signed in · preview only" },
        ssra_staff: { initials: "P", name: "Preview persona", label: "Not signed in · preview only" },
        ssra_auditor: { initials: "P", name: "Preview persona", label: "Not signed in · preview only" },
      };

      const mainEl = document.getElementById("staff-main");
      const railEl = document.getElementById("staff-rail");
      const railGroupsEl = document.getElementById("staff-rail-groups");
      const pinBtn = document.getElementById("rail-pin-btn");
      const acctTrigger = document.getElementById("staff-acct-trigger");
      const acctMenu = document.getElementById("staff-acct-menu");

      function readUiPreference(key, fallback) {
        try {
          return localStorage.getItem(key) || fallback;
        } catch {
          return fallback;
        }
      }

      function writeUiPreference(key, value) {
        try {
          localStorage.setItem(key, value);
        } catch {}
      }

      let state = {
        route: mainEl?.getAttribute("data-route") || "/admin",
        role: readUiPreference("ssra-ops-preview-persona", "ssra_admin"),
        theme: readUiPreference("ssra-ops-theme", "dark"),
        railMode: readUiPreference("ssra-ops-rail-mode", "always-open"),
      };

      function escapeHtml(s) {
        return String(s ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;")
          .replace(/\x60/g, "&#96;");
      }

      const ttPolicy = window.trustedTypes?.createPolicy
        ? window.trustedTypes.createPolicy("ssra-ops-html", { createHTML: (h) => h })
        : null;
      function setSafeHtml(el, htmlStr) {
        if (!el) return;
        el.innerHTML = ttPolicy ? ttPolicy.createHTML(htmlStr) : htmlStr;
      }

      function applyChrome() {
        if (!["dark", "light", "high-contrast"].includes(state.theme)) state.theme = "dark";
        if (!ROLE_META[state.role]) state.role = "ssra_admin";
        if (!["always-open", "hover"].includes(state.railMode)) state.railMode = "always-open";

        document.documentElement.setAttribute("data-theme", state.theme);
        document.documentElement.setAttribute("data-rail-mode", state.railMode);
        const shouldExpandRail = state.railMode === "always-open" || Boolean(
          railEl?.matches(":hover") || railEl?.contains(document.activeElement) || acctMenu?.classList.contains("open"),
        );
        railEl?.classList.toggle("is-expanded", shouldExpandRail);
        railEl?.classList.toggle("is-collapsed", !shouldExpandRail);
        pinBtn?.classList.toggle("is-on", state.railMode === "always-open");
        pinBtn?.setAttribute("aria-pressed", String(state.railMode === "always-open"));
        if (pinBtn) setSafeHtml(pinBtn, state.railMode === "always-open" ? ICONS.chevronsLeft : ICONS.chevronsRight);

        document.querySelectorAll("[data-set-role]").forEach((btn) => {
          const isSelected = btn.getAttribute("data-set-role") === state.role;
          btn.setAttribute("aria-checked", String(isSelected));
          btn.classList.toggle("active", isSelected);
          const checkSpan = btn.querySelector("span:last-child");
          if (checkSpan && checkSpan !== btn.firstElementChild) {
            setSafeHtml(checkSpan, isSelected ? ICONS.check : "");
          }
        });
        document.querySelectorAll("[data-set-theme]").forEach((btn) => {
          const isSelected = btn.getAttribute("data-set-theme") === state.theme;
          btn.setAttribute("aria-checked", String(isSelected));
          btn.classList.toggle("active", isSelected);
        });

        const groups = ["Work", "Audit", "Configure", "Observe"];
        if (railGroupsEl) {
          setSafeHtml(
            railGroupsEl,
            groups.map((group) => {
              const destinations = DESTINATIONS.filter((item) => item.group === group && item.roles.includes(state.role));
              if (!destinations.length) return "";
              return '<div class="staff-rail-group">' +
                '<p class="staff-rail-group-label">' + escapeHtml(group) + "</p>" +
                "<ul>" + destinations.map((item) => {
                  const active = item.href === state.route;
                  return '<li><a href="' + escapeHtml(item.href) + '" data-nav="' + escapeHtml(item.href) + '" class="nav-item' + (active ? " active" : "") + '" title="' + escapeHtml(item.label) + '"' + (active ? ' aria-current="page"' : "") + ">" +
                    '<span class="staff-rail-icon" aria-hidden="true">' + item.icon + "</span>" +
                    '<span class="staff-rail-label">' + escapeHtml(item.navLabel) + "</span>" +
                  "</a></li>";
                }).join("") + "</ul></div>";
            }).join(""),
          );
        }
      }

      function renderCurrentRoute() {
        applyChrome();
        if (!mainEl) return;
        const route = DESTINATIONS.find((destination) => destination.href === state.route);
        const title = route?.label || "Operations overview";
        document.title = "SSRA Operations Console Preview — " + title;
        setSafeHtml(
          mainEl,
          '<section class="ops-panel ops-preview-card" aria-labelledby="preview-title">' +
            '<span class="ops-preview-chip">Preview only</span>' +
            '<h1 id="preview-title">' + escapeHtml(title) + "</h1>" +
            '<p>This screen is not connected to an authenticated staff session. It contains no live taxpayer records, casework, service telemetry, or operational controls.</p>' +
            '<p>Staff access will be enabled after SSRA approves the identity provider and role mapping, and the service can verify those permissions on the server.</p>' +
            '<ul><li>Use a staff identity provider with server-validated sessions.</li><li>Show live data only with its source, observation time, and freshness state.</li><li>Require server-side authorization and an audit record for every staff action.</li></ul>' +
            '<a class="ops-btn primary" href="/en" data-nav="/en">Open the public assistant ' + ICONS.arrowUpRight + "</a>" +
          "</section>",
        );
      }

      function navigateTo(href) {
        if (!href) return;
        if (href === "/en" || href.startsWith("/en")) {
          window.location.assign(href);
          return;
        }
        state.route = href;
        try { window.history.pushState({}, "", href); } catch {}
        railEl?.classList.remove("is-drawer-open");
        document.getElementById("ops-mobile-backdrop")?.classList.remove("open");
        syncStaffRailA11y(false);
        renderCurrentRoute();
        mainEl?.focus();
      }

      window.addEventListener("popstate", () => {
        state.route = window.location.pathname || "/admin";
        renderCurrentRoute();
      });

      document.body.addEventListener("click", (e) => {
        const navLink = e.target.closest("[data-nav]");
        if (navLink) {
          e.preventDefault();
          navigateTo(navLink.getAttribute("data-nav"));
          return;
        }
      });

      // Rail pin toggle, mobile drawer & hover expand
      const mobileBackdrop = document.getElementById("ops-mobile-backdrop");
      const mobileNavBtn = document.getElementById("mobile-ops-nav-btn");
      const focusAfterStaffRailStateSync = (target) => {
        if (!target || typeof target.focus !== "function") return;
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            if (target.isConnected && !target.closest("[inert]")) {
              target.focus({ preventScroll: true });
            }
          });
        });
      };
      const syncStaffRailA11y = (moveFocus = false) => {
        const isMobile = window.matchMedia?.("(max-width: 820px)")?.matches ?? false;
        const isOpen = railEl?.classList.contains("is-drawer-open") ?? false;
        railEl?.toggleAttribute("inert", isMobile && !isOpen);
        mobileNavBtn?.setAttribute("aria-expanded", String(isMobile && isOpen));
        mobileNavBtn?.setAttribute("aria-label", isMobile && isOpen ? "Close preview navigation" : "Open preview navigation");
        if (moveFocus) {
          if (isMobile && isOpen) focusAfterStaffRailStateSync(railGroupsEl?.querySelector("a"));
          else focusAfterStaffRailStateSync(mobileNavBtn);
        }
      };
      const closeStaffRail = () => {
        railEl?.classList.remove("is-drawer-open");
        mobileBackdrop?.classList.remove("open");
        syncStaffRailA11y(true);
      };
      mobileNavBtn?.addEventListener("click", () => {
        const isOpen = railEl?.classList.toggle("is-drawer-open");
        mobileBackdrop?.classList.toggle("open", Boolean(isOpen));
        syncStaffRailA11y(true);
      });
      mobileBackdrop?.addEventListener("click", closeStaffRail);
      window.addEventListener("resize", () => syncStaffRailA11y(false));
      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && railEl?.classList.contains("is-drawer-open")) closeStaffRail();
      });
      syncStaffRailA11y(false);
      pinBtn?.addEventListener("click", () => {
        state.railMode = state.railMode === "always-open" ? "hover" : "always-open";
        writeUiPreference("ssra-ops-rail-mode", state.railMode);
        applyChrome();
      });
      railEl?.addEventListener("mouseenter", () => {
        if (state.railMode === "hover") {
          railEl.classList.add("is-expanded");
          railEl.classList.remove("is-collapsed");
        }
      });
      railEl?.addEventListener("mouseleave", () => {
        if (
          state.railMode === "hover" &&
          !acctMenu?.classList.contains("open") &&
          !railEl.contains(document.activeElement)
        ) {
          railEl.classList.remove("is-expanded");
          railEl.classList.add("is-collapsed");
        }
      });
      railEl?.addEventListener("focusin", () => {
        if (state.railMode === "hover") {
          railEl.classList.add("is-expanded");
          railEl.classList.remove("is-collapsed");
        }
      });
      railEl?.addEventListener("focusout", (e) => {
        const focusMovedOutsideRail = !(e.relatedTarget instanceof Node) || !railEl.contains(e.relatedTarget);
        if (
          state.railMode === "hover" &&
          focusMovedOutsideRail &&
          !railEl.matches(":hover") &&
          !acctMenu?.classList.contains("open")
        ) {
          railEl.classList.remove("is-expanded");
          railEl.classList.add("is-collapsed");
        }
      });

      // AccountMenu popover
      acctTrigger?.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = acctMenu?.classList.toggle("open");
        acctTrigger.setAttribute("aria-expanded", String(Boolean(isOpen)));
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".staff-rail-foot")) {
          acctMenu?.classList.remove("open");
          acctTrigger?.setAttribute("aria-expanded", "false");
        }
      });
      acctMenu?.addEventListener("click", (e) => {
        const roleBtn = e.target.closest("[data-set-role]");
        if (roleBtn) {
          state.role = roleBtn.getAttribute("data-set-role") || "ssra_admin";
          writeUiPreference("ssra-ops-preview-persona", state.role);
          acctMenu.classList.remove("open");
          renderCurrentRoute();
          return;
        }
        const themeBtn = e.target.closest("[data-set-theme]");
        if (themeBtn) {
          state.theme = themeBtn.getAttribute("data-set-theme") || "dark";
          writeUiPreference("ssra-ops-theme", state.theme);
          acctMenu.classList.remove("open");
          applyChrome();
        }
      });

      // Command Palette (⌘K / Ctrl+K)
      const cmdkBackdrop = document.getElementById("cmdk-backdrop");
      const cmdkInput = document.getElementById("cmdk-input");
      const cmdkList = document.getElementById("cmdk-list");
      let cmdkActiveIdx = 0;

      function getFilteredCommands(q) {
        const needle = (q || "").trim().toLowerCase();
        const base = [
          ...DESTINATIONS.filter((d) => d.roles.includes(state.role)).map((d) => ({
            label: d.navLabel + " — " + d.label,
            hint: d.group,
            run: () => navigateTo(d.href),
          })),
          { label: "Open Taxpayer MainChat (/en)", hint: "Surface", run: () => window.location.assign("/en") },
          { label: "Preview persona: Administrator", hint: "Preview", run: () => { state.role = "ssra_admin"; renderCurrentRoute(); } },
          { label: "Preview persona: Tax Agent", hint: "Preview", run: () => { state.role = "ssra_staff"; renderCurrentRoute(); } },
          { label: "Preview persona: Auditor", hint: "Preview", run: () => { state.role = "ssra_auditor"; renderCurrentRoute(); } },
          { label: "Cycle Theme (Dark / Light / High-Contrast)", hint: "Appearance", run: () => {
            state.theme = state.theme === "dark" ? "light" : state.theme === "light" ? "high-contrast" : "dark";
            applyChrome();
          } },
        ];
        if (!needle) return base;
        return base.filter((c) => c.label.toLowerCase().includes(needle) || c.hint.toLowerCase().includes(needle));
      }

      let cmdkReturnFocusEl = null;

      function renderCmdkList() {
        const cmds = getFilteredCommands(cmdkInput?.value || "");
        if (cmdkActiveIdx >= cmds.length) cmdkActiveIdx = 0;
        if (cmdkList) {
          setSafeHtml(
            cmdkList,
            cmds.map((c, idx) =>
              '<li class="ops-cmdk-item" role="option" data-cmd-idx="' + idx + '" data-active="' + (idx === cmdkActiveIdx) + '">' +
                "<span>" + escapeHtml(c.label) + "</span>" +
                '<span class="ops-kbd">' + escapeHtml(c.hint) + "</span>" +
              "</li>"
            ).join("")
          );
        }
        return cmds;
      }

      function openCmdk() {
        cmdkReturnFocusEl = document.activeElement;
        cmdkBackdrop?.classList.add("open");
        if (cmdkInput) {
          cmdkInput.value = "";
          cmdkActiveIdx = 0;
          renderCmdkList();
          cmdkInput.focus();
        }
      }
      function closeCmdk() {
        cmdkBackdrop?.classList.remove("open");
        if (
          cmdkReturnFocusEl &&
          cmdkReturnFocusEl.isConnected &&
          typeof cmdkReturnFocusEl.focus === "function"
        ) {
          cmdkReturnFocusEl.focus();
        } else if (mainEl && typeof mainEl.focus === "function") {
          mainEl.focus();
        }
      }

      document.getElementById("cmdk-open-btn")?.addEventListener("click", openCmdk);
      cmdkBackdrop?.addEventListener("click", (e) => {
        if (e.target === cmdkBackdrop) closeCmdk();
      });
      cmdkInput?.addEventListener("input", () => {
        cmdkActiveIdx = 0;
        renderCmdkList();
      });
      cmdkList?.addEventListener("click", (e) => {
        const li = e.target.closest("[data-cmd-idx]");
        if (li) {
          const idx = Number(li.getAttribute("data-cmd-idx")) || 0;
          const cmds = getFilteredCommands(cmdkInput?.value || "");
          closeCmdk();
          cmds[idx]?.run();
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
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          if (cmdkBackdrop?.classList.contains("open")) closeCmdk();
          else openCmdk();
          return;
        }
        if (cmdkBackdrop?.classList.contains("open")) {
          if (e.key === "Tab") {
            trapModalTabFocus(e, cmdkBackdrop);
            return;
          }
          const cmds = getFilteredCommands(cmdkInput?.value || "");
          if (e.key === "Escape") { e.preventDefault(); closeCmdk(); }
          else if (e.key === "ArrowDown" && cmds.length) { e.preventDefault(); cmdkActiveIdx = (cmdkActiveIdx + 1) % cmds.length; renderCmdkList(); }
          else if (e.key === "ArrowUp" && cmds.length) { e.preventDefault(); cmdkActiveIdx = (cmdkActiveIdx - 1 + cmds.length) % cmds.length; renderCmdkList(); }
          else if (e.key === "Enter" && cmds.length) { e.preventDefault(); closeCmdk(); cmds[cmdkActiveIdx]?.run(); }
          return;
        }
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.metaKey || e.altKey) return;
      });

      renderCurrentRoute();
    })();
  </script>
</body>
</html>`;
  return compactOpsHtmlAssetBlocks(rawHtml);
}
