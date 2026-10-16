/**
 * BFF Server-Side Session Cookie & CSRF Protection (`apps/web/src/app/api/auth/session/route.ts` — Section 9.4, ADR-012).
 *
 * Security Invariants:
 * 1. OAuth 2.1 tokens stay in Valkey on the server; browser receives only `__Host-ssra_session`.
 * 2. Cookie flags: `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=1800`.
 * 3. Mutations require matching `Origin` and `X-SSRA-CSRF` double-submit token.
 */

export const BFF_SESSION_COOKIE_NAME = "__Host-ssra_session" as const;

export function buildHttpOnlySessionCookieHeader(sessionId: string, maxAgeSeconds = 1800): string {
  const cleanId = sessionId.replace(/[^a-zA-Z0-9_-]/g, "");
  return `${BFF_SESSION_COOKIE_NAME}=${cleanId}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${maxAgeSeconds}`;
}

export function validateBffCsrfMutation(input: {
  readonly method: string;
  readonly originHeader?: string;
  readonly allowedOrigin: string;
  readonly csrfCookieToken?: string;
  readonly csrfHeaderToken?: string;
}): { readonly valid: boolean; readonly reason?: string } {
  const m = input.method.toUpperCase();
  if (m === "GET" || m === "HEAD" || m === "OPTIONS") {
    return { valid: true };
  }
  if (!input.originHeader || input.originHeader !== input.allowedOrigin) {
    return { valid: false, reason: "CSRF_ORIGIN_MISMATCH" };
  }
  if (
    !input.csrfCookieToken ||
    !input.csrfHeaderToken ||
    input.csrfCookieToken !== input.csrfHeaderToken
  ) {
    return { valid: false, reason: "CSRF_TOKEN_MISMATCH" };
  }
  return { valid: true };
}
