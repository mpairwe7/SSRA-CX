/**
 * Staff Console (`apps/console`) — ASVS 5.0 Level 3 Passkey Gate & 6-Step Knowledge Release Workflow (Section 7, 9.2, 12.1).
 */

export const KNOWLEDGE_RELEASE_STEPS = [
  "1_DRAFT",
  "2_LEGAL_REVIEW",
  "3_APPROVAL",
  "4_PUBLISH_IMMUTABLE_SNAPSHOT",
  "5_AUTO_REINDEX_AND_EVAL_REGRESSION",
  "6_ONE_STEP_ROLLBACK_ON_GATE_FAILURE",
] as const;

export type KnowledgeReleaseStep = (typeof KNOWLEDGE_RELEASE_STEPS)[number];

export interface ConsoleSession {
  readonly staffId: string;
  readonly role:
    | "agent"
    | "supervisor"
    | "qa"
    | "legal_approver"
    | "secops"
    | "admin"
    | "ssra_staff"
    | "ssra_admin"
    | "ssra_auditor";
  readonly passkeyVerified: boolean;
  readonly officeCode: string;
  readonly idleAgeSeconds: number;
  readonly originHeader?: string;
  readonly allowedOrigin?: string;
}

/**
 * Check whether a console session role is a read-only auditor (`qa` or `ssra_auditor`) under Separation of Duties.
 */
export function isReadOnlyAuditorRole(role: ConsoleSession["role"] | undefined | null): boolean {
  return role === "qa" || role === "ssra_auditor";
}

/**
 * Authorize baseline Staff Console access (WebAuthn passkey, origin match, and 15-min idle timeout).
 */
export function authorizeConsoleAccess(session: ConsoleSession | null): {
  readonly allowed: boolean;
  readonly reason?: string;
} {
  if (!session) {
    return { allowed: false, reason: "MISSING_SESSION" };
  }
  if (!session.passkeyVerified) {
    return { allowed: false, reason: "WEBAUTHN_PASSKEY_REQUIRED" };
  }
  // CVE-2026-27978: Explicitly reject 'null' or missing/mismatched origin from sandboxed contexts
  if (session.originHeader === undefined || !session.allowedOrigin) {
    return { allowed: false, reason: "NULL_OR_UNTRUSTED_ORIGIN" };
  }

  const cleanOrigin = session.originHeader.trim();
  if (cleanOrigin.toLowerCase() === "null" || cleanOrigin !== session.allowedOrigin) {
    return { allowed: false, reason: "NULL_OR_UNTRUSTED_ORIGIN" };
  }
  // Short session idle timeout (900 seconds = 15 minutes per ADR-012)
  if (session.idleAgeSeconds > 900) {
    return { allowed: false, reason: "SESSION_IDLE_EXPIRED" };
  }
  return { allowed: true };
}

/**
 * Authorize route-specific Staff Console access by role and HTTP method (enforcing Auditor read-only Separation of Duties).
 */
export function authorizeConsoleRoute(
  session: ConsoleSession | null,
  pathname: string,
  method = "GET",
): { readonly allowed: boolean; readonly reason?: string } {
  const base = authorizeConsoleAccess(session);
  if (!base.allowed || !session) {
    return base;
  }
  const upperMethod = method.trim().toUpperCase();
  const isMutation = !["GET", "HEAD", "OPTIONS"].includes(upperMethod);

  // Separation of Duties (ISO/IEC 42001 Clause 9.2 & EU AI Act Art. 14):
  // Auditors (`qa` / `ssra_auditor`) are read-only across operational routes and may only submit QA rubric scores.
  if (isMutation && isReadOnlyAuditorRole(session.role)) {
    const allowedAuditorMutation =
      /^\/v1\/conversations\/[^/]+\/qa-score$/.test(pathname) ||
      /^\/admin\/audit\/export$/.test(pathname);
    if (!allowedAuditorMutation) {
      return { allowed: false, reason: "AUDITOR_READ_ONLY_SEPARATION_OF_DUTIES" };
    }
  }

  if (pathname.startsWith("/admin/kill-switches") || pathname.startsWith("/admin/jit")) {
    if (session.role !== "admin" && session.role !== "secops" && session.role !== "ssra_admin") {
      return { allowed: false, reason: "INSUFFICIENT_ROLE_ADMIN_REQUIRED" };
    }
  }
  if (pathname.startsWith("/knowledge-release/approve")) {
    if (
      session.role !== "legal_approver" &&
      session.role !== "admin" &&
      session.role !== "ssra_admin"
    ) {
      return { allowed: false, reason: "INSUFFICIENT_ROLE_LEGAL_APPROVER_REQUIRED" };
    }
  }
  return { allowed: true };
}

/**
 * Execute request-level Next.js 16 console proxy enforcing passkey, origin, idle timeout, and route/method RBAC.
 */
export function executeConsoleProxy(input: {
  readonly session: ConsoleSession | null;
  readonly pathname: string;
  readonly method?: string;
}): {
  readonly status: 200 | 401 | 403;
  readonly allowed: boolean;
  readonly reason?: string;
} {
  const decision = authorizeConsoleRoute(input.session, input.pathname, input.method ?? "GET");
  if (!decision.allowed) {
    const status = decision.reason === "MISSING_SESSION" ? 401 : 403;
    return {
      status,
      allowed: false,
      ...(decision.reason !== undefined ? { reason: decision.reason } : {}),
    };
  }
  return { status: 200, allowed: true };
}
