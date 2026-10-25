/**
 * Keycloak 26.4.11 OIDC + PKCE S256 + WebAuthn Passkey (`urn:ssra:acr:passkey`) Sign-In,
 * Sign-Up (`prompt=create`), Callback & Role Routing for Admin, Staff, and Auditor Dashboards
 * (`apps/console/src/oidc-keycloak.ts`).
 *
 * Ported and hardened from `FinalYearProject/App/frontend/src/lib/{oidc,oidcFlow,authSession}.ts`
 * and `FinalYearProject/App/frontend/src/app/{signin,signup,signin/callback}/page.tsx`
 * for SSRA Assist (October 2026 standards: OAuth 2.1 §4.1, RFC 7636 PKCE S256, RFC 9126 PAR,
 * RFC 9449 DPoP, OIDC Core 1.0 §3.1.2.1, OIDC Initiating User Registration 1.0 `prompt=create`,
 * W3C WebAuthn Level 3 `urn:ssra:acr:passkey`, and ADR-012).
 */

import {
  isStaffRole,
  type StaffDestination,
  type StaffRole,
  staffDestinationsFor,
  staffLandingPath,
} from "./roles-and-audit.js";

export const KEYCLOAK_CONSOLE_OIDC_CONFIG = {
  realm: "ssra",
  issuer: "https://sso.ssra.gov.ss/realms/ssra",
  consoleClientId: "ssra-staff-console",
  webBffClientId: "ssra-web-bff",
  requiredStaffAcr: "urn:ssra:acr:passkey",
  pkceMethod: "S256",
  scope: "openid profile email",
  redirectPath: "/signin/callback",
  postLogoutPath: "/signin",
} as const;

export const PKCE_VERIFIER_STORAGE_KEY = "ssra_pkce_verifier";
export const OIDC_STATE_STORAGE_KEY = "ssra_oidc_state";
export const OIDC_NONCE_STORAGE_KEY = "ssra_oidc_nonce";
export const OIDC_RETURN_TO_STORAGE_KEY = "ssra_oidc_return_to";

export type OidcAuthorizeMode = "signin" | "signup";

export interface KeycloakOidcEndpoints {
  readonly issuer: string;
  readonly discoveryUrl: string;
  readonly authorizationEndpoint: string;
  readonly registrationEndpoint: string;
  readonly tokenEndpoint: string;
  readonly userinfoEndpoint: string;
  readonly endSessionEndpoint: string;
  readonly jwksUri: string;
  readonly pushedAuthorizationRequestEndpoint: string;
}

/**
 * Strip a pasted or stored JWT down to strict base64url + dot characters (`A-Z`, `a-z`, `0-9`, `-`, `_`, `.`).
 * Deliberately avoids NFKC normalization so a truncated ellipsis (`…`) is dropped instead of turned into `...`.
 */
export function sanitizeAuthToken(raw: string): string {
  let out = "";
  for (const ch of raw) {
    const cp = ch.codePointAt(0) ?? 0;
    const keep =
      (cp >= 0x30 && cp <= 0x39) ||
      (cp >= 0x41 && cp <= 0x5a) ||
      (cp >= 0x61 && cp <= 0x7a) ||
      cp === 0x2d ||
      cp === 0x5f ||
      cp === 0x2e;
    if (keep) out += ch;
  }
  return out;
}

/** Shape check only — cryptographic signature verification always runs on the server. */
export function looksLikeJwt(token: string): boolean {
  const clean = sanitizeAuthToken(token);
  const parts = clean.split(".");
  return (
    parts.length === 3 &&
    (parts[0]?.length ?? 0) > 0 &&
    (parts[1]?.length ?? 0) > 0 &&
    (parts[2]?.length ?? 0) > 0
  );
}

const PKCE_CHALLENGE_B64URL_RE = /^[A-Za-z0-9_-]{43,128}$/;
const PKCE_VERIFIER_RFC7636_RE = /^[A-Za-z0-9._~-]{43,128}$/;
const OPAQUE_TOKEN_NO_SPACE_RE = /^[\x21-\x7E]{32,256}$/;

