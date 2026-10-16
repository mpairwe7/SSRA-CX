/**
 * Next.js 16 `proxy.ts` (replaces legacy middleware.ts — Section 9.1, 9.4, ADR-010, ADR-012).
 *
 * Responsibilities:
 * 1. Generate per-request cryptographic CSP nonce + Trusted-Types + ASVS L2/L3 headers.
 * 2. Negotiate locale (`en`, `pga`, `ar` RTL) and text direction.
 * 3. Gate authenticated `/[locale]/(account)` routes on `httpOnly` server-side BFF session cookie.
 */

import type { LocaleCode } from "@ssra/contracts";
import { getTextDirection, PHASE1_LOCALES } from "@ssra/i18n";

export interface ProxyRequestContext {
  readonly pathname: string;
  readonly acceptLanguage?: string;
  readonly saveDataHeader?: string;
  readonly hasHttpOnlySessionCookie?: boolean;
  readonly nonce: string;
  readonly hostHeader?: string;
  readonly allowedHosts?: readonly string[];
  readonly nextResumeHeader?: string;
}

export interface ProxyDecision {
  readonly status: 200 | 307 | 400 | 401;
  readonly redirectLocation?: string;
  readonly locale: LocaleCode;
  readonly dir: "ltr" | "rtl";
  readonly lowDataMode: boolean;
  readonly headers: Record<string, string>;
}

const VALID_HOST_PATTERN = /^[a-zA-Z0-9.[\]:-]+$/;

export function buildSecurityHeaders(nonce: string, strictConsole = false): Record<string, string> {
  const cspDirectives = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src 'self' 'nonce-${nonce}'`,
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
    "require-trusted-types-for 'script'",
  ];
  if (strictConsole) {
    cspDirectives.push("upgrade-insecure-requests");
  }

  return {
    "Content-Security-Policy": cspDirectives.join("; "),
    "Cache-Control": "private, no-cache, no-store, must-revalidate",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), payment=(), usb=()",
  };
}

export function negotiateLocale(pathname: string, acceptLanguage?: string): LocaleCode {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0] as LocaleCode | undefined;
  if (first && (PHASE1_LOCALES as readonly string[]).includes(first)) {
    return first;
  }
  const lower = (acceptLanguage ?? "").toLowerCase();
  if (lower.includes("pga")) {
    return "pga";
  }
  if (lower.includes("ar")) {
    return "ar";
  }
  return "en";
}

export function executeProxy(req: ProxyRequestContext): ProxyDecision {
  const locale = negotiateLocale(req.pathname, req.acceptLanguage);
  const dir = getTextDirection(locale);
  const lowDataMode = req.saveDataHeader?.toLowerCase() === "on";
  const headers = {
    ...buildSecurityHeaders(req.nonce, false),
    "X-SSRA-Locale": locale,
    "X-SSRA-Dir": dir,
    "X-SSRA-Low-Data": lowDataMode ? "1" : "0",
  };

  // CVE-2026-27979: Block untrusted client `next-resume` header
  if (req.nextResumeHeader !== undefined && req.nextResumeHeader !== "") {
    return {
      status: 400,
      locale,
      dir,
      lowDataMode,
      headers,
    };
  }

  // CVE-2026-64649: Validate Host header grammar & optional allow-list
  if (req.hostHeader !== undefined) {
    const cleanHost = req.hostHeader.trim().toLowerCase();
    const allowlistFail =
      req.allowedHosts && req.allowedHosts.length > 0 && !req.allowedHosts.includes(cleanHost);
    if (!cleanHost || !VALID_HOST_PATTERN.test(cleanHost) || allowlistFail) {
      return {
        status: 400,
        locale,
        dir,
        lowDataMode,
        headers,
      };
    }
  }

  // Gate /[locale]/account routes on httpOnly server-side BFF session cookie
  const isAccountRoute = req.pathname.includes("/account") || req.pathname.includes("/(account)");
  if (isAccountRoute && !req.hasHttpOnlySessionCookie) {
    return {
      status: 401,
      locale,
      dir,
      lowDataMode,
      headers,
    };
  }

  return {
    status: 200,
    locale,
    dir,
    lowDataMode,
    headers,
  };
}
