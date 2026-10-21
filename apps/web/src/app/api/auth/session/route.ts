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

export function buildSessionLogoutHeaders(): Record<string, string> {
  return {
    "Set-Cookie": `${BFF_SESSION_COOKIE_NAME}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`,
    "Clear-Site-Data": '"cache", "cookies", "storage"',
    "Cache-Control": "no-store",
  };
}

export function dispatchServiceWorkerLogoutPurge(target?: {
  readonly serviceWorker?: {
    readonly controller?: {
      postMessage: (msg: { readonly type: "SSRA_LOGOUT_PURGE" }) => void;
    } | null;
  };
}): boolean {
  const ctrl = target?.serviceWorker?.controller;
  if (!ctrl) {
    return false;
  }
  ctrl.postMessage({ type: "SSRA_LOGOUT_PURGE" });
  return true;
}

function timingSafeTokenMatch(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
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
  // CVE-2026-27978: Explicitly reject 'null' origin from sandboxed iframes
  if (input.originHeader && input.originHeader.trim().toLowerCase() === "null") {
    return { valid: false, reason: "CSRF_NULL_ORIGIN_REJECTED" };
  }
  if (!input.originHeader || input.originHeader !== input.allowedOrigin) {
    return { valid: false, reason: "CSRF_ORIGIN_MISMATCH" };
  }
  if (
    !input.csrfCookieToken ||
    !input.csrfHeaderToken ||
    !timingSafeTokenMatch(input.csrfCookieToken, input.csrfHeaderToken)
  ) {
    return { valid: false, reason: "CSRF_TOKEN_MISMATCH" };
  }
  return { valid: true };
}

const ALLOWED_LOGOUT_ALGS = new Set(["ES256", "RS256", "PS256", "EdDSA"]);
const CONSUMED_LOGOUT_JTIS = new Map<string, number>();

function decodeBase64UrlJson(segment: string): Record<string, unknown> | null {
  try {
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Validate an OIDC Back-Channel Logout 1.0 `logout_token` JWT (mitigating `CVE-2026-18569` unsigned logout bypass).
 */
export function verifyOidcBackchannelLogoutJwt(input: {
  readonly logoutToken: string;
  readonly expectedAudience: string;
  readonly expectedIssuer?: string;
  readonly nowMs?: number;
}): {
  readonly valid: boolean;
  readonly reason?: string;
  readonly sid?: string;
  readonly sub?: string;
} {
  const expectedIssuer = input.expectedIssuer ?? "https://sso.ssra.gov.ss/realms/ssra";
  const nowSec = Math.floor((input.nowMs ?? Date.now()) / 1000);
  const parts = input.logoutToken.trim().split(".");
  if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) {
    return { valid: false, reason: "UNSIGNED_OR_MALFORMED_LOGOUT_JWT" };
  }
  const header = decodeBase64UrlJson(parts[0]);
  const payload = decodeBase64UrlJson(parts[1]);
  if (!header || !payload) {
    return { valid: false, reason: "INVALID_LOGOUT_JWT_ENCODING" };
  }
  const alg = typeof header.alg === "string" ? header.alg : "";
  if (!ALLOWED_LOGOUT_ALGS.has(alg)) {
    return { valid: false, reason: "UNSUPPORTED_OR_NONE_LOGOUT_ALG_CVE_2026_18569" };
  }
  const jti = typeof payload.jti === "string" ? payload.jti : "";
  const iss = typeof payload.iss === "string" ? payload.iss : "";
  const aud = typeof payload.aud === "string" ? payload.aud : "";
  const sid = typeof payload.sid === "string" ? payload.sid : undefined;
  const sub = typeof payload.sub === "string" ? payload.sub : undefined;
  const iat = typeof payload.iat === "number" ? payload.iat : NaN;
  const exp = typeof payload.exp === "number" ? payload.exp : NaN;
  const events = payload.events as Record<string, unknown> | undefined;

  if (
    !jti ||
    iss !== expectedIssuer ||
    aud !== input.expectedAudience ||
    payload.nonce !== undefined ||
    !events ||
    typeof events["http://schemas.openid.net/event/backchannel-logout"] !== "object" ||
    (!sid && !sub) ||
    !Number.isFinite(iat) ||
    !Number.isFinite(exp) ||
    nowSec > exp ||
    Math.abs(nowSec - iat) > 120
  ) {
    return { valid: false, reason: "INVALID_BACKCHANNEL_LOGOUT_CLAIMS" };
  }
  for (const [k, expSec] of CONSUMED_LOGOUT_JTIS.entries()) {
    if (expSec < nowSec) CONSUMED_LOGOUT_JTIS.delete(k);
  }
  if (CONSUMED_LOGOUT_JTIS.has(jti)) {
    return { valid: false, reason: "REPLAYED_BACKCHANNEL_LOGOUT_JTI" };
  }
  CONSUMED_LOGOUT_JTIS.set(jti, exp);
  return {
    valid: true,
    ...(sid !== undefined ? { sid } : {}),
    ...(sub !== undefined ? { sub } : {}),
  };
}