/**
 * Constant-time string comparison (mitigates CWE-208 timing side-channels on OAuth `state`, `nonce`, and PKCE checks per GHSA-xpv3-w29h-x7cv).
 */
export function timingSafeEqualStrings(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const len = Math.max(a.length, b.length);
  let diff = a.length ^ b.length;
  for (let i = 0; i < len; i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

function hasAsciiControlChar(value: string): boolean {
  for (let i = 0; i < value.length; i++) {
    const code = value.charCodeAt(i);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

/**
 * Validate that a `returnTo` redirect target is a safe, same-origin relative path
 * starting with a single `/` (mitigates CWE-601 Open Redirect, including WHATWG URL
 * tab/newline stripping bypasses such as `/\t/evil.com` or `//evil.com`).
 */
export function sanitizeReturnTo(raw: string | null | undefined): string | undefined {
  if (!raw || typeof raw !== "string") return undefined;
  const trimmed = raw.trim();
  if (hasAsciiControlChar(trimmed)) return undefined;
  let decoded = trimmed;
  try {
    decoded = decodeURIComponent(trimmed);
  } catch {
    return undefined;
  }
  if (
    !trimmed.startsWith("/") ||
    trimmed.startsWith("//") ||
    trimmed.includes("\\") ||
    !decoded.startsWith("/") ||
    decoded.startsWith("//") ||
    decoded.includes("\\") ||
    hasAsciiControlChar(decoded)
  ) {
    return undefined;
  }
  if (/^\/[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed) || /^\/[a-zA-Z][a-zA-Z0-9+.-]*:/.test(decoded)) {
    return undefined;
  }
  try {
    const base = "https://ssra-same-origin.internal";
    const parsed = new URL(trimmed, base);
    if (
      parsed.origin !== base ||
      !parsed.pathname.startsWith("/") ||
      parsed.pathname.startsWith("//")
    ) {
      return undefined;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return undefined;
  }
}

/**
 * Build deterministic Keycloak 26.4.11 OIDC endpoints from a realm issuer URL,
 * enforcing HTTPS in production (`sslRequired: "all"`).
 */
export function buildKeycloakOidcEndpoints(
  issuer: string = KEYCLOAK_CONSOLE_OIDC_CONFIG.issuer,
  options?: { readonly allowLoopbackHttp?: boolean | undefined },
): KeycloakOidcEndpoints {
  const base = issuer.trim().replace(/\/+$/, "");
  let parsed: URL;
  try {
    parsed = new URL(base);
  } catch {
    throw new Error(`Invalid Keycloak OIDC issuer URL: ${issuer}`);
  }
  const isLoopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost";
  if (
    parsed.protocol !== "https:" &&
    !(options?.allowLoopbackHttp && parsed.protocol === "http:" && isLoopback)
  ) {
    throw new Error("Keycloak OIDC issuer must use https:// (sslRequired=all)");
  }
  if (!parsed.pathname.includes("/realms/")) {
    throw new Error("Keycloak OIDC issuer must include /realms/<realm>");
  }
  const oidcBase = `${base}/protocol/openid-connect`;
  return {
    issuer: base,
    discoveryUrl: `${base}/.well-known/openid-configuration`,
    authorizationEndpoint: `${oidcBase}/auth`,
    registrationEndpoint: `${oidcBase}/registrations`,
    tokenEndpoint: `${oidcBase}/token`,
    userinfoEndpoint: `${oidcBase}/userinfo`,
    endSessionEndpoint: `${oidcBase}/logout`,
    jwksUri: `${oidcBase}/certs`,
    pushedAuthorizationRequestEndpoint: `${oidcBase}/ext/par/request`,
  };
}

/**
 * Validate that an OIDC `redirect_uri` uses HTTPS (or loopback HTTP), has no `@` userinfo,
 * no query/fragment, and ends with `/signin/callback` (OAuth 2.1 §4.1.3).
 */
export function validateOidcRedirectUri(redirectUri: string): string {
  const trimmed = (redirectUri || "").trim();
  if (!trimmed || trimmed.includes("*")) {
    throw new Error("Invalid OIDC redirect_uri: wildcards or empty values are forbidden");
  }
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error(`Invalid OIDC redirect_uri: ${redirectUri}`);
  }
  if (parsed.username || parsed.password) {
    throw new Error("Invalid OIDC redirect_uri: userinfo credentials are forbidden");
  }
  const isLoopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost";
  if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && isLoopback)) {
    throw new Error("Invalid OIDC redirect_uri: must use https:// (or loopback http://)");
  }
  if (parsed.pathname !== "/signin/callback" || parsed.search || parsed.hash) {
    throw new Error("Invalid OIDC redirect_uri: path must be exact /signin/callback");
  }
  return parsed.toString();
}

export interface BuildKeycloakAuthUrlParams {
  readonly issuer?: string | undefined;
  readonly clientId?: string | undefined;
  readonly redirectUri: string;
  readonly codeChallenge: string;
  readonly state: string;
  readonly nonce?: string | undefined;
  readonly mode?: OidcAuthorizeMode | undefined;
  readonly prompt?: "login" | "select_account" | undefined;
  readonly requirePasskeyAcr?: boolean | undefined;
  readonly returnTo?: string | null | undefined;
  readonly loginHint?: string | undefined;
}

/**
 * Construct a Keycloak 26.4.11 OAuth 2.1 Authorization Code + PKCE `S256` URL
 * for `/signin` (`acr_values=urn:ssra:acr:passkey` or `prompt=login`) and `/signup` (`prompt=create` + `screen_hint=signup`).
 */
export function buildKeycloakAuthorizationUrl(params: BuildKeycloakAuthUrlParams): {
  readonly url: string;
  readonly sanitizedReturnTo: string | undefined;
  readonly mode: OidcAuthorizeMode;
  readonly acrValues: string | null;
} {
  const safeRedirectUri = validateOidcRedirectUri(params.redirectUri);
  const cleanChallenge = (params.codeChallenge || "").trim();
  if (!PKCE_CHALLENGE_B64URL_RE.test(cleanChallenge)) {
    throw new Error(
      "PKCE S256 code_challenge must be 43..128 base64url characters without padding",
    );
  }
  const cleanState = (params.state || "").trim();
  if (!OPAQUE_TOKEN_NO_SPACE_RE.test(cleanState)) {
    throw new Error("OIDC CSRF state parameter must be 32..256 printable ASCII characters");
  }
  const cleanNonce = params.nonce?.trim();
  if (
    cleanNonce !== undefined &&
    cleanNonce.length > 0 &&
    !OPAQUE_TOKEN_NO_SPACE_RE.test(cleanNonce)
  ) {
    throw new Error("OIDC nonce parameter must be 32..256 printable ASCII characters");
  }
  const endpoints = buildKeycloakOidcEndpoints(
    params.issuer ?? KEYCLOAK_CONSOLE_OIDC_CONFIG.issuer,
    { allowLoopbackHttp: true },
  );
  const mode: OidcAuthorizeMode = params.mode ?? "signin";
  const clientId = (params.clientId ?? KEYCLOAK_CONSOLE_OIDC_CONFIG.consoleClientId).trim();
  const requirePasskey =
    params.requirePasskeyAcr ?? clientId === KEYCLOAK_CONSOLE_OIDC_CONFIG.consoleClientId;
  const acrValues = requirePasskey ? KEYCLOAK_CONSOLE_OIDC_CONFIG.requiredStaffAcr : null;

  const url = new URL(endpoints.authorizationEndpoint);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", safeRedirectUri);
  url.searchParams.set("scope", KEYCLOAK_CONSOLE_OIDC_CONFIG.scope);
  url.searchParams.set("code_challenge", params.codeChallenge.trim());
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("state", params.state.trim());
  if (params.nonce?.trim()) {
    url.searchParams.set("nonce", params.nonce.trim());
  }
  if (acrValues) {
    url.searchParams.set("acr_values", acrValues);
  }
  if (mode === "signup") {
    url.searchParams.set("prompt", "create");
    url.searchParams.set("screen_hint", "signup");
  } else if (params.prompt) {
    url.searchParams.set("prompt", params.prompt);
  }
  if (params.loginHint?.trim()) {
    url.searchParams.set("login_hint", params.loginHint.trim());
  }

  return {
    url: url.toString(),
    sanitizedReturnTo: sanitizeReturnTo(params.returnTo),
    mode,
    acrValues,
  };
}

export interface OidcCallbackValidationInput {
  readonly code?: string | null | undefined;
  readonly state?: string | null | undefined;
  readonly expectedState?: string | null | undefined;
  readonly pkceVerifier?: string | null | undefined;
  readonly iss?: string | null | undefined;
  readonly expectedIssuer?: string | null | undefined;
  readonly error?: string | null | undefined;
  readonly errorDescription?: string | null | undefined;
  readonly resolvedRole?: string | null | undefined;
  readonly returnTo?: string | null | undefined;
}

export interface OidcCallbackValidationResult {
  readonly valid: boolean;
  readonly phase: "done" | "error";
  readonly errorReason: string | null;
  readonly detailMessage: string;
  readonly targetPath: string;
  readonly allowedDestinations: readonly StaffDestination[];
}

/**
 * Validate OIDC `/signin/callback` query parameters against stored CSRF `state` (constant-time),
 * RFC 9207 `iss` (OAuth Mix-Up defense), and RFC 7636 PKCE `code_verifier`,
 * and resolve the role-scoped dashboard landing route (`/admin`, `/agent`, `/analytics`, or `/en`).
 */
export function validateOidcCallbackParams(
  input: OidcCallbackValidationInput,
): OidcCallbackValidationResult {
  if (input.error) {
    const desc = input.errorDescription?.trim() || "the identity provider refused the request";
    return {
      valid: false,
      phase: "error",
      errorReason: "PROVIDER_ERROR",
      detailMessage: `${input.error}: ${desc}`,
      targetPath: "/signin",
      allowedDestinations: [],
    };
  }
  if (!input.code?.trim()) {
    return {
      valid: false,
      phase: "error",
      errorReason: "MISSING_AUTH_CODE",
      detailMessage: "The identity provider returned no authorization code.",
      targetPath: "/signin",
      allowedDestinations: [],
    };
  }
  const cleanState = input.state?.trim() ?? "";
  const cleanExpectedState = input.expectedState?.trim() ?? "";
  if (
    !cleanState ||
    !cleanExpectedState ||
    !timingSafeEqualStrings(cleanState, cleanExpectedState)
  ) {
    return {
      valid: false,
      phase: "error",
      errorReason: "CSRF_STATE_MISMATCH",
      detailMessage:
        "State mismatch — this sign-in did not start in this browser tab. Start again from /signin.",
      targetPath: "/signin",
      allowedDestinations: [],
    };
  }
  if (input.iss !== undefined && input.iss !== null) {
    const cleanIss = input.iss.trim().replace(/\/+$/, "");
    const expectedIss = (input.expectedIssuer ?? KEYCLOAK_CONSOLE_OIDC_CONFIG.issuer)
      .trim()
      .replace(/\/+$/, "");
    if (!cleanIss || !timingSafeEqualStrings(cleanIss, expectedIss)) {
      return {
        valid: false,
        phase: "error",
        errorReason: "RFC9207_ISSUER_MISMATCH",
        detailMessage:
          "Issuer mismatch (RFC 9207) — callback issuer does not match the configured SSRA Keycloak realm.",
        targetPath: "/signin",
        allowedDestinations: [],
      };
    }
  }
  const verifier = input.pkceVerifier?.trim() ?? "";
  if (!PKCE_VERIFIER_RFC7636_RE.test(verifier)) {
    return {
      valid: false,
      phase: "error",
      errorReason: "MISSING_OR_INVALID_PKCE_VERIFIER",
      detailMessage: "The PKCE S256 code_verifier is missing or invalid. Start the sign-in again.",
      targetPath: "/signin",
      allowedDestinations: [],
    };
  }

  const safeReturnTo = sanitizeReturnTo(input.returnTo);
  const staff = isStaffRole(input.resolvedRole);
  const targetPath = staff ? staffLandingPath(input.resolvedRole) : safeReturnTo || "/en";

  return {
    valid: true,
    phase: "done",
    errorReason: null,
    detailMessage: staff
      ? `Keycloak PKCE & state verified for role ${input.resolvedRole}. Routing to ${targetPath}.`
      : "Keycloak PKCE & state verified. Routing to the taxpayer assistant.",
    targetPath,
    allowedDestinations: staffDestinationsFor(input.resolvedRole),
  };
}

export interface ConsoleSignInRoleOption {
  readonly role: StaffRole;
  readonly label: string;
  readonly badge: string;
  readonly landingPath: "/admin" | "/agent" | "/analytics";
  readonly description: string;
}

export const CONSOLE_SIGNIN_ROLE_OPTIONS: readonly ConsoleSignInRoleOption[] = [
  {
    role: "ssra_admin",
    label: "Administrator (ssra_admin)",
    badge: "AD",
    landingPath: "/admin",
    description:
      "Operations overview, 5-step degradation ladder, 6-step knowledge release governance, and JIT passkey elevation (/admin).",
  },
  {
    role: "ssra_staff",
    label: "Tax Agent & Officer (ssra_staff)",
    badge: "ST",
    landingPath: "/agent",
    description:
      "One-case-at-a-time escalation queue, Cited Copilot drafts, phone call takeover desk, and T3 two-officer maker-checker (/agent).",
  },
  {
    role: "ssra_auditor",
    label: "Forensic & QA Auditor (ssra_auditor)",
    badge: "AU",
    landingPath: "/analytics",
    description:
      "Read-only Separation of Duties (ISO/IEC 42001 Clause 9.2): WORM hash-chain & Merkle seal inspector, forensic turn replay, and QA rubric scoring (/analytics).",
  },
] as const;

export const CONSOLE_SIGNUP_BENEFITS = [
  {
    title: "Ask without an account (T0 Public Assistant)",
    body: "General South Sudan tax questions, PAYE/WHT calculators, official channel checks, and client-side document preflight all work signed out with zero PII stored.",
  },
  {
    title: "Taxpayer e-Tax continuity (T1–T3 Progressive Proofing)",
    body: "Registering a taxpayer account links saved guidance preferences and enables deterministic TIN + OTP step-up verification outside the LLM.",
  },
  {
    title: "SSRA employees, officers, administrators & auditors",
    body: "Staff (ssra_staff), administrator (ssra_admin), and read-only auditor (ssra_auditor) roles are provisioned by SSRA Identity Governance in the ssra Keycloak realm with mandatory FIDO2 passkey enrollment. Staff accounts are never self-assigned on /signup — sign in directly on /signin.",
  },
] as const;

export function buildSignInPageViewModel(params?: {
  readonly selectedRole?: StaffRole | undefined;
  readonly returnTo?: string | null | undefined;
}) {
  const selectedRole: StaffRole = params?.selectedRole ?? "ssra_admin";
  const roleOption =
    CONSOLE_SIGNIN_ROLE_OPTIONS.find((r) => r.role === selectedRole) ??
    CONSOLE_SIGNIN_ROLE_OPTIONS[0];
  return {
    title: "Sign in",
    subtitle: "South Sudan Revenue Authority (SSRA) — Operations, Staff & Audit Console",
    keycloakRealm: KEYCLOAK_CONSOLE_OIDC_CONFIG.realm,
    keycloakIssuer: KEYCLOAK_CONSOLE_OIDC_CONFIG.issuer,
    keycloakClientId: KEYCLOAK_CONSOLE_OIDC_CONFIG.consoleClientId,
    requiredAcr: KEYCLOAK_CONSOLE_OIDC_CONFIG.requiredStaffAcr,
    selectedRole,
    targetLandingPath: sanitizeReturnTo(params?.returnTo) ?? roleOption?.landingPath ?? "/admin",
    roleOptions: CONSOLE_SIGNIN_ROLE_OPTIONS,
  };
}

export function buildSignUpPageViewModel() {
  return {
    title: "Create an account",
    subtitle: "South Sudan Revenue Authority (SSRA) — Identity & Role Provisioning",
    keycloakRealm: KEYCLOAK_CONSOLE_OIDC_CONFIG.realm,
    keycloakIssuer: KEYCLOAK_CONSOLE_OIDC_CONFIG.issuer,
    benefits: CONSOLE_SIGNUP_BENEFITS,
  };
}
