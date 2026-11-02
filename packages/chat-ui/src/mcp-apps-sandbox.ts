/**
 * MCP Apps Sandboxed Iframe Policy (`packages/chat-ui/src/mcp-apps-sandbox.ts` — Section 9.3).
 *
 * "If MCP Apps are adopted later, render them only in a sandboxed iframe from allow-listed servers."
 * Security Invariant:
 * 1. Only allow-listed HTTPS origins (`https://apps.ssra.gov.ss`) are permitted.
 * 2. The `sandbox` attribute NEVER combines `allow-scripts` with `allow-same-origin`.
 */

const ALLOWED_MCP_APP_ORIGINS = new Set(["https://apps.ssra.gov.ss"]);
const DANGEROUS_SCHEME_IN_PARAM_RE = /(?:javascript|data|vbscript|file):/i;
const ENCODED_TRAVERSAL_RE = /%(?:2e|2f|5c|00)/i;
export const MCP_APP_PERMISSIONS_POLICY =
  "geolocation 'none'; microphone 'none'; camera 'none'; payment 'none'; usb 'none'" as const;
export const MCP_APP_CSP =
  "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'" as const;

export interface SandboxedMcpAppDescriptor {
  readonly allowed: boolean;
  readonly src: string | null;
  readonly sandboxAttr: "allow-scripts";
  readonly referrerPolicy: "no-referrer";
  readonly allowAttr: typeof MCP_APP_PERMISSIONS_POLICY;
  readonly cspAttr: typeof MCP_APP_CSP;
  readonly reason?: string;
}

export function validateMcpAppIframe(candidateUrl: string): SandboxedMcpAppDescriptor {
  try {
    if (
      !candidateUrl ||
      candidateUrl.length > 1024 ||
      ENCODED_TRAVERSAL_RE.test(candidateUrl) ||
      DANGEROUS_SCHEME_IN_PARAM_RE.test(candidateUrl)
    ) {
      return {
        allowed: false,
        src: null,
        sandboxAttr: "allow-scripts",
        referrerPolicy: "no-referrer",
        allowAttr: MCP_APP_PERMISSIONS_POLICY,
        cspAttr: MCP_APP_CSP,
        reason: "UNSAFE_MCP_APP_URL_PAYLOAD",
      };
    }
    const parsed = new URL(candidateUrl);
    if (
      parsed.protocol !== "https:" ||
      !ALLOWED_MCP_APP_ORIGINS.has(parsed.origin) ||
      parsed.username !== "" ||
      parsed.password !== "" ||
      (parsed.port !== "" && parsed.port !== "443") ||
      parsed.pathname.includes("..") ||
      parsed.pathname.includes("//")
    ) {
      return {
        allowed: false,
        src: null,
        sandboxAttr: "allow-scripts",
        referrerPolicy: "no-referrer",
        allowAttr: MCP_APP_PERMISSIONS_POLICY,
        cspAttr: MCP_APP_CSP,
        reason: "UNALLOWLISTED_MCP_APP_ORIGIN",
      };
    }
    return {
      allowed: true,
      src: parsed.toString(),
      sandboxAttr: "allow-scripts",
      referrerPolicy: "no-referrer",
      allowAttr: MCP_APP_PERMISSIONS_POLICY,
      cspAttr: MCP_APP_CSP,
    };
  } catch {
    return {
      allowed: false,
      src: null,
      sandboxAttr: "allow-scripts",
      referrerPolicy: "no-referrer",
      allowAttr: MCP_APP_PERMISSIONS_POLICY,
      cspAttr: MCP_APP_CSP,
      reason: "INVALID_MCP_APP_URL",
    };
  }
}
