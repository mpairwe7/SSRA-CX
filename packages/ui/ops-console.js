/**
 * SSRA Assist Operations Console Preview & Staff Sidebar Design System (`packages/ui/ops-console.js`).
 *
 * Shares the public assistant's visual language (`apps/web/server.js`):
 * - IBM Plex Sans (400/500/600), white canvas with the indigo top glow, `#1E40AF` rail with pill rows
 * - Pill buttons with ghost hovers and a spring press; white cards with hairline borders and soft shadows
 * - Status readings are plain text in text-safe inks (no capsules, no leading-edge colour bars)
 * - Collapsible `.staff-rail` (`56px` collapsed / `248px` expanded, `always-open` vs `hover` mode)
 * - 4-group navigation hierarchy (`Work` / `Audit` / `Configure` / `Observe`) + `AccountMenu` upward popover
 * - `CommandPalette` (`⌘K` / `Ctrl+K`) modal with keyboard navigation and role-scoped destinations
 * - Light (default), Dark and High contrast themes
 * - Explicit non-operational preview until authenticated staff sessions and provenance-bearing data are available
 */

import { ICONS } from "./icons.js";
import {
  renderThemeBootstrapScript,
  SSRA_PALETTE,
  SSRA_THEME_COLORS,
  SSRA_THEME_STORAGE_KEY,
} from "./theme.js";

const DARK = SSRA_PALETTE.dark;
const HC = SSRA_PALETTE["high-contrast"];

const OPS_ROUTE_PREFIXES = [
  "/admin",
  "/agent",
  "/calls",
  "/analytics",
  "/queue",
  "/auditor",
  "/ops",
  "/signin",
  "/signup",
];

