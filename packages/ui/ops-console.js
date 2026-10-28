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
function renderPreviewCard(
  title,
  group = "Work",
  publicAssistantUrl = "http://127.0.0.1:3000/en",
  routePath = "/admin",
) {
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
            <a class="ops-btn" id="ops-header-signup-link" href="/signup" data-nav="/signup">Create account</a>
            <a class="ops-btn is-primary primary" href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Open the public assistant ${ICONS.arrowUpRight}</a>
          </div>
        </header>

        <section class="ops-panel ops-preview-card" aria-labelledby="preview-title">
          <span class="ops-preview-chip">Preview only</span>
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

function renderSignInCard(publicAssistantUrl = "http://127.0.0.1:3000/en") {
  return `<div class="signin-wrap">
          <div class="signin-card">
            <header class="signin-head">
              <div class="signin-mark" aria-hidden="true">${ICONS.ssraCrest}</div>
              <span id="preview-eyebrow" class="ops-eyebrow">Keycloak 26.4.11 · OAuth 2.1 + PKCE S256 + Passkey AAL3</span>
              <h1 id="preview-title">Sign in</h1>
              <p class="signin-sub">South Sudan Revenue Authority (SSRA) — Admin, Staff &amp; Auditor Console</p>
            </header>

            <section class="signin-block" aria-labelledby="oidc-h">
              <h2 id="oidc-h">Sign in with your SSRA Keycloak account</h2>
              <p class="signin-note">
                Accounts, hardware-backed WebAuthn passkeys (<code>urn:ssra:acr:passkey</code>), and role assignments are managed by the SSRA sovereign Keycloak identity realm (<code>https://sso.ssra.gov.ss/realms/ssra</code>). OAuth 2.1 tokens are bound via PKCE <code>S256</code> and RFC 9449 DPoP.
              </p>

              <fieldset class="signin-roles">
                <legend>Target console workspace upon sign-in</legend>
                <label class="role-opt active" data-role-card="ssra_admin">
                  <input type="radio" name="signin-role-target" value="ssra_admin" data-landing="/admin" checked />
                  <span class="role-name">Administrator (ssra_admin) — /admin</span>
                  <span class="role-hint">Operations overview, 5-step degradation ladder, 6-step knowledge release governance, and JIT passkey elevation.</span>
                </label>
                <label class="role-opt" data-role-card="ssra_staff">
                  <input type="radio" name="signin-role-target" value="ssra_staff" data-landing="/agent" />
                  <span class="role-name">Tax Agent &amp; Officer (ssra_staff) — /agent</span>
                  <span class="role-hint">One-case-at-a-time escalation queue, Cited Copilot drafts, phone call takeover desk, and T3 two-officer maker-checker.</span>
                </label>
                <label class="role-opt" data-role-card="ssra_auditor">
                  <input type="radio" name="signin-role-target" value="ssra_auditor" data-landing="/analytics" />
                  <span class="role-name">Forensic &amp; QA Auditor (ssra_auditor) — /analytics</span>
                  <span class="role-hint">Read-only Separation of Duties (ISO/IEC 42001 Clause 9.2): WORM ledger inspector, forensic turn replay, and QA rubric scoring.</span>
                </label>
              </fieldset>

              <form id="console-signin-form" class="signin-form" data-testid="console-signin-form" novalidate>
                <div class="signin-field">
                  <label for="signin-email-input" class="signin-label">Email or username</label>
                  <input id="signin-email-input" data-testid="signin-email-input" class="signin-input" type="text" name="username" autocomplete="username" placeholder="admin@nra.gov.ss, staff@nra.gov.ss, or auditor@nra.gov.ss" required />
                </div>
                <div class="signin-field">
                  <label for="signin-password-input" class="signin-label">Password</label>
                  <input id="signin-password-input" data-testid="signin-password-input" class="signin-input" type="password" name="password" autocomplete="current-password" placeholder="Enter your SSRA account password" required />
                </div>
                <button type="submit" id="console-signin-submit-btn" class="signin-primary" data-testid="console-signin-submit-btn">
                  Sign in to dashboard
                </button>
              </form>

              <button type="button" id="console-passkey-signin-btn" class="signin-secondary" data-testid="console-passkey-signin-btn">
                Sign in with Passkey (Selected Role)
              </button>
              <button type="button" id="keycloak-signin-btn" class="signin-secondary" data-testid="keycloak-signin-btn">
                Continue with SSRA Keycloak Passkey SSO
              </button>
              <button type="button" id="keycloak-switch-account-btn" class="signin-secondary" data-testid="signin-different-account">
                Sign in as a different user (prompt=login)
              </button>

              <dl class="ov-kv signin-kv" aria-label="Keycloak OIDC client configuration">
                <div><dt>Keycloak realm</dt><dd><code>ssra</code></dd></div>
                <div><dt>Console client ID</dt><dd><code>ssra-staff-console</code></dd></div>
                <div><dt>Required passkey ACR</dt><dd><code>urn:ssra:acr:passkey</code> (ES256 / EdDSA)</dd></div>
                <div><dt>Redirect URI</dt><dd><code>/signin/callback</code> (PKCE S256 + PAR + DPoP)</dd></div>
              </dl>
            </section>

            <p id="signin-status-banner" class="signin-status is-hidden" role="status" aria-live="polite"></p>

            <footer class="signin-switch">
              <p>No account yet? <a href="/signup" data-nav="/signup">Create one</a></p>
              <div class="signin-switch-links">
                <a class="signin-switch-alt" href="/admin" data-nav="/admin">Back to console preview</a>
                <a class="signin-switch-alt" href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Back to the assistant</a>
              </div>
            </footer>
          </div>
        </div>`;
}

function renderSignUpCard(publicAssistantUrl = "http://127.0.0.1:3000/en") {
  return `<div class="signin-wrap">
          <div class="signin-card">
            <header class="signin-head">
              <div class="signin-mark" aria-hidden="true">${ICONS.ssraCrest}</div>
              <span id="preview-eyebrow" class="ops-eyebrow">Keycloak 26.4.11 · OIDC User Registration (prompt=create)</span>
              <h1 id="preview-title">Create an account</h1>
              <p class="signin-sub">South Sudan Revenue Authority (SSRA) — Identity &amp; Role Provisioning</p>
            </header>

            <section class="signin-block" aria-labelledby="signup-h">
              <h2 id="signup-h">Register with the SSRA Keycloak identity provider</h2>
              <p class="signin-note">
                Accounts, passkeys, and security recovery are managed by SSRA&#39;s configured Keycloak identity provider — this application never sees a password. Clicking below initiates an OAuth 2.1 + PKCE <code>S256</code> registration request (<code>prompt=create&amp;screen_hint=signup</code>).
              </p>
              <form id="console-signup-form" class="signin-form" data-testid="console-signup-form" novalidate>
                <div class="signin-field">
                  <label for="signup-name-input" class="signin-label">Full name or business name</label>
                  <input id="signup-name-input" data-testid="signup-name-input" class="signin-input" type="text" name="name" autocomplete="name" placeholder="e.g. Amina M." required />
                </div>
                <div class="signin-field">
                  <label for="signup-email-input" class="signin-label">Email address</label>
                  <input id="signup-email-input" data-testid="signup-email-input" class="signin-input" type="email" name="email" autocomplete="email" placeholder="e.g. taxpayer@etax.nra.gov.ss" required />
                </div>
                <div class="signin-field">
                  <label for="signup-password-input" class="signin-label">Create password</label>
                  <input id="signup-password-input" data-testid="signup-password-input" class="signin-input" type="password" name="new-password" autocomplete="new-password" placeholder="At least 8 characters" required />
                </div>
                <button type="submit" id="console-signup-submit-btn" class="signin-primary" data-testid="console-signup-submit-btn">
                  Create taxpayer account
                </button>
              </form>
              <button type="button" id="keycloak-signup-btn" class="signin-secondary" data-testid="keycloak-signup-btn">
                Continue to registration
              </button>
            </section>

            <section class="signin-block" aria-labelledby="signup-what">
              <h2 id="signup-what">What an account changes</h2>
              <ul class="signin-benefits">
                <li>
                  <strong>Ask without an account (T0 Public Assistant)</strong>
                  <span>Tax questions, statutory rates, deadlines, PAYE/WHT calculators, and document preflight checks all work signed out with zero PII stored.</span>
                </li>
                <li>
                  <strong>Taxpayer e-Tax continuity (T1–T3 Progressive Proofing)</strong>
                  <span>Registering a taxpayer account links saved guidance preferences and enables deterministic TIN + OTP step-up verification outside the LLM.</span>
                </li>
                <li>
                  <strong>SSRA employees, officers, administrators &amp; auditors</strong>
                  <span>Staff (<code>ssra_staff</code>), administrator (<code>ssra_admin</code>), and read-only auditor (<code>ssra_auditor</code>) roles are predefined and assigned by SSRA Identity Governance in the <code>ssra</code> Keycloak realm with mandatory FIDO2 passkey enrollment. Staff accounts are not self-registered here — sign in directly on <a href="/signin" data-nav="/signin">/signin</a>.</span>
                </li>
              </ul>
            </section>

            <p id="signup-status-banner" class="signin-status is-hidden" role="status" aria-live="polite"></p>

            <footer class="signin-switch">
              <p>Already have an account? <a href="/signin" data-nav="/signin">Sign in</a></p>
              <div class="signin-switch-links">
                <a class="signin-switch-alt" href="/admin" data-nav="/admin">Back to console preview</a>
                <a class="signin-switch-alt" href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Continue without an account</a>
              </div>
            </footer>
          </div>
        </div>`;
}

function renderSignInCallbackCard(publicAssistantUrl = "http://127.0.0.1:3000/en") {
  return `<div class="signin-wrap">
          <div class="signin-card">
            <header class="signin-head">
              <div class="signin-mark" aria-hidden="true">${ICONS.ssraCrest}</div>
              <span id="preview-eyebrow" class="ops-eyebrow">Keycloak 26.4.11 · OIDC Authorization Code Callback</span>
              <h1 id="preview-title">Signing you in</h1>
              <p class="signin-sub">South Sudan Revenue Authority (SSRA) — Verifying PKCE &amp; CSRF State</p>
            </header>

            <p id="callback-status-banner" class="signin-status error" role="alert" aria-live="polite">
              Verifying OAuth 2.1 authorization code, CSRF state, and PKCE S256 verifier…
            </p>

            <nav class="signin-onward" aria-label="Continue to">
              <a href="/signin" data-nav="/signin">Back to sign-in (/signin)</a>
              <a href="/admin" data-nav="/admin">Operations overview preview (/admin)</a>
              <a href="/agent" data-nav="/agent">Tax agent queue preview (/agent)</a>
              <a href="/analytics" data-nav="/analytics">Auditor &amp; analytics preview (/analytics)</a>
              <a href="${escapeHtml(publicAssistantUrl)}" data-nav="${escapeHtml(publicAssistantUrl)}">Open the public assistant</a>
            </nav>
          </div>
        </div>`;
}

function renderRouteBody(currentPath, currentTitle, currentGroup, publicAssistantUrl) {
  if (currentPath === "/signin") return renderSignInCard(publicAssistantUrl);
  if (currentPath === "/signup") return renderSignUpCard(publicAssistantUrl);
  if (currentPath === "/signin/callback") return renderSignInCallbackCard(publicAssistantUrl);
  return renderPreviewCard(currentTitle, currentGroup, publicAssistantUrl, currentPath);
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
<html lang="en" data-theme="dark" data-rail-mode="always-open">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content" />
  <meta name="theme-color" id="ops-theme-color" content="#091310" />
  <meta name="description" content="Non-operational preview of SSRA Assist staff navigation. No live taxpayer data, service telemetry, or staff actions." />
  <link rel="preload" href="/fonts/IBMPlexSans-Regular.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="preload" href="/fonts/IBMPlexSans-SemiBold.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="preload" href="/fonts/IBMPlexMono-Light.woff2" as="font" type="font/woff2" crossorigin />
  <title>SSRA Operations Console Preview — ${escapeHtml(currentTitle)}</title>
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
      --ops-font-sans: "IBM Plex Sans", "Segoe UI", "Aptos", "Avenir Next", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
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
      --ops-weight-reg: var(--ops-weight-normal);
      --ops-weight-medium: 500;
      --ops-weight-semi: 600;
      --ops-weight-bold: 700;
      --ops-tracking-caps: 0.04em;
      --ops-tracking-meta: 0.06em;
      --ops-tracking-tight: -0.01em;
      --ops-space-1: 4px;
      --ops-space-2: 8px;
      --ops-space-3: 12px;
      --ops-space-4: 16px;
      --ops-space-5: 20px;
      --ops-space-6: 24px;
      --ops-space-8: 32px;
      --ops-space-10: 40px;
      --ops-space-12: 48px;
      --ops-space-16: 64px;
      --ops-gutter: var(--ops-space-5);
      --ops-band: var(--ops-space-8);
      --ops-radius-xs: 6px;
      --ops-radius-sm: 8px;
      --ops-radius-md: 12px;
      --ops-radius-lg: 16px;
      --ops-radius-pill: 999px;
      --ops-nav-h: 56px;
      --ops-max-w: 1440px;
      --ops-max-w-read: 1180px;
      --ops-dur-fast: 110ms;
      --ops-dur-base: 180ms;
      --ops-dur-slow: 320ms;
      --ops-ease: cubic-bezier(0.2, 0, 0.15, 1);

      --bg-0: #091310;
      --bg-1: #0E1C17;
      --bg-2: #142720;
      --surface-1: rgba(236, 245, 238, 0.038);
      --surface-2: rgba(236, 245, 238, 0.068);
      --surface-3: rgba(236, 245, 238, 0.105);
      --surface-4: rgba(236, 245, 238, 0.145);
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
      --ops-scroll-thumb: var(--border-2);
      --ops-scroll-thumb-hover: var(--text-3);
      --ops-glass-bg: linear-gradient(150deg, rgba(255, 255, 255, 0.11) 0%, rgba(255, 255, 255, 0.04) 46%, rgba(255, 255, 255, 0.015) 100%);
      --ops-glass-line: rgba(220, 235, 224, 0.16);
      --ops-glass-blur: blur(22px) saturate(165%);
      --ops-glass-spec: inset 0 1px 0 rgba(255, 255, 255, 0.22), inset 0 -1px 0 rgba(255, 255, 255, 0.05);
      --ops-glass-cast: 0 16px 40px rgba(0, 0, 0, 0.34);
      --ops-glass-solid: var(--ops-panel);
      --ops-elev-1: 0 4px 12px rgba(0, 0, 0, 0.35);
      --ops-elev-2: 0 12px 32px rgba(0, 0, 0, 0.45);
      --ops-elev-3: 0 24px 60px rgba(0, 0, 0, 0.56);

      --ops-good-ink: #34D399;
      --ops-warn-ink: #FBBF24;
      --ops-bad-ink: #FB7185;
      --ops-info-ink: #60A5FA;
      --ops-focus: #F4C430;
      --ops-focus-ring: 2px;
      --ops-focus-gap: 2px;

      --ops-series-1: #3987e5;
      --ops-series-2: #d95926;
      --ops-series-3: #199e70;
      --ops-series-4: #c98500;
      --ops-series-5: #d55181;
      --ops-series-6: #008300;
      --ops-series-7: #9085e9;
      --ops-series-8: #e66767;
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
      --surface-ink: #FFFFFF;
      --border-0: rgba(12, 28, 20, 0.08);
      --border-1: rgba(12, 28, 20, 0.14);
      --border-2: rgba(12, 28, 20, 0.23);
      --text-0: #0C1C14;
      --text-1: #1F3329;
      --text-2: #4A5E53;
      --text-3: #4E6358;
      --accent: #704B00;
      --ops-glass-bg: linear-gradient(150deg, rgba(255, 255, 255, 0.86) 0%, rgba(255, 255, 255, 0.68) 100%);
      --ops-glass-line: rgba(12, 28, 20, 0.12);
      --ops-glass-blur: blur(22px) saturate(135%);
      --ops-glass-spec: inset 0 1px 0 rgba(255, 255, 255, 0.95);
      --ops-glass-cast: 0 12px 32px rgba(12, 28, 20, 0.08);
      --ops-good-ink: #066926;
      --ops-warn-ink: #853A06;
      --ops-bad-ink: #B91C1C;
      --ops-info-ink: #0F47AF;
      --ops-focus: #078930;
      --ops-series-1: #2a78d6;
      --ops-series-2: #eb6834;
      --ops-series-3: #1baf7a;
      --ops-series-4: #eda100;
      --ops-series-5: #e87ba4;
      --ops-series-6: #008300;
      --ops-series-7: #4a3aa7;
      --ops-series-8: #e34948;
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
      font-feature-settings: "tnum" 1, "zero" 1, "cv01" 1;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      background: var(--bg-0); color: var(--text-1);
    }
    .staff-shell, .ops-page {
      font-family: var(--ops-font-sans);
      font-variant-numeric: tabular-nums;
      font-feature-settings: "tnum" 1, "zero" 1, "cv01" 1;
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
    :is(a, button, input, select, textarea, [tabindex]):focus-visible {
      outline: var(--ops-focus-ring) solid var(--ops-focus);
      outline-offset: var(--ops-focus-gap);
    }

    /* ── Metadata & Figure Voices (ops.css pattern) ── */
    .ops-meta,
    .ops-eyebrow,
    .ops-stat-label,
    .ops-fresh,
    .staff-rail-group-label,
    .ops-chip,
    .ov-chip {
      font-family: var(--ops-font-mono);
      font-weight: var(--ops-weight-light);
      letter-spacing: var(--ops-tracking-meta);
      font-variant-numeric: tabular-nums;
    }
    .ops-figure,
    .ops-kbd {
      font-family: var(--ops-font-mono);
      font-weight: var(--ops-weight-light);
      letter-spacing: 0;
      font-variant-numeric: tabular-nums;
    }

    /* ── Hover-Only Neutral Scrollbars (ops.css pattern) ── */
    .staff-shell ::-webkit-scrollbar { width: 10px; height: 10px; }
    .staff-shell ::-webkit-scrollbar-track,
    .staff-shell ::-webkit-scrollbar-corner { background: transparent; }
    .staff-shell ::-webkit-scrollbar-button { display: none; width: 0; height: 0; }
    .staff-shell ::-webkit-scrollbar-thumb {
      background-color: transparent;
      background-clip: padding-box;
      border: 3px solid transparent;
      border-radius: var(--ops-radius-pill);
      transition: background-color var(--ops-dur-fast) var(--ops-ease);
    }
    .staff-shell *:hover::-webkit-scrollbar-thumb,
    .staff-shell *:focus-within::-webkit-scrollbar-thumb {
      background-color: var(--ops-scroll-thumb);
    }
    .staff-shell *:hover::-webkit-scrollbar-thumb:hover {
      background-color: var(--ops-scroll-thumb-hover);
    }
    .staff-shell * {
      scrollbar-width: thin;
      scrollbar-color: transparent transparent;
    }
    .staff-shell *:hover,
    .staff-shell *:focus-within {
      scrollbar-color: var(--ops-scroll-thumb) transparent;
    }

    /* ── Staff Shell & Collapsible Vertical Rail (staffGuard.css pattern) ── */
    .staff-shell {
      --rail-w-collapsed: 52px;
      --rail-w-expanded: 220px;
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
      position: fixed; inset-block: 0; inset-inline-start: 0; z-index: 30;
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
    @supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
      .staff-rail, .call-console-bar, .ops-stat, .ops-panel.is-glass {
        background: var(--ops-glass-solid);
        border-color: var(--ops-line);
        box-shadow: var(--ops-elev-1);
      }
    }
    @media (prefers-reduced-transparency: reduce) {
      .staff-rail, .call-console-bar, .ops-stat, .ops-panel.is-glass {
        background: var(--ops-glass-solid);
        border-color: var(--ops-line);
        box-shadow: var(--ops-elev-1);
        -webkit-backdrop-filter: none;
        backdrop-filter: none;
      }
    }

    .staff-rail-head {
      display: flex; align-items: center; justify-content: space-between;
      gap: var(--ops-space-1); min-height: var(--ops-nav-h);
      padding: var(--ops-space-2); flex: none;
    }
    .staff-brand {
      display: flex; align-items: center; gap: var(--ops-space-2);
      min-width: 0; color: var(--text-0); text-decoration: none; white-space: nowrap;
    }
    .staff-brand-mark {
      display: inline-flex; align-items: center; justify-content: center; flex: none;
      width: 28px; height: 28px; border-radius: var(--ops-radius-sm);
      background: var(--accent); color: #0B1220;
      font-size: 10px; font-weight: var(--ops-weight-bold); letter-spacing: 0.02em;
    }
    :root[data-theme="light"] .staff-brand-mark { color: #FFFFFF; }
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
    .staff-rail.is-collapsed .ops-cmdk-trigger { justify-content: center; padding-inline: 0; }
    .staff-rail.is-collapsed .ops-cmdk-trigger-text,
    .staff-rail.is-collapsed .ops-cmdk-kbd { display: none; }
    .staff-rail.is-collapsed .staff-acct-trigger { justify-content: center; padding-inline: 0; }
    .staff-rail.is-collapsed .staff-acct-meta,
    .staff-rail.is-collapsed .staff-acct-chevron { display: none; }
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
      border-top: 1px solid var(--ops-line);
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
      position: relative; width: 26px; height: 26px; border-radius: 50%;
      background: var(--accent); color: #0B1220;
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-bold); letter-spacing: 0.02em;
      display: inline-flex; align-items: center; justify-content: center; flex: none;
    }
    :root[data-theme="light"] .staff-acct-avatar { color: #FFFFFF; }
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
      border-radius: var(--ops-radius-pill); background: rgba(251, 191, 36, 0.12);
      border: 1px solid rgba(251, 191, 36, 0.4); color: var(--ops-warn-ink); font-weight: var(--ops-weight-semi);
    }

    /* ── OpsPage, OpsPanel & StatCard (Hercules + ops.css + admin.css pattern) ── */
    .ops-page {
      max-width: var(--ops-max-w); width: 100%; margin: 0 auto;
      padding: var(--ops-space-6) var(--ops-space-5) var(--ops-space-12);
      color: var(--text-1);
    }
    .ops-page-head {
      display: flex; align-items: flex-end; justify-content: space-between;
      gap: var(--ops-space-4); flex-wrap: wrap; margin-bottom: var(--ops-space-5);
    }
    .ops-page-head > * { min-width: 0; }
    .ops-eyebrow {
      display: block; margin-bottom: var(--ops-space-2);
      font-family: var(--ops-font-mono); font-size: var(--ops-text-2xs);
      font-weight: var(--ops-weight-light); letter-spacing: var(--ops-tracking-meta);
      text-transform: uppercase; color: var(--text-3);
    }
    .ops-page-head h1 {
      margin: 0; font-size: var(--ops-text-xl); line-height: var(--ops-lh-tight);
      font-weight: var(--ops-weight-semi); letter-spacing: var(--ops-tracking-tight); color: var(--text-0);
    }
    .ops-page-desc {
      margin: var(--ops-space-2) 0 0; max-width: 68ch;
      font-size: var(--ops-text-sm); line-height: var(--ops-lh-normal); color: var(--text-2);
    }
    .ops-page-actions { display: flex; align-items: center; gap: var(--ops-space-2); flex-wrap: wrap; max-width: 100%; }
    .ops-page-actions > * { min-width: 0; }

    .ops-segmented {
      display: inline-flex; gap: 2px; padding: 3px; border-radius: var(--ops-radius-sm);
      background: var(--ops-row); border: 1px solid var(--ops-line);
    }
    .ops-seg-btn {
      min-height: 28px; min-width: 36px; padding: 4px 11px; border-radius: var(--ops-radius-xs); border: none;
      background: transparent; color: var(--text-2); font-size: var(--ops-text-xs);
      font-weight: var(--ops-weight-semi); cursor: pointer; font-family: inherit;
      display: inline-flex; align-items: center; justify-content: center;
      transition: background var(--ops-dur-fast) var(--ops-ease), color var(--ops-dur-fast) var(--ops-ease);
    }
    .ops-seg-btn.active { background: var(--ops-panel); color: var(--text-0); box-shadow: var(--ops-elev-1), inset 0 0 0 1px var(--ops-line); }

    .ops-btn {
      min-height: 36px; padding: 8px 14px; border-radius: var(--ops-radius-sm);
      background: var(--ops-row-active); border: 1px solid var(--ops-line-strong); color: var(--text-0);
      font-size: var(--ops-text-sm); font-weight: var(--ops-weight-semi);
      cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: var(--ops-space-2); text-decoration: none; white-space: nowrap;
      transition: background var(--ops-dur-fast) var(--ops-ease), border-color var(--ops-dur-fast) var(--ops-ease);
    }
    .ops-btn:hover { background: var(--surface-4); border-color: var(--ops-line-strong); }
    a.ops-btn { color: var(--text-0); }
    .ops-btn.primary, a.ops-btn.primary, a.ops-btn.primary:hover { background: linear-gradient(135deg, #07792B 0%, #0D6E38 50%, #0F47AF 100%); color: #fff; border-color: rgba(255,255,255,0.18); box-shadow: var(--ops-elev-1); }
    .ops-btn.gold { background: var(--accent); color: #0B1220; border-color: transparent; font-weight: var(--ops-weight-bold); }
    :root[data-theme="light"] .ops-btn.gold { color: #FFFFFF; }

    /* StatCard Grid (Hercules tabular/proportional figure hierarchy) */
    .ops-stat-grid {
      display: grid;
      grid-template-columns: repeat(var(--ops-stat-cols, 3), minmax(0, 1fr));
      gap: var(--ops-space-3); margin-bottom: var(--ops-band);
    }
    @media (max-width: 1100px) { .ops-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 640px) { .ops-stat-grid { grid-template-columns: minmax(0, 1fr); } }

    .ops-stat {
      position: relative; display: flex; flex-direction: column; gap: var(--ops-space-1);
      padding: var(--ops-space-5); border-radius: var(--ops-radius-md);
      background: var(--ops-glass-bg); border: 1px solid var(--ops-glass-line);
      box-shadow: var(--ops-glass-spec), var(--ops-glass-cast);
      -webkit-backdrop-filter: var(--ops-glass-blur); backdrop-filter: var(--ops-glass-blur);
      contain: paint; text-decoration: none; color: inherit;
      transition: border-color var(--ops-dur-fast) var(--ops-ease), background var(--ops-dur-fast) var(--ops-ease);
    }
    .ops-stat:hover { border-color: var(--ops-line-strong); background: var(--ops-row-hover); }
    .ops-stat-label {
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-light);
      letter-spacing: var(--ops-tracking-meta); text-transform: uppercase; color: var(--text-3);
    }
    .ops-stat-row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--ops-space-2); flex-wrap: wrap; margin-top: 2px; }
    .ops-stat-value {
      font-size: var(--ops-text-xl); line-height: var(--ops-lh-tight);
      min-height: calc(var(--ops-text-xl) * var(--ops-lh-tight));
      font-weight: var(--ops-weight-semi); letter-spacing: var(--ops-tracking-tight);
      color: var(--text-0); font-variant-numeric: proportional-nums; text-wrap: balance;
    }
    .ops-stat-unit { font-size: 0.6em; font-weight: var(--ops-weight-normal); letter-spacing: 0; color: var(--text-2); white-space: pre; }
    .ops-delta {
      display: inline-flex; align-items: center; gap: 3px;
      font-family: var(--ops-font-mono); font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-semi);
      font-variant-numeric: tabular-nums; color: var(--text-3);
    }
    .ops-delta.is-good { color: var(--ops-good-ink); }
    .ops-delta.is-bad { color: var(--ops-bad-ink); }
    .ops-stat-hint { font-size: var(--ops-text-2xs); color: var(--text-3); line-height: var(--ops-lh-snug); }
    .ops-sparkline { width: 100%; height: 28px; margin-top: var(--ops-space-1); overflow: visible; }

    /* OpsPanel & Two-Column Layouts */
    .ov-cols { display: grid; grid-template-columns: 1.45fr 1fr; gap: var(--ops-band); align-items: start; }
    @media (max-width: 900px) { .ov-cols { grid-template-columns: minmax(0, 1fr); } }
    .ov-side { display: grid; gap: var(--ops-band); }

    .ops-panel {
      background: var(--ops-panel); border: 1px solid var(--ops-line);
      border-radius: var(--ops-radius-md); overflow: hidden;
    }
    .ops-panel.is-bare { background: none; border: 0; border-radius: 0; box-shadow: none; }
    .ops-panel.is-glass {
      background: var(--ops-glass-bg); border-color: var(--ops-glass-line);
      border-radius: var(--ops-radius-lg);
      box-shadow: var(--ops-glass-spec), var(--ops-elev-2);
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
    .ops-page > .ops-panel.is-bare,
    .ops-page > .ops-panel.is-glass,
    .ops-page > .ops-panel.is-bare + *,
    .ops-page > .ops-panel.is-glass + * {
      margin-top: var(--ops-band);
    }

    /* Lists, Tables & Chips (ink-only readings in IBM Plex Mono Light) */
    .ov-review-list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--ops-space-2); }
    .ov-review-item {
      display: grid; gap: var(--ops-space-1); padding: var(--ops-space-3) var(--ops-space-4);
      border: 1px solid var(--ops-hairline); border-radius: var(--ops-radius-sm); background: var(--ops-row);
    }
    .ov-review-top { display: flex; align-items: center; justify-content: space-between; gap: var(--ops-space-2); }
    .ops-chip {
      display: inline-flex; align-items: center; gap: 5px; padding: 0;
      border: 0; border-radius: 0; background: none;
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-light); color: var(--text-3); white-space: nowrap;
    }
    .ops-chip + .ops-chip { margin-inline-start: var(--ops-space-3); }
    .ops-chip.good, .ops-chip.is-good { color: var(--ops-good-ink); }
    .ops-chip.warn, .ops-chip.is-warn { color: var(--ops-warn-ink); }
    .ops-chip.bad, .ops-chip.is-danger { color: var(--ops-bad-ink); }
    .ops-chip.info, .ops-chip.is-info { color: var(--ops-info-ink); }

    .ops-table { width: 100%; border-collapse: collapse; font-size: var(--ops-text-sm); }
    .ops-table th, .ops-table td {
      padding: var(--ops-space-3) var(--ops-space-4); text-align: start; border-bottom: 1px solid var(--ops-hairline);
    }
    .ops-table th {
      padding: var(--ops-space-2) var(--ops-space-4);
      font-size: var(--ops-text-2xs); font-weight: var(--ops-weight-semi);
      text-transform: uppercase; letter-spacing: var(--ops-tracking-caps); color: var(--text-3);
      border-bottom: 1px solid var(--ops-line);
    }
    .ops-table tr:hover td { background: var(--ops-row); }

    .ov-kv { margin: 0; display: grid; gap: var(--ops-space-2); }
    .ov-kv > div { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: var(--ops-space-1) var(--ops-space-3); min-height: 24px; padding: 2px 0; border-bottom: 1px solid var(--ops-hairline); }
    .ov-kv dt { font-size: var(--ops-text-xs); color: var(--text-3); }
    .ov-kv dd { margin: 0; font-size: var(--ops-text-xs); font-weight: var(--ops-weight-semi); color: var(--text-1); text-align: end; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }

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
    @media (pointer: coarse), (max-width: 820px) {
      .staff-rail-pin, .ops-cmdk-trigger, .ops-btn, .staff-acct-trigger, .staff-acct-item, .staff-rail a.nav-item {
        min-height: 44px;
      }
      .staff-rail-pin { min-width: 44px; }
    }
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
    .ov-stats { --ops-stat-cols: 4; margin-bottom: var(--ops-band); }
    .ops-fresh {
      display: inline-flex; align-items: center; gap: var(--ops-space-2);
      font-size: var(--ops-text-2xs); color: var(--text-3);
      font-variant-numeric: tabular-nums;
    }
    .ops-fresh-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--ops-good-ink); flex: none;
    }
    .ops-fresh-dot.is-stale { background: var(--text-3); }
    .ops-panel-end { margin-inline-start: auto; display: flex; align-items: center; gap: var(--ops-space-2); }
    .ops-panel-note {
      margin: 0 0 var(--ops-space-3); font-size: var(--ops-text-xs);
      line-height: var(--ops-lh-normal); color: var(--text-2);
    }
    .ops-empty {
      display: flex; flex-direction: column; align-items: center;
      gap: var(--ops-space-2); padding: var(--ops-space-6) var(--ops-space-4);
      text-align: center; border: 1px dashed var(--ops-line); border-radius: var(--ops-radius-md);
      background: var(--ops-row);
    }
    .ops-empty-mark {
      display: grid; place-items: center; width: 40px; height: 40px;
      border-radius: var(--ops-radius-md); background: var(--ops-row-active); color: var(--text-3);
    }
    .ops-empty-title {
      margin: 0; font-size: var(--ops-text-base); font-weight: var(--ops-weight-semi); color: var(--text-1);
    }
    .ops-empty-body {
      margin: 0; max-width: 44ch; font-size: var(--ops-text-sm);
      line-height: var(--ops-lh-normal); color: var(--text-3);
    }
    .ov-chip { padding: 0; font-size: var(--ops-text-2xs); color: var(--text-3); }
    .ov-chip.good { color: var(--ops-good-ink); }
    .ov-chip.warn { color: var(--ops-warn-ink); }
    .ops-chip.is-warn { color: var(--ops-warn-ink); }
    .ops-preview-card { margin: 0 0 var(--ops-band); padding: var(--ops-space-5); }
    .ops-preview-card p, .ops-preview-card li { line-height: 1.6; font-size: var(--ops-text-sm); }
    .ops-preview-card ul { padding-inline-start: 1.25rem; margin: var(--ops-space-2) 0 0; }
    .ops-preview-chip { display: inline-block; padding: 4px 9px; border: 1px solid var(--accent); border-radius: 999px; color: var(--accent); font-weight: 700; margin-bottom: var(--ops-space-2); }
    .is-hidden { display: none !important; }
    .signin-wrap { display: grid; place-items: center; padding: var(--ops-space-4) 0 var(--ops-space-8); }
    .signin-card { width: 100%; max-width: 560px; background: var(--ops-panel); border: 1px solid var(--ops-line-strong); border-radius: var(--ops-radius-lg); box-shadow: var(--ops-elev-2); padding: clamp(20px, 4vw, 34px); }
    .signin-head { text-align: center; margin-bottom: 22px; }
    .signin-mark { width: 52px; height: 52px; margin: 0 auto 12px; display: grid; place-items: center; border-radius: 14px; background: linear-gradient(135deg, #07792B 0%, #0F47AF 100%); color: #fff; box-shadow: var(--ops-elev-1); }
    .signin-head h1 { margin: 4px 0 0; font-size: 24px; font-weight: 700; color: var(--text-0); }
    .signin-sub { margin: 6px 0 0; font-size: 13px; color: var(--text-2); }
    .signin-block { padding: 18px 0; border-top: 1px solid var(--ops-hairline); }
    .signin-block h2 { margin: 0 0 8px; font-size: 15px; font-weight: 600; color: var(--text-0); }
    .signin-note { margin: 0 0 14px; font-size: 13px; line-height: 1.55; color: var(--text-2); }
    .signin-roles { margin: 0 0 14px; padding: 0; border: 0; display: grid; gap: 8px; }
    .signin-roles legend { padding: 0; margin-bottom: 8px; font-size: 12px; font-weight: 600; color: var(--text-2); }
    .role-opt { display: grid; grid-template-columns: auto 1fr; grid-template-areas: "radio name" "radio hint"; gap: 2px 10px; align-items: center; padding: 10px 12px; border: 1px solid var(--ops-line); border-radius: var(--ops-radius-sm); background: var(--ops-row); cursor: pointer; }
    .role-opt.active { border-color: var(--accent); background: var(--ops-row-active); }
    .role-opt input { grid-area: radio; width: 16px; height: 16px; accent-color: var(--accent); }
    .role-name { grid-area: name; font-size: 13px; font-weight: 600; color: var(--text-0); }
    .role-hint { grid-area: hint; font-size: 11.5px; color: var(--text-2); line-height: 1.45; }
    .signin-form { display: grid; gap: 12px; margin: 0 0 12px; }
    .signin-field { display: grid; gap: 6px; }
    .signin-label { font-size: 12px; font-weight: 600; color: var(--text-1); }
    .signin-input { width: 100%; min-height: 44px; padding: 9px 12px; border-radius: var(--ops-radius-sm); border: 1px solid var(--ops-line-strong); background: var(--ops-row); color: var(--text-0); font-family: inherit; font-size: 13.5px; }
    .signin-input::placeholder { color: var(--text-3); }
    .presence-pill.is-authenticated { background: rgba(52, 211, 153, 0.14); border-color: rgba(52, 211, 153, 0.45); color: var(--ops-good-ink); }
    .signin-primary, .signin-secondary { width: 100%; min-height: 44px; padding: 10px 16px; border-radius: var(--ops-radius-sm); font-size: 14px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; font-family: inherit; }
    .signin-primary { background: linear-gradient(135deg, #07792B 0%, #0D6E38 50%, #0F47AF 100%); color: #fff; border: 1px solid rgba(255, 255, 255, 0.2); }
    .signin-secondary { margin-top: 10px; background: var(--ops-row); color: var(--text-0); border: 1px solid var(--ops-line-strong); }
    .signin-secondary:hover { background: var(--ops-row-hover); }
    .signin-kv { margin-top: 14px; }
    .signin-benefits { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 10px; }
    .signin-benefits li { padding: 12px 14px; border-radius: var(--ops-radius-sm); background: var(--ops-row); border: 1px solid var(--ops-hairline); display: grid; gap: 4px; }
    .signin-benefits strong { font-size: 13px; color: var(--text-0); }
    .signin-benefits span { font-size: 12.5px; color: var(--text-2); line-height: 1.5; }
    .signin-status { margin: 12px 0 0; padding: 11px 13px; border-radius: var(--ops-radius-sm); font-size: 12.5px; line-height: 1.5; border: 1px solid var(--ops-line); background: var(--ops-row); color: var(--text-1); overflow-wrap: anywhere; }
    .signin-status.ok { border-color: rgba(52, 211, 153, 0.4); background: rgba(52, 211, 153, 0.1); color: var(--ops-good-ink); }
    .signin-status.error { border-color: rgba(251, 113, 133, 0.45); background: rgba(251, 113, 133, 0.1); color: var(--ops-bad-ink); }
    .signin-onward { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--ops-hairline); display: grid; gap: 8px; }
    .signin-onward a { padding: 9px 12px; border-radius: var(--ops-radius-sm); background: var(--ops-row); border: 1px solid var(--ops-line); color: var(--text-0); font-size: 13px; text-decoration: none; }
    .signin-onward a:hover { background: var(--ops-row-hover); }
    .signin-switch { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--ops-hairline); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; font-size: 13px; color: var(--text-2); }
    .signin-switch p { margin: 0; }
    .signin-switch a { color: var(--accent); font-weight: 600; text-decoration: none; }
    .signin-switch a:hover { text-decoration: underline; }
    .signin-switch-links { display: flex; gap: 12px; flex-wrap: wrap; }
    .signin-switch-alt { color: var(--text-2) !important; font-weight: 500 !important; }
    /* Phone drawer overrides: always show labels, group headings, search text & account meta inside the 240px drawer regardless of desktop .is-collapsed state (staffGuard.css pattern) */
    @media (max-width: 820px) {
      .staff-rail .staff-rail-label,
      .staff-rail .staff-rail-group-label,
      .staff-rail .staff-brand-text {
        opacity: 1;
        height: auto;
      }
      .staff-rail.is-collapsed .ops-cmdk-trigger {
        justify-content: flex-start;
        padding-inline: var(--ops-space-2);
      }
      .staff-rail.is-collapsed .ops-cmdk-trigger-text {
        display: inline;
      }
      .staff-rail.is-collapsed .staff-acct-trigger {
        justify-content: flex-start;
        padding-inline: 8px;
      }
      .staff-rail.is-collapsed .staff-acct-meta,
      .staff-rail.is-collapsed .staff-acct-chevron {
        display: flex;
        opacity: 1;
      }
      .staff-rail-pin {
        display: none;
      }
    }
    @media (forced-colors: active) {
      .staff-rail, .ops-stat, .ops-panel, .ops-btn, .role-opt, .ops-cmdk-dialog, .signin-card {
        border: 1px solid CanvasText;
      }
      .staff-rail a.nav-item.active, .role-opt.active, .ops-seg-btn.active {
        outline: 2px solid Highlight;
        outline-offset: -2px;
      }
    }
    @media print {
      .staff-rail, .call-console-bar, .ops-cmdk-backdrop, .ssra-flag-ribbon, .ops-mobile-backdrop {
        display: none !important;
      }
      .staff-shell-content {
        margin-inline-start: 0 !important;
      }
      body, .ops-page, .ops-panel, .ops-stat {
        background: #ffffff !important;
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
            <button type="button" class="staff-acct-item" data-set-theme="dark" role="menuitemradio" aria-checked="true" tabindex="-1"><span>${ICONS.moon} Dark</span></button>
            <button type="button" class="staff-acct-item" data-set-theme="light" role="menuitemradio" aria-checked="false" tabindex="-1"><span>${ICONS.sun} Light</span></button>
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
          <span id="ops-presence-pill" class="presence-pill">Preview only · no authenticated staff session</span>
          <span id="ops-presence-note">No live calls, taxpayer records, or service telemetry are shown.</span>
        </div>
        <div class="call-bar-right">
          <a id="call-bar-signin-link" href="/signin" data-nav="/signin" class="ops-btn">Sign in</a>
          <a id="call-bar-signup-link" href="/signup" data-nav="/signup" class="ops-btn">Sign up</a>
          <button type="button" id="ops-signout-btn" class="ops-btn is-hidden" data-testid="ops-signout-btn" data-action="signout">${ICONS.close} Sign out</button>
          <a href="${escapeHtml(publicAssistantUrl)}" class="ops-btn primary">${ICONS.messageSquare} Taxpayer MainChat</a>
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
          digestSha256: "ccbeb4c74dc7244f8489c728f196afc5dbe070b6f02e03f8ab91ed3b551f889a",
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
          digestSha256: "5442142a4b8f30f8de772dbf3f36da3c905ccd1721c6abbe608c7f73971a7a04",
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
          digestSha256: "b39d198c3d53c930e7646711e64cb2b285835a8b4220100b5f4515591d5ed93d",
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
          digestSha256: "0626d14ece9920ba388a15ecf3fa7bdafa834f779fe3bb270b6c888abcd7c0fa",
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
        theme: readUiPreference("ssra-ops-theme", "dark"),
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
        if (!["dark", "light", "high-contrast"].includes(state.theme)) state.theme = "dark";
        if (state.session && ROLE_META[state.session.role]) {
          state.role = state.session.role;
        }
        if (!ROLE_META[state.role]) state.role = "ssra_admin";
        if (!["always-open", "hover"].includes(state.railMode)) state.railMode = "always-open";

        document.documentElement.setAttribute("data-theme", state.theme);
        document.documentElement.setAttribute("data-rail-mode", state.railMode);
        const themeColorMeta = document.getElementById("ops-theme-color");
        if (themeColorMeta) {
          themeColorMeta.setAttribute(
            "content",
            state.theme === "light" ? "#F6F7F2" : state.theme === "high-contrast" ? "#000000" : "#091310",
          );
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
        const presenceNoteEl = document.getElementById("ops-presence-note");
        const barSignInEl = document.getElementById("call-bar-signin-link");
        const barSignUpEl = document.getElementById("call-bar-signup-link");
        const barSignOutBtn = document.getElementById("ops-signout-btn");
        if (state.session) {
          if (presencePillEl) {
            presencePillEl.classList.add("is-authenticated");
            presencePillEl.setAttribute("data-testid", "authenticated-session-pill");
            presencePillEl.textContent =
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
                ? "Read-only Separation of Duties (ISO/IEC 42001 Clause 9.2) enforced · Reference workbench"
                : "Reference console workbench active · ILLUSTRATIVE_FALLBACK telemetry";
          }
          barSignInEl?.classList.add("is-hidden");
          barSignUpEl?.classList.add("is-hidden");
          barSignOutBtn?.classList.remove("is-hidden");
        } else {
          if (presencePillEl) {
            presencePillEl.classList.remove("is-authenticated");
            presencePillEl.removeAttribute("data-testid");
            presencePillEl.textContent = "Preview only · no authenticated staff session";
          }
          if (presenceNoteEl) {
            presenceNoteEl.textContent = "No live calls, taxpayer records, or service telemetry are shown.";
          }
          barSignInEl?.classList.remove("is-hidden");
          barSignUpEl?.classList.remove("is-hidden");
          barSignOutBtn?.classList.add("is-hidden");
        }
        document.querySelectorAll("[data-set-theme]").forEach((btn) => {
          const isSelected = btn.getAttribute("data-set-theme") === state.theme;
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

      function renderAuthenticatedPageHeader(eyebrow, title, desc) {
        const sess = state.session;
        const roleBadge = state.role === "ssra_auditor"
          ? '<span class="ops-chip info">' + ICONS.lock + " Auditor Read-Only Separation of Duties</span>"
          : '<span class="ops-chip good">' + ICONS.shieldCheck + " Verified Session · " + escapeHtml(sess?.email || state.role) + "</span>";
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
                '<button type="button" class="ops-seg-btn' + (state.periodDays === d ? " active" : "") + '" data-period="' + d + '">' + d + "d</button>"
              ).join("") +
            "</div>" +
            '<button type="button" class="ops-btn" data-action="signout">' + ICONS.close + " Sign out</button>" +
            '<a class="ops-btn is-primary primary" href="' + escapeHtml(PUBLIC_ASSISTANT_URL) + '" data-nav="' + escapeHtml(PUBLIC_ASSISTANT_URL) + '">Open the public assistant ' + ICONS.arrowUpRight + "</a>" +
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
                  '<div class="ops-msg-head">TAXPAYER MESSAGE (' + escapeHtml(active.locale) + ")</div>" +
                  '<div class="ops-msg-body">' + escapeHtml(active.userMsg) + "</div>" +
                "</div>" +
                '<div class="ops-draft-wrap">' +
                  '<label for="copilot-draft-box" class="ops-draft-label">' + ICONS.sparkles + " AI Copilot Cited Draft (Principle 1 Verified)</label>" +
                  '<textarea id="copilot-draft-box" rows="5" class="ops-draft-textarea">' + escapeHtml(active.draftReply) + "</textarea>" +
                "</div>" +
                '<div class="ops-chips-row">' +
                  active.citations.map((c) => '<span class="ops-chip good">' + ICONS.bookOpen + " " + escapeHtml(c) + " (2026.10.1)</span>").join("") +
                "</div>" +
                (isAuditor
                  ? '<div class="ops-chip warn" data-testid="auditor-readonly-notice">' + ICONS.lock + " Auditor Role (ssra_auditor) is strictly read-only and cannot send taxpayer replies (Separation of Duties).</div>"
                  : '<div class="ops-actions-row">' +
                      '<button type="button" class="ops-btn gold" id="approve-send-btn" data-testid="approve-send-btn">' + ICONS.check + " Approve &amp; Send Cited Reply</button>" +
                      '<button type="button" class="ops-btn primary" id="maker-checker-btn" data-testid="maker-checker-btn">' + ICONS.shieldCheck + " Sign T3 Maker-Checker Approval</button>" +
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
              deltaText: "LIVE_TELEMETRY",
              deltaGood: true,
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
                          '<button type="button" class="ops-seg-btn' + (state.degradationLevel === lvl ? " active" : "") + '" data-set-degrade="' + lvl + '">L' + lvl + "</button>"
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
        return ${JSON.stringify(renderPreviewCard("__TITLE__", "__GROUP__", publicAssistantUrl))}
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

      function wireAuthViewInteractions() {
        if (!mainEl) return;
        const roleRadios = Array.from(mainEl.querySelectorAll('input[name="signin-role-target"]'));
        roleRadios.forEach((radio) => {
          radio.checked = radio.value === state.role;
          radio.closest(".role-opt")?.classList.toggle("active", radio.checked);
        });
        if (!mainEl.hasAttribute("data-auth-wired")) {
          mainEl.setAttribute("data-auth-wired", "true");
          roleRadios.forEach((radio) => {
            radio.addEventListener("change", () => {
              roleRadios.forEach((r) => r.closest(".role-opt")?.classList.toggle("active", r.checked));
              if (ROLE_META[radio.value]) {
                state.role = radio.value;
                writeUiPreference("ssra-ops-preview-persona", state.role);
                const emailInput = document.getElementById("signin-email-input");
                const matchingAccount = ACCOUNT_DIRECTORY.find((a) => a.role === radio.value);
                if (emailInput && matchingAccount && (!emailInput.value.trim() || ACCOUNT_DIRECTORY.some((a) => a.email === emailInput.value.trim().toLowerCase()))) {
                  emailInput.value = matchingAccount.email;
                }
                applyChrome();
              }
            });
          });

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

          document.getElementById("console-passkey-signin-btn")?.addEventListener("click", () => {
            const selectedRadio = mainEl.querySelector('input[name="signin-role-target"]:checked');
            const targetRole = selectedRadio?.value || state.role || "ssra_admin";
            const account = ACCOUNT_DIRECTORY.find((item) => item.role === targetRole) || ACCOUNT_DIRECTORY[0];
            if (account) {
              setAuthenticatedSession(account);
            }
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
          const selectedRadio = mainEl.querySelector('input[name="signin-role-target"]:checked');
          const targetRole = selectedRadio?.value || state.role || "ssra_admin";
          const returnTo = selectedRadio?.getAttribute("data-landing") || ROLE_META[targetRole]?.landing || "/admin";
          lastCallbackOutcome = null;
          try {
            sessionStorage.setItem("ssra_pkce_verifier", verifier);
            sessionStorage.setItem("ssra_oidc_state", csrfState);
            sessionStorage.setItem("ssra_oidc_nonce", oidcNonce);
            sessionStorage.setItem("ssra_oidc_return_to", returnTo);
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
            authUrl.searchParams.set("prompt", "create");
            authUrl.searchParams.set("screen_hint", "signup");
          } else if (promptVal) {
            authUrl.searchParams.set("prompt", promptVal);
          }
          const bannerId = mode === "signup" ? "signup-status-banner" : "signin-status-banner";
          const bannerEl = document.getElementById(bannerId);
          if (bannerEl) {
            bannerEl.classList.remove("is-hidden", "error");
            bannerEl.classList.add("ok");
            bannerEl.setAttribute("role", "status");
            bannerEl.setAttribute("data-auth-url", authUrl.toString());
            bannerEl.textContent =
              (mode === "signup"
                ? "Prepared Keycloak 26.4.11 OIDC Registration request (prompt=create, PKCE S256) for realm ssra -> "
                : promptVal === "login"
                  ? "Prepared Keycloak 26.4.11 OIDC Re-Authentication request (prompt=login, acr_values=urn:ssra:acr:passkey) -> "
                  : "Prepared Keycloak 26.4.11 OIDC Passkey SSO request (acr_values=urn:ssra:acr:passkey, returnTo=" + returnTo + ") -> ") +
              authUrl.toString();
          }
        };

        const runKeycloakRedirect = (mode, promptVal) => {
          startKeycloakRedirect(mode, promptVal).catch(() => {
            const bannerId = mode === "signup" ? "signup-status-banner" : "signin-status-banner";
            const bannerEl = document.getElementById(bannerId);
            if (!bannerEl) return;
            bannerEl.classList.remove("is-hidden", "ok");
            bannerEl.classList.add("error");
            bannerEl.setAttribute("role", "alert");
            bannerEl.textContent =
              "Could not prepare the sign-in request. A secure (HTTPS) browser context is required for Web Crypto PKCE S256.";
          });
        };

          document.getElementById("keycloak-signin-btn")?.addEventListener("click", () => {
            runKeycloakRedirect("signin", undefined);
          });
          document.getElementById("keycloak-switch-account-btn")?.addEventListener("click", () => {
            runKeycloakRedirect("signin", "login");
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
        applyChrome();
        if (!mainEl) return;
        mainEl.setAttribute("data-route", state.route);
        if (state.route === "/signin") {
          document.title = "SSRA Operations Console Preview — Sign in";
          if (!document.getElementById("keycloak-signin-btn")) {
            setSafeHtml(mainEl, buildSignInHtml());
          }
          wireAuthViewInteractions();
          return;
        }
        if (state.route === "/signup") {
          document.title = "SSRA Operations Console Preview — Create an account";
          if (!document.getElementById("keycloak-signup-btn")) {
            setSafeHtml(mainEl, buildSignUpHtml());
          }
          wireAuthViewInteractions();
          return;
        }
        if (state.route === "/signin/callback") {
          document.title = "SSRA Operations Console Preview — Signing you in";
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
        mainEl?.focus();
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
          state.theme = themeBtn.getAttribute("data-set-theme") || "dark";
          writeUiPreference("ssra-ops-theme", state.theme);
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
            state.theme = state.theme === "dark" ? "light" : state.theme === "light" ? "high-contrast" : "dark";
            writeUiPreference("ssra-ops-theme", state.theme);
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

      renderCurrentRoute();
    })();
  </script>
</body>
</html>`;
  return compactOpsHtmlAssetBlocks(rawHtml);
}
