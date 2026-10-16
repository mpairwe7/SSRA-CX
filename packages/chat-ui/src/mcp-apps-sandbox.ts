/**
 * MCP Apps Sandboxed Iframe Policy (`packages/chat-ui/src/mcp-apps-sandbox.ts` — Section 9.3).
 *
 * "If MCP Apps are adopted later, render them only in a sandboxed iframe from allow-listed servers."
 * Security Invariant:
 * 1. Only allow-listed HTTPS origins (`https://apps.ssra.gov.ss`) are permitted.
 * 2. The `sandbox` attribute NEVER combines `allow-scripts` with `allow-same-origin`.
 */

const ALLOWED_MCP_APP_ORIGINS = new Set(["https://apps.ssra.gov.ss"]);

export interface SandboxedMcpAppDescriptor {
  readonly allowed: boolean;
  readonly src: string | null;
  readonly sandboxAttr: "allow-scripts";
  readonly referrerPolicy: "no-referrer";
  readonly reason?: string;
}

export function validateMcpAppIframe(candidateUrl: string): SandboxedMcpAppDescriptor {
  try {
    const parsed = new URL(candidateUrl);
    if (parsed.protocol !== "https:" || !ALLOWED_MCP_APP_ORIGINS.has(parsed.origin)) {
      return {
        allowed: false,
        src: null,
        sandboxAttr: "allow-scripts",
        referrerPolicy: "no-referrer",
        reason: "UNALLOWLISTED_MCP_APP_ORIGIN",
      };
    }
    return {
      allowed: true,
      src: parsed.toString(),
      sandboxAttr: "allow-scripts",
      referrerPolicy: "no-referrer",
    };
  } catch {
    return {
      allowed: false,
      src: null,
      sandboxAttr: "allow-scripts",
      referrerPolicy: "no-referrer",
      reason: "INVALID_MCP_APP_URL",
    };
  }
}