// Preview destinations. Every route renders the same non-operational preview card.
const DESTINATIONS = [
  {
    href: "/admin",
    label: "Operations overview",
    navLabel: "Overview",
    group: "Work",
    icon: ICONS.gauge,
    roles: ["ssra_admin", "ssra_auditor", "ssra_staff"],
  },
  {
    href: "/agent",
    label: "My queue & Copilot",
    navLabel: "My queue",
    group: "Work",
    icon: ICONS.inbox,
    roles: ["ssra_staff", "ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/tickets",
    label: "All tickets",
    navLabel: "All tickets",
    group: "Work",
    icon: ICONS.list,
    roles: ["ssra_staff", "ssra_admin", "ssra_auditor"],
  },
  {
    href: "/calls",
    label: "Phone calls desk",
    navLabel: "Calls",
    group: "Work",
    icon: ICONS.phone,
    roles: ["ssra_staff", "ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/quality",
    label: "Service quality audit",
    navLabel: "Quality audit",
    group: "Audit",
    icon: ICONS.clipboardCheck,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/audit",
    label: "WORM Audit trail",
    navLabel: "Audit trail",
    group: "Audit",
    icon: ICONS.shieldCheck,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/replay",
    label: "Forensic turn replay",
    navLabel: "Forensic replay",
    group: "Audit",
    icon: ICONS.history,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/flags",
    label: "Flags & kill switches",
    navLabel: "Flags",
    group: "Configure",
    icon: ICONS.flag,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/discrepancies",
    label: "Knowledge & Bug Reports",
    navLabel: "Bug Reports",
    group: "Configure",
    icon: ICONS.alertTriangle,
    roles: ["ssra_staff", "ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/overrides",
    label: "Knowledge release & overrides",
    navLabel: "Overrides",
    group: "Configure",
    icon: ICONS.sliders,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/outbox",
    label: "Notification outbox",
    navLabel: "Outbox",
    group: "Configure",
    icon: ICONS.send,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/admin/connectors",
    label: "MCP System connectors",
    navLabel: "Connectors",
    group: "Configure",
    icon: ICONS.plug,
    roles: ["ssra_staff", "ssra_admin", "ssra_auditor"],
  },
  {
    href: "/analytics",
    label: "Analytics & CX Scorecard",
    navLabel: "Analytics",
    group: "Observe",
    icon: ICONS.chart,
    roles: ["ssra_admin", "ssra_auditor"],
  },
  {
    href: "/analytics/evaluation",
    label: "Answer evaluation",
    navLabel: "Evaluation",
    group: "Observe",
    icon: ICONS.beaker,
    roles: ["ssra_admin", "ssra_auditor"],
  },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/\x60/g, "&#96;");
}

const ROUTE_SPECS = {
  "/admin": {
    roles: "ssra_admin, ssra_auditor",
    standard: "ISO/IEC 42001 §9.1 · ADR-012",
    surface: "Service levels, officers on duty & answer authority",
    gate: "Server-verified passkey session + freshness provenance",
  },
  "/agent": {
    roles: "ssra_staff, ssra_admin, ssra_auditor",
    standard: "ISO/IEC 25010 §4 · OWASP ASI03",
    surface: "One-case-at-a-time queue & Cited Copilot draft review",
    gate: "Passkey session + Principle 1 citation & TIN redaction guard",
  },
  "/admin/tickets": {
    roles: "ssra_staff, ssra_admin, ssra_auditor",
    standard: "ISO/IEC 42001 §8.3 · SLA Triage",
    surface: "Omnichannel escalations across Web, WhatsApp, SMS, USSD & Voice",
    gate: "Server-verified staff session + priority SLA thresholds",
  },
  "/calls": {
    roles: "ssra_staff, ssra_admin, ssra_auditor",
    standard: "ADR-024 · ADR-025 · ADR-026",
    surface: "Voice call lobby, officer takeover & post-call wrap-up",
    gate: "First-claim-wins lobby lock + rule-attributed call briefs",
  },
  "/admin/quality": {
    roles: "ssra_admin, ssra_auditor",
    standard: "ISO/IEC 42001 §9.2 · NIST MEASURE 2.6",
    surface: "Sampled 4-dimension QA rubric & discrepancy triggers",
    gate: "Finding note required when any rubric dimension < gate",
  },
  "/admin/audit": {
    roles: "ssra_admin, ssra_auditor",
    standard: "ISO/IEC 42001 A.6.2.8 · EU AI Act Art. 12",
    surface: "Hash-chained WORM ledger & batch integrity verification",
    gate: "Sealing paused automatically on any hash or anchor break",
  },
  "/admin/replay": {
    roles: "ssra_admin, ssra_auditor",
    standard: "Principle 9 · NIST AI 600-1",
    surface: "Turn-by-turn redacted input, policy decision & tool reconstruction",
    gate: "64-hex WORM event digest + snapshot version provenance",
  },
  "/admin/flags": {
    roles: "ssra_admin, ssra_auditor",
    standard: "Section 6.4 · ADR-012 JIT Admin",
    surface: "5-step degradation ladder & channel/tool kill switches",
    gate: "Active JIT passkey elevation + two-officer maker-checker",
  },
  "/admin/discrepancies": {
    roles: "ssra_staff, ssra_admin, ssra_auditor",
    standard: "ISO/IEC 42001 §10.2 · Continuous Improvement",
    surface: "Taxpayer-reported statutory discrepancies & corpus gaps",
    gate: "Server-verified staff session + legal reviewer triage",
  },
  "/admin/overrides": {
    roles: "ssra_admin, ssra_auditor",
    standard: "Principle 1 · Section 7 Knowledge Release",
    surface: "6-step knowledge release & exact-match answer overrides",
    gate: "Maker-checker separation + approved sectionAnchor citation",
  },
  "/admin/outbox": {
    roles: "ssra_admin, ssra_auditor",
    standard: "Section 11 · Omnichannel Delivery",
    surface: "Transactional SMS, WhatsApp template & email outbox queue",
    gate: "24-hour WhatsApp window guard + GSM-7/UCS-2 segment bounds",
  },
  "/admin/connectors": {
    roles: "ssra_staff, ssra_admin, ssra_auditor",
    standard: "OQ-001 · OQ-002 · OQ-006",
    surface: "Circuit-breaker health for e-Tax, e-Customs & BoSS FX",
    gate: "Fail-closed circuit breakers + T3 write step-up gating",
  },
  "/analytics": {
    roles: "ssra_admin, ssra_auditor",
    standard: "OpenSLO v1 · OQ-013 Warehouse Provenance",
    surface: "p95 TTFT, quality-adjusted containment & language parity",
    gate: "Observation timestamp freshness <= 5 min (fail-closed)",
  },
  "/analytics/evaluation": {
    roles: "ssra_admin, ssra_auditor",
    standard: "NIST AI RMF MEASURE 2.6 · OWASP ASI01–ASI10",
    surface: "Golden evaluation suite, groundedness & red-team gates",
    gate: "All-gates-pass claim forbidden on illustrative fallback data",
  },
};

function destinationMeta(route) {
  if (route === "/signin") {
    return {
      href: "/signin",
      label: "Sign in",
      navLabel: "Sign in",
      group: "Account",
    };
  }
  if (route === "/signup") {
    return {
      href: "/signup",
      label: "Create an account",
      navLabel: "Create account",
      group: "Account",
    };
  }
  if (route === "/signin/callback") {
    return {
      href: "/signin/callback",
      label: "Signing you in",
      navLabel: "Callback",
      group: "Account",
    };
  }
  return (
    DESTINATIONS.find((destination) => destination.href === route) || {
      href: "/admin",
      label: "Operations overview",
      navLabel: "Overview",
      group: "Work",
    }
  );
}

function resolvePublicAssistantUrl(publicWebOrigin) {
  const candidate = String(
    publicWebOrigin ??
      process.env.PUBLIC_WEB_URL ??
      process.env.NEXT_PUBLIC_WEB_URL ??
      "http://127.0.0.1:3000",
  ).trim();
  if (candidate === "/en") {
    return "/en";
  }
  try {
    const parsed = new URL(candidate);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return `${parsed.origin}/en`;
    }
  } catch {}
  return "http://127.0.0.1:3000/en";
}

// Rendered on the server so the preview state is readable without JavaScript.
function renderPreviewCard(title, group = "Work", routePath = "/admin") {
  const spec = ROUTE_SPECS[routePath] || ROUTE_SPECS["/admin"];
  return `<header class="ops-page-head">
          <div>
            <span id="preview-eyebrow" class="ops-eyebrow">${escapeHtml(group)} · Preview only</span>
            <h1 id="preview-title">${escapeHtml(title)}</h1>
            <p id="preview-desc" class="ops-page-desc">Read-only layout preview of the SSRA Assist operations console. Staff data and action routes fail closed until server-verified staff sessions are active.</p>
          </div>
          <div class="ops-page-actions">
            <span class="ops-fresh"><span class="ops-fresh-dot is-stale" aria-hidden="true"></span>Session unverified · preview only</span>
            <a class="ops-btn" id="ops-header-signin-link" href="/signin" data-nav="/signin">Sign in</a>
            <a class="ops-btn primary" id="ops-header-signup-link" href="/signup" data-nav="/signup">Create account</a>
          </div>
        </header>

        <section class="ops-panel ops-preview-card" aria-labelledby="preview-title">
          <span class="ops-preview-chip">${ICONS.eye} Preview only</span>
          <p>This screen is not connected to an authenticated staff session. It contains no live taxpayer records, casework, service telemetry, or operational controls.</p>
          <p>Staff access will be enabled after SSRA approves the identity provider and role mapping, and the service can verify those permissions on the server.</p>
          <ul><li>Use a staff identity provider with server-validated sessions.</li><li>Show live data only with its source, observation time, and freshness state.</li><li>Require server-side authorization and an audit record for every staff action.</li></ul>
        </section>

        <section aria-label="Service quality summary preview">
          <div class="ops-stat-grid ov-stats">
            <div class="ops-stat">
              <span class="ops-stat-label">AI answers found helpful</span>
              <span class="ops-stat-row"><strong class="ops-stat-value">—</strong><span class="ops-delta">Unverified</span></span>
              <span class="ops-stat-hint">Requires an authenticated staff session and live telemetry source</span>
            </div>
            <div class="ops-stat">
              <span class="ops-stat-label">Voice &amp; call reviews</span>
              <span class="ops-stat-row"><strong class="ops-stat-value">—</strong><span class="ops-delta">Unverified</span></span>
              <span class="ops-stat-hint">Requires an authenticated staff session and live telemetry source</span>
            </div>
            <div class="ops-stat">
              <span class="ops-stat-label">Officer chat satisfaction</span>
              <span class="ops-stat-row"><strong class="ops-stat-value">—</strong><span class="ops-delta">Unverified</span></span>
              <span class="ops-stat-hint">Requires an authenticated staff session and live telemetry source</span>
            </div>
            <div class="ops-stat">
              <span class="ops-stat-label">Officer call satisfaction</span>
              <span class="ops-stat-row"><strong class="ops-stat-value">—</strong><span class="ops-delta">Unverified</span></span>
              <span class="ops-stat-hint">Requires an authenticated staff session and live telemetry source</span>
            </div>
          </div>
        </section>

        <div class="ov-cols">
          <section class="ops-panel is-bare ov-review-panel" aria-labelledby="nr-h">
            <div class="ops-panel-head">
              <h2 id="nr-h">Needs review</h2>
              <div class="ops-panel-end"><span class="ops-chip is-warn">Preview only</span></div>
            </div>
            <div class="ops-panel-body">
              <p class="ops-panel-note">Escalated conversations, low-rated answers, and cases awaiting supervisor review appear here only when connected to an authenticated staff session.</p>
              <div class="ops-empty">
                <span class="ops-empty-mark" aria-hidden="true">${ICONS.inboxEmpty}</span>
                <p class="ops-empty-title">No live review queue connected</p>
                <p class="ops-empty-body">Sign-in and server-side role verification are required before casework or taxpayer transcripts can be loaded.</p>
              </div>
            </div>
          </section>

          <div class="ov-side">
            <section class="ops-panel is-bare" aria-labelledby="a-h">
              <div class="ops-panel-head">
                <h2 id="a-h">Answer authority</h2>
                <div class="ops-panel-end"><span class="ops-chip">Unverified</span></div>
              </div>
              <div class="ops-panel-body">
                <p class="ops-panel-note">Statutory rate and deadline answers require an approved knowledge snapshot manifest with verified freshness.</p>
                <dl class="ov-kv">
                  <div><dt>Status</dt><dd><span class="ov-chip warn">Session required</span></dd></div>
                  <div><dt>Snapshot version</dt><dd>—</dd></div>
                  <div><dt>Observation time</dt><dd>—</dd></div>
                  <div><dt>Verified sources</dt><dd>—</dd></div>
                </dl>
              </div>
            </section>

            <section class="ops-panel is-bare" aria-labelledby="s-h">
              <div class="ops-panel-head">
                <h2 id="s-h">Service levels</h2>
                <div class="ops-panel-end"><span class="ops-chip">Unverified</span></div>
              </div>
              <div class="ops-panel-body">
                <p class="ops-panel-note">Live queue depth and SLA response medians are hidden until authenticated telemetry provenance is configured.</p>
                <dl class="ov-kv">
                  <div><dt>Open escalations</dt><dd>—</dd></div>
                  <div><dt>Past 24-hour SLA</dt><dd>—</dd></div>
                  <div><dt>Median first response</dt><dd>—</dd></div>
                  <div><dt>Median time to resolve</dt><dd>—</dd></div>
                </dl>
              </div>
            </section>

            <section id="route-spec-panel" class="ops-panel is-bare" aria-labelledby="g-h">
              <div class="ops-panel-head">
                <h2 id="g-h">Route governance &amp; specification</h2>
                <div class="ops-panel-end"><span class="ops-chip is-info">Keycloak RBAC</span></div>
              </div>
              <div class="ops-panel-body">
                <dl class="ov-kv">
                  <div><dt>Permitted roles</dt><dd id="spec-roles">${escapeHtml(spec.roles)}</dd></div>
                  <div><dt>Standard anchor</dt><dd id="spec-standard">${escapeHtml(spec.standard)}</dd></div>
                  <div><dt>Workbench surface</dt><dd id="spec-surface">${escapeHtml(spec.surface)}</dd></div>
                  <div><dt>Fail-closed gate</dt><dd id="spec-gate">${escapeHtml(spec.gate)}</dd></div>
                </dl>
              </div>
            </section>
          </div>
        </div>`;
}

const AUTH_ROUTES = new Set(["/signin", "/signup", "/signin/callback"]);

function isAuthRoute(route) {
  return AUTH_ROUTES.has(route);
}

// Dedicated auth pages: brand, heading, one form, single sign-on, and a way back. No navigation or role choice;
// the account you sign in with decides the workspace you land in.
function renderAuthBrand() {
  return `<div class="auth-brand">
              <span class="signin-mark" aria-hidden="true">${ICONS.ssraCrest}</span>
              <span class="auth-wordmark">SSRA Assist</span>
            </div>`;
}

function renderAuthDivider() {
  return `<div class="auth-divider"><span class="auth-divider-line" aria-hidden="true"></span><span>or</span><span class="auth-divider-line" aria-hidden="true"></span></div>`;
}

function renderSignInCard(publicAssistantUrl = "http://127.0.0.1:3000/en") {
  return `<div class="signin-wrap">
          <div class="signin-card">
            ${renderAuthBrand()}
            <header class="signin-head">
              <h1 id="preview-title">Sign in</h1>
              <p class="signin-sub">Use your SSRA account. You&#39;ll go straight to your workspace.</p>
            </header>

            <form id="console-signin-form" class="signin-form" data-testid="console-signin-form" novalidate>
              <div class="signin-field">
                <label for="signin-email-input" class="signin-label">Email or username</label>
                <input id="signin-email-input" data-testid="signin-email-input" class="signin-input" type="text" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="name@example.com" required />
              </div>
              <div class="signin-field">
                <label for="signin-password-input" class="signin-label">Password</label>
                <input id="signin-password-input" data-testid="signin-password-input" class="signin-input" type="password" name="password" autocomplete="current-password" required />
              </div>
              <button type="submit" id="console-signin-submit-btn" class="signin-primary" data-testid="console-signin-submit-btn">Sign in</button>
            </form>
            <p id="signin-status-banner" class="signin-status is-hidden" role="status" aria-live="polite"></p>

            ${renderAuthDivider()}
            <button type="button" id="keycloak-signin-btn" class="signin-secondary" data-testid="keycloak-signin-btn">${ICONS.shieldCheck} Continue with SSRA single sign-on</button>

            <footer class="auth-foot">
              <p>Don&#39;t have an account? <a href="/signup" data-nav="/signup">Create one</a></p>
              <a class="auth-back" href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Back to SSRA Assist</a>
            </footer>
          </div>
          <p class="auth-note">Preview environment: sign-in is checked in this browser only.</p>
        </div>`;
}

function renderSignUpCard(publicAssistantUrl = "http://127.0.0.1:3000/en") {
  return `<div class="signin-wrap">
          <div class="signin-card">
            ${renderAuthBrand()}
            <header class="signin-head">
              <h1 id="preview-title">Create an account</h1>
              <p class="signin-sub">For taxpayers. SSRA staff accounts are issued by SSRA, so staff should sign in instead.</p>
            </header>

            <form id="console-signup-form" class="signin-form" data-testid="console-signup-form" novalidate>
              <div class="signin-field">
                <label for="signup-name-input" class="signin-label">Full name or business name</label>
                <input id="signup-name-input" data-testid="signup-name-input" class="signin-input" type="text" name="name" autocomplete="name" required />
              </div>
              <div class="signin-field">
                <label for="signup-email-input" class="signin-label">Email address</label>
                <input id="signup-email-input" data-testid="signup-email-input" class="signin-input" type="email" name="email" autocomplete="email" autocapitalize="none" spellcheck="false" placeholder="name@example.com" required />
              </div>
              <div class="signin-field">
                <label for="signup-password-input" class="signin-label">Password</label>
                <input id="signup-password-input" data-testid="signup-password-input" class="signin-input" type="password" name="new-password" autocomplete="new-password" placeholder="At least 8 characters" required />
              </div>
              <button type="submit" id="console-signup-submit-btn" class="signin-primary" data-testid="console-signup-submit-btn">Create account</button>
            </form>
            <p id="signup-status-banner" class="signin-status is-hidden" role="status" aria-live="polite"></p>

            ${renderAuthDivider()}
            <button type="button" id="keycloak-signup-btn" class="signin-secondary" data-testid="keycloak-signup-btn">${ICONS.shieldCheck} Continue with SSRA single sign-on</button>

            <footer class="auth-foot">
              <p>Already have an account? <a href="/signin" data-nav="/signin">Sign in</a></p>
              <a class="auth-back" href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Continue without an account</a>
            </footer>
          </div>
          <p class="auth-note">Preview environment: accounts are kept in this browser only.</p>
        </div>`;
}

function renderSignInCallbackCard(publicAssistantUrl = "http://127.0.0.1:3000/en") {
  return `<div class="signin-wrap">
          <div class="signin-card">
            ${renderAuthBrand()}
            <header class="signin-head">
              <h1 id="preview-title">Signing you in</h1>
              <p class="signin-sub">Checking the response from SSRA single sign-on.</p>
            </header>

            <p id="callback-status-banner" class="signin-status" role="status" aria-live="polite">Verifying the sign-in response…</p>

            <div class="auth-actions">
              <a class="signin-primary" href="/signin" data-nav="/signin">Back to sign in</a>
              <a class="signin-secondary" href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Back to SSRA Assist</a>
            </div>
          </div>
        </div>`;
}

function renderRouteBody(currentPath, currentTitle, currentGroup, publicAssistantUrl) {
  if (currentPath === "/signin") return renderSignInCard(publicAssistantUrl);
  if (currentPath === "/signup") return renderSignUpCard(publicAssistantUrl);
  if (currentPath === "/signin/callback") return renderSignInCallbackCard(publicAssistantUrl);
  return renderPreviewCard(currentTitle, currentGroup, currentPath);
}

function renderServerRailGroups(currentPath = "/admin", role = "ssra_admin") {
  const groups = ["Work", "Audit", "Configure", "Observe"];
  return groups
    .map((group) => {
      const destinations = DESTINATIONS.filter(
        (item) => item.group === group && item.roles.includes(role),
      );
      if (!destinations.length) return "";
      const groupId = `rail-group-${group.toLowerCase()}`;
      return `<div class="staff-rail-group"><p class="staff-rail-group-label" id="${escapeHtml(groupId)}">${escapeHtml(group)}</p><ul aria-labelledby="${escapeHtml(groupId)}">${destinations
        .map((item) => {
          const active = item.href === currentPath;
          return `<li><a href="${escapeHtml(item.href)}" data-nav="${escapeHtml(item.href)}" class="nav-item${active ? " active" : ""}" title="${escapeHtml(item.label)}"${active ? ' aria-current="page"' : ""}><span class="staff-rail-icon" aria-hidden="true">${item.icon}</span><span class="staff-rail-label">${escapeHtml(item.navLabel)}</span></a></li>`;
        })
        .join("")}</ul></div>`;
    })
    .join("");
}

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

export function renderOpsDashboardHtml(rawPathname, nonce, publicWebOrigin) {
  const currentPath = normalizeOpsRoute(rawPathname);
  const currentMeta = destinationMeta(currentPath);
  const currentTitle = currentMeta.label;
  const publicAssistantUrl = resolvePublicAssistantUrl(publicWebOrigin);
  const rawHtml = `<!DOCTYPE html>
<html lang="en" data-theme="light" data-rail-mode="always-open">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content" />
  <meta name="theme-color" id="ops-theme-color" content="${SSRA_THEME_COLORS.light}" />
  <script nonce="${nonce}">${renderThemeBootstrapScript()}</script>
  <meta name="description" content="Non-operational preview of SSRA Assist staff navigation. No live taxpayer data, service telemetry, or staff actions." />
  <link rel="preload" href="/fonts/IBMPlexSans-Regular.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="preload" href="/fonts/IBMPlexSans-Medium.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="preload" href="/fonts/IBMPlexSans-SemiBold.woff2" as="font" type="font/woff2" crossorigin />
  <title>${isAuthRoute(currentPath) ? `${escapeHtml(currentTitle)} — SSRA Assist` : `SSRA Operations Console Preview — ${escapeHtml(currentTitle)}`}</title>
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

    /* Design tokens shared with the public assistant (apps/web/server.js): IBM Plex Sans, white canvas with
       an indigo top glow, #1E40AF rail, pill buttons with ghost hovers, and text-safe status inks. */
    :root,
    :root[data-theme="light"] {
      color-scheme: light;
      --ops-font-sans: "IBM Plex Sans", "Aptos", "Avenir Next", "Segoe UI", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      --ops-font-mono: "IBM Plex Mono", "Cascadia Code", "SFMono-Regular", "Fira Code", monospace;
      --ops-text-xl: 28px;
      --ops-band: 24px;
      --ops-max-w: 1440px;
      --ops-dur-fast: 160ms;
      --ops-dur-base: 200ms;
      --ops-dur-slow: 280ms;
      --ops-ease: ease;
      --ops-ease-out: cubic-bezier(0.22, 1, 0.36, 1);
      --ops-spring: cubic-bezier(0.34, 1.35, 0.64, 1);

      --bg-0: #FFFFFF;
      --border-0: rgba(0, 72, 145, 0.10);
      --border-1: rgba(0, 72, 145, 0.18);
      --border-2: rgba(0, 72, 145, 0.28);
      --text-0: #0B192C;
      --text-1: #1E293B;
      --text-2: #334155;
      --text-3: #475569;
      --accent: #1E40AF;
      --accent-soft: #EEF2FF;
      --ssra-blue: #005DB4;
      --ssra-civic-green: #078930;
      --ssra-gold: #FCD34D;
      --grad-primary: linear-gradient(135deg, #005DB4 0%, #056824 100%);
      --canvas-glow: #C7D2FE;
      --topbar-bg: rgba(255, 255, 255, 0.78);
      --ghost-hover: rgba(15, 23, 42, 0.08);
      --ghost-active: rgba(15, 23, 42, 0.12);
      --seg-track: rgba(15, 23, 42, 0.05);
      --seg-active-bg: #FFFFFF;
      --btn-primary-bg: #1E40AF;
      --btn-primary-hover: #1E3A8A;
      --btn-primary-ink: #FFFFFF;

      --ops-panel: #FFFFFF;
      --ops-inset: #F8FAFC;
      --ops-row-hover: rgba(15, 23, 42, 0.035);
      --ops-hairline: rgba(0, 72, 145, 0.08);
      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(0, 45, 98, 0.06);
      --shadow-md: 0 6px 20px rgba(0, 45, 98, 0.08), 0 1px 3px rgba(15, 23, 42, 0.05);
      --shadow-lg: 0 16px 44px rgba(0, 45, 98, 0.14), 0 0 0 1px rgba(0, 72, 145, 0.08);
      --shadow-modal: 0 24px 64px rgba(15, 23, 42, 0.18);

      --rail-bg: #1E40AF;
      --rail-text: #FFFFFF;
      --rail-current: rgba(0, 0, 0, 0.18);
      --rail-hover: rgba(255, 255, 255, 0.12);
      --rail-active: rgba(255, 255, 255, 0.18);
      --rail-muted: rgba(255, 255, 255, 0.72);
      --rail-field: rgba(255, 255, 255, 0.12);
      --rail-field-hover: rgba(255, 255, 255, 0.2);
      --avatar-bg: #FFFFFF;
      --avatar-ink: #1E40AF;
      --on-grad: #FFFFFF;
      --auth-canvas: radial-gradient(125% 125% at 50% -50%, #C7D2FE 40%, transparent 100%);
      --auth-card-shadow: 0 24px 64px rgba(15, 23, 42, 0.10), 0 1px 3px rgba(15, 23, 42, 0.05);
      --scrim: rgba(15, 23, 42, 0.32);

      --ops-good-ink: #056824;
      --ops-warn-ink: #853A06;
      --ops-bad-ink: #B91C1C;
      --ops-info-ink: #1E40AF;
      --ops-focus: #005DB4;
      --ops-focus-rail: #FFD60A;
    }

    /* Dark: #0A0A0A canvas with the public assistant's indigo top glow and a #1F1F1F rail (packages/ui/theme.js). */
    :root[data-theme="dark"] {
      color-scheme: dark;
      --bg-0: ${DARK.canvas};
      --border-0: ${DARK.border0};
      --border-1: ${DARK.border1};
      --border-2: ${DARK.border2};
      --text-0: ${DARK.text0};
      --text-1: ${DARK.text1};
      --text-2: ${DARK.text2};
      --text-3: ${DARK.text3};
      --accent: ${DARK.accent};
      --accent-soft: ${DARK.accentSoft};
      --ssra-blue: ${DARK.accent};
      --canvas-glow: ${DARK.glow};
      --auth-canvas: radial-gradient(125% 125% at 50% -50%, ${DARK.glow} 40%, transparent 100%);
      --auth-card-shadow: 0 24px 64px rgba(0, 0, 0, 0.45);
      --topbar-bg: rgba(10, 10, 10, 0.78);
      --ghost-hover: ${DARK.ghostHover};
      --ghost-active: ${DARK.ghostActive};
      --seg-track: rgba(255, 255, 255, 0.06);
      --seg-active-bg: ${DARK.surface4};
      --btn-primary-bg: ${DARK.primary};
      --btn-primary-hover: ${DARK.primaryHover};
      --btn-primary-ink: ${DARK.primaryInk};
      --ops-panel: ${DARK.card};
      --ops-inset: ${DARK.inset};
      --ops-row-hover: ${DARK.rowHover};
      --ops-hairline: rgba(255, 255, 255, 0.06);
      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.32);
      --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.42);
      --shadow-lg: 0 16px 44px rgba(0, 0, 0, 0.55), 0 0 0 1px ${DARK.border0};
      --shadow-modal: 0 24px 64px rgba(0, 0, 0, 0.6);
      --scrim: ${DARK.scrim};
      --rail-bg: ${DARK.railBg};
      --rail-text: ${DARK.railText};
      --rail-current: ${DARK.railCurrent};
      --rail-hover: ${DARK.railHover};
      --rail-active: ${DARK.railActive};
      --rail-muted: ${DARK.railMuted};
      --rail-field: ${DARK.railField};
      --rail-field-hover: ${DARK.railFieldHover};
      --avatar-bg: ${DARK.avatarBg};
      --avatar-ink: ${DARK.avatarInk};
      --ops-good-ink: ${DARK.good};
      --ops-warn-ink: ${DARK.warn};
      --ops-bad-ink: ${DARK.bad};
      --ops-info-ink: ${DARK.accent};
      --ops-focus: ${DARK.focus};
      --ops-focus-rail: ${DARK.focus};
    }

    /* High contrast: GitHub "Dark high contrast"-style palette; borders >= 3:1, yellow reserved for focus. */
    :root[data-theme="high-contrast"] {
      color-scheme: dark;
      --bg-0: ${HC.canvas};
      --border-0: ${HC.border0};
      --border-1: ${HC.border1};
      --border-2: ${HC.border2};
      --text-0: ${HC.text0};
      --text-1: ${HC.text1};
      --text-2: ${HC.text2};
      --text-3: ${HC.text3};
      --accent: ${HC.accent};
      --accent-soft: ${HC.accentSoft};
      --ssra-blue: ${HC.accent};
      --grad-primary: linear-gradient(135deg, ${HC.primary} 0%, ${HC.primary} 100%);
      --on-grad: ${HC.primaryInk};
      --canvas-glow: transparent;
      --auth-canvas: none;
      --auth-card-shadow: none;
      --topbar-bg: ${HC.canvas};
      --ghost-hover: ${HC.ghostHover};
      --ghost-active: ${HC.ghostActive};
      --seg-track: transparent;
      --seg-active-bg: ${HC.accentPill};
      --btn-primary-bg: ${HC.primary};
      --btn-primary-hover: ${HC.primaryHover};
      --btn-primary-ink: ${HC.primaryInk};
      --ops-panel: ${HC.card};
      --ops-inset: ${HC.inset};
      --ops-row-hover: ${HC.rowHover};
      --ops-hairline: #4B525C;
      --shadow-sm: none;
      --shadow-md: none;
      --shadow-lg: none;
      --shadow-modal: none;
      --scrim: ${HC.scrim};
      --rail-bg: ${HC.railBg};
      --rail-text: ${HC.railText};
      --rail-current: ${HC.railCurrent};
      --rail-hover: ${HC.railHover};
      --rail-active: ${HC.railActive};
      --rail-muted: ${HC.railMuted};
      --rail-field: ${HC.railField};
      --rail-field-hover: ${HC.railFieldHover};
      --avatar-bg: ${HC.avatarBg};
      --avatar-ink: ${HC.avatarInk};
      --ops-good-ink: ${HC.good};
      --ops-warn-ink: ${HC.warn};
      --ops-bad-ink: ${HC.bad};
      --ops-info-ink: ${HC.accent};
      --ops-focus: ${HC.focus};
      --ops-focus-rail: ${HC.focus};
    }

    *, *::before, *::after { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; min-height: 100dvh;
      font-family: var(--ops-font-sans); font-feature-settings: "cv11", "ss01";
      -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
      -webkit-text-size-adjust: 100%; text-size-adjust: 100%;
      background: var(--bg-0); color: var(--text-1);
    }
    code, kbd { font-family: var(--ops-font-mono); font-size: 0.92em; font-weight: 400; }

    .ops-sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); border: 0;
    }
    .staff-skip {
      position: absolute; left: 12px; top: -48px; z-index: 95; padding: 8px 14px;
      background: var(--ops-panel); color: var(--text-0); border: 2px solid var(--ops-focus);
      border-radius: 10px; font-size: 0.84rem; font-weight: 600; text-decoration: none;
    }
    .staff-skip:focus { top: 10px; }
    :is(a, button, input, select, textarea, [tabindex]):focus-visible {
      outline: 3px solid var(--ops-focus);
      outline-offset: 2px;
    }
    .staff-rail *:focus-visible { outline-color: var(--ops-focus-rail); outline-offset: 1px; }
    .staff-rail .staff-acct-menu *:focus-visible { outline-color: var(--ops-focus); }
    #staff-main:focus { outline: none; }

    /* Neutral scrollbars that only appear on hover, as on the public assistant. */
    .staff-shell *::-webkit-scrollbar { width: 10px; height: 10px; }
    .staff-shell *::-webkit-scrollbar-track,
    .staff-shell *::-webkit-scrollbar-corner { background: transparent; }
    .staff-shell *::-webkit-scrollbar-thumb {
      background-color: transparent; background-clip: padding-box;
      border: 3px solid transparent; border-radius: 999px;
    }
    .staff-shell *:hover::-webkit-scrollbar-thumb { background-color: var(--border-2); }
    .staff-shell * { scrollbar-width: thin; scrollbar-color: transparent transparent; }
    .staff-shell *:hover { scrollbar-color: var(--border-2) transparent; }

    /* App shell: fixed indigo rail (56px collapsed / 248px expanded) beside the content column. */
    .staff-shell {
      --rail-w-collapsed: 56px;
      --rail-w-expanded: 248px;
      --rail-w: var(--rail-w-collapsed);
      min-height: 100dvh;
    }
    .staff-shell:has(.staff-rail.is-expanded),
    :root[data-rail-mode="always-open"] .staff-shell {
      --rail-w: var(--rail-w-expanded);
    }
    .staff-shell-content {
      margin-inline-start: var(--rail-w);
      transition: margin-inline-start var(--ops-dur-slow) var(--ops-ease-out);
      min-height: 100dvh; min-width: 0; display: flex; flex-direction: column;
      background:
        radial-gradient(125% 125% at 50% -50%, var(--canvas-glow) 40%, transparent 100%) top center / 100% 760px no-repeat,
        var(--bg-0);
    }

    .staff-rail {
      position: fixed; inset-block: 0; inset-inline-start: 0; z-index: 30;
      display: flex; flex-direction: column;
      width: var(--rail-w-collapsed);
      background: var(--rail-bg); color: var(--rail-text);
      overflow: hidden; contain: paint;
      transition: width var(--ops-dur-slow) var(--ops-ease-out), box-shadow var(--ops-dur-base) var(--ops-ease);
    }
    .staff-rail.is-expanded,
    :root[data-rail-mode="always-open"] .staff-rail {
      width: var(--rail-w-expanded);
    }
    :root[data-rail-mode="hover"] .staff-rail.is-expanded { box-shadow: 0 18px 48px rgba(0, 0, 0, 0.32); }
    :root[data-theme="high-contrast"] .staff-rail { border-inline-end: 1px solid var(--border-0); }

    .staff-rail-head {
      display: flex; align-items: center; justify-content: space-between; gap: 4px;
      min-height: 60px; padding: 10px 8px 6px 14px; flex: none;
    }
    .staff-brand {
      display: flex; align-items: center; gap: 10px; min-width: 0;
      color: var(--rail-text); text-decoration: none; white-space: nowrap; border-radius: 10px;
    }
    .staff-brand-mark {
      display: inline-flex; align-items: center; justify-content: center; flex: none;
      width: 28px; height: 28px; color: var(--ssra-gold);
    }
    .staff-brand-mark svg { width: 22px; height: 22px; }
    .staff-brand-text {
      display: flex; flex-direction: column; min-width: 0; line-height: 1.2;
      font-size: 1.05rem; font-weight: 500; letter-spacing: -0.01em;
      opacity: 0; transition: opacity var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail.is-expanded .staff-brand-text { opacity: 1; }
    .staff-brand-sub {
      font-size: 0.72rem; font-weight: 400; letter-spacing: 0; color: var(--rail-muted);
      overflow: hidden; text-overflow: ellipsis;
    }
    .staff-rail-pin {
      flex: none; width: 36px; height: 36px; border-radius: 50%; padding: 0;
      background: transparent; border: 1px solid transparent; color: var(--rail-text); cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center;
      transition: background-color var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail-pin:hover { background: var(--rail-hover); }
    .staff-rail-pin:active { background: var(--rail-active); }
    .staff-rail.is-collapsed .staff-rail-pin { display: none; }

    .staff-rail-search { flex: none; padding: 4px 8px 8px; }
    .ops-cmdk-trigger {
      width: 100%; min-height: 40px; padding: 0 14px 0 12px; border-radius: 999px;
      background: var(--rail-field); border: 1px solid transparent; color: var(--rail-text);
      font: inherit; font-size: 0.8125rem; font-weight: 400; cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      transition: background-color var(--ops-dur-fast) var(--ops-ease);
    }
    .ops-cmdk-trigger:hover { background: var(--rail-field-hover); }
    .ops-cmdk-trigger:active { background: var(--rail-active); }
    .ops-cmdk-trigger > span:first-child { display: inline-flex; align-items: center; gap: 10px; min-width: 0; white-space: nowrap; }
    .ops-cmdk-trigger-text { color: rgba(255, 255, 255, 0.9); overflow: hidden; text-overflow: ellipsis; }
    .ops-kbd { font: inherit; font-size: 0.72rem; font-weight: 400; color: var(--text-3); white-space: nowrap; }
    .ops-cmdk-kbd { color: var(--rail-muted); opacity: 0; transition: opacity var(--ops-dur-fast) var(--ops-ease); }
    .ops-cmdk-trigger:hover .ops-cmdk-kbd,
    .ops-cmdk-trigger:focus-visible .ops-cmdk-kbd { opacity: 1; }
    @media (hover: none) { .ops-cmdk-kbd { display: none; } }
    .staff-rail.is-collapsed .ops-cmdk-trigger { justify-content: center; padding-inline: 0; }
    .staff-rail.is-collapsed .ops-cmdk-trigger-text,
    .staff-rail.is-collapsed .ops-cmdk-kbd { display: none; }

    .staff-rail-scroll {
      flex: 1; overflow-y: auto; overflow-x: hidden; padding: 0 0 12px;
      scrollbar-color: rgba(255, 255, 255, 0.28) transparent;
    }
    .staff-rail-group + .staff-rail-group { margin-top: 6px; }
    .staff-rail-group-label {
      margin: 0; padding: 0 20px; height: 0; overflow: hidden; opacity: 0;
      font-size: 0.75rem; font-weight: 500; color: var(--rail-muted); white-space: nowrap;
      transition: opacity var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail.is-expanded .staff-rail-group-label { opacity: 1; height: auto; padding-block: 12px 6px; }
    .staff-rail ul {
      list-style: none; margin: 0; padding: 0 8px;
      display: flex; flex-direction: column; gap: 2px;
    }
    .staff-rail a.nav-item {
      position: relative; display: flex; align-items: center; gap: 12px; min-height: 40px; padding: 0 10px;
      border-radius: 999px; color: var(--rail-text); text-decoration: none; white-space: nowrap;
      font-size: 0.8125rem; font-weight: 400;
      transition: background-color var(--ops-dur-base) var(--ops-ease);
    }
    .staff-rail a.nav-item:hover { background: var(--rail-hover); }
    .staff-rail a.nav-item:active { background: var(--rail-active); }
    .staff-rail a.nav-item.active { background: var(--rail-current); font-weight: 500; }
    .staff-rail a.nav-item.active:hover { background: var(--rail-hover); }
    :root[data-theme="high-contrast"] .staff-rail a.nav-item.active { box-shadow: inset 0 0 0 1px var(--accent); }
    :root[data-theme="high-contrast"] .ops-cmdk-trigger { box-shadow: inset 0 0 0 1px var(--border-0); }
    .staff-rail-icon { display: inline-flex; flex: none; width: 20px; justify-content: center; }
    .staff-rail-icon svg, .ops-cmdk-trigger svg { width: 18px; height: 18px; }
    .staff-rail-label {
      min-width: 0; overflow: hidden; text-overflow: ellipsis;
      opacity: 0; transition: opacity var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail.is-expanded .staff-rail-label { opacity: 1; }

    /* Account footer with an upward popover menu (public assistant header-menu pattern). */
    .staff-rail-foot { flex: none; padding: 8px; position: relative; }
    .staff-acct-trigger {
      width: 100%; min-height: 48px; display: flex; align-items: center; gap: 10px;
      padding: 4px 10px 4px 4px; border-radius: 999px; background: transparent; border: 1px solid transparent;
      color: var(--rail-text); cursor: pointer; text-align: start; font: inherit;
      transition: background-color var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-acct-trigger:hover,
    .staff-acct-trigger[aria-expanded="true"] { background: var(--rail-hover); }
    .staff-acct-avatar {
      position: relative; width: 36px; height: 36px; border-radius: 50%;
      background: var(--avatar-bg); color: var(--avatar-ink); font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
      display: inline-flex; align-items: center; justify-content: center; flex: none;
    }
    .staff-acct-meta {
      display: flex; flex-direction: column; gap: 1px; min-width: 0; flex: 1;
      opacity: 0; transition: opacity var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-rail.is-expanded .staff-acct-meta { opacity: 1; }
    .staff-acct-name,
    .staff-acct-role { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .staff-acct-name { font-size: 0.8125rem; font-weight: 500; color: var(--rail-text); }
    .staff-acct-role { font-size: 0.72rem; color: var(--rail-muted); }
    .staff-acct-chevron { display: inline-flex; flex: none; color: var(--rail-muted); }
    .staff-rail.is-collapsed .staff-acct-trigger { justify-content: center; padding-inline: 0; }
    .staff-rail.is-collapsed .staff-acct-meta,
    .staff-rail.is-collapsed .staff-acct-chevron { display: none; }
    .staff-acct-menu {
      position: absolute; bottom: calc(100% + 6px); left: 8px; right: 8px;
      background: var(--ops-panel); color: var(--text-0); border: 1px solid var(--border-0);
      border-radius: 16px; box-shadow: var(--shadow-lg); padding: 6px;
      display: none; flex-direction: column; gap: 2px; z-index: 45;
    }
    .staff-acct-menu.open { display: flex; animation: opsMenuIn var(--ops-dur-base) var(--ops-ease-out) both; }
    .staff-acct-heading { padding: 8px 12px 4px; font-size: 0.75rem; font-weight: 500; color: var(--text-3); }
    .staff-acct-hr { border: 0; border-top: 1px solid var(--border-0); margin: 4px 6px; }
    .staff-acct-item {
      width: 100%; min-height: 40px; padding: 8px 12px; border-radius: 10px; border: none;
      background: transparent; color: var(--text-0); font: inherit; font-size: 0.8125rem; text-align: start;
      cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 10px;
      text-decoration: none; transition: background-color var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-acct-item > span:first-child { display: inline-flex; align-items: center; gap: 10px; min-width: 0; }
    .staff-acct-item:hover { background: var(--ghost-hover); }
    .staff-acct-item:active { background: var(--ghost-active); }
    .staff-acct-item.active { color: var(--accent); font-weight: 500; }

    /* Top bar: session state as plain text plus the global actions. */
    .call-console-bar {
      position: sticky; top: 0; z-index: 20;
      display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
      gap: 8px 16px; min-height: 56px; padding: 8px 32px;
      background: var(--topbar-bg); border-bottom: 1px solid var(--border-0);
      -webkit-backdrop-filter: saturate(180%) blur(12px); backdrop-filter: saturate(180%) blur(12px);
      font-size: 0.8125rem;
    }
    .call-bar-left, .call-bar-right { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
    .call-bar-left { flex: 1 1 360px; column-gap: 0; row-gap: 2px; }
    .call-bar-right { flex: none; margin-inline-start: auto; }
    .presence-pill { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; color: var(--ops-warn-ink); }
    .presence-pill.is-authenticated { color: var(--ops-good-ink); }
    .presence-icon { display: inline-flex; flex: none; }
    #ops-presence-note { margin-inline-start: 20px; color: var(--text-2); }

    /* Page layout & header */
    .ops-page {
      max-width: var(--ops-max-w); width: 100%; margin: 0 auto;
      padding: 28px 32px 64px; color: var(--text-1);
    }
    .ops-page > * + * { margin-top: var(--ops-band); }
    .ops-page-head {
      display: flex; align-items: flex-end; justify-content: space-between;
      gap: 16px 24px; flex-wrap: wrap;
    }
    .ops-page-head > * { min-width: 0; }
    .ops-eyebrow { display: block; margin-bottom: 6px; font-size: 0.8125rem; font-weight: 500; color: var(--text-3); }
    .ops-page-head h1 {
      margin: 0; font-size: clamp(1.5rem, 2.2vw, 1.75rem); line-height: 1.2;
      font-weight: 500; letter-spacing: -0.015em; color: var(--text-0); text-wrap: balance;
    }
    .ops-page-desc { margin: 8px 0 0; max-width: 68ch; font-size: 0.875rem; line-height: 1.55; color: var(--text-2); }
    .ops-page-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; max-width: 100%; }
    .ops-page-actions > * { min-width: 0; }

    /* Segmented control (public assistant Settings pattern) */
    .ops-segmented {
      display: inline-flex; align-items: center; gap: 2px; padding: 3px;
      border-radius: 999px; background: var(--seg-track); flex-wrap: wrap; max-width: 100%;
    }
    .ops-seg-btn {
      min-height: 32px; min-width: 40px; padding: 0 12px; border-radius: 999px; border: 1px solid transparent;
      background: transparent; color: var(--text-1); font: inherit; font-size: 0.78rem; font-weight: 500; cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center;
      transition: background-color var(--ops-dur-fast) var(--ops-ease), color var(--ops-dur-fast) var(--ops-ease), box-shadow var(--ops-dur-fast) var(--ops-ease);
    }
    .ops-seg-btn:hover:not(.active) { background: var(--ghost-hover); }
    .ops-seg-btn.active { background: var(--seg-active-bg); color: var(--accent); box-shadow: 0 1px 3px rgba(15, 23, 42, 0.16); }
    :root[data-theme="high-contrast"] .ops-seg-btn.active { border-color: var(--accent); box-shadow: none; }
    :root[data-theme="high-contrast"] .ops-segmented { box-shadow: inset 0 0 0 1px var(--border-0); }

    /* Buttons: pill shaped, ghost hover, spring press */
    .ops-btn {
      min-height: 40px; padding: 0 16px; border-radius: 999px;
      background: transparent; border: 1px solid var(--border-1); color: var(--text-0);
      font: inherit; font-size: 0.8125rem; font-weight: 500; line-height: 1.2;
      cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
      text-decoration: none; white-space: nowrap;
      transition: background-color var(--ops-dur-fast) var(--ops-ease), border-color var(--ops-dur-fast) var(--ops-ease),
        box-shadow var(--ops-dur-fast) var(--ops-ease), transform 140ms var(--ops-spring);
    }
    .ops-btn svg { flex: none; }
    .ops-btn:hover { background: var(--ghost-hover); }
    .ops-btn:active { background: var(--ghost-active); transform: scale(0.97); }
    a.ops-btn { color: var(--text-0); }
    .ops-btn.primary,
    .ops-btn.gold,
    a.ops-btn.primary { background: var(--btn-primary-bg); border-color: transparent; color: var(--btn-primary-ink); }
    .ops-btn.primary:hover,
    .ops-btn.gold:hover,
    a.ops-btn.primary:hover { background: var(--btn-primary-hover); box-shadow: var(--shadow-sm); }

    /* KPI cards */
    .ops-stat-grid {
      display: grid; grid-template-columns: repeat(var(--ops-stat-cols, 3), minmax(0, 1fr)); gap: 16px;
    }
    .ops-stat-grid.cols-3 { --ops-stat-cols: 3; }
    .ops-stat-grid.cols-4,
    .ov-stats { --ops-stat-cols: 4; }
    @media (max-width: 1180px) { .ops-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 640px) { .ops-stat-grid { grid-template-columns: minmax(0, 1fr); } }
    .ops-stat {
      position: relative; display: flex; flex-direction: column; gap: 6px; min-width: 0;
      padding: 18px 20px; border-radius: 16px;
      background: var(--ops-panel); border: 1px solid var(--border-0); box-shadow: var(--shadow-sm);
      text-decoration: none; color: inherit;
      transition: border-color var(--ops-dur-fast) var(--ops-ease), box-shadow var(--ops-dur-base) var(--ops-ease), transform 140ms var(--ops-spring);
    }
    a.ops-stat:hover { border-color: var(--border-1); box-shadow: var(--shadow-md); }
    a.ops-stat:active { transform: scale(0.99); }
    .ops-stat-label {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      font-size: 0.8125rem; font-weight: 500; line-height: 1.35; color: var(--text-2);
    }
    .ops-stat-go {
      display: inline-flex; flex: none; color: var(--text-3); opacity: 0; transform: translate(-2px, 2px);
      transition: opacity var(--ops-dur-fast) var(--ops-ease), transform var(--ops-dur-base) var(--ops-ease-out), color var(--ops-dur-fast) var(--ops-ease);
    }
    a.ops-stat:hover .ops-stat-go,
    a.ops-stat:focus-visible .ops-stat-go { opacity: 1; transform: none; color: var(--accent); }
    @media (hover: none) { .ops-stat-go { opacity: 1; transform: none; } }
    .ops-stat-row { display: flex; align-items: baseline; justify-content: space-between; gap: 4px 12px; flex-wrap: wrap; }
    .ops-stat-value {
      font-size: var(--ops-text-xl); line-height: 1.15; font-weight: 600; letter-spacing: -0.02em;
      color: var(--text-0); font-variant-numeric: tabular-nums;
    }
    .ops-stat-unit { font-size: 0.875rem; font-weight: 400; letter-spacing: 0; color: var(--text-2); white-space: pre; }
    .ops-delta {
      display: inline-flex; align-items: center; gap: 4px;
      font-size: 0.78rem; font-weight: 600; font-variant-numeric: tabular-nums; color: var(--text-2);
    }
    .ops-delta.is-good { color: var(--ops-good-ink); }
    .ops-delta.is-bad { color: var(--ops-bad-ink); }
    .ops-stat-hint { font-size: 0.78rem; line-height: 1.45; color: var(--text-3); }
    .ops-sparkline { display: block; width: 100%; height: 36px; margin-top: 6px; color: var(--accent); overflow: visible; }

    /* Cards, two-column layouts and card headers */
    .ov-cols { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr); gap: var(--ops-band); align-items: start; }
    @media (max-width: 1080px) { .ov-cols { grid-template-columns: minmax(0, 1fr); } }
    .ov-side { display: grid; gap: var(--ops-band); min-width: 0; }
    .ops-panel {
      min-width: 0; background: var(--ops-panel); border: 1px solid var(--border-0);
      border-radius: 16px; box-shadow: var(--shadow-sm); overflow: hidden;
    }
    .ops-panel-head {
      display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px 20px;
      min-height: 56px; padding: 14px 20px; border-bottom: 1px solid var(--ops-hairline);
    }
    .ops-panel-head h2 { margin: 0; min-width: 0; font-size: 0.9375rem; line-height: 1.35; font-weight: 600; color: var(--text-0); }
    .ops-panel-body { padding: 16px 20px 20px; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .ops-panel-body:has(> .ops-table:only-child) { padding: 0; }
    .ops-panel-end { margin-inline-start: auto; display: flex; align-items: center; gap: 8px; }
    .ops-panel-note { margin: 0 0 16px; font-size: 0.8125rem; line-height: 1.55; color: var(--text-2); }

    /* Status readings: plain text, meaning carried by a text-safe ink (no capsules). */
    .ops-chip,
    .ov-chip {
      display: inline-flex; align-items: center; gap: 6px; padding: 0; border: 0; border-radius: 0; background: none;
      font-size: 0.8125rem; font-weight: 500; line-height: 1.4; color: var(--text-2);
    }
    .ops-chip svg, .ov-chip svg { flex: none; }
    .ops-chip + .ops-chip { margin-inline-start: 20px; }
    .ops-page-actions > .ops-chip,
    .ops-page-actions > .ops-fresh { margin-inline-end: 8px; }
    .ops-chip.good, .ops-chip.is-good, .ov-chip.good { color: var(--ops-good-ink); }
    .ops-chip.warn, .ops-chip.is-warn, .ov-chip.warn { color: var(--ops-warn-ink); }
    .ops-chip.bad, .ops-chip.is-danger { color: var(--ops-bad-ink); }
    .ops-chip.info, .ops-chip.is-info { color: var(--ops-info-ink); }
    .ops-fresh { display: inline-flex; align-items: center; gap: 8px; font-size: 0.8125rem; font-weight: 500; color: var(--text-2); }
    .ops-fresh-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ssra-civic-green); flex: none; }
    .ops-fresh-dot.is-stale { background: var(--text-3); }
    .ops-meta-xs { font-size: 0.75rem; color: var(--text-3); }

    /* Tables */
    .ops-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.8125rem; color: var(--text-1); }
    .ops-table th, .ops-table td {
      padding: 12px 16px; text-align: start; vertical-align: middle; border-bottom: 1px solid var(--ops-hairline);
    }
    .ops-table th {
      padding-block: 10px; background: var(--ops-inset); border-bottom-color: var(--border-0);
      font-size: 0.75rem; font-weight: 500; color: var(--text-3); white-space: nowrap;
    }
    .ops-panel-body > .ops-table:only-child th:first-child,
    .ops-panel-body > .ops-table:only-child td:first-child { padding-inline-start: 20px; }
    .ops-panel-body > .ops-table:only-child th:last-child,
    .ops-panel-body > .ops-table:only-child td:last-child { padding-inline-end: 20px; }
    .ops-table tbody tr { transition: background-color var(--ops-dur-fast) var(--ops-ease); }
    .ops-table tbody tr:hover { background: var(--ops-row-hover); }
    .ops-table tbody tr:last-child td { border-bottom: 0; }
    .ops-table td strong { font-weight: 500; color: var(--text-0); }

    /* Definition lists */
    .ov-kv { margin: 0; display: grid; }
    .ov-kv > div {
      display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 4px 16px;
      padding: 10px 0; border-bottom: 1px solid var(--ops-hairline);
    }
    .ov-kv > div:first-child { padding-top: 0; }
    .ov-kv > div:last-child { padding-bottom: 0; border-bottom: 0; }
    .ov-kv dt { font-size: 0.8125rem; color: var(--text-2); }
    .ov-kv dd { margin: 0; font-size: 0.8125rem; font-weight: 500; color: var(--text-0); text-align: end; overflow-wrap: anywhere; }

    /* Review queue rows: selection is carried by the row's own border colour and a surface tint. */
    .ov-review-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
    .ov-review-item {
      display: grid; gap: 4px; padding: 12px 14px; border: 1px solid transparent; border-radius: 12px; background: transparent;
      transition: background-color var(--ops-dur-fast) var(--ops-ease), border-color var(--ops-dur-fast) var(--ops-ease);
    }
    .ov-review-item.is-clickable { cursor: pointer; }
    .ov-review-item.is-clickable:hover { background: var(--ops-row-hover); }
    .ov-review-item.is-selected,
    .ov-review-item.is-selected:hover { border-color: var(--accent); background: var(--accent-soft); }
    .ov-review-list > .ov-review-item:not(.is-clickable) {
      padding-inline: 0; border-radius: 0; border-bottom-color: var(--ops-hairline);
    }
    .ov-review-list > .ov-review-item:not(.is-clickable):first-child { padding-top: 0; }
    .ov-review-list > .ov-review-item:not(.is-clickable):last-child { padding-bottom: 0; border-bottom-color: transparent; }
    .ov-review-top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; row-gap: 4px; }
    .ov-review-top > * + * { margin-inline-start: 20px; }
    .ops-ticket-title { font-size: 0.875rem; font-weight: 500; color: var(--text-0); }
    .ops-review-link { justify-self: start; font-size: 0.875rem; font-weight: 500; color: var(--text-0); text-decoration: none; }
    .ops-review-link:hover { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
    .ops-review-quote { margin: 0; font-size: 0.8125rem; line-height: 1.5; color: var(--text-2); }
    .ops-duty-lead { margin: 0 0 16px; font-size: 0.875rem; color: var(--text-2); }
    .ops-duty-lead strong { font-weight: 600; color: var(--text-0); }

    /* Copilot case panel */
    .ops-msg-box { margin-bottom: 16px; padding: 14px 16px; border-radius: 12px; background: var(--ops-inset); border: 1px solid var(--border-0); }
    .ops-msg-head { margin-bottom: 4px; font-size: 0.75rem; font-weight: 500; color: var(--text-3); }
    .ops-msg-body { font-size: 0.875rem; line-height: 1.55; color: var(--text-0); }
    .ops-draft-wrap { margin-bottom: 12px; }
    .ops-draft-label { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 0.8125rem; font-weight: 500; color: var(--text-1); }
    .ops-draft-label svg { color: var(--accent); }
    .ops-draft-textarea {
      display: block; width: 100%; min-height: 136px; padding: 12px 14px; border-radius: 12px; resize: vertical;
      background: var(--ops-panel); color: var(--text-0); border: 1px solid var(--border-1);
      font: inherit; font-size: 0.875rem; line-height: 1.55;
      transition: border-color 150ms var(--ops-ease), box-shadow 150ms var(--ops-ease);
    }
    .ops-draft-textarea:hover { border-color: var(--border-2); }
    .ops-draft-textarea:focus { border-color: var(--ssra-blue); }
    .ops-chips-row { display: flex; flex-wrap: wrap; gap: 8px 20px; margin-bottom: 16px; }
    .ops-chips-row > .ops-chip + .ops-chip { margin-inline-start: 0; }
    .ops-actions-row, .ops-actions-row-mt { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .ops-actions-row-mt { margin-top: 16px; }
    .ops-status-msg { margin-top: 12px; font-size: 0.8125rem; font-weight: 500; color: var(--ops-good-ink); }

    /* Control-plane pieces */
    .ops-degrade-bar {
      display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
      margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--ops-hairline);
    }
    .ops-degrade-label { font-size: 0.8125rem; font-weight: 500; color: var(--text-0); }
    .ops-release-steps { margin: 0; padding: 0; list-style: none; display: grid; font-size: 0.8125rem; line-height: 1.5; }
    .ops-release-steps li { padding: 10px 0; border-bottom: 1px solid var(--ops-hairline); }
    .ops-release-steps li:first-child { padding-top: 0; }
    .ops-release-steps li:last-child { padding-bottom: 0; border-bottom: 0; }
    .ops-release-steps strong { font-weight: 600; color: var(--text-0); }
    .ops-release-steps .ops-chip { display: inline; }

    /* Empty states & the preview notice */
    .ops-empty {
      display: flex; flex-direction: column; align-items: center; gap: 8px;
      padding: 32px 20px; text-align: center; border-radius: 12px; background: var(--ops-inset);
    }
    .ops-empty-mark {
      display: grid; place-items: center; width: 44px; height: 44px; margin-bottom: 4px;
      border-radius: 50%; background: var(--accent-soft); color: var(--accent);
    }
    .ops-empty-title { margin: 0; font-size: 0.9375rem; font-weight: 600; color: var(--text-0); }
    .ops-empty-body { margin: 0; max-width: 44ch; font-size: 0.8125rem; line-height: 1.55; color: var(--text-2); }
    .ops-preview-card { padding: 20px 24px; }
    .ops-preview-card p, .ops-preview-card li { margin: 0; font-size: 0.875rem; line-height: 1.6; color: var(--text-1); }
    .ops-preview-card p + p { margin-top: 8px; }
    .ops-preview-card ul { display: grid; gap: 4px; margin: 12px 0 0; padding-inline-start: 1.25rem; }
    .ops-preview-chip { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 0.8125rem; font-weight: 600; color: var(--ops-warn-ink); }
    .is-hidden { display: none !important; }

    /* Command palette (public assistant Settings modal motion) */
    .ops-cmdk-backdrop {
      position: fixed; inset: 0; z-index: 90; display: none; place-items: start center; padding: 12vh 16px 16px;
      background: var(--scrim); -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px);
    }
    .ops-cmdk-backdrop.open { display: grid; animation: opsFade 180ms var(--ops-ease) both; }
    .ops-cmdk-dialog {
      width: min(600px, 100%); background: var(--ops-panel); border: 1px solid var(--border-0);
      border-radius: 20px; box-shadow: var(--shadow-modal); overflow: hidden;
    }
    .ops-cmdk-backdrop.open .ops-cmdk-dialog { animation: opsRise 240ms var(--ops-ease-out) both; }
    .ops-cmdk-input {
      width: 100%; min-height: 56px; padding: 0 20px; border: none; border-bottom: 1px solid var(--border-0);
      background: transparent; color: var(--text-0); font: inherit; font-size: 1rem;
    }
    .ops-cmdk-input::placeholder { color: var(--text-3); }
    .ops-cmdk-input:focus-visible { outline-offset: -3px; }
    .ops-cmdk-list { list-style: none; margin: 0; padding: 8px; max-height: min(360px, 50vh); overflow-y: auto; }
    .ops-cmdk-item {
      min-height: 40px; padding: 8px 12px; border-radius: 10px; cursor: pointer;
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      color: var(--text-0); font-size: 0.875rem; transition: background-color 120ms var(--ops-ease);
    }
    .ops-cmdk-item:hover,
    .ops-cmdk-item[data-active="true"] { background: var(--ghost-hover); }
    .ops-cmdk-foot {
      display: flex; justify-content: space-between; flex-wrap: wrap; gap: 4px 12px; padding: 10px 16px;
      border-top: 1px solid var(--border-0); background: var(--ops-inset); font-size: 0.75rem; color: var(--text-3);
    }
    .ops-cmdk-foot > span { display: inline-flex; align-items: center; gap: 6px; }

    /* Dedicated auth pages (/signin, /signup, /signin/callback): no rail, top bar or palette; one centred card on the
       public assistant's canvas. */
    .staff-shell[data-layout="auth"] .staff-rail,
    .staff-shell[data-layout="auth"] .call-console-bar,
    .staff-shell[data-layout="auth"] .ops-mobile-backdrop { display: none !important; }
    .staff-shell[data-layout="auth"] .staff-shell-content {
      margin-inline-start: 0; transition: none; background: var(--auth-canvas), var(--bg-0);
    }
    .staff-shell[data-layout="auth"] .ops-page {
      max-width: none; min-height: 100dvh; padding: 40px 16px;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
    }
    .signin-wrap { width: 100%; max-width: 420px; display: flex; flex-direction: column; align-items: stretch; gap: 16px; }
    .signin-card {
      width: 100%; padding: 32px; background: var(--ops-panel); border: 1px solid var(--border-0); border-radius: 24px;
      box-shadow: var(--auth-card-shadow);
    }
    .auth-brand { display: flex; flex-direction: column; align-items: center; gap: 10px; margin-bottom: 20px; }
    .signin-mark {
      display: grid; place-items: center; width: 48px; height: 48px;
      border-radius: 50%; background: var(--grad-primary); color: var(--on-grad); box-shadow: 0 6px 20px rgba(0, 93, 180, 0.25);
    }
    .signin-mark svg { width: 22px; height: 22px; }
    .auth-wordmark { font-size: 0.9375rem; font-weight: 500; letter-spacing: -0.005em; color: var(--text-1); }
    .signin-head { text-align: center; margin-bottom: 24px; }
    .signin-head h1 { margin: 0; font-size: 1.625rem; line-height: 1.2; font-weight: 500; letter-spacing: -0.015em; color: var(--text-0); }
    .signin-sub { margin: 8px 0 0; font-size: 0.875rem; line-height: 1.5; color: var(--text-2); }
    .signin-form { display: grid; gap: 16px; }
    .signin-field { display: grid; gap: 6px; }
    .signin-label { font-size: 0.8125rem; font-weight: 500; color: var(--text-1); }
    .signin-input {
      width: 100%; min-height: 44px; padding: 0 14px; border-radius: 12px; border: 1px solid var(--border-1);
      background: var(--ops-panel); color: var(--text-0); font: inherit; font-size: 0.875rem;
      transition: border-color 150ms var(--ops-ease), box-shadow 150ms var(--ops-ease);
    }
    .signin-input:hover { border-color: var(--border-2); }
    .signin-input:focus { border-color: var(--ssra-blue); }
    .signin-input::placeholder { color: var(--text-3); }
    .signin-primary, .signin-secondary {
      width: 100%; min-height: 44px; padding: 0 20px; border-radius: 999px;
      font: inherit; font-size: 0.875rem; font-weight: 500; cursor: pointer; text-decoration: none;
      display: inline-flex; align-items: center; justify-content: center; gap: 8px;
      transition: background-color var(--ops-dur-fast) var(--ops-ease), box-shadow var(--ops-dur-fast) var(--ops-ease), transform 140ms var(--ops-spring);
    }
    .signin-primary { margin-top: 4px; background: var(--btn-primary-bg); color: var(--btn-primary-ink); border: 1px solid transparent; }
    .signin-primary:hover { background: var(--btn-primary-hover); box-shadow: var(--shadow-sm); }
    .signin-secondary { background: transparent; color: var(--text-0); border: 1px solid var(--border-1); }
    .signin-secondary:hover { background: var(--ghost-hover); }
    .signin-primary:active, .signin-secondary:active { transform: scale(0.98); }
    .auth-divider { display: flex; align-items: center; gap: 12px; margin: 20px 0; font-size: 0.75rem; color: var(--text-3); }
    .auth-divider-line { flex: 1; height: 1px; background: var(--border-0); }
    .auth-actions { display: grid; gap: 8px; margin-top: 20px; }
    .signin-status {
      margin: 16px 0 0; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--border-1);
      background: var(--ops-inset); color: var(--text-1); font-size: 0.8125rem; line-height: 1.5; overflow-wrap: anywhere;
    }
    .signin-status.ok {
      border-color: color-mix(in srgb, var(--ops-good-ink) 35%, transparent);
      background: color-mix(in srgb, var(--ops-good-ink) 7%, var(--ops-panel)); color: var(--ops-good-ink);
    }
    .signin-status.error {
      border-color: color-mix(in srgb, var(--ops-bad-ink) 35%, transparent);
      background: color-mix(in srgb, var(--ops-bad-ink) 6%, var(--ops-panel)); color: var(--ops-bad-ink);
    }
    .signin-status.info {
      border-color: color-mix(in srgb, var(--accent) 35%, transparent);
      background: var(--accent-soft); color: var(--text-0);
    }
    .auth-foot { display: grid; justify-items: center; gap: 12px; margin-top: 24px; font-size: 0.8125rem; color: var(--text-2); text-align: center; }
    .auth-foot p { margin: 0; }
    .auth-foot a { color: var(--accent); font-weight: 500; text-decoration: underline; text-underline-offset: 2px; }
    .auth-foot .auth-back { color: var(--text-2); font-weight: 400; text-decoration: none; }
    .auth-foot .auth-back:hover { color: var(--text-0); text-decoration: underline; }
    .auth-note { margin: 0; font-size: 0.75rem; line-height: 1.5; color: var(--text-2); text-align: center; }
    @media (max-width: 480px) {
      .staff-shell[data-layout="auth"] .ops-page { justify-content: flex-start; padding: 24px 16px; }
      .signin-card { padding: 24px 20px; border-radius: 20px; }
    }

    @keyframes opsFade { from { opacity: 0; } }
    @keyframes opsRise { from { opacity: 0; transform: translateY(8px) scale(0.985); } }
    @keyframes opsMenuIn { from { opacity: 0; transform: translateY(4px); } }

    /* Phone drawer */
    .mobile-nav-btn { display: none; }
    .ops-mobile-backdrop { display: none; position: fixed; inset: 0; background: var(--scrim); z-index: 25; }
    @media (pointer: coarse), (max-width: 820px) {
      .staff-rail-pin, .ops-cmdk-trigger, .ops-btn, .staff-acct-item, .staff-rail a.nav-item, .ops-seg-btn { min-height: 44px; }
      .staff-rail-pin { min-width: 44px; }
    }
    @media (max-width: 820px) {
      .staff-shell { --rail-w: 0px !important; }
      .staff-rail {
        transform: translateX(-100%); visibility: hidden; width: min(280px, 86vw) !important;
        transition: transform 220ms var(--ops-ease), visibility 0s linear 220ms;
      }
      .staff-rail.is-drawer-open {
        transform: translateX(0); visibility: visible; box-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
        transition: transform 220ms var(--ops-ease), visibility 0s;
      }
      .ops-mobile-backdrop.open { display: block; }
      .mobile-nav-btn { display: inline-flex; }
      .call-console-bar {
        position: static; display: grid; grid-template-columns: auto minmax(0, 1fr);
        grid-template-areas: "menu actions" "presence presence" "note note"; gap: 8px 12px; padding: 8px 16px 12px;
      }
      .call-bar-left { display: contents; }
      .call-bar-right { grid-area: actions; justify-content: flex-end; }
      #mobile-ops-nav-btn { grid-area: menu; justify-self: start; }
      .presence-pill { grid-area: presence; }
      #ops-presence-note { grid-area: note; margin-inline-start: 0; }
      .ops-page { padding: 20px 16px 48px; }
      /* Always show labels, group headings, search text & account details inside the drawer. */
      .staff-rail .staff-rail-label,
      .staff-rail .staff-rail-group-label,
      .staff-rail .staff-brand-text,
      .staff-rail .staff-acct-meta { opacity: 1; }
      .staff-rail .staff-rail-group-label { height: auto; padding-block: 12px 6px; }
      .staff-rail.is-collapsed .ops-cmdk-trigger { justify-content: space-between; padding-inline: 12px 14px; }
      .staff-rail.is-collapsed .ops-cmdk-trigger-text { display: inline; }
      .staff-rail.is-collapsed .staff-acct-trigger { justify-content: flex-start; padding-inline: 4px 10px; }
      .staff-rail.is-collapsed .staff-acct-meta,
      .staff-rail.is-collapsed .staff-acct-chevron { display: flex; }
      .staff-rail-pin { display: none; }
    }
    @media (max-width: 480px) {
      .ops-panel-head, .ops-panel-body { padding-inline: 16px; }
      .ops-stat { padding: 16px; }
      .call-bar-right .ops-btn.primary { width: 44px; padding: 0; }
      .call-bar-right .ops-btn-label {
        position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
        overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
      }
    }

    @media (prefers-reduced-transparency: reduce) {
      .call-console-bar, .ops-cmdk-backdrop { -webkit-backdrop-filter: none; backdrop-filter: none; }
      .call-console-bar { background: var(--bg-0); }
    }
    @media (forced-colors: active) {
      .staff-rail, .ops-stat, .ops-panel, .ops-btn, .ops-cmdk-dialog, .signin-card, .signin-secondary, .staff-acct-menu {
        border: 1px solid CanvasText;
      }
      .staff-rail a.nav-item.active, .ops-seg-btn.active, .ov-review-item.is-selected {
        outline: 2px solid Highlight;
        outline-offset: -2px;
      }
      :is(a, button, input, select, textarea, [tabindex]):focus-visible { outline-color: Highlight; }
    }
    @media print {
      .staff-rail, .call-console-bar, .ops-cmdk-backdrop, .ops-mobile-backdrop {
        display: none !important;
      }
      .staff-shell-content {
        margin-inline-start: 0 !important;
        background: #FFFFFF !important;
      }
      body, .ops-page, .ops-panel, .ops-stat {
        background: #FFFFFF !important;
        color: #000000 !important;
        box-shadow: none !important;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .staff-rail, .staff-shell-content, .staff-rail-label, .staff-rail-group-label, .staff-brand-text { transition: none !important; }
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
    }
  </style>
</head>
<body>
  <a class="staff-skip" href="#staff-main">Skip to content</a>

  <div class="staff-shell" id="ssra-staff-shell" data-layout="${isAuthRoute(currentPath) ? "auth" : "app"}">
    <div id="ops-mobile-backdrop" class="ops-mobile-backdrop" aria-hidden="true"></div>
    <!-- Left Vertical Operations Rail (StaffGuard.tsx pattern) -->
    <nav id="staff-rail" class="staff-rail is-expanded" aria-label="Staff console preview navigation">
      <div class="staff-rail-head">
        <a class="staff-brand" href="/admin" aria-label="SSRA Operations Console preview">
          <span class="staff-brand-mark" aria-hidden="true">${ICONS.ssraCrest}</span>
          <span class="staff-brand-text">
            SSRA Assist
            <span class="staff-brand-sub">Operations console</span>
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

      <div class="staff-rail-scroll" id="staff-rail-groups">${renderServerRailGroups(currentPath, "ssra_admin")}</div>

      <div class="staff-rail-foot">
        <div id="staff-acct-menu" class="staff-acct-menu" role="menu" aria-label="Preview persona and appearance">
          <div role="group" aria-label="Preview persona, not access control">
            <div class="staff-acct-heading" aria-hidden="true">Preview persona · not access control</div>
            <button type="button" class="staff-acct-item" data-set-role="ssra_admin" role="menuitemradio" aria-checked="true" tabindex="-1"><span>Administrator view (preview)</span><span>${ICONS.check}</span></button>
            <button type="button" class="staff-acct-item" data-set-role="ssra_staff" role="menuitemradio" aria-checked="false" tabindex="-1"><span>Tax agent view (preview)</span><span></span></button>
            <button type="button" class="staff-acct-item" data-set-role="ssra_auditor" role="menuitemradio" aria-checked="false" tabindex="-1"><span>Auditor view (preview)</span><span></span></button>
          </div>
          <hr class="staff-acct-hr" role="separator" />
          <div role="group" aria-label="Appearance">
            <div class="staff-acct-heading" aria-hidden="true">Appearance</div>
            <button type="button" class="staff-acct-item" data-set-theme="system" role="menuitemradio" aria-checked="true" tabindex="-1"><span>${ICONS.monitor} System</span></button>
            <button type="button" class="staff-acct-item" data-set-theme="light" role="menuitemradio" aria-checked="false" tabindex="-1"><span>${ICONS.sun} Light</span></button>
            <button type="button" class="staff-acct-item" data-set-theme="dark" role="menuitemradio" aria-checked="false" tabindex="-1"><span>${ICONS.moon} Dark</span></button>
            <button type="button" class="staff-acct-item" data-set-theme="high-contrast" role="menuitemradio" aria-checked="false" tabindex="-1"><span>${ICONS.contrast} High contrast</span></button>
          </div>
          <hr class="staff-acct-hr" role="separator" />
          <a href="/signin" data-nav="/signin" class="staff-acct-item" role="menuitem" tabindex="-1"><span>${ICONS.logIn} Sign in with Keycloak SSO</span></a>
          <a href="/signup" data-nav="/signup" class="staff-acct-item" role="menuitem" tabindex="-1"><span>${ICONS.userPlus} Create an account</span></a>
          <a href="${escapeHtml(publicAssistantUrl)}" class="staff-acct-item" role="menuitem" tabindex="-1"><span>${ICONS.messageSquare} Return to the public assistant</span><span>${ICONS.arrowUpRight}</span></a>
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
          <button type="button" id="mobile-ops-nav-btn" class="ops-btn mobile-nav-btn" aria-expanded="false" aria-controls="staff-rail">${ICONS.panelLeft} Menu</button>
          <span id="ops-presence-pill" class="presence-pill"><span id="ops-presence-icon" class="presence-icon" aria-hidden="true">${ICONS.eye}</span><span id="ops-presence-text">Preview only · no authenticated staff session</span></span>
          <span id="ops-presence-note">No live calls, taxpayer records, or service telemetry are shown.</span>
        </div>
        <div class="call-bar-right">
          <a id="call-bar-signin-link" href="/signin" data-nav="/signin" class="ops-btn">Sign in</a>
          <a id="call-bar-signup-link" href="/signup" data-nav="/signup" class="ops-btn">Sign up</a>
          <button type="button" id="ops-signout-btn" class="ops-btn is-hidden" data-testid="ops-signout-btn" data-action="signout">Sign out</button>
          <a href="${escapeHtml(publicAssistantUrl)}" class="ops-btn primary">${ICONS.messageSquare}<span class="ops-btn-label">Taxpayer MainChat</span></a>
        </div>
      </div>

      <main id="staff-main" class="ops-page" data-route="${escapeHtml(currentPath)}" tabindex="-1">
        ${renderRouteBody(currentPath, currentTitle, currentMeta.group, publicAssistantUrl)}
      </main>
    </div>
  </div>

  <!-- Command Palette Dialog (⌘K / Ctrl+K) -->
  <div id="cmdk-backdrop" class="ops-cmdk-backdrop" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="ops-cmdk-dialog">
      <input id="cmdk-input" class="ops-cmdk-input" type="text" role="combobox" aria-expanded="true" aria-controls="cmdk-list" aria-autocomplete="list" aria-label="Search preview navigation" placeholder="Search preview pages… (type to filter)" autocomplete="off" />
      <ul id="cmdk-list" class="ops-cmdk-list" role="listbox" aria-label="Available commands"></ul>
      <p id="cmdk-count" class="ops-sr-only" role="status" aria-live="polite"></p>
      <div class="ops-cmdk-foot">
        <span>${ICONS.chevronUpDown} Up/Down to navigate · Enter to open · Esc to close</span>
        <span>Preview only · no staff session</span>
      </div>
    </div>
  </div>

  <script nonce="${nonce}">
    (() => {
      const ICONS = ${JSON.stringify(ICONS)};
      const DESTINATIONS = ${JSON.stringify(DESTINATIONS)};
      const ROUTE_SPECS = ${JSON.stringify(ROUTE_SPECS)};
      const PUBLIC_ASSISTANT_URL = ${JSON.stringify(publicAssistantUrl)};

      const ROLE_META = {
        ssra_admin: { initials: "AD", name: "Administrator preview", label: "Not signed in · preview only", landing: "/admin" },
        ssra_staff: { initials: "ST", name: "Tax agent preview", label: "Not signed in · preview only", landing: "/agent" },
        ssra_auditor: { initials: "AU", name: "Auditor preview (read-only)", label: "Not signed in · preview only", landing: "/analytics" },
      };

      const ACCOUNT_DIRECTORY = [
        {
          role: "ssra_admin",
          email: "admin@nra.gov.ss",
          username: "ssra_admin",
          aliases: ["admin@nra.gov.ss", "admin@ssra.gov.ss", "ssra_admin", "admin", "officer.admin", "officer.admin@nra.gov.ss"],
          displayName: "Grace A.",
          roleLabel: "Administrator",
          staffId: "stf_admin_grace_01",
          officeCode: "JUBA_HQ",
          initials: "GA",
          landingPath: "/admin",
          digestSha256: "15e2bad00ca51b94f0f4f6c54b0191467fd68a5678b9fa585a10dbab1db3ab0b",
        },
        {
          role: "ssra_staff",
          email: "staff@nra.gov.ss",
          username: "ssra_staff",
          aliases: ["staff@nra.gov.ss", "staff@ssra.gov.ss", "ssra_staff", "staff", "agent@nra.gov.ss", "officer.staff", "officer.staff@nra.gov.ss"],
          displayName: "Deng M.",
          roleLabel: "Tax Agent",
          staffId: "stf_agent_deng_02",
          officeCode: "JUBA_HQ",
          initials: "DM",
          landingPath: "/agent",
          digestSha256: "3974ad6a9bfae75807da570ddae63d49e1c4fe0176c619a0aac998fd7289d347",
        },
        {
          role: "ssra_auditor",
          email: "auditor@nra.gov.ss",
          username: "ssra_auditor",
          aliases: ["auditor@nra.gov.ss", "auditor@ssra.gov.ss", "ssra_auditor", "auditor", "officer.auditor", "officer.auditor@nra.gov.ss"],
          displayName: "Nyabol K.",
          roleLabel: "Forensic Auditor (Read-Only)",
          staffId: "stf_auditor_nyabol_03",
          officeCode: "JUBA_HQ",
          initials: "NK",
          landingPath: "/analytics",
          digestSha256: "400c6c4df7c2cf00c0b4ac189325343348e90c64acc7e80fa7cedf3ff4021a46",
        },
        {
          role: "verified_taxpayer",
          email: "taxpayer@etax.nra.gov.ss",
          username: "verified_taxpayer",
          aliases: ["taxpayer@etax.nra.gov.ss", "taxpayer@nra.gov.ss", "taxpayer@ssra.gov.ss", "verified_taxpayer", "taxpayer", "amina@etax.nra.gov.ss"],
          displayName: "Amina M. (TIN ••••1234)",
          roleLabel: "Verified Taxpayer",
          staffId: "sub_taxpayer_amina_01",
          officeCode: "JUBA_HQ",
          initials: "AM",
          landingPath: "/en",
          digestSha256: "13f0de343c3ef088f5b4d62702b01ca6a1ce22748dea5cc0366653e52d405012",
        },
      ];

      const AUTH_SESSION_STORAGE_KEY = "ssra-authenticated-session-v1";

      function sha256Hex(ascii) {
        const K = [
          0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
          0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
          0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
          0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
          0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
          0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
          0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
          0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
        ];
        const bytes = Array.from(new TextEncoder().encode(ascii));
        const bitLen = bytes.length * 8;
        bytes.push(0x80);
        while ((bytes.length % 64) !== 56) bytes.push(0);
        const hi = Math.floor(bitLen / 0x100000000);
        const lo = bitLen >>> 0;
        for (let i = 3; i >= 0; i--) bytes.push((hi >>> (i * 8)) & 0xff);
        for (let i = 3; i >= 0; i--) bytes.push((lo >>> (i * 8)) & 0xff);
        let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
        let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
        const w = new Int32Array(64);
        const ror = (v, n) => (v >>> n) | (v << (32 - n));
        for (let off = 0; off < bytes.length; off += 64) {
          for (let i = 0; i < 16; i++) {
            const j = off + i * 4;
            w[i] = (bytes[j] << 24) | (bytes[j + 1] << 16) | (bytes[j + 2] << 8) | bytes[j + 3];
          }
          for (let i = 16; i < 64; i++) {
            const s0 = ror(w[i - 15], 7) ^ ror(w[i - 15], 18) ^ (w[i - 15] >>> 3);
            const s1 = ror(w[i - 2], 17) ^ ror(w[i - 2], 19) ^ (w[i - 2] >>> 10);
            w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
          }
          let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
          for (let i = 0; i < 64; i++) {
            const S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25);
            const ch = (e & f) ^ (~e & g);
            const temp1 = (h + S1 + ch + K[i] + w[i]) | 0;
            const S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22);
            const maj = (a & b) ^ (a & c) ^ (b & c);
            const temp2 = (S0 + maj) | 0;
            h = g; g = f; f = e; e = (d + temp1) | 0; d = c; c = b; b = a; a = (temp1 + temp2) | 0;
          }
          h0 = (h0 + a) | 0; h1 = (h1 + b) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0;
          h4 = (h4 + e) | 0; h5 = (h5 + f) | 0; h6 = (h6 + g) | 0; h7 = (h7 + h) | 0;
        }
        return [h0, h1, h2, h3, h4, h5, h6, h7].map((x) => (x >>> 0).toString(16).padStart(8, "0")).join("");
      }

      const mainEl = document.getElementById("staff-main");
      const railEl = document.getElementById("staff-rail");
      const railGroupsEl = document.getElementById("staff-rail-groups");
      const pinBtn = document.getElementById("rail-pin-btn");
      const acctTrigger = document.getElementById("staff-acct-trigger");
      const acctMenu = document.getElementById("staff-acct-menu");

      const THEME_STORAGE_KEY = ${JSON.stringify(SSRA_THEME_STORAGE_KEY)};
      const THEME_COLORS = ${JSON.stringify(SSRA_THEME_COLORS)};
      const VALID_THEMES = ["light", "dark", "high-contrast"];
      function systemTheme() {
        if (window.matchMedia?.("(prefers-contrast: more)")?.matches) return "high-contrast";
        return window.matchMedia?.("(prefers-color-scheme: light)")?.matches ? "light" : "dark";
      }
      // Same order as the pre-paint bootstrap: shared choice, the public assistant's store, the legacy console key.
      function readThemeChoice() {
        try {
          const shared = localStorage.getItem(THEME_STORAGE_KEY);
          if (shared === "system" || VALID_THEMES.includes(shared)) return shared;
          const store = JSON.parse(localStorage.getItem("ssra-chat-store-v2") || "null");
          if (store && VALID_THEMES.includes(store.theme)) return store.theme;
          const legacy = localStorage.getItem("ssra-ops-theme");
          if (VALID_THEMES.includes(legacy)) return legacy;
        } catch {}
        return "system";
      }
      function writeThemeChoice(choice) {
        try {
          localStorage.setItem(THEME_STORAGE_KEY, choice);
          localStorage.removeItem("ssra-ops-theme");
        } catch {}
      }

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

      function readStoredSession() {
        try {
          const raw = localStorage.getItem(AUTH_SESSION_STORAGE_KEY);
          if (!raw) return null;
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed.role === "string" && typeof parsed.email === "string" && ROLE_META[parsed.role]) {
            return parsed;
          }
        } catch {}
        return null;
      }

      const initialSession = readStoredSession();

      let state = {
        route: mainEl?.getAttribute("data-route") || "/admin",
        role: initialSession?.role || readUiPreference("ssra-ops-preview-persona", "ssra_admin"),
        session: initialSession,
        themeChoice: readThemeChoice(),
        theme: "light",
        railMode: readUiPreference("ssra-ops-rail-mode", "always-open"),
        periodDays: 30,
        degradationLevel: 1,
        selectedTicketIdx: 0,
        flagOverrides: {
          "kill_switch.disable_tier2_writes": false,
          "degrade.retrieval_only_mode": false,
          "voice.enable_orpheus_tts": true,
          "memory.enable_qdrant_episodic_sync": true,
        },
      };

      function setAuthenticatedSession(account) {
        const sessionObj = {
          role: account.role,
          email: account.email,
          username: account.username,
          displayName: account.displayName,
          roleLabel: account.roleLabel,
          staffId: account.staffId,
          officeCode: account.officeCode,
          initials: account.initials,
          landingPath: account.landingPath,
          signedInAt: new Date().toISOString(),
        };
        try {
          localStorage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(sessionObj));
        } catch {}
        if (account.role === "verified_taxpayer") {
          window.location.assign(PUBLIC_ASSISTANT_URL);
          return;
        }
        state.session = sessionObj;
        state.role = account.role;
        writeUiPreference("ssra-ops-preview-persona", account.role);
        navigateTo(account.landingPath || "/admin");
      }

      function clearAuthenticatedSession() {
        state.session = null;
        try {
          localStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
        } catch {}
        navigateTo("/signin");
      }

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
        if (el === mainEl) el.removeAttribute("data-auth-wired");
        el.innerHTML = ttPolicy ? ttPolicy.createHTML(htmlStr) : htmlStr;
      }

      let lastRenderedRailKey = "ssra_admin|" + (mainEl?.getAttribute("data-route") || "/admin");

      function applyChrome() {
        if (state.themeChoice !== "system" && !VALID_THEMES.includes(state.themeChoice)) state.themeChoice = "system";
        state.theme = state.themeChoice === "system" ? systemTheme() : state.themeChoice;
        if (state.session && ROLE_META[state.session.role]) {
          state.role = state.session.role;
        }
        if (!ROLE_META[state.role]) state.role = "ssra_admin";
        if (!["always-open", "hover"].includes(state.railMode)) state.railMode = "always-open";

        document.documentElement.setAttribute("data-theme", state.theme);
        document.documentElement.setAttribute("data-rail-mode", state.railMode);
        const themeColorMeta = document.getElementById("ops-theme-color");
        if (themeColorMeta) {
          themeColorMeta.setAttribute("content", THEME_COLORS[state.theme]);
        }
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
        const roleMeta = ROLE_META[state.role] || ROLE_META.ssra_admin;
        const acctInitialsEl = document.getElementById("acct-initials");
        const acctNameEl = document.getElementById("acct-display-name");
        const acctRoleEl = document.getElementById("acct-role-label");
        if (state.session) {
          if (acctInitialsEl) acctInitialsEl.textContent = state.session.initials || roleMeta.initials;
          if (acctNameEl) acctNameEl.textContent = state.session.displayName + " (" + state.session.email + ")";
          if (acctRoleEl) acctRoleEl.textContent = state.session.roleLabel + " · " + state.session.officeCode;
          acctTrigger?.setAttribute("aria-label", "Signed in as " + state.session.displayName + " (" + state.session.roleLabel + ")");
        } else {
          if (acctInitialsEl) acctInitialsEl.textContent = roleMeta.initials;
          if (acctNameEl) acctNameEl.textContent = roleMeta.name;
          if (acctRoleEl) acctRoleEl.textContent = roleMeta.label;
          acctTrigger?.setAttribute("aria-label", "Preview persona menu; not signed in");
        }
        const presencePillEl = document.getElementById("ops-presence-pill");
        const presenceTextEl = document.getElementById("ops-presence-text");
        const presenceIconEl = document.getElementById("ops-presence-icon");
        const presenceNoteEl = document.getElementById("ops-presence-note");
        const barSignInEl = document.getElementById("call-bar-signin-link");
        const barSignUpEl = document.getElementById("call-bar-signup-link");
        const barSignOutBtn = document.getElementById("ops-signout-btn");
        if (state.session) {
          if (presencePillEl) {
            presencePillEl.classList.add("is-authenticated");
            presencePillEl.setAttribute("data-testid", "authenticated-session-pill");
          }
          if (presenceIconEl) setSafeHtml(presenceIconEl, ICONS.shieldCheck);
          if (presenceTextEl) {
            presenceTextEl.textContent =
              "Signed in · " +
              state.session.displayName +
              " (" +
              state.session.roleLabel +
              " · " +
              state.session.officeCode +
              ")";
          }
          if (presenceNoteEl) {
            presenceNoteEl.textContent =
              state.session.role === "ssra_auditor"
                ? "Read-only Separation of Duties (ISO/IEC 42001 Clause 9.2) · ILLUSTRATIVE_FALLBACK telemetry"
                : "Reference console workbench active · ILLUSTRATIVE_FALLBACK telemetry";
          }
          barSignInEl?.classList.add("is-hidden");
          barSignUpEl?.classList.add("is-hidden");
          barSignOutBtn?.classList.remove("is-hidden");
        } else {
          if (presencePillEl) {
            presencePillEl.classList.remove("is-authenticated");
            presencePillEl.removeAttribute("data-testid");
          }
          if (presenceIconEl) setSafeHtml(presenceIconEl, ICONS.eye);
          if (presenceTextEl) presenceTextEl.textContent = "Preview only · no authenticated staff session";
          if (presenceNoteEl) {
            presenceNoteEl.textContent = "No live calls, taxpayer records, or service telemetry are shown.";
          }
          barSignInEl?.classList.remove("is-hidden");
          barSignUpEl?.classList.remove("is-hidden");
          barSignOutBtn?.classList.add("is-hidden");
        }
        document.querySelectorAll("[data-set-theme]").forEach((btn) => {
          const isSelected = btn.getAttribute("data-set-theme") === state.themeChoice;
          btn.setAttribute("aria-checked", String(isSelected));
          btn.classList.toggle("active", isSelected);
        });

        const nextRailKey = state.role + "|" + state.route;
        const groups = ["Work", "Audit", "Configure", "Observe"];
        if (railGroupsEl && lastRenderedRailKey !== nextRailKey) {
          lastRenderedRailKey = nextRailKey;
          setSafeHtml(
            railGroupsEl,
            groups.map((group) => {
              const destinations = DESTINATIONS.filter((item) => item.group === group && item.roles.includes(state.role));
              if (!destinations.length) return "";
              const groupId = "rail-group-" + group.toLowerCase();
              return '<div class="staff-rail-group">' +
                '<p class="staff-rail-group-label" id="' + escapeHtml(groupId) + '">' + escapeHtml(group) + "</p>" +
                '<ul aria-labelledby="' + escapeHtml(groupId) + '">' + destinations.map((item) => {
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

      function renderSparklineSvg(points) {
        if (!Array.isArray(points) || points.length < 2) return "";
        const min = Math.min(...points);
        const max = Math.max(...points);
        const span = max - min || 1;
        const w = 160;
        const h = 36;
        const coords = points.map((p, i) => {
          const x = ((i / (points.length - 1)) * w).toFixed(1);
          const y = (h - 4 - ((p - min) / span) * (h - 10)).toFixed(1);
          return x + "," + y;
        });
        return '<svg class="ops-sparkline" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none" aria-hidden="true">' +
          '<polygon fill="currentColor" fill-opacity="0.08" stroke="none" points="0,' + h + " " + coords.join(" ") + " " + w + "," + h + '" />' +
          '<polyline fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" points="' + coords.join(" ") + '" />' +
        "</svg>";
      }

      function renderStatCard({ label, figure, unit, deltaText, deltaGood, hint, sparkline, href }) {
        const tag = href ? "a" : "div";
        const hrefAttr = href ? ' href="' + escapeHtml(href) + '" data-nav="' + escapeHtml(href) + '"' : "";
        const deltaCls = deltaGood === true ? " is-good" : deltaGood === false ? " is-bad" : "";
        const trendIcon = /^[+][0-9]/.test(deltaText || "") ? ICONS.trendUp : /^-[0-9]/.test(deltaText || "") ? ICONS.trendDown : "";
        return "<" + tag + ' class="ops-stat"' + hrefAttr + ">" +
          '<span class="ops-stat-label"><span>' + escapeHtml(label) + "</span>" +
            (href ? '<span class="ops-stat-go" aria-hidden="true">' + ICONS.arrowUpRight + "</span>" : "") +
          "</span>" +
          '<span class="ops-stat-row">' +
            '<strong class="ops-stat-value">' + escapeHtml(figure) + (unit ? '<span class="ops-stat-unit"> ' + escapeHtml(unit) + "</span>" : "") + "</strong>" +
            (deltaText ? '<span class="ops-delta' + deltaCls + '">' + trendIcon + escapeHtml(deltaText) + "</span>" : "") +
          "</span>" +
          (hint ? '<span class="ops-stat-hint">' + escapeHtml(hint) + "</span>" : "") +
          (sparkline ? renderSparklineSvg(sparkline) : "") +
        "</" + tag + ">";
      }

      function renderAuthenticatedPageHeader(eyebrow, title, desc) {
        const sess = state.session;
        const roleBadge = state.role === "ssra_auditor"
          ? '<span class="ops-chip info">' + ICONS.lock + " Auditor read-only · Separation of Duties</span>"
          : '<span class="ops-chip good">' + ICONS.shieldCheck + " Verified session · " + escapeHtml(sess?.email || state.role) + "</span>";
        return '<header class="ops-page-head">' +
          "<div>" +
            '<span id="preview-eyebrow" class="ops-eyebrow">' + escapeHtml(eyebrow) + "</span>" +
            '<h1 id="preview-title">' + escapeHtml(title) + "</h1>" +
            '<p id="preview-desc" class="ops-page-desc">' + escapeHtml(desc) + "</p>" +
          "</div>" +
          '<div class="ops-page-actions">' +
            roleBadge +
            '<div class="ops-segmented" role="group" aria-label="Comparison window">' +
              [7, 30, 90].map((d) =>
                '<button type="button" class="ops-seg-btn' + (state.periodDays === d ? " active" : "") + '" aria-pressed="' + (state.periodDays === d) + '" data-period="' + d + '">' + d + "d</button>"
              ).join("") +
            "</div>" +
          "</div>" +
        "</header>";
      }

      function renderRouteSpecSection(routePath) {
        const spec = ROUTE_SPECS[routePath] || ROUTE_SPECS["/admin"];
        return '<section id="route-spec-panel" class="ops-panel is-bare ops-panel-mt" aria-labelledby="g-h">' +
          '<div class="ops-panel-head">' +
            '<h2 id="g-h">Route governance &amp; specification</h2>' +
            '<div class="ops-panel-end"><span class="ops-chip is-info">Keycloak RBAC</span></div>' +
          "</div>" +
          '<div class="ops-panel-body">' +
            '<dl class="ov-kv">' +
              '<div><dt>Permitted roles</dt><dd id="spec-roles">' + escapeHtml(spec.roles) + "</dd></div>" +
              '<div><dt>Standard anchor</dt><dd id="spec-standard">' + escapeHtml(spec.standard) + "</dd></div>" +
              '<div><dt>Workbench surface</dt><dd id="spec-surface">' + escapeHtml(spec.surface) + "</dd></div>" +
              '<div><dt>Fail-closed gate</dt><dd id="spec-gate">' + escapeHtml(spec.gate) + "</dd></div>" +
            "</dl>" +
          "</div>" +
        "</section>";
      }

      function renderAuthenticatedDashboard(routePath, title, group) {
        if (routePath === "/agent" || routePath === "/admin/tickets") {
          const tickets = [
            {
              id: "TIC-8F3A19C0",
              priority: "URGENT",
              priCls: "bad",
              wait: "12m · ok",
              locale: "din · Voice/Chat",
              subject: "Deng Trading Co. (TIN ••••5678)",
              title: "Goods held at Nimule border & overdue BPT balance reconciliation",
              eq: "anxious_distressed -> calm_reassuring",
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
              eq: "frustrated -> empathetic_deescalation",
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
          return renderAuthenticatedPageHeader(
            group + " · Omnichannel Agent Queue & Copilot",
            title,
            "One case at a time: inspect taxpayer context, affective EQ telemetry, and statutory citations before approving or editing the AI-drafted reply.",
          ) +
          '<div class="ov-cols">' +
            '<section class="ops-panel" aria-label="Escalated ticket queue">' +
              '<div class="ops-panel-head"><h2>Active Escalations (3)</h2><span class="ops-meta-xs">Hotkeys: j/k move · r reply</span></div>' +
              '<div class="ops-panel-body">' +
                '<ul class="ov-review-list">' +
                  tickets.map((t, idx) =>
                    '<li class="ov-review-item is-clickable' + (idx === state.selectedTicketIdx ? " is-selected" : "") + '" data-ticket-idx="' + idx + '">' +
                      '<div class="ov-review-top">' +
                        '<span class="ops-chip ' + t.priCls + '">' + escapeHtml(t.priority) + " · " + escapeHtml(t.id) + "</span>" +
                        '<span class="ops-chip">' + escapeHtml(t.wait) + "</span>" +
                      "</div>" +
                      '<div class="ops-ticket-title">' + escapeHtml(t.title) + "</div>" +
                      '<div class="ops-meta-xs">' + escapeHtml(t.subject) + " · " + escapeHtml(t.locale) + "</div>" +
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
                '<div class="ops-msg-box">' +
                  '<div class="ops-msg-head">Taxpayer message · ' + escapeHtml(active.locale) + "</div>" +
                  '<div class="ops-msg-body">' + escapeHtml(active.userMsg) + "</div>" +
                "</div>" +
                '<div class="ops-draft-wrap">' +
                  '<label for="copilot-draft-box" class="ops-draft-label">' + ICONS.sparkles + " AI Copilot cited draft (Principle 1 verified)</label>" +
                  '<textarea id="copilot-draft-box" rows="5" class="ops-draft-textarea">' + escapeHtml(active.draftReply) + "</textarea>" +
                "</div>" +
                '<div class="ops-chips-row">' +
                  active.citations.map((c) => '<span class="ops-chip good">' + ICONS.bookOpen + " " + escapeHtml(c) + " (2026.10.1)</span>").join("") +
                "</div>" +
                (isAuditor
                  ? '<div class="ops-chip warn" data-testid="auditor-readonly-notice">' + ICONS.lock + " Auditor Role (ssra_auditor) is strictly read-only and cannot send taxpayer replies (Separation of Duties).</div>"
                  : '<div class="ops-actions-row">' +
                      '<button type="button" class="ops-btn gold" id="approve-send-btn" data-testid="approve-send-btn">' + ICONS.check + " Approve &amp; Send Cited Reply</button>" +
                      '<button type="button" class="ops-btn" id="maker-checker-btn" data-testid="maker-checker-btn">' + ICONS.shieldCheck + " Sign T3 Maker-Checker Approval</button>" +
                    "</div>"
                ) +
                '<div id="agent-action-status" class="ops-status-msg" role="status" aria-live="polite"></div>' +
              "</div>" +
            "</section>" +
          "</div>" +
          renderRouteSpecSection(routePath);
        }

        if (routePath === "/calls") {
          return renderAuthenticatedPageHeader(
            group + " · Officer Call Desk & G122 Carryover",
            title,
            "Monitor live toll-free voice sessions (Whisper-SALT + Orpheus-3B TTS), inspect pre-call chat carryover briefs, and take over transferred calls.",
          ) +
          '<div class="ops-stat-grid cols-4">' +
            renderStatCard({ label: "Waiting for Officer", figure: "1", unit: "caller", deltaText: "0m 42s wait", deltaGood: true, hint: "Dinka (din) · Nimule Customs" }) +
            renderStatCard({ label: "Voice Sessions Active", figure: "2", unit: "calls", deltaText: "Streaming", deltaGood: true, hint: "Juba Arabic (pga) & English (en)" }) +
            renderStatCard({ label: "ASR Word Error Rate", figure: "8.4", unit: "%", deltaText: "<= 12% gate", deltaGood: true, hint: "Whisper-large-v3-turbo + SunflowerASR" }) +
            renderStatCard({ label: "TTS Phrase Cache Hit", figure: "91.5", unit: "%", deltaText: "+4.0%", deltaGood: true, hint: "Orpheus-3B-TTS magic-byte verified" }) +
          "</div>" +
          '<div class="ov-cols">' +
            '<section class="ops-panel" aria-label="4-section call desk queue">' +
              '<div class="ops-panel-head"><h2>Call Desk Queue (4 Sections)</h2><span class="ops-chip good">VAD Barge-In Active</span></div>' +
              '<div class="ops-panel-body">' +
                '<table class="ops-table"><thead><tr><th>Section</th><th>Caller / Locale</th><th>Topic &amp; Carryover</th><th>State</th></tr></thead><tbody>' +
                  '<tr><td><strong>1. Waiting Transfer</strong></td><td>+211 •••• 4412 (<code>din</code>)</td><td>Customs valuation at Nimule (from Web Chat)</td><td><span class="ops-chip warn">Ringing Desk 4</span></td></tr>' +
                  '<tr><td><strong>2. Active Officer</strong></td><td>+211 •••• 8801 (<code>en</code>)</td><td>TIN Registration biometric appointment</td><td><span class="ops-chip info">03:18 · Deng M.</span></td></tr>' +
                  '<tr><td><strong>3. Automated Voice</strong></td><td>+211 •••• 1920 (<code>pga</code>)</td><td>PAYE monthly salary calculation (250k SSP)</td><td><span class="ops-chip good">Answering</span></td></tr>' +
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
                '<div class="ops-actions-row-mt">' +
                  (state.role === "ssra_auditor"
                    ? '<span class="ops-chip warn" data-testid="auditor-readonly-notice">' + ICONS.lock + " Auditor Read-Only: Live audio takeover disabled</span>"
                    : '<button type="button" class="ops-btn gold" id="takeover-call-btn" data-testid="takeover-call-btn">' + ICONS.phone + " Take Over Audio Stream</button>"
                  ) +
                  '<a href="' + escapeHtml(PUBLIC_ASSISTANT_URL) + '" class="ops-btn">Open Taxpayer Voice Modal ' + ICONS.arrowUpRight + "</a>" +
                "</div>" +
                '<div id="call-action-status" class="ops-status-msg" role="status" aria-live="polite"></div>' +
              "</div>" +
            "</section>" +
          "</div>" +
          renderRouteSpecSection(routePath);
        }

        if (routePath === "/analytics" || routePath === "/analytics/evaluation") {
          return renderAuthenticatedPageHeader(
            group + " · Production Analytics & CX Scorecard",
            title,
            "Plain-language observability across all 8 South Sudan languages (en, pga, ar, din, nus, bfa, zne, shk) with explicit telemetry provenance (LIVE_TELEMETRY vs CI_VERIFIED_TARGET).",
          ) +
          '<div class="ops-stat-grid cols-3">' +
            renderStatCard({
              label: "Quality-Adjusted Resolution",
              figure: "91.0",
              unit: "%",
              deltaText: "ILLUSTRATIVE_FALLBACK",
              hint: "Grounded resolution with verified citations & zero user re-asks",
              sparkline: [85, 87, 88.5, 89.2, 90.4, 91.0],
            }) +
            renderStatCard({
              label: "Zero Fabricated Tax Figures",
              figure: "100",
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
              figure: "26.8",
              unit: "KB",
              deltaText: "Target <= 120 KB",
              deltaGood: true,
              hint: "CI_VERIFIED_TARGET · WCAG 2.2 AA & 2G low-bandwidth budget",
              sparkline: [32, 30, 29, 28, 27, 26.8],
            }) +
          "</div>" +
          '<section class="ops-panel" aria-label="South Sudan 8-language parity and evaluation matrix">' +
            '<div class="ops-panel-head"><h2>South Sudan 8-Language Parity &amp; Benchmark Verification (600-Item Golden Suite)</h2><span class="ops-chip good">600 / 600 Passed</span></div>' +
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
          "</section>" +
          renderRouteSpecSection(routePath);
        }

        if (
          routePath === "/admin/flags" ||
          routePath === "/admin/overrides" ||
          routePath === "/admin/discrepancies" ||
          routePath === "/admin/outbox" ||
          routePath === "/admin/connectors"
        ) {
          return renderAuthenticatedPageHeader(
            group + " · Control Plane, Flags, Knowledge Release & MCP Connectors",
            title,
            "Manage runtime degradation switches, inspect the 6-step immutable KnowledgeSnapshot release pipeline, and verify all 11 governed MCP servers.",
          ) +
          '<div class="ov-cols">' +
            '<section class="ops-panel is-glass" aria-label="Feature flags and degradation ladder">' +
              '<div class="ops-panel-head"><h2>Degradation Ladder (L1–L5) &amp; Feature Flags</h2><span class="ops-chip info">Replica-Synced</span></div>' +
              '<div class="ops-panel-body">' +
                '<div class="ops-degrade-bar">' +
                  '<span class="ops-degrade-label">Active SecOps Degradation Level: <code>L' + escapeHtml(state.degradationLevel) + "</code></span>" +
                  (state.role !== "ssra_admin"
                    ? '<span class="ops-chip" data-testid="auditor-readonly-notice">L' + escapeHtml(state.degradationLevel) + " (Read-Only)</span>"
                    : '<div class="ops-segmented" role="group" aria-label="Select degradation level">' +
                        [1, 2, 3, 4, 5].map((lvl) =>
                          '<button type="button" class="ops-seg-btn' + (state.degradationLevel === lvl ? " active" : "") + '" aria-pressed="' + (state.degradationLevel === lvl) + '" data-set-degrade="' + lvl + '">L' + lvl + "</button>"
                        ).join("") +
                      "</div>"
                  ) +
                "</div>" +
                '<table class="ops-table"><thead><tr><th>Flag Key</th><th>Purpose</th><th>State</th></tr></thead><tbody>' +
                  Object.entries(state.flagOverrides).map(([k, v]) =>
                    "<tr><td><code>" + escapeHtml(k) + "</code></td><td>Runtime safety / capability toggle</td>" +
                    "<td>" +
                    (state.role !== "ssra_admin"
                      ? '<span class="ops-chip">' + (v ? "ON (Read-Only)" : "OFF (Read-Only)") + "</span>"
                      : '<button type="button" class="ops-btn' + (v ? " gold" : "") + '" aria-pressed="' + v + '" data-toggle-flag="' + escapeHtml(k) + '">' + (v ? "ON (Enabled)" : "OFF (Disabled)") + "</button>"
                    ) +
                    "</td></tr>"
                  ).join("") +
                "</tbody></table>" +
              "</div>" +
            "</section>" +
            '<section class="ops-panel" aria-label="6-step knowledge release pipeline">' +
              '<div class="ops-panel-head"><h2>6-Step KnowledgeSnapshot Release Pipeline</h2><span class="ops-chip good">2026.10.1 PUBLISHED</span></div>' +
              '<div class="ops-panel-body">' +
                '<ol class="ops-release-steps">' +
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
          '<section class="ops-panel ops-panel-mt" aria-label="11 MCP servers health">' +
            '<div class="ops-panel-head"><h2>11 Governed MCP Servers (Streamable HTTP 2026-07-28 via agentgateway)</h2><span class="ops-chip good">11 / 11 Healthy</span></div>' +
            '<div class="ops-panel-body">' +
              '<table class="ops-table"><thead><tr><th>MCP Server</th><th>Risk Tier Scope</th><th>Auth &amp; Subject Binding</th><th>Status</th></tr></thead><tbody>' +
                '<tr><td><code>mcp-tax-facts</code> / <code>mcp-knowledge</code> / <code>mcp-official-channels</code></td><td>Tier T0 (Public Deterministic)</td><td>Snapshot <code>2026.10.1</code></td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                '<tr><td><code>mcp-taxpayer</code> / <code>mcp-ledger</code> / <code>mcp-payments-info</code> / <code>mcp-customs</code></td><td>Tier T1 / T2 (TIN-Bound)</td><td>RFC 8693 + DPoP <code>subject_ref</code></td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                '<tr><td><code>mcp-tcc</code> / <code>mcp-cases</code> / <code>mcp-appointments</code> / <code>mcp-notifications</code></td><td>Tier T1–T3 (Governed)</td><td>OPA Policy Gate + WORM Audit</td><td><span class="ops-chip good">Healthy</span></td></tr>' +
              "</tbody></table>" +
            "</div>" +
          "</section>" +
          renderRouteSpecSection(routePath);
        }

        if (routePath === "/admin/audit" || routePath === "/admin/replay") {
          return renderAuthenticatedPageHeader(
            group + " · WORM Audit Trail & Forensic Turn Replay",
            title,
            "Tamper-evident SHA-256 hash chain of every administrative change, tool invocation, and Presidio-redacted conversation turn.",
          ) +
          '<div class="ops-stat-grid cols-3">' +
            renderStatCard({ label: "WORM Hash Chain Seal", figure: "VERIFIED", unit: "", deltaText: "0 tampered", deltaGood: true, hint: "PostgreSQL 18 WORM audit partition + SHA-256 chain" }) +
            renderStatCard({ label: "PII Redaction Gate", figure: "100", unit: "%", deltaText: "Presidio Active", deltaGood: true, hint: "TINs, phones & national IDs masked before log/index" }) +
            renderStatCard({ label: "OPA Policy Gate Decisions", figure: "100", unit: "%", deltaText: "Zero bypasses", deltaGood: true, hint: "Dual enforcement in agent-runtime & agentgateway" }) +
          "</div>" +
          '<section class="ops-panel is-glass" aria-label="Forensic turn replay and audit entries">' +
            '<div class="ops-panel-head"><h2>Turn-by-Turn Forensic Replay &amp; Audit Ledger (Head Digest: <code>8f2b1290a5…</code>)</h2><span class="ops-chip good">SHA-256 Chain Intact</span></div>' +
            '<div class="ops-panel-body">' +
              '<table class="ops-table"><thead><tr><th>Timestamp (CAT)</th><th>Actor / Thread</th><th>Stage / Action</th><th>Provenance &amp; Policy Verdict</th></tr></thead><tbody>' +
                '<tr><td><code>2026-10-28 08:40:12</code></td><td><code>thr_web_paye_01</code></td><td>1. Ingress &amp; Presidio Redaction</td><td><span class="ops-chip good">PII Masked · Locale: en</span></td></tr>' +
                '<tr><td><code>2026-10-28 08:40:12</code></td><td><code>deterministic_router</code></td><td>2. Statutory PAYE Calculator (250,000 SSP)</td><td><span class="ops-chip good">Tier T0 · Tool: calculate_paye</span></td></tr>' +
                '<tr><td><code>2026-10-28 08:40:12</code></td><td><code>numeric_provenance</code></td><td>3. Output Guardrail &amp; Citation Check</td><td><span class="ops-chip good">PASS · ssra-fin-act-2025-2026:sec-14-paye</span></td></tr>' +
                '<tr><td><code>2026-10-28 08:38:04</code></td><td><code>sub_taxpayer_amina_01</code></td><td>4. Compound T1-to-T2 Confirmation Token</td><td><span class="ops-chip info">HMAC Bound · create_support_ticket</span></td></tr>' +
              "</tbody></table>" +
            "</div>" +
          "</section>" +
          renderRouteSpecSection(routePath);
        }

        const isQuality = routePath === "/admin/quality";
        return renderAuthenticatedPageHeader(
          group + (isQuality ? " · Service Quality Audit" : " · Operations Overview"),
          title,
          isQuality
            ? "Where answers went wrong or triggered escalation across AI chat, voice sessions, and officer handoffs."
            : "How each of the four service streams was rated, what is waiting in the Needs Review queue, who is on duty at Juba HQ, and whether the KnowledgeSnapshot authority manifest is fresh.",
        ) +
        '<div class="ops-stat-grid cols-3">' +
          renderStatCard({
            label: "AI Answers in Chat (CSAT)",
            figure: "4.8/5",
            unit: "",
            deltaText: "+3.4%",
            deltaGood: true,
            hint: "94.2% satisfied (4 or 5) across en, pga, ar, din · vs previous " + state.periodDays + "d",
            sparkline: [88, 90, 91, 92, 93, 94.2],
            href: "/admin/quality",
          }) +
          renderStatCard({
            label: "AI on Phone Calls",
            figure: "84.0",
            unit: "%",
            deltaText: "+2.8%",
            deltaGood: true,
            hint: "Resolved by Whisper-SALT + Orpheus-3B TTS without transfer",
            sparkline: [78, 80, 81, 82.5, 83.4, 84.0],
            href: "/calls",
          }) +
          renderStatCard({
            label: "Officer Chats & SLA",
            figure: "98.6",
            unit: "%",
            deltaText: "+1.1%",
            deltaGood: true,
            hint: "Median first officer response: 4m 12s (target <= 15m)",
            sparkline: [96, 97, 97.5, 98, 98.2, 98.6],
            href: "/agent",
          }) +
          renderStatCard({
            label: "Numeric Provenance Gate",
            figure: "100",
            unit: "%",
            deltaText: "100%",
            deltaGood: true,
            hint: "Zero unverified SSP tax rates, thresholds, or balances emitted",
            sparkline: [100, 100, 100, 100, 100, 100],
            href: "/analytics/evaluation",
          }) +
          renderStatCard({
            label: "GPU Turn Latency (p50)",
            figure: "4.2",
            unit: " milliseconds",
            deltaText: "-92%",
            deltaGood: true,
            hint: "13.2x fast-path graph execution · Sovereign vLLM GPU cluster",
            sparkline: [55, 24, 12, 6, 4.5, 4.2],
            href: "/analytics",
          }) +
          renderStatCard({
            label: "Qdrant Episodic Memory",
            figure: "128",
            unit: "vectors",
            deltaText: "Active",
            deltaGood: true,
            hint: "Collection ssra_episodic_memory_v1 (384-d cosine, GDPR erasure ready)",
            sparkline: [16, 32, 64, 88, 112, 128],
            href: "/admin/connectors",
          }) +
        "</div>" +
        '<div class="ov-cols">' +
          '<div class="ov-side">' +
            '<section class="ops-panel is-bare" aria-label="Needs review queue">' +
              '<div class="ops-panel-head"><h2>Needs review (3 open)</h2><a href="/agent" data-nav="/agent" class="ops-btn">Open Agent Queue</a></div>' +
              '<div class="ops-panel-body">' +
                '<ul class="ov-review-list">' +
                  '<li class="ov-review-item"><div class="ov-review-top"><span class="ops-chip warn">Voice · Dinka (din)</span><span class="ops-meta-xs">12m ago · TIC-8F3A19C0</span></div><a href="/calls" data-nav="/calls" class="ops-review-link">Nimule border customs valuation dispute &amp; urgent release</a><p class="ops-review-quote">Asked: <q>My goods are held at Nimule border and e-Tax is showing pending assessment</q></p></li>' +
                  '<li class="ov-review-item"><div class="ov-review-top"><span class="ops-chip info">Chat · Juba Arabic (pga)</span><span class="ops-meta-xs">28m ago · TIC-4C91B20E</span></div><a href="/agent" data-nav="/agent" class="ops-review-link">T4 Penalty Waiver Request — routed to human officer per risk-tiers.yaml</a><p class="ops-review-quote">Asked: <q>Please waive my late filing penalty for Q3 Business Profits Tax</q></p></li>' +
                  '<li class="ov-review-item"><div class="ov-review-top"><span class="ops-chip good">Officer chat · Maker-Checker T3</span><span class="ops-meta-xs">41m ago · TIC-7E22D91A</span></div><a href="/agent" data-nav="/agent" class="ops-review-link">TCC Revival &amp; Ledger Adjustment awaiting second officer approval</a><p class="ops-review-quote">Maker: Officer Deng M. · Citations attached: <code>ssra-tcc-guide-2026:sec-4</code></p></li>' +
                "</ul>" +
              "</div>" +
            "</section>" +
            '<section class="ops-panel" aria-label="Sovereign GPU and Local HF Cache Stack">' +
              '<div class="ops-panel-head"><h2>Sovereign GPU &amp; Local HF Cache Topology</h2><span class="ops-chip good">All Nodes Healthy</span></div>' +
              '<div class="ops-panel-body">' +
                '<table class="ops-table"><thead><tr><th>Component</th><th>Model / Engine</th><th>Status</th></tr></thead><tbody>' +
                  '<tr><td>Primary LLM (:8011)</td><td><code>Sunbird/Sunflower-Qwen3.5-9B</code> (vLLM GPU)</td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                  '<tr><td>Reasoner LLM (:8012)</td><td><code>Qwen/Qwen3.8-27B-FP8</code> (vLLM GPU)</td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                  '<tr><td>Multilingual TTS (:18100)</td><td><code>Sunbird/orpheus-3b-tts-multilingual</code> (GPU)</td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                  '<tr><td>Agent Runtime (:18001)</td><td><code>ssra-agent-runtime</code> + Whisper-SALT (GPU)</td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                  '<tr><td>Episodic Vector DB (:26333)</td><td><code>Qdrant v1.19.0</code> (<code>ssra_episodic_memory_v1</code>)</td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                  '<tr><td>Core DB &amp; Cache</td><td><code>PostgreSQL 18</code> + <code>Valkey 8</code></td><td><span class="ops-chip good">Healthy</span></td></tr>' +
                "</tbody></table>" +
              "</div>" +
            "</section>" +
          "</div>" +
          '<div class="ov-side">' +
            '<section class="ops-panel is-bare" aria-label="Officers on duty">' +
              '<div class="ops-panel-head"><h2>Officers on duty (Juba HQ)</h2><span class="ops-chip good">4 active</span></div>' +
              '<div class="ops-panel-body">' +
                '<p class="ops-duty-lead"><strong>4 officers</strong> online across Domestic Taxes, Customs (Nimule/Juba), and e-Tax Helpdesk.</p>' +
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
                  '<div><dt>Statutory Sources Checked</dt><dd>16 / 16 valid (0 stale)</dd></div>' +
                  '<div><dt>Effective Tax Jurisdiction</dt><dd>South Sudan (Africa/Juba UTC+02:00)</dd></div>' +
                  '<div><dt>Cosign &amp; CycloneDX 1.6 ML-BOM</dt><dd><span class="ops-chip good">Verified</span></dd></div>' +
                "</dl>" +
              "</div>" +
            "</section>" +
            renderRouteSpecSection(routePath) +
          "</div>" +
        "</div>";
      }

      function randomHex(bytes = 32) {
        const buf = new Uint8Array(bytes);
        crypto.getRandomValues(buf);
        return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
      }

      async function computePkceChallenge(verifier) {
        const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
        return btoa(String.fromCharCode(...new Uint8Array(digest)))
          .replace(/\\+/g, "-")
          .replace(/\\//g, "_")
          .replace(/=+$/, "");
      }

      function buildSignInHtml() {
        return ${JSON.stringify(renderSignInCard(publicAssistantUrl))};
      }
      function buildSignUpHtml() {
        return ${JSON.stringify(renderSignUpCard(publicAssistantUrl))};
      }
      function buildCallbackHtml() {
        return ${JSON.stringify(renderSignInCallbackCard(publicAssistantUrl))};
      }
      function buildPreviewHtml(title, group) {
        return ${JSON.stringify(renderPreviewCard("__TITLE__", "__GROUP__"))}
          .replace(/__TITLE__/g, escapeHtml(title))
          .replace(/__GROUP__/g, escapeHtml(group));
      }

      function timingSafeEqualStr(a, b) {
        if (typeof a !== "string" || typeof b !== "string") return false;
        const len = Math.max(a.length, b.length);
        let diff = a.length ^ b.length;
        for (let i = 0; i < len; i++) {
          diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
        }
        return diff === 0;
      }

      let lastCallbackOutcome = null;

      // Only same-origin workspace paths are honoured as a post-sign-in destination.
      function readSafeNextPath() {
        try {
          const next = new URLSearchParams(window.location.search).get("next") || "";
          if (!next.startsWith("/") || next.startsWith("//") || !/^[A-Za-z0-9/_-]*$/.test(next)) return "";
          return ["signin", "signup", "api", "v1"].includes(next.split("/")[1] || "") ? "" : next;
        } catch {
          return "";
        }
      }

      function wireAuthViewInteractions() {
        if (!mainEl) return;
        if (!mainEl.hasAttribute("data-auth-wired")) {
          mainEl.setAttribute("data-auth-wired", "true");

          document.getElementById("console-signin-form")?.addEventListener("submit", (e) => {
            e.preventDefault();
            const emailInput = document.getElementById("signin-email-input");
            const pwInput = document.getElementById("signin-password-input");
            const bannerEl = document.getElementById("signin-status-banner");
            const rawId = (emailInput?.value || "").trim().toLowerCase();
            const rawPw = (pwInput?.value || "").trim();
            if (!rawId || !rawPw) {
              if (bannerEl) {
                bannerEl.classList.remove("is-hidden", "ok");
                bannerEl.classList.add("error");
                bannerEl.setAttribute("role", "alert");
                bannerEl.textContent = "Enter both your SSRA email/username and password to sign in.";
              }
              (rawId ? pwInput : emailInput)?.focus();
              return;
            }
            const account = ACCOUNT_DIRECTORY.find((item) => item.aliases.includes(rawId));
            const computedDigest = account ? sha256Hex("ssra-console-auth-v1:" + account.role + ":" + rawPw) : "";
            if (!account || !timingSafeEqualStr(computedDigest, account.digestSha256)) {
              if (bannerEl) {
                bannerEl.classList.remove("is-hidden", "ok");
                bannerEl.classList.add("error");
                bannerEl.setAttribute("role", "alert");
                bannerEl.textContent = "Invalid email/username or password. Please verify your SSRA account credentials.";
              }
              pwInput?.focus();
              return;
            }
            if (bannerEl) {
              bannerEl.classList.remove("is-hidden", "error");
              bannerEl.classList.add("ok");
              bannerEl.setAttribute("role", "status");
              bannerEl.textContent = "Authenticated as " + account.displayName + " (" + account.roleLabel + "). Opening " + account.landingPath + "…";
            }
            setAuthenticatedSession(account);
          });

          document.getElementById("console-signup-form")?.addEventListener("submit", (e) => {
            e.preventDefault();
            const nameVal = (document.getElementById("signup-name-input")?.value || "").trim();
            const emailVal = (document.getElementById("signup-email-input")?.value || "").trim().toLowerCase();
            const pwVal = (document.getElementById("signup-password-input")?.value || "").trim();
            const bannerEl = document.getElementById("signup-status-banner");
            if (!nameVal || !emailVal || pwVal.length < 8) {
              if (bannerEl) {
                bannerEl.classList.remove("is-hidden", "ok");
                bannerEl.classList.add("error");
                bannerEl.setAttribute("role", "alert");
                bannerEl.textContent = "Enter your full name, email address, and a password of at least 8 characters.";
              }
              return;
            }
            const customTaxpayer = {
              role: "verified_taxpayer",
              email: emailVal,
              username: emailVal.split("@")[0] || "taxpayer",
              displayName: nameVal,
              roleLabel: "Verified Taxpayer",
              staffId: "sub_taxpayer_" + randomHex(4),
              officeCode: "JUBA_HQ",
              initials: nameVal.slice(0, 2).toUpperCase(),
              landingPath: "/en",
            };
            setAuthenticatedSession(customTaxpayer);
          });

        const startKeycloakRedirect = async (mode, promptVal) => {
          const verifier = randomHex(32);
          const challenge = await computePkceChallenge(verifier);
          const csrfState = randomHex(32);
          const oidcNonce = randomHex(32);
          const returnTo = readSafeNextPath();
          lastCallbackOutcome = null;
          try {
            sessionStorage.setItem("ssra_pkce_verifier", verifier);
            sessionStorage.setItem("ssra_oidc_state", csrfState);
            sessionStorage.setItem("ssra_oidc_nonce", oidcNonce);
            if (returnTo) sessionStorage.setItem("ssra_oidc_return_to", returnTo);
            else sessionStorage.removeItem("ssra_oidc_return_to");
          } catch {}
          const authUrl = new URL("https://sso.ssra.gov.ss/realms/ssra/protocol/openid-connect/auth");
          authUrl.searchParams.set("response_type", "code");
          authUrl.searchParams.set("client_id", "ssra-staff-console");
          authUrl.searchParams.set("redirect_uri", window.location.origin + "/signin/callback");
          authUrl.searchParams.set("scope", "openid profile email");
          authUrl.searchParams.set("code_challenge", challenge);
          authUrl.searchParams.set("code_challenge_method", "S256");
          authUrl.searchParams.set("state", csrfState);
          authUrl.searchParams.set("nonce", oidcNonce);
          authUrl.searchParams.set("acr_values", "urn:ssra:acr:passkey");
          if (mode === "signup") {
            new URLSearchParams("prompt=create&screen_hint=signup").forEach((value, key) => authUrl.searchParams.set(key, value));
          } else if (promptVal) {
            authUrl.searchParams.set("prompt", promptVal);
          }
          // Single sign-on is not connected in this preview (OQ-005 / OQ-014): say so plainly and keep the prepared
          // request on the banner's data-auth-url.
          const bannerId = mode === "signup" ? "signup-status-banner" : "signin-status-banner";
          const bannerEl = document.getElementById(bannerId);
          if (bannerEl) {
            bannerEl.classList.remove("is-hidden", "error", "ok");
            bannerEl.classList.add("info");
            bannerEl.setAttribute("role", "status");
            bannerEl.setAttribute("data-auth-url", authUrl.toString());
            bannerEl.textContent =
              mode === "signup"
                ? "SSRA single sign-on isn't connected in this preview yet. Create your account with the form above."
                : "SSRA single sign-on isn't connected in this preview yet. Sign in with your email and password.";
          }
        };

        const runKeycloakRedirect = (mode, promptVal) => {
          startKeycloakRedirect(mode, promptVal).catch(() => {
            const bannerId = mode === "signup" ? "signup-status-banner" : "signin-status-banner";
            const bannerEl = document.getElementById(bannerId);
            if (!bannerEl) return;
            bannerEl.classList.remove("is-hidden", "ok", "info");
            bannerEl.classList.add("error");
            bannerEl.setAttribute("role", "alert");
            bannerEl.textContent =
              "Could not prepare the sign-in request. A secure (HTTPS) browser context is required for Web Crypto PKCE S256.";
          });
        };

          document.getElementById("keycloak-signin-btn")?.addEventListener("click", () => {
            runKeycloakRedirect("signin", undefined);
          });
          document.getElementById("keycloak-signup-btn")?.addEventListener("click", () => {
            runKeycloakRedirect("signup", undefined);
          });
        }

        if (state.route === "/signin/callback") {
          const cbBanner = document.getElementById("callback-status-banner");
          if (!lastCallbackOutcome) {
            const rawSearch = window.location.search;
            const params = new URLSearchParams(rawSearch);
            const err = params.get("error");
            const code = params.get("code");
            const st = params.get("state");
            const iss = params.get("iss");
            let expectedState = null;
            let verifier = null;
            try {
              expectedState = sessionStorage.getItem("ssra_oidc_state");
              verifier = sessionStorage.getItem("ssra_pkce_verifier");
              sessionStorage.removeItem("ssra_oidc_state");
              sessionStorage.removeItem("ssra_pkce_verifier");
              sessionStorage.removeItem("ssra_oidc_nonce");
            } catch {}
            if (rawSearch) {
              try {
                window.history.replaceState({}, "", "/signin/callback");
              } catch {}
            }
            const cleanIss = iss;
            const expectedIss = "https://sso.ssra.gov.ss/realms/ssra";
            if (err) {
              lastCallbackOutcome = {
                ok: false,
                text: err + ": " + (params.get("error_description") || "the identity provider refused the request"),
              };
            } else if (!code) {
              lastCallbackOutcome = {
                ok: false,
                text: "The identity provider returned no authorization code.",
              };
            } else if (!st || !expectedState || !timingSafeEqualStr(st, expectedState)) {
              lastCallbackOutcome = {
                ok: false,
                text: "State mismatch — this sign-in did not start in this browser tab. Start again from /signin.",
              };
            } else if (!cleanIss || !timingSafeEqualStr(cleanIss, expectedIss)) {
              lastCallbackOutcome = {
                ok: false,
                text: "Issuer mismatch (RFC 9207) — callback issuer does not match the configured SSRA Keycloak realm.",
              };
            } else if (!verifier || !/^[A-Za-z0-9._~-]{43,128}$/.test(verifier)) {
              lastCallbackOutcome = {
                ok: false,
                text: "The PKCE S256 code_verifier is missing. Start the sign-in again from /signin.",
              };
            } else {
              lastCallbackOutcome = {
                ok: true,
                text: "Keycloak PKCE S256 & CSRF state verified. Server-side token exchange requires live Keycloak connectivity (OQ-005 / OQ-014).",
              };
            }
          }
          if (cbBanner && lastCallbackOutcome) {
            cbBanner.classList.toggle("ok", lastCallbackOutcome.ok);
            cbBanner.classList.toggle("error", !lastCallbackOutcome.ok);
            cbBanner.setAttribute("role", lastCallbackOutcome.ok ? "status" : "alert");
            cbBanner.textContent = lastCallbackOutcome.text;
          }
        }
      }

      function renderCurrentRoute() {
        if (state.route !== "/signin/callback") {
          lastCallbackOutcome = null;
        }
        const isAuthRoute = state.route === "/signin" || state.route === "/signup" || state.route === "/signin/callback";
        if (!isAuthRoute) {
          const matchedDest = DESTINATIONS.find((destination) => destination.href === state.route);
          if (matchedDest && !matchedDest.roles.includes(state.role)) {
            state.route = ROLE_META[state.role]?.landing || "/admin";
            try {
              window.history.replaceState({}, "", state.route);
            } catch {}
          }
        }
        document.getElementById("ssra-staff-shell")?.setAttribute("data-layout", isAuthRoute ? "auth" : "app");
        applyChrome();
        if (!mainEl) return;
        mainEl.setAttribute("data-route", state.route);
        if (state.route === "/signin") {
          document.title = "Sign in — SSRA Assist";
          if (!document.getElementById("keycloak-signin-btn")) {
            setSafeHtml(mainEl, buildSignInHtml());
          }
          wireAuthViewInteractions();
          return;
        }
        if (state.route === "/signup") {
          document.title = "Create an account — SSRA Assist";
          if (!document.getElementById("keycloak-signup-btn")) {
            setSafeHtml(mainEl, buildSignUpHtml());
          }
          wireAuthViewInteractions();
          return;
        }
        if (state.route === "/signin/callback") {
          document.title = "Signing you in — SSRA Assist";
          if (!document.getElementById("callback-status-banner")) {
            setSafeHtml(mainEl, buildCallbackHtml());
          }
          wireAuthViewInteractions();
          return;
        }
        const route = DESTINATIONS.find((destination) => destination.href === state.route);
        const title = route?.label || "Operations overview";
        const group = route?.group || "Work";
        if (state.session) {
          document.title = "SSRA Operations Console — " + title;
          setSafeHtml(mainEl, renderAuthenticatedDashboard(state.route, title, group));
          return;
        }
        document.title = "SSRA Operations Console Preview — " + title;
        if (!document.getElementById("nr-h")) {
          setSafeHtml(mainEl, buildPreviewHtml(title, group));
        } else {
          const titleEl = document.getElementById("preview-title");
          if (titleEl) titleEl.textContent = title;
          const eyebrowEl = document.getElementById("preview-eyebrow");
          if (eyebrowEl) eyebrowEl.textContent = group + " · Preview only";
        }
        const spec = ROUTE_SPECS[state.route] || ROUTE_SPECS["/admin"];
        if (spec) {
          const rolesEl = document.getElementById("spec-roles");
          const stdEl = document.getElementById("spec-standard");
          const surfEl = document.getElementById("spec-surface");
          const gateEl = document.getElementById("spec-gate");
          if (rolesEl) rolesEl.textContent = spec.roles;
          if (stdEl) stdEl.textContent = spec.standard;
          if (surfEl) surfEl.textContent = spec.surface;
          if (gateEl) gateEl.textContent = spec.gate;
        }
      }

      function navigateTo(href) {
        if (!href) return;
        if (href === PUBLIC_ASSISTANT_URL || href === "/en" || href.startsWith("/en") || /^https?:\\/\\//i.test(href)) {
          window.location.assign(href === "/en" || href.startsWith("/en") ? PUBLIC_ASSISTANT_URL : href);
          return;
        }
        let targetPathname = href;
        let targetSearch = "";
        try {
          const parsedHref = new URL(href, window.location.origin);
          targetPathname = parsedHref.pathname || "/admin";
          targetSearch = parsedHref.search || "";
        } catch {}
        if (targetSearch) {
          lastCallbackOutcome = null;
        }
        state.route = targetPathname;
        try { window.history.pushState({}, "", targetPathname + targetSearch); } catch {}
        railEl?.classList.remove("is-drawer-open");
        document.getElementById("ops-mobile-backdrop")?.classList.remove("open");
        syncStaffRailA11y(false);
        renderCurrentRoute();
        window.scrollTo(0, 0);
        mainEl?.focus({ preventScroll: true });
      }

      window.addEventListener("popstate", () => {
        state.route = window.location.pathname || "/admin";
        renderCurrentRoute();
      });

      document.body.addEventListener("click", (e) => {
        const signOutTrigger = e.target.closest('[data-action="signout"]');
        if (signOutTrigger) {
          e.preventDefault();
          clearAuthenticatedSession();
          return;
        }
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
        if (degBtn && state.role === "ssra_admin") {
          state.degradationLevel = Number(degBtn.getAttribute("data-set-degrade")) || 1;
          renderCurrentRoute();
          return;
        }
        const flagBtn = e.target.closest("[data-toggle-flag]");
        if (flagBtn && state.role === "ssra_admin") {
          const k = flagBtn.getAttribute("data-toggle-flag");
          if (k) {
            state.flagOverrides[k] = !state.flagOverrides[k];
            renderCurrentRoute();
          }
          return;
        }
        if (e.target.closest("#approve-send-btn")) {
          const st = document.getElementById("agent-action-status");
          if (st) st.textContent = "Cited reply approved and dispatched to taxpayer with KnowledgeSnapshot 2026.10.1 provenance.";
          return;
        }
        if (e.target.closest("#maker-checker-btn")) {
          const st = document.getElementById("agent-action-status");
          if (st) st.textContent = "T3 Maker-Checker cryptographic countersignature recorded in WORM Audit Trail.";
          return;
        }
        if (e.target.closest("#takeover-call-btn")) {
          const st = document.getElementById("call-action-status");
          if (st) st.textContent = "Audio stream claimed by " + (state.session?.displayName || "Officer") + " — bridged to Desk 4.";
          return;
        }
      });

      // Rail pin toggle, mobile drawer & hover expand
      const mobileBackdrop = document.getElementById("ops-mobile-backdrop");
      const mobileNavBtn = document.getElementById("mobile-ops-nav-btn");
      const focusAfterStaffRailStateSync = (target) => {
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
      const syncStaffRailA11y = (moveFocus = false) => {
        const isMobile = window.matchMedia?.("(max-width: 820px)")?.matches ?? false;
        const isOpen = railEl?.classList.contains("is-drawer-open") ?? false;
        railEl?.toggleAttribute("inert", isMobile && !isOpen);
        mobileNavBtn?.setAttribute("aria-expanded", String(isMobile && isOpen));
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

      // AccountMenu (APG menu button): arrow keys move, Escape closes and returns focus.
      const menuItems = () => Array.from(acctMenu?.querySelectorAll('[role^="menuitem"]') || []);
      function openAcctMenu() {
        acctMenu?.classList.add("open");
        acctTrigger?.setAttribute("aria-expanded", "true");
        menuItems()[0]?.focus();
      }
      function closeAcctMenu(returnFocus) {
        if (!acctMenu?.classList.contains("open")) return;
        acctMenu.classList.remove("open");
        acctTrigger?.setAttribute("aria-expanded", "false");
        if (returnFocus) acctTrigger?.focus();
        applyChrome();
      }
      function setPreviewPersona(role) {
        state.role = ROLE_META[role] ? role : "ssra_admin";
        writeUiPreference("ssra-ops-preview-persona", state.role);
        const isAuthRoute = state.route === "/signin" || state.route === "/signup" || state.route === "/signin/callback";
        const currentDest = DESTINATIONS.find((d) => d.href === state.route);
        if (!isAuthRoute && (!currentDest || !currentDest.roles.includes(state.role))) {
          state.route = ROLE_META[state.role]?.landing || "/admin";
          try { window.history.replaceState({}, "", state.route); } catch {}
        }
        renderCurrentRoute();
      }
      acctTrigger?.addEventListener("click", (e) => {
        e.stopPropagation();
        if (acctMenu?.classList.contains("open")) closeAcctMenu(false);
        else openAcctMenu();
      });
      acctTrigger?.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          openAcctMenu();
          if (e.key === "ArrowUp") menuItems().at(-1)?.focus();
        }
      });
      acctMenu?.addEventListener("keydown", (e) => {
        const items = menuItems();
        const current = items.indexOf(document.activeElement);
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          closeAcctMenu(true);
        } else if (e.key === "Tab") {
          closeAcctMenu(false);
        } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key) && items.length > 0) {
          e.preventDefault();
          const next = e.key === "Home" ? 0
            : e.key === "End" ? items.length - 1
              : (current + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
          items[next]?.focus();
        }
      });
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".staff-rail-foot")) closeAcctMenu(false);
      });
      acctMenu?.addEventListener("click", (e) => {
        const roleBtn = e.target.closest("[data-set-role]");
        if (roleBtn) {
          closeAcctMenu(true);
          setPreviewPersona(roleBtn.getAttribute("data-set-role"));
          return;
        }
        const themeBtn = e.target.closest("[data-set-theme]");
        if (themeBtn) {
          state.themeChoice = themeBtn.getAttribute("data-set-theme") || "system";
          writeThemeChoice(state.themeChoice);
          closeAcctMenu(true);
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
          { label: "Sign in — Keycloak 26 OIDC + Passkey (/signin)", hint: "Auth", run: () => navigateTo("/signin") },
          { label: "Create an account — Keycloak Registration (/signup)", hint: "Auth", run: () => navigateTo("/signup") },
          { label: "Open Taxpayer MainChat (/en)", hint: "Surface", run: () => window.location.assign(PUBLIC_ASSISTANT_URL) },
          { label: "Preview persona: Administrator", hint: "Preview", run: () => setPreviewPersona("ssra_admin") },
          { label: "Preview persona: Tax Agent", hint: "Preview", run: () => setPreviewPersona("ssra_staff") },
          { label: "Preview persona: Auditor", hint: "Preview", run: () => setPreviewPersona("ssra_auditor") },
          { label: "Cycle Theme (Dark / Light / High-Contrast)", hint: "Appearance", run: () => {
            state.themeChoice = state.theme === "dark" ? "light" : state.theme === "light" ? "high-contrast" : "dark";
            writeThemeChoice(state.themeChoice);
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
              '<li id="cmdk-opt-' + idx + '" class="ops-cmdk-item" role="option" aria-selected="' + (idx === cmdkActiveIdx) + '" data-cmd-idx="' + idx + '" data-active="' + (idx === cmdkActiveIdx) + '">' +
                "<span>" + escapeHtml(c.label) + "</span>" +
                '<span class="ops-kbd">' + escapeHtml(c.hint) + "</span>" +
              "</li>"
            ).join("")
          );
          cmdkList.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
        }
        if (cmds.length > 0) cmdkInput?.setAttribute("aria-activedescendant", "cmdk-opt-" + cmdkActiveIdx);
        else cmdkInput?.removeAttribute("aria-activedescendant");
        const countEl = document.getElementById("cmdk-count");
        if (countEl) countEl.textContent = cmds.length === 0 ? "No matching destinations" : cmds.length + (cmds.length === 1 ? " destination" : " destinations");
        return cmds;
      }

      function openCmdk() {
        closeAcctMenu(false);
        cmdkReturnFocusEl = document.activeElement;
        cmdkBackdrop?.classList.add("open");
        document.getElementById("ssra-staff-shell")?.setAttribute("inert", "");
        if (cmdkInput) {
          cmdkInput.value = "";
          cmdkActiveIdx = 0;
          renderCmdkList();
          cmdkInput.focus();
        }
      }
      function closeCmdk() {
        cmdkBackdrop?.classList.remove("open");
        document.getElementById("ssra-staff-shell")?.removeAttribute("inert");
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
          if (document.getElementById("ssra-staff-shell")?.getAttribute("data-layout") === "auth") return;
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
          else if (e.key === "Home" && cmds.length) { e.preventDefault(); cmdkActiveIdx = 0; renderCmdkList(); }
          else if (e.key === "End" && cmds.length) { e.preventDefault(); cmdkActiveIdx = cmds.length - 1; renderCmdkList(); }
          else if (e.key === "Enter" && cmds.length) { e.preventDefault(); closeCmdk(); cmds[cmdkActiveIdx]?.run(); }
          return;
        }
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        if (state.session && (state.route === "/agent" || state.route === "/admin/tickets")) {
          if (e.key === "j") { e.preventDefault(); state.selectedTicketIdx = (state.selectedTicketIdx + 1) % 3; renderCurrentRoute(); }
          else if (e.key === "k") { e.preventDefault(); state.selectedTicketIdx = (state.selectedTicketIdx + 2) % 3; renderCurrentRoute(); }
          else if (e.key === "r") { e.preventDefault(); document.getElementById("copilot-draft-box")?.focus(); }
        }
      });

      // Follow the device while "System" is chosen, and apply a theme picked on another page or tab.
      ["(prefers-color-scheme: light)", "(prefers-contrast: more)"].forEach((query) => {
        window.matchMedia?.(query)?.addEventListener?.("change", () => {
          if (state.themeChoice === "system") applyChrome();
        });
      });
      window.addEventListener("storage", (e) => {
        if (e.key !== THEME_STORAGE_KEY) return;
        state.themeChoice = VALID_THEMES.includes(e.newValue) ? e.newValue : "system";
        applyChrome();
      });

      renderCurrentRoute();
    })();
  </script>
</body>
</html>`;
  return compactOpsHtmlAssetBlocks(rawHtml);
}
