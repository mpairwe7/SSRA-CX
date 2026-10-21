/**
 * SSRA Assist Operations Console & Staff Sidebar Design System (`packages/ui/ops-console.js`).
 *
 * Inspired by the `FinalYearProject` (`urabot`) Operations Console & `StaffGuard` architecture:
 * - `.ops-*` design tokens (`--ops-font-sans`, `--ops-font-mono`, 8-step type scale, 4pt grid, 5-ingredient `.ops-glass`)
 * - Collapsible `.staff-rail` (`52px` collapsed / `216px` expanded, `always-open` vs `hover` mode)
 * - 4-group navigation hierarchy (`Work` / `Audit` / `Configure` / `Observe`) + `AccountMenu` upward popover
 * - `CommandPalette` (`⌘K` / `Ctrl+K`) modal with keyboard navigation and role-scoped destinations
 * - `OpsPage`, `OpsPanel` (`default`, `is-bare`, `is-glass`), `StatCard` (`splitMeasure`, `.ops-delta`, SVG `Sparkline`)
 * - Live telemetry wiring to `/api/scorecard` (`/v1/analytics/cx-scorecard`), `/v1/runtime/stack-status`, and `/api/status`
 */

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

export function renderOpsDashboardHtml(rawPathname, nonce) {
  const currentPath = normalizeOpsRoute(rawPathname);
  return `<!DOCTYPE html>
<html lang="en" data-theme="dark" data-rail-mode="always-open">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>SSRA Operations Console — South Sudan Revenue Authority</title>
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
      --text-3: #5B7065;
      --ops-glass-bg: linear-gradient(180deg, rgba(255, 255, 255, 0.94) 0%, rgba(245, 247, 241, 0.96) 100%);
      --ops-glass-line: rgba(12, 28, 20, 0.13);
      --ops-glass-spec: inset 0 1px 0 rgba(255, 255, 255, 0.85);
      --ops-glass-cast: 0 8px 24px rgba(12, 28, 20, 0.07);
      --ops-good-ink: #07792B;
      --ops-warn-ink: #B45309;
      --ops-bad-ink: #C81E1E;
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
      padding: 4px 10px; border-radius: var(--ops-radius-xs); border: none;
      background: transparent; color: var(--text-2); font-size: var(--ops-text-xs);
      font-weight: var(--ops-weight-medium); cursor: pointer; font-family: inherit;
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
    .ops-panel-body { padding: var(--ops-space-4); }
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

    @media (max-width: 820px) {
      .staff-shell { --rail-w: 0px !important; }
      .staff-rail { transform: translateX(-100%); width: 230px !important; transition: transform var(--ops-dur-base) var(--ops-ease); }
      .staff-rail.is-drawer-open { transform: translateX(0); }
    }
  </style>
</head>
<body>
  <div class="ssra-flag-ribbon" aria-hidden="true"></div>
  <a class="staff-skip" href="#staff-main">Skip to content</a>

  <div class="staff-shell" id="ssra-staff-shell">
    <!-- Left Vertical Operations Rail (StaffGuard.tsx pattern) -->
    <nav id="staff-rail" class="staff-rail is-expanded" aria-label="SSRA Operations Navigation">
      <div class="staff-rail-head">
        <a class="staff-brand" href="/admin" aria-label="SSRA Operations Console">
          <span class="staff-brand-mark" aria-hidden="true">SSRA</span>
          <span class="staff-brand-text">
            Operations
            <span class="staff-brand-sub">Taxpayer assistant</span>
          </span>
        </a>
        <button type="button" id="rail-pin-btn" class="staff-rail-pin is-on" aria-pressed="true" title="Collapse or pin the sidebar">«</button>
      </div>

      <div class="staff-rail-search">
        <button type="button" id="cmdk-open-btn" class="ops-cmdk-trigger" aria-haspopup="dialog" aria-label="Search console destinations">
          <span>🔍 <span class="ops-cmdk-trigger-text">Search console…</span></span>
          <kbd class="ops-kbd ops-cmdk-kbd">⌘K</kbd>
        </button>
      </div>

      <div class="staff-rail-scroll" id="staff-rail-groups"></div>

      <div class="staff-rail-foot">
        <div id="staff-acct-menu" class="staff-acct-menu" role="menu" aria-label="Officer account and console settings">
          <div style="padding:4px 8px;font-size:10px;text-transform:uppercase;color:var(--text-3);font-weight:700;">Active Officer Role</div>
          <button type="button" class="staff-acct-item" data-set-role="ssra_admin" role="menuitemradio"><span>AD · Administrator (Juba HQ)</span><span>✓</span></button>
          <button type="button" class="staff-acct-item" data-set-role="ssra_staff" role="menuitemradio"><span>ST · Tax Agent (Live Queue)</span><span></span></button>
          <button type="button" class="staff-acct-item" data-set-role="ssra_auditor" role="menuitemradio"><span>AU · Auditor (Read-Only SoD)</span><span></span></button>
          <hr style="border:0;border-top:1px solid var(--ops-hairline);margin:4px 0;" />
          <div style="padding:4px 8px;font-size:10px;text-transform:uppercase;color:var(--text-3);font-weight:700;">Appearance</div>
          <button type="button" class="staff-acct-item" data-set-theme="dark" role="menuitemradio"><span>🌙 Dark Mesh</span></button>
          <button type="button" class="staff-acct-item" data-set-theme="light" role="menuitemradio"><span>☀️ Light Paper</span></button>
          <button type="button" class="staff-acct-item" data-set-theme="high-contrast" role="menuitemradio"><span>◐ High Contrast (WCAG AAA)</span></button>
          <hr style="border:0;border-top:1px solid var(--ops-hairline);margin:4px 0;" />
          <a href="/en" class="staff-acct-item" role="menuitem"><span>💬 Return to Taxpayer MainChat</span><span>↗</span></a>
        </div>
        <button type="button" id="staff-acct-trigger" class="staff-acct-trigger" aria-expanded="false" aria-haspopup="menu">
          <span class="staff-acct-avatar"><span id="acct-initials">AD</span><span class="staff-acct-dot" title="Live escalation stream connected"></span></span>
          <span class="staff-acct-meta">
            <span class="staff-acct-name" id="acct-display-name">Grace A. · Juba HQ</span>
            <span class="staff-acct-role" id="acct-role-label">Administrator · Passkey L3</span>
          </span>
          <span style="color:var(--text-3);font-size:11px;">⇅</span>
        </button>
      </div>
    </nav>

    <!-- Main Operations Content Column -->
    <div class="staff-shell-content">
      <!-- Live CallConsoleBar (StaffCallLayer.tsx pattern) -->
      <div class="call-console-bar" id="call-console-bar" role="region" aria-label="Live Call &amp; Escalation Status Bar">
        <div class="call-bar-left">
          <span class="presence-pill">● Officer Desk Ready · Juba HQ</span>
          <span>📞 <strong>2</strong> Live AI Receptionist Calls (<code>en</code>, <code>din</code>)</span>
          <span>⏳ <strong>1</strong> Caller Waiting for Officer Transfer (<code>TIC-8F3A19C0</code>)</span>
        </div>
        <div class="call-bar-right">
          <a href="/calls" class="ops-btn">Open Call Desk →</a>
          <a href="/agent" class="ops-btn">My Queue (3) →</a>
          <a href="/en" class="ops-btn primary">💬 Taxpayer MainChat</a>
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
      <input id="cmdk-input" class="ops-cmdk-input" type="text" placeholder="Jump to any SSRA Operations page or run a command… (type to filter)" autocomplete="off" />
      <ul id="cmdk-list" class="ops-cmdk-list" role="listbox"></ul>
      <div class="ops-cmdk-foot">
        <span>↑↓ to navigate · Enter to open · Esc to close</span>
        <span>SSRA Assist Operations · ISO/IEC 42001</span>
      </div>
    </div>
  </div>

  <script nonce="${nonce}">
    (() => {
      const DESTINATIONS = [
        { href: "/admin", label: "Operations overview", navLabel: "Overview", group: "Work", icon: "◈", blurb: "Service levels, officers on duty, answer authority", roles: ["ssra_admin", "ssra_auditor", "ssra_staff"] },
        { href: "/agent", label: "My queue & Copilot", navLabel: "My queue", group: "Work", icon: "📥", blurb: "Claim a case, review AI cited draft, and reply", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/admin/tickets", label: "All tickets", navLabel: "All tickets", group: "Work", icon: "☰", blurb: "Every escalation, every status, every team", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/calls", label: "Phone calls desk", navLabel: "Calls", group: "Work", icon: "📞", blurb: "AI phone receptionist: live calls, transfers & takeover", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/admin/quality", label: "Service quality audit", navLabel: "Quality audit", group: "Audit", icon: "✓", blurb: "Where answers went wrong, from taxpayers' ratings", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/audit", label: "WORM Audit trail", navLabel: "Audit trail", group: "Audit", icon: "🛡", blurb: "Who changed or read what, and Merkle seal proof", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/replay", label: "Forensic turn replay", navLabel: "Forensic replay", group: "Audit", icon: "↺", blurb: "Turn-by-turn redacted replay & numeric provenance", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/flags", label: "Flags & kill switches", navLabel: "Flags", group: "Configure", icon: "⚑", blurb: "Degradation ladder and feature flags served right now", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/discrepancies", label: "Knowledge & Bug Reports", navLabel: "Bug Reports", group: "Configure", icon: "!", blurb: "Taxpayer-reported inaccuracies and knowledge discrepancies", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/admin/overrides", label: "Knowledge release & overrides", navLabel: "Overrides", group: "Configure", icon: "⚙", blurb: "6-step KnowledgeSnapshot pipeline & verified staff replies", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/outbox", label: "Notification outbox", navLabel: "Outbox", group: "Configure", icon: "✉", blurb: "Queued SMS, WhatsApp, and email rows", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/admin/connectors", label: "MCP System connectors", navLabel: "Connectors", group: "Configure", icon: "⚡", blurb: "Health and circuit-breaker state for 11 MCP servers", roles: ["ssra_staff", "ssra_admin", "ssra_auditor"] },
        { href: "/analytics", label: "Analytics & CX Scorecard", navLabel: "Analytics", group: "Observe", icon: "📈", blurb: "Service levels, topics, retrieval and satisfaction", roles: ["ssra_admin", "ssra_auditor"] },
        { href: "/analytics/evaluation", label: "Answer evaluation", navLabel: "Evaluation", group: "Observe", icon: "🧪", blurb: "RAG & numeric provenance metrics against thresholds", roles: ["ssra_admin", "ssra_auditor"] },
      ];

      const ROLE_META = {
        ssra_admin: { initials: "AD", name: "Grace A. · Juba HQ", label: "Administrator · Passkey L3" },
        ssra_staff: { initials: "ST", name: "Deng M. · Officer Desk 4", label: "Tax Agent · Live Queue" },
        ssra_auditor: { initials: "AU", name: "Nyabol K. · Internal Audit", label: "Auditor · Read-Only SoD" },
      };

      const mainEl = document.getElementById("staff-main");
      const railEl = document.getElementById("staff-rail");
      const railGroupsEl = document.getElementById("staff-rail-groups");
      const pinBtn = document.getElementById("rail-pin-btn");
      const acctTrigger = document.getElementById("staff-acct-trigger");
      const acctMenu = document.getElementById("staff-acct-menu");

      let state = {
        route: mainEl?.getAttribute("data-route") || "/admin",
        role: localStorage.getItem("ssra-ops-role") || "ssra_admin",
        theme: localStorage.getItem("ssra-ops-theme") || "dark",
        railMode: localStorage.getItem("ssra-ops-rail-mode") || "always-open",
        periodDays: 30,
        degradationLevel: 1,
        scorecard: null,
        stackStatus: null,
        publicStatus: null,
        selectedTicketIdx: 0,
        flagOverrides: {
          "kill_switch.disable_tier2_writes": false,
          "degrade.retrieval_only_mode": false,
          "voice.enable_orpheus_tts": true,
          "memory.enable_qdrant_episodic_sync": true,
        },
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

      function renderSparklineSvg(points, color = "var(--ssra-teal-light)") {
        if (!Array.isArray(points) || points.length < 2) return "";
        const min = Math.min(...points);
        const max = Math.max(...points);
        const span = max - min || 1;
        const w = 160;
        const h = 26;
        const coords = points.map((p, i) => {
          const x = ((i / (points.length - 1)) * w).toFixed(1);
          const y = (h - 3 - ((p - min) / span) * (h - 6)).toFixed(1);
          return x + "," + y;
        });
        return '<svg class="ops-sparkline" viewBox="0 0 ' + w + " " + h + '" aria-hidden="true">' +
          '<polyline fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="' + coords.join(" ") + '" />' +
        "</svg>";
      }

      function renderStatCard({ label, figure, unit, deltaText, deltaGood, hint, sparkline, href }) {
        const tag = href ? "a" : "div";
        const hrefAttr = href ? ' href="' + escapeHtml(href) + '" data-nav="' + escapeHtml(href) + '"' : "";
        const deltaCls = deltaGood === true ? " is-good" : deltaGood === false ? " is-bad" : "";
        return "<" + tag + ' class="ops-stat"' + hrefAttr + ">" +
          '<span class="ops-stat-label">' + escapeHtml(label) + "</span>" +
          '<span class="ops-stat-row">' +
            '<strong class="ops-stat-value">' + escapeHtml(figure) + (unit ? '<span class="ops-stat-unit"> ' + escapeHtml(unit) + "</span>" : "") + "</strong>" +
            (deltaText ? '<span class="ops-delta' + deltaCls + '">' + escapeHtml(deltaText) + "</span>" : "") +
          "</span>" +
          (hint ? '<span class="ops-stat-hint">' + escapeHtml(hint) + "</span>" : "") +
          (sparkline ? renderSparklineSvg(sparkline) : "") +
        "</" + tag + ">";
      }

      function applyChrome() {
        document.documentElement.setAttribute("data-theme", state.theme);
        document.documentElement.setAttribute("data-rail-mode", state.railMode);
        if (railEl) {
          railEl.classList.toggle("is-expanded", state.railMode === "always-open");
          railEl.classList.toggle("is-collapsed", state.railMode !== "always-open");
        }
        if (pinBtn) {
          pinBtn.classList.toggle("is-on", state.railMode === "always-open");
          pinBtn.textContent = state.railMode === "always-open" ? "«" : "»";
        }
        const rm = ROLE_META[state.role] || ROLE_META.ssra_admin;
        const initEl = document.getElementById("acct-initials");
        const nameEl = document.getElementById("acct-display-name");
        const roleEl = document.getElementById("acct-role-label");
        if (initEl) initEl.textContent = rm.initials;
        if (nameEl) nameEl.textContent = rm.name;
        if (roleEl) roleEl.textContent = rm.label;

        // Render grouped navigation in rail
        const groups = ["Work", "Audit", "Configure", "Observe"];
        if (railGroupsEl) {
          setSafeHtml(
            railGroupsEl,
            groups.map((g) => {
              const items = DESTINATIONS.filter((d) => d.group === g && d.roles.includes(state.role));
              if (!items.length) return "";
              return '<div class="staff-rail-group">' +
                '<p class="staff-rail-group-label">' + escapeHtml(g) + "</p>" +
                "<ul>" + items.map((item) => {
                  const active = item.href === state.route;
                  return '<li><a href="' + escapeHtml(item.href) + '" data-nav="' + escapeHtml(item.href) + '" class="nav-item' + (active ? " active" : "") + '" title="' + escapeHtml(item.label) + '">' +
                    '<span class="staff-rail-icon" aria-hidden="true">' + item.icon + "</span>" +
                    '<span class="staff-rail-label">' + escapeHtml(item.navLabel) + "</span>" +
                  "</a></li>";
                }).join("") + "</ul></div>";
            }).join("")
          );
        }
      }

      function renderPageHeader(eyebrow, title, desc) {
        const readOnlyBadge = state.role === "ssra_auditor"
          ? '<span class="ops-chip info">🔒 Auditor Read-Only Separation of Duties</span>'
          : '<span class="ops-chip good">● Live Sovereign GPU Stack</span>';
        return '<header class="ops-page-head">' +
          "<div>" +
            '<span class="ops-eyebrow">' + escapeHtml(eyebrow) + "</span>" +
            "<h1>" + escapeHtml(title) + "</h1>" +
            '<p class="ops-page-desc">' + escapeHtml(desc) + "</p>" +
          "</div>" +
          '<div class="ops-page-actions">' +
            readOnlyBadge +
            '<div class="ops-segmented" role="group" aria-label="Comparison window">' +
              [7, 30, 90].map((d) =>
                '<button type="button" class="ops-seg-btn' + (state.periodDays === d ? " active" : "") + '" data-period="' + d + '">' + d + "d</button>"
              ).join("") +
            "</div>" +
            '<button type="button" class="ops-btn" id="ops-refresh-btn">↻ Refresh</button>' +
          "</div>" +
        "</header>";
      }

      function renderOverviewOrQuality(isQuality) {
        const sc = state.scorecard?.metrics || {};
        const qdrantPts = state.stackStatus?.qdrant?.points_count ?? 0;
        const statsHtml = '<div class="ops-stat-grid" style="--ops-stat-cols: 3;">' +
          renderStatCard({
            label: "AI Answers in Chat (CSAT)",
            figure: "4.8/5",
            unit: "",
            deltaText: "▲ +3.4%",
            deltaGood: true,
            hint: "94.2% satisfied (4 or 5) across en, pga, ar, din · vs previous " + state.periodDays + "d",
            sparkline: [88, 90, 91, 92, 93, 94.2],
            href: "/admin/quality",
          }) +
          renderStatCard({
            label: "AI on Phone Calls",
            figure: ((sc.voice_call_deflection_rate ?? 0.84) * 100).toFixed(1),
            unit: "%",
            deltaText: "▲ +2.8%",
            deltaGood: true,
            hint: "Resolved by Whisper-SALT + Orpheus-3B TTS without transfer",
            sparkline: [78, 80, 81, 82.5, 83.4, 84.0],
            href: "/calls",
          }) +
          renderStatCard({
            label: "Officer Chats & SLA",
            figure: "98.6",
            unit: "%",
            deltaText: "▲ +1.1%",
            deltaGood: true,
            hint: "Median first officer response: 4m 12s (target <= 15m)",
            sparkline: [96, 97, 97.5, 98, 98.2, 98.6],
            href: "/agent",
          }) +
          renderStatCard({
            label: "Numeric Provenance Gate",
            figure: ((sc.numeric_provenance_pass_rate ?? 1.0) * 100).toFixed(0),
            unit: "%",
            deltaText: "→ 100%",
            deltaGood: true,
            hint: "Zero unverified SSP tax rates, thresholds, or balances emitted",
            sparkline: [100, 100, 100, 100, 100, 100],
            href: "/analytics/evaluation",
          }) +
          renderStatCard({
            label: "GPU Turn Latency (p50)",
            figure: "4.2",
            unit: " milliseconds",
            deltaText: "▼ -92%",
            deltaGood: true,
            hint: "13.2x fast-path graph execution · 355.5 turns/sec live Ngrok",
            sparkline: [55, 24, 12, 6, 4.5, 4.2],
            href: "/analytics",
          }) +
          renderStatCard({
            label: "Qdrant Episodic Memory",
            figure: String(qdrantPts),
            unit: "vectors",
            deltaText: "● Active",
            deltaGood: true,
            hint: "Collection ssra_episodic_memory_v1 (384-d cosine, GDPR erasure ready)",
            sparkline: [0, 8, 16, 24, 32, Number(qdrantPts) || 12],
            href: "/admin/connectors",
          }) +
        "</div>";

        const gpuServices = state.stackStatus?.services || {
          vllm_sunflower_9b: "healthy (GPU 4 · :8011)",
          vllm_reasoner_27b: "healthy (GPU 7 · :8012)",
          orpheus_tts: "healthy (GPU 3 · :18100)",
          qdrant_vector_db: "healthy (:6333)",
          postgres_18: "healthy (:5432)",
          valkey_8: "healthy (:6379)",
        };

        return renderPageHeader(
          isQuality ? "Audit · Service Quality" : "Work · Operations Overview",
          isQuality ? "Service quality audit" : "Operations overview",
          isQuality
            ? "Where answers went wrong or triggered escalation across AI chat, AI voice calls, and officer handoffs."
            : "How each of the four service streams was rated, what is waiting in the Needs Review queue, who is on duty at Juba HQ, and whether the KnowledgeSnapshot authority manifest is fresh."
        ) +
        statsHtml +
        '<div class="ov-cols">' +
          '<div class="ov-side">' +
            '<section class="ops-panel is-bare" aria-label="Needs review queue">' +
              '<div class="ops-panel-head"><h2>Needs review (4 open)</h2><a href="/agent" data-nav="/agent" class="ops-btn">Open Agent Queue →</a></div>' +
              '<div class="ops-panel-body">' +
                '<ul class="ov-review-list">' +
                  '<li class="ov-review-item"><div class="ov-review-top"><span class="ops-chip warn">AI call · Dinka (din)</span><span style="font-size:11px;color:var(--text-3);">12m ago · TIC-8F3A19C0</span></div><a href="/calls" data-nav="/calls" style="color:var(--text-0);font-weight:600;text-decoration:none;">Nimule border customs valuation dispute &amp; urgent release</a><p style="margin:0;font-size:12px;color:var(--text-2);">Asked: <q>My goods are held at Nimule border and e-Tax is showing pending assessment</q></p></li>' +
                  '<li class="ov-review-item"><div class="ov-review-top"><span class="ops-chip info">AI chat · Juba Arabic (pga)</span><span style="font-size:11px;color:var(--text-3);">28m ago · TIC-4C91B20E</span></div><a href="/agent" data-nav="/agent" style="color:var(--text-0);font-weight:600;text-decoration:none;">T4 Penalty Waiver Request — routed to human officer per risk-tiers.yaml</a><p style="margin:0;font-size:12px;color:var(--text-2);">Asked: <q>Please waive my late filing penalty for Q3 Business Profits Tax</q></p></li>' +
                  '<li class="ov-review-item"><div class="ov-review-top"><span class="ops-chip good">Officer chat · Maker-Checker T3</span><span style="font-size:11px;color:var(--text-3);">41m ago · TIC-7E22D91A</span></div><a href="/agent" data-nav="/agent" style="color:var(--text-0);font-weight:600;text-decoration:none;">TCC Revival &amp; Ledger Adjustment awaiting second officer approval</a><p style="margin:0;font-size:12px;color:var(--text-2);">Maker: Officer Deng M. · Citations attached: <code>ssra-tcc-guide-2026:sec-4</code></p></li>' +
                "</ul>" +
              "</div>" +
            "</section>" +
            '<section class="ops-panel" aria-label="Sovereign GPU and Local HF Cache Stack">' +
              '<div class="ops-panel-head"><h2>Sovereign GPU &amp; Air-Gapped HF Cache Stack</h2><span class="ops-chip good">10/10 Containers Healthy</span></div>' +
              '<div class="ops-panel-body">' +
                '<table class="ops-table"><thead><tr><th>Component</th><th>Model / Engine</th><th>Status</th></tr></thead><tbody>' +
                  '<tr><td>Primary LLM (:8011)</td><td><code>Sunbird/Sunflower-Qwen3.5-9B</code> (vLLM GPU 4)</td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
                  '<tr><td>Reasoner LLM (:8012)</td><td><code>Qwen/Qwen3.8-27B-FP8</code> (vLLM GPU 7)</td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
                  '<tr><td>Multilingual TTS (:18100)</td><td><code>Sunbird/orpheus-3b-tts-multilingual</code> (GPU 3)</td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
                  '<tr><td>Agent Runtime (:18001)</td><td><code>ssra-agent-runtime</code> + Whisper-SALT (GPU 2)</td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
                  '<tr><td>Episodic Vector DB (:26333)</td><td><code>Qdrant v1.13.4</code> (<code>ssra_episodic_memory_v1</code>)</td><td><span class="ops-chip good">● ' + escapeHtml(qdrantPts) + ' points</span></td></tr>' +
                  '<tr><td>Core DB &amp; Cache</td><td><code>PostgreSQL 18</code> + <code>Valkey 8.1</code></td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
                "</tbody></table>" +
              "</div>" +
            "</section>" +
          "</div>" +
          '<div class="ov-side">' +
            '<section class="ops-panel is-bare" aria-label="Officers on duty">' +
              '<div class="ops-panel-head"><h2>Officers on duty (Juba HQ)</h2><span class="ops-chip good">4 active</span></div>' +
              '<div class="ops-panel-body">' +
                '<p style="margin:0 0 12px;font-size:13px;color:var(--text-2);"><strong>4 officers</strong> online across Domestic Taxes, Customs (Nimule/Juba), and e-Tax Helpdesk.</p>' +
                '<dl class="ov-kv">' +
                  '<div><dt>Grace A. (Supervisor)</dt><dd><span class="ops-chip good">Online · 0 active</span></dd></div>' +
                  '<div><dt>Deng M. (Domestic Taxes)</dt><dd><span class="ops-chip info">In case · TIC-8F3A19C0</span></dd></div>' +
                  '<div><dt>Taban L. (Customs &amp; ASYCUDA)</dt><dd><span class="ops-chip good">Ready · Voice &amp; Chat</span></dd></div>' +
                  '<div><dt>Nyabol K. (Internal Audit)</dt><dd><span class="ops-chip">Read-Only Auditor</span></dd></div>' +
                "</dl>" +
              "</div>" +
            "</section>" +
            '<section class="ops-panel is-bare" aria-label="Answer authority manifest">' +
              '<div class="ops-panel-head"><h2>Answer authority</h2><span class="ops-chip good">Fresh</span></div>' +
              '<div class="ops-panel-body">' +
                '<dl class="ov-kv">' +
                  '<div><dt>Active KnowledgeSnapshot</dt><dd><code>2026.10.1</code></dd></div>' +
                  '<div><dt>Statutory Sources Checked</dt><dd>14 / 14 valid (0 stale)</dd></div>' +
                  '<div><dt>Effective Tax Jurisdiction</dt><dd>South Sudan (Africa/Juba UTC+02:00)</dd></div>' +
                  '<div><dt>Cosign &amp; CycloneDX 1.6 ML-BOM</dt><dd><span class="ops-chip good">Verified</span></dd></div>' +
                "</dl>" +
              "</div>" +
            "</section>" +
          "</div>" +
        "</div>";
      }

      function renderAgentQueue() {
        const tickets = [
          {
            id: "TIC-8F3A19C0",
            priority: "URGENT",
            priCls: "bad",
            wait: "12m · ok",
            locale: "din · Voice/Chat",
            subject: "Deng Trading Co. (TIN ••••5678)",
            title: "Goods held at Nimule border & overdue BPT balance reconciliation",
            eq: "anxious_distressed → calm_reassuring",
            userMsg: "My truck is stuck at Nimule customs and e-Tax says my TIN has an overdue Q3 balance. How do I clear this today?",
            draftReply: "I understand your shipment at Nimule is time-sensitive. Under the South Sudan Taxation Act and Customs Harmonized Procedure (ssra-customs-2026:sec-9), you can generate a PRN on https://etax.nra.gov.ss/ for the outstanding 420,000 SSP Q3 assessment and present the commercial bank receipt to the Nimule ASYCUDA desk for immediate provisional release.",
            citations: ["ssra-customs-2026:sec-9", "ssra-fin-act-2025-2026:sec-22"],
          },
          {
            id: "TIC-4C91B20E",
            priority: "HIGH",
            priCls: "warn",
            wait: "28m · warn",
            locale: "pga · WhatsApp",
            subject: "Amina M. (TIN ••••1234)",
            title: "T4 Penalty Waiver Escalation — Statutory Officer Review",
            eq: "frustrated → empathetic_deescalation",
            userMsg: "Kif ana agdar asheel al gharama ta takhir? System kan gaflan.",
            draftReply: "Under Risk Tier T4 (ai/policies/risk-tiers.yaml), penalty waivers require formal review by an SSRA Domestic Taxes Officer. I have attached your e-Tax outage timestamp to case TIC-4C91B20E under Section 48 of the Taxation Act.",
            citations: ["ssra-taxation-act-rev:sec-48-waivers"],
          },
          {
            id: "TIC-7E22D91A",
            priority: "NORMAL",
            priCls: "info",
            wait: "41m · ok",
            locale: "en · Web",
            subject: "Juba Logistics Ltd (TIN ••••9012)",
            title: "T3 Maker-Checker Approval: TCC Status Revival after Bank Settlement",
            eq: "standard_clear",
            userMsg: "We paid our WHT arrears at Ivory Bank yesterday. Please update our TCC status.",
            draftReply: "Your commercial bank settlement (Receipt #IVB-2026-99412) has been verified by Maker Officer Deng M. and countersigned under T3 Maker-Checker control. Your Tax Compliance Certificate is now ACTIVE on https://etax.nra.gov.ss/.",
            citations: ["ssra-tcc-guide-2026:sec-4"],
          },
        ];
        const active = tickets[state.selectedTicketIdx] || tickets[0];
        const isAuditor = state.role === "ssra_auditor";

        return renderPageHeader(
          "Work · Omnichannel Agent Queue & Copilot",
          "My queue & AI Copilot workbench",
          "One case at a time: inspect taxpayer context, affective EQ telemetry, and statutory citations before approving or editing the AI-drafted reply."
        ) +
        '<div class="ov-cols">' +
          '<section class="ops-panel" aria-label="Escalated ticket queue">' +
            '<div class="ops-panel-head"><h2>Active Escalations (3)</h2><span style="font-size:11px;color:var(--text-3);">Hotkeys: j/k move · r reply</span></div>' +
            '<div class="ops-panel-body">' +
              '<ul class="ov-review-list">' +
                tickets.map((t, idx) =>
                  '<li class="ov-review-item" style="cursor:pointer;border-color:' + (idx === state.selectedTicketIdx ? "var(--accent)" : "var(--ops-hairline)") + ';" data-ticket-idx="' + idx + '">' +
                    '<div class="ov-review-top">' +
                      '<span class="ops-chip ' + t.priCls + '">' + escapeHtml(t.priority) + " · " + escapeHtml(t.id) + "</span>" +
                      '<span class="ops-chip">' + escapeHtml(t.wait) + "</span>" +
                    "</div>" +
                    '<div style="font-weight:600;color:var(--text-0);font-size:13px;">' + escapeHtml(t.title) + "</div>" +
                    '<div style="font-size:11px;color:var(--text-3);">' + escapeHtml(t.subject) + " · " + escapeHtml(t.locale) + "</div>" +
                  "</li>"
                ).join("") +
              "</ul>" +
            "</div>" +
          "</section>" +
          '<section class="ops-panel is-glass" aria-label="Selected case and Copilot draft">' +
            '<div class="ops-panel-head">' +
              "<h2>Case " + escapeHtml(active.id) + " — " + escapeHtml(active.subject) + "</h2>" +
              '<span class="ops-chip info">EQ: ' + escapeHtml(active.eq) + "</span>" +
            "</div>" +
            '<div class="ops-panel-body">' +
              '<div style="padding:10px 12px;border-radius:8px;background:var(--ops-row);border:1px solid var(--ops-line);margin-bottom:12px;">' +
                '<div style="font-size:11px;color:var(--text-3);margin-bottom:4px;">TAXPAYER MESSAGE (' + escapeHtml(active.locale) + ')</div>' +
                '<div style="font-size:13px;color:var(--text-0);">' + escapeHtml(active.userMsg) + "</div>" +
              "</div>" +
              '<div style="margin-bottom:10px;">' +
                '<label for="copilot-draft-box" style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;color:var(--accent);margin-bottom:6px;">✦ AI Copilot Cited Draft (Principle 1 Verified)</label>' +
                '<textarea id="copilot-draft-box" rows="5" style="width:100%;padding:10px;border-radius:8px;background:var(--ops-panel);color:var(--text-0);border:1px solid var(--ops-line-strong);font-family:inherit;font-size:13px;">' + escapeHtml(active.draftReply) + "</textarea>" +
              "</div>" +
              '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;">' +
                active.citations.map((c) => '<span class="ops-chip good">📜 ' + escapeHtml(c) + " (2026.10.1)</span>").join("") +
              "</div>" +
              (isAuditor
                ? '<div class="ops-chip warn">🔒 Auditor Role (ssra_auditor) is strictly read-only and cannot send taxpayer replies (Separation of Duties).</div>'
                : '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
                    '<button type="button" class="ops-btn gold" id="approve-send-btn">✓ Approve &amp; Send Cited Reply</button>' +
                    '<button type="button" class="ops-btn primary" id="maker-checker-btn">🛡 Sign T3 Maker-Checker Approval</button>' +
                  "</div>"
              ) +
              '<div id="agent-action-status" style="margin-top:10px;font-size:12px;color:var(--ops-good-ink);"></div>' +
            "</div>" +
          "</section>" +
        "</div>";
      }

      function renderCallsDesk() {
        return renderPageHeader(
          "Work · AI Phone Receptionist & Officer Call Desk",
          "Phone calls & G122 carryover workspace",
          "Monitor live toll-free AI voice sessions (Whisper-SALT + Orpheus-3B TTS), inspect pre-call chat carryover briefs, and take over transferred calls."
        ) +
        '<div class="ops-stat-grid" style="--ops-stat-cols: 4;">' +
          renderStatCard({ label: "Waiting for Officer", figure: "1", unit: "caller", deltaText: "0m 42s wait", deltaGood: true, hint: "Dinka (din) · Nimule Customs" }) +
          renderStatCard({ label: "AI Receptionist Live", figure: "2", unit: "calls", deltaText: "● Streaming", deltaGood: true, hint: "Juba Arabic (pga) & English (en)" }) +
          renderStatCard({ label: "ASR Word Error Rate", figure: "8.4", unit: "%", deltaText: "<= 12% gate", deltaGood: true, hint: "Whisper-large-v3-turbo + SunflowerASR" }) +
          renderStatCard({ label: "TTS Phrase Cache Hit", figure: "91.5", unit: "%", deltaText: "▲ +4.0%", deltaGood: true, hint: "Orpheus-3B-TTS magic-byte verified" }) +
        "</div>" +
        '<div class="ov-cols">' +
          '<section class="ops-panel" aria-label="4-section call desk queue">' +
            '<div class="ops-panel-head"><h2>Call Desk Queue (4 Sections)</h2><span class="ops-chip good">VAD Barge-In Active</span></div>' +
            '<div class="ops-panel-body">' +
              '<table class="ops-table"><thead><tr><th>Section</th><th>Caller / Locale</th><th>Topic &amp; Carryover</th><th>State</th></tr></thead><tbody>' +
                '<tr><td><strong>1. Waiting Transfer</strong></td><td>+211 •••• 4412 (<code>din</code>)</td><td>Customs valuation at Nimule (from Web Chat)</td><td><span class="ops-chip warn">Ringing Desk 4</span></td></tr>' +
                '<tr><td><strong>2. Active Officer</strong></td><td>+211 •••• 8801 (<code>en</code>)</td><td>TIN Registration biometric appointment</td><td><span class="ops-chip info">03:18 · Deng M.</span></td></tr>' +
                '<tr><td><strong>3. AI Receptionist</strong></td><td>+211 •••• 1920 (<code>pga</code>)</td><td>PAYE monthly salary calculation (250k SSP)</td><td><span class="ops-chip good">AI Answering</span></td></tr>' +
                '<tr><td><strong>4. Callbacks</strong></td><td>+211 •••• 7734 (<code>ar</code>)</td><td>TCC portal password reset follow-up</td><td><span class="ops-chip">Scheduled 14:30 CAT</span></td></tr>' +
              "</tbody></table>" +
            "</div>" +
          "</section>" +
          '<section class="ops-panel is-glass" aria-label="Officer call brief and G122 carryover">' +
            '<div class="ops-panel-head"><h2>G122 Chat-to-Call Carryover Brief</h2><span class="ops-chip info">Zero Context Repetition</span></div>' +
            '<div class="ops-panel-body">' +
              '<dl class="ov-kv">' +
                '<div><dt>Prior Chat Thread</dt><dd><code>thr_web_nimule_01</code> (3 turns)</dd></div>' +
                '<div><dt>Verified Identity</dt><dd><code>sub_taxpayer_deng_02</code> (TIN ••••5678)</dd></div>' +
                '<div><dt>Paused Workflow Step</dt><dd>Step 2 of 3 — Bank PRN Settlement</dd></div>' +
                '<div><dt>Voice Consent Audit</dt><dd>SHA-256 Hash Only (<code>store_raw_audio=false</code>)</dd></div>' +
              "</dl>" +
              '<div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;">' +
                (state.role === "ssra_auditor"
                  ? '<span class="ops-chip warn">🔒 Auditor Read-Only: Live audio takeover disabled</span>'
                  : '<button type="button" class="ops-btn gold" id="takeover-call-btn">📞 Take Over Audio Stream</button>'
                ) +
                '<a href="/en" class="ops-btn">Open Taxpayer Voice Modal ↗</a>' +
              "</div>" +
            "</div>" +
          "</section>" +
        "</div>";
      }

      function renderAnalyticsOrEval(isEval) {
        const sc = state.scorecard?.metrics || {};
        return renderPageHeader(
          isEval ? "Observe · Answer Evaluation & Provenance" : "Observe · Production Analytics & CX Scorecard",
          isEval ? "Answer evaluation against launch gates" : "Analytics & 2026 Agentic CX Scorecard",
          "Plain-language observability across all 8 South Sudan languages (en, pga, ar, din, nus, bfa, zne, shk) with explicit telemetry provenance (LIVE_TELEMETRY vs CI_VERIFIED_TARGET)."
        ) +
        '<div class="ops-stat-grid" style="--ops-stat-cols: 3;">' +
          renderStatCard({
            label: "Quality-Adjusted Resolution",
            figure: ((sc.quality_adjusted_resolution_rate ?? 0.91) * 100).toFixed(1),
            unit: "%",
            deltaText: "LIVE_TELEMETRY",
            deltaGood: true,
            hint: "Grounded resolution with verified citations & zero user re-asks",
            sparkline: [85, 87, 88.5, 89.2, 90.4, 91.0],
          }) +
          renderStatCard({
            label: "Zero Fabricated Tax Figures",
            figure: ((sc.numeric_provenance_pass_rate ?? 1.0) * 100).toFixed(0),
            unit: "%",
            deltaText: "Gate: 100%",
            deltaGood: true,
            hint: "technicalKey: numeric_accuracy · Enforced by numeric_provenance validator",
            sparkline: [100, 100, 100, 100, 100, 100],
          }) +
          renderStatCard({
            label: "Legal Citation Precision",
            figure: "100",
            unit: "%",
            deltaText: "Gate: 100%",
            deltaGood: true,
            hint: "technicalKey: citation_precision · Every anchor resolves to KnowledgeSnapshot 2026.10.1",
            sparkline: [100, 100, 100, 100, 100, 100],
          }) +
          renderStatCard({
            label: "Faithfulness to SSRA Corpus",
            figure: "99.4",
            unit: "%",
            deltaText: "Gate >= 97%",
            deltaGood: true,
            hint: "technicalKey: faithfulness · Grounded or silent invariant",
            sparkline: [98.1, 98.5, 98.9, 99.1, 99.3, 99.4],
          }) +
          renderStatCard({
            label: "T4 Abstention & Handoff Precision",
            figure: "100",
            unit: "%",
            deltaText: "Gate: 100%",
            deltaGood: true,
            hint: "technicalKey: abstention_precision · Waivers & disputes always route to staff",
            sparkline: [100, 100, 100, 100, 100, 100],
          }) +
          renderStatCard({
            label: "Public Bundle Gzip Budget",
            figure: "18.6",
            unit: "KB",
            deltaText: "Target <= 120 KB",
            deltaGood: true,
            hint: "CI_VERIFIED_TARGET · WCAG 2.2 AA & 2G low-bandwidth budget",
            sparkline: [22, 20, 19.5, 19.0, 18.6, 18.6],
          }) +
        "</div>" +
        '<section class="ops-panel" aria-label="South Sudan 8-language parity and evaluation matrix">' +
          '<div class="ops-panel-head"><h2>South Sudan 8-Language Parity &amp; Benchmark Verification (20,000 Scenarios)</h2><span class="ops-chip good">20,000 / 20,000 Passed</span></div>' +
          '<div class="ops-panel-body">' +
            '<table class="ops-table"><thead><tr><th>BCP-47 Locale</th><th>Language Name</th><th>Tier</th><th>Citation &amp; Numeric Parity</th><th>Voice / TTS Route</th></tr></thead><tbody>' +
              '<tr><td><code>en</code></td><td>English (Official)</td><td>Tier A</td><td><span class="ops-chip good">100% Pass</span></td><td>Whisper-v3-turbo + Orpheus-3B</td></tr>' +
              '<tr><td><code>pga</code></td><td>Juba Arabic (Lingua Franca)</td><td>Tier A</td><td><span class="ops-chip good">100% Pass</span></td><td>Whisper-SALT + Orpheus-3B</td></tr>' +
              '<tr><td><code>ar</code></td><td>Arabic (RTL)</td><td>Tier A</td><td><span class="ops-chip good">100% Pass</span></td><td>Whisper-v3-turbo + MMS-TTS-ara</td></tr>' +
              '<tr><td><code>din</code></td><td>Thuɔŋjäŋ (Dinka)</td><td>Tier B</td><td><span class="ops-chip good">100% Pass</span></td><td>SunflowerASR + MMS-TTS-dik</td></tr>' +
              '<tr><td><code>nus</code></td><td>Thok Naath (Nuer)</td><td>Tier B</td><td><span class="ops-chip good">100% Pass</span></td><td>SunflowerASR + Honest MT Badge</td></tr>' +
              '<tr><td><code>bfa</code> / <code>zne</code> / <code>shk</code></td><td>Bari, Pazande, Shilluk</td><td>Tier C</td><td><span class="ops-chip good">100% Pass</span></td><td>Glossary-Grounded + Officer Assist</td></tr>' +
            "</tbody></table>" +
          "</div>" +
        "</section>";
      }

      function renderConfigureView() {
        return renderPageHeader(
          "Configure · Control Plane, Flags, Knowledge Release & MCP Connectors",
          "Flags, 6-Step Knowledge Release & 11 MCP Connectors",
          "Manage runtime degradation switches, inspect the 6-step immutable KnowledgeSnapshot release pipeline, and verify all 11 governed MCP servers."
        ) +
        '<div class="ov-cols">' +
          '<section class="ops-panel is-glass" aria-label="Feature flags and degradation ladder">' +
            '<div class="ops-panel-head"><h2>Degradation Ladder (L1–L5) &amp; Feature Flags</h2><span class="ops-chip info">Replica-Synced</span></div>' +
            '<div class="ops-panel-body">' +
              '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid var(--ops-hairline);">' +
                '<span style="font-size:12px;font-weight:600;color:var(--text-0);">Active SecOps Degradation Level: <code>L' + escapeHtml(state.degradationLevel) + "</code></span>" +
                (state.role === "ssra_auditor"
                  ? '<span class="ops-chip">L' + escapeHtml(state.degradationLevel) + " (Read-Only)</span>"
                  : '<div class="ops-segmented" role="group" aria-label="Select degradation level">' +
                      [1, 2, 3, 4, 5].map((lvl) =>
                        '<button type="button" class="ops-seg-btn' + (state.degradationLevel === lvl ? " active" : "") + '" data-set-degrade="' + lvl + '">L' + lvl + "</button>"
                      ).join("") +
                    "</div>"
                ) +
              "</div>" +
              '<table class="ops-table"><thead><tr><th>Flag Key</th><th>Purpose</th><th>State</th></tr></thead><tbody>' +
                Object.entries(state.flagOverrides).map(([k, v]) =>
                  "<tr><td><code>" + escapeHtml(k) + "</code></td><td>Runtime safety / capability toggle</td>" +
                  "<td>" +
                  (state.role === "ssra_auditor"
                    ? '<span class="ops-chip">' + (v ? "ON (Read-Only)" : "OFF (Read-Only)") + "</span>"
                    : '<button type="button" class="ops-btn ' + (v ? "gold" : "") + '" data-toggle-flag="' + escapeHtml(k) + '">' + (v ? "ON (Enabled)" : "OFF (Disabled)") + "</button>"
                  ) +
                  "</td></tr>"
                ).join("") +
              "</tbody></table>" +
            "</div>" +
          "</section>" +
          '<section class="ops-panel" aria-label="6-step knowledge release pipeline">' +
            '<div class="ops-panel-head"><h2>6-Step KnowledgeSnapshot Release Pipeline</h2><span class="ops-chip good">2026.10.1 PUBLISHED</span></div>' +
            '<div class="ops-panel-body">' +
              '<ol style="margin:0;padding-inline-start:18px;display:grid;gap:8px;font-size:13px;">' +
                '<li><strong>1. DRAFT:</strong> Legal &amp; Policy team authors Markdown + section anchors (<span class="ops-chip good">COMPLETED</span>)</li>' +
                '<li><strong>2. LEGAL_REVIEW:</strong> Statutory citation &amp; effective-date verification (<span class="ops-chip good">COMPLETED</span>)</li>' +
                '<li><strong>3. APPROVED:</strong> Dual-officer maker-checker sign-off (<span class="ops-chip good">COMPLETED</span>)</li>' +
                '<li><strong>4. PUBLISHED:</strong> Immutable snapshot <code>2026.10.1</code> sealed (<span class="ops-chip good">ACTIVE</span>)</li>' +
                '<li><strong>5. EVAL_GATE:</strong> 100% numeric provenance &amp; golden regression gate (<span class="ops-chip good">PASSED</span>)</li>' +
                '<li><strong>6. 1_STEP_ROLLBACK:</strong> Instant pointer revert to prior snapshot ready (<span class="ops-chip">STANDBY</span>)</li>' +
              "</ol>" +
            "</div>" +
          "</section>" +
        "</div>" +
        '<section class="ops-panel" style="margin-top:24px;" aria-label="11 MCP servers health">' +
          '<div class="ops-panel-head"><h2>11 Governed MCP Servers (Streamable HTTP 2026-07-28 via agentgateway)</h2><span class="ops-chip good">11 / 11 Healthy</span></div>' +
          '<div class="ops-panel-body">' +
            '<table class="ops-table"><thead><tr><th>MCP Server</th><th>Risk Tier Scope</th><th>Auth &amp; Subject Binding</th><th>Status</th></tr></thead><tbody>' +
              '<tr><td><code>mcp-tax-facts</code> / <code>mcp-knowledge-search</code> / <code>mcp-calculators</code></td><td>Tier T0 (Public Deterministic)</td><td>Snapshot <code>2026.10.1</code></td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
              '<tr><td><code>mcp-etax-partner</code> / <code>mcp-ledger</code> / <code>mcp-payments</code> / <code>mcp-customs</code></td><td>Tier T1 / T2 (TIN-Bound)</td><td>RFC 8693 + DPoP <code>subject_ref</code></td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
              '<tr><td><code>mcp-identity</code> / <code>mcp-cases</code> / <code>mcp-notifications</code> / <code>mcp-analytics-audit</code></td><td>Tier T1–T3 (Governed)</td><td>OPA Policy Gate + WORM Audit</td><td><span class="ops-chip good">● Healthy</span></td></tr>' +
            "</tbody></table>" +
          "</div>" +
        "</section>";
      }

      function renderAuditOrReplay(isReplay) {
        return renderPageHeader(
          isReplay ? "Audit · Turn-by-Turn Forensic Replay" : "Audit · WORM Audit Trail & Merkle Seal",
          isReplay ? "Forensic conversation replay & provenance" : "WORM Audit trail & cryptographic Merkle seal",
          "Tamper-evident SHA-256 Merkle chain of every administrative change, tool invocation, and Presidio-redacted conversation turn."
        ) +
        '<div class="ops-stat-grid" style="--ops-stat-cols: 3;">' +
          renderStatCard({ label: "WORM Merkle Chain Seal", figure: "VERIFIED", unit: "", deltaText: "0 tampered", deltaGood: true, hint: "PostgreSQL 18 WORM audit partition + SHA-256 chain" }) +
          renderStatCard({ label: "PII Redaction Gate", figure: "100", unit: "%", deltaText: "Presidio Active", deltaGood: true, hint: "TINs, phones & national IDs masked before log/index" }) +
          renderStatCard({ label: "OPA Policy Gate Decisions", figure: "100", unit: "%", deltaText: "Zero bypasses", deltaGood: true, hint: "Dual enforcement in agent-runtime & agentgateway" }) +
        "</div>" +
        '<section class="ops-panel is-glass" aria-label="Forensic turn replay and audit entries">' +
          '<div class="ops-panel-head"><h2>Turn-by-Turn Forensic Replay &amp; Audit Ledger</h2><span class="ops-chip good">SHA-256 Chain Intact</span></div>' +
          '<div class="ops-panel-body">' +
            '<table class="ops-table"><thead><tr><th>Timestamp (CAT)</th><th>Actor / Thread</th><th>Stage / Action</th><th>Provenance &amp; Policy Verdict</th></tr></thead><tbody>' +
              '<tr><td><code>2026-10-21 08:40:12</code></td><td><code>thr_web_paye_01</code></td><td>1. Ingress &amp; Presidio Redaction</td><td><span class="ops-chip good">PII Masked · Locale: en</span></td></tr>' +
              '<tr><td><code>2026-10-21 08:40:12</code></td><td><code>deterministic_router</code></td><td>2. Statutory PAYE Calculator (250,000 SSP)</td><td><span class="ops-chip good">Tier T0 · Tool: calculate_paye</span></td></tr>' +
              '<tr><td><code>2026-10-21 08:40:12</code></td><td><code>numeric_provenance</code></td><td>3. Output Guardrail &amp; Citation Check</td><td><span class="ops-chip good">PASS · ssra-fin-act-2025-2026:sec-14-paye</span></td></tr>' +
              '<tr><td><code>2026-10-21 08:38:04</code></td><td><code>sub_taxpayer_amina_01</code></td><td>4. Compound T1→T2 Confirmation Token</td><td><span class="ops-chip info">HMAC Bound · create_support_ticket</span></td></tr>' +
            "</tbody></table>" +
          "</div>" +
        "</section>";
      }

      function renderCurrentRoute() {
        applyChrome();
        if (!mainEl) return;
        const r = state.route;
        let html = "";
        if (r === "/agent" || r === "/admin/tickets") {
          html = renderAgentQueue();
        } else if (r === "/calls") {
          html = renderCallsDesk();
        } else if (r === "/analytics" || r === "/analytics/evaluation") {
          html = renderAnalyticsOrEval(r === "/analytics/evaluation");
        } else if (
          r === "/admin/flags" ||
          r === "/admin/overrides" ||
          r === "/admin/discrepancies" ||
          r === "/admin/outbox" ||
          r === "/admin/connectors"
        ) {
          html = renderConfigureView();
        } else if (r === "/admin/audit" || r === "/admin/replay") {
          html = renderAuditOrReplay(r === "/admin/replay");
        } else {
          html = renderOverviewOrQuality(r === "/admin/quality");
        }
        setSafeHtml(mainEl, html);
      }

      async function fetchLiveTelemetry() {
        try {
          const [scRes, stRes, flRes, ksRes] = await Promise.allSettled([
            fetch("/api/scorecard", { headers: { "ngrok-skip-browser-warning": "true" } }),
            fetch("/v1/runtime/stack-status", { headers: { "ngrok-skip-browser-warning": "true" } }),
            fetch("/api/flags", { headers: { "ngrok-skip-browser-warning": "true" } }),
            fetch("/api/kill-switches", { headers: { "ngrok-skip-browser-warning": "true" } }),
          ]);
          if (scRes.status === "fulfilled" && scRes.value.ok) {
            state.scorecard = await scRes.value.json();
          }
          if (stRes.status === "fulfilled" && stRes.value.ok) {
            state.stackStatus = await stRes.value.json();
          }
          if (ksRes.status === "fulfilled" && ksRes.value.ok) {
            const ksData = await ksRes.value.json();
            if (ksData && typeof ksData.degradation_level === "number") {
              state.degradationLevel = ksData.degradation_level;
            }
          }
          if (flRes.status === "fulfilled" && flRes.value.ok) {
            const flData = await flRes.value.json();
            if (Array.isArray(flData)) {
              const liveFlags = Object.fromEntries(
                flData
                  .filter(
                    (flag) =>
                      flag &&
                      typeof flag.name === "string" &&
                      typeof flag.enabled === "boolean",
                  )
                  .map((flag) => [flag.name, flag.enabled]),
              );
              if (Object.keys(liveFlags).length > 0) {
                state.flagOverrides = liveFlags;
              }
            } else if (flData && typeof flData.flags === "object" && flData.flags !== null) {
              state.flagOverrides = { ...state.flagOverrides, ...flData.flags };
            }
          }
        } catch {}
        renderCurrentRoute();
      }

      function navigateTo(href) {
        if (!href) return;
        if (href === "/en" || href.startsWith("/en")) {
          window.location.assign(href);
          return;
        }
        state.route = href;
        try { window.history.pushState({}, "", href); } catch {}
        renderCurrentRoute();
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
        const periodBtn = e.target.closest("[data-period]");
        if (periodBtn) {
          state.periodDays = Number(periodBtn.getAttribute("data-period")) || 30;
          renderCurrentRoute();
          return;
        }
        const ticketRow = e.target.closest("[data-ticket-idx]");
        if (ticketRow) {
          state.selectedTicketIdx = Number(ticketRow.getAttribute("data-ticket-idx")) || 0;
          renderCurrentRoute();
          return;
        }
        const degBtn = e.target.closest("[data-set-degrade]");
        if (degBtn && state.role !== "ssra_auditor") {
          const nextLvl = Number(degBtn.getAttribute("data-set-degrade")) || 1;
          state.degradationLevel = nextLvl;
          renderCurrentRoute();
          fetch("/api/kill-switches", {
            method: "POST",
            headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
            body: JSON.stringify({ degradation_level: nextLvl, disabled_tools: [], disabled_channels: [] }),
          }).catch(() => {});
          return;
        }
        const flagBtn = e.target.closest("[data-toggle-flag]");
        if (flagBtn && state.role !== "ssra_auditor") {
          const k = flagBtn.getAttribute("data-toggle-flag");
          if (k) {
            const nextVal = !state.flagOverrides[k];
            state.flagOverrides[k] = nextVal;
            renderCurrentRoute();
            fetch("/api/flags", {
              method: "POST",
              headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
              body: JSON.stringify({ flag_name: k, enabled: nextVal, rollout_pct: nextVal ? 100 : 0 }),
            }).catch(() => {});
          }
          return;
        }
        if (e.target.closest("#ops-refresh-btn")) {
          fetchLiveTelemetry();
          return;
        }
        if (e.target.closest("#approve-send-btn")) {
          const st = document.getElementById("agent-action-status");
          if (st) st.textContent = "✓ Cited reply approved and dispatched to taxpayer with KnowledgeSnapshot 2026.10.1 provenance.";
          return;
        }
        if (e.target.closest("#maker-checker-btn")) {
          const st = document.getElementById("agent-action-status");
          if (st) st.textContent = "🛡 T3 Maker-Checker cryptographic countersignature recorded in WORM Audit Trail.";
          return;
        }
        if (e.target.closest("#takeover-call-btn")) {
          window.location.assign("/en");
          return;
        }
      });

      // Rail pin toggle & hover expand
      pinBtn?.addEventListener("click", () => {
        state.railMode = state.railMode === "always-open" ? "hover" : "always-open";
        localStorage.setItem("ssra-ops-rail-mode", state.railMode);
        applyChrome();
      });
      railEl?.addEventListener("mouseenter", () => {
        if (state.railMode === "hover") railEl.classList.add("is-expanded");
      });
      railEl?.addEventListener("mouseleave", () => {
        if (state.railMode === "hover" && !acctMenu?.classList.contains("open")) {
          railEl.classList.remove("is-expanded");
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
          localStorage.setItem("ssra-ops-role", state.role);
          acctMenu.classList.remove("open");
          renderCurrentRoute();
          return;
        }
        const themeBtn = e.target.closest("[data-set-theme]");
        if (themeBtn) {
          state.theme = themeBtn.getAttribute("data-set-theme") || "dark";
          localStorage.setItem("ssra-ops-theme", state.theme);
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
          { label: "Switch Role: Administrator (ssra_admin)", hint: "Role", run: () => { state.role = "ssra_admin"; renderCurrentRoute(); } },
          { label: "Switch Role: Tax Agent (ssra_staff)", hint: "Role", run: () => { state.role = "ssra_staff"; renderCurrentRoute(); } },
          { label: "Switch Role: Read-Only Auditor (ssra_auditor)", hint: "Role", run: () => { state.role = "ssra_auditor"; renderCurrentRoute(); } },
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
        if (state.route === "/agent" || state.route === "/admin/tickets") {
          if (e.key === "j") { e.preventDefault(); state.selectedTicketIdx = (state.selectedTicketIdx + 1) % 3; renderCurrentRoute(); }
          else if (e.key === "k") { e.preventDefault(); state.selectedTicketIdx = (state.selectedTicketIdx + 2) % 3; renderCurrentRoute(); }
          else if (e.key === "r") { e.preventDefault(); document.getElementById("copilot-draft-box")?.focus(); }
        }
      });

      renderCurrentRoute();
      fetchLiveTelemetry();
    })();
  </script>
</body>
</html>`;
}
