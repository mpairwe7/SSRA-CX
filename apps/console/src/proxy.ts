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
  readonly role: "agent" | "supervisor" | "qa" | "legal_approver" | "secops" | "admin";
  readonly passkeyVerified: boolean;
  readonly officeCode: string;
  readonly idleAgeSeconds: number;
  readonly originHeader?: string;
  readonly allowedOrigin?: string;
}

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
  // CVE-2026-27978: Explicitly reject 'null' origin from sandboxed contexts
  if (session.originHeader !== undefined) {
    const cleanOrigin = session.originHeader.trim();
    if (
      cleanOrigin.toLowerCase() === "null" ||
      (session.allowedOrigin && cleanOrigin !== session.allowedOrigin)
    ) {
      return { allowed: false, reason: "NULL_OR_UNTRUSTED_ORIGIN" };
    }
  }
  // Short session idle timeout (900 seconds = 15 minutes per ADR-012)
  if (session.idleAgeSeconds > 900) {
    return { allowed: false, reason: "SESSION_IDLE_EXPIRED" };
  }
  return { allowed: true };
}
