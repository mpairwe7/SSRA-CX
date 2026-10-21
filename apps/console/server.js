/**
 * Production Node.js HTTP & BFF Server for SSRA Assist Staff, Admin & Auditor Console (`apps/console/server.js`).
 *
 * Uses the unified `FinalYearProject`-inspired Operations Console & `.staff-rail` Sidebar design system
 * (`packages/ui/ops-console.js`) with OWASP ASVS 5.0 Level 3 headers, method allowlisting, W3C traceparent,
 * and upstream timeout bounds.
 */

import crypto from "node:crypto";
import http from "node:http";
import { renderOpsDashboardHtml } from "../../packages/ui/ops-console.js";

const PORT = Number.parseInt(process.env.PORT ?? "3001", 10);
const HOSTNAME = process.env.HOSTNAME ?? "0.0.0.0";
const INTERNAL_API_URL = (process.env.INTERNAL_API_URL ?? "http://ssra-api:8000").replace(
  /\/$/,
  "",
);
const INTERNAL_RUNTIME_URL = (
  process.env.INTERNAL_RUNTIME_URL ?? "http://ssra-agent-runtime:8001"
).replace(/\/$/, "");
const VALID_HOST_RE = /^[A-Za-z0-9.[\]:-]+$/;
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "OPTIONS"]);
const ALLOWED_CONSOLE_READ_STAFF = new Set([
  "secops_admin",
  "ssra_admin",
  "stf_01",
  "stf_supervisor_02",
  "ssra_auditor",
]);
const ALLOWED_CONSOLE_WRITE_STAFF = new Set([
  "secops_admin",
  "ssra_admin",
  "stf_01",
  "stf_supervisor_02",
]);

async function readConsoleBody(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > 262_144) {
      throw new Error("PAYLOAD_TOO_LARGE");
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8");
}

function createTraceparent(existing) {
  if (typeof existing === "string" && /^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$/.test(existing)) {
    return existing;
  }
  const traceId = crypto.randomBytes(16).toString("hex");
  const spanId = crypto.randomBytes(8).toString("hex");
  return `00-${traceId}-${spanId}-01`;
}

function buildConsoleHeaders(nonce) {
  return {
    "Content-Security-Policy": `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
    "X-Nonce": nonce,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), geolocation=(), payment=(), usb=()",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Cache-Control": "private, no-cache, no-store, must-revalidate",
  };
}

const server = http.createServer(async (req, res) => {
  const nonce = crypto.randomBytes(16).toString("base64");
  const secHeaders = buildConsoleHeaders(nonce);
  const method = String(req.method ?? "GET").toUpperCase();
  if (!ALLOWED_METHODS.has(method)) {
    res.writeHead(405, {
      "Content-Type": "application/json",
      Allow: "GET, HEAD, POST, OPTIONS",
      ...secHeaders,
    });
    res.end(JSON.stringify({ error: "METHOD_NOT_ALLOWED" }));
    return;
  }

  const hostHeader = String(req.headers.host ?? "localhost");
  if (!VALID_HOST_RE.test(hostHeader)) {
    res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "INVALID_HOST_HEADER" }));
    return;
  }

  let pathname = "/";
  try {
    const rawTarget = req.url ?? "/";
    if (!rawTarget.startsWith("/")) {
      throw new Error("INVALID_TARGET");
    }
    pathname = new URL(rawTarget, "http://127.0.0.1").pathname;
  } catch {
    res.writeHead(400, { "Content-Type": "application/json", ...secHeaders });
    res.end(JSON.stringify({ error: "INVALID_REQUEST_TARGET" }));
    return;
  }

  const isGetOrHead = method === "GET" || method === "HEAD";
  const traceparent = createTraceparent(req.headers.traceparent);

  if (isGetOrHead && (pathname === "/healthz" || pathname === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json", ...secHeaders });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "ssra-console",
        internal_api_url: INTERNAL_API_URL,
        internal_runtime_url: INTERNAL_RUNTIME_URL,
      }),
    );
    return;
  }

  if (isGetOrHead && pathname === "/api/scorecard") {
    try {
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/analytics/cx-scorecard`, {
        headers: { Accept: "application/json", traceparent },
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "unavailable" }));
    }
    return;
  }

  if (pathname === "/api/flags") {
    const callerStaff = String(req.headers["x-ssra-staff-id"] ?? "").trim();
    const allowedSet = method === "POST" ? ALLOWED_CONSOLE_WRITE_STAFF : ALLOWED_CONSOLE_READ_STAFF;
    if (!allowedSet.has(callerStaff)) {
      res.writeHead(403, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: "STAFF_AUTHORIZATION_REQUIRED" }));
      return;
    }
    try {
      const bodyStr = method === "POST" ? await readConsoleBody(req) : undefined;
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/admin/feature-flags`, {
        method,
        headers: {
          Accept: "application/json",
          ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
          "X-SSRA-Staff-Id": callerStaff,
          traceparent,
        },
        body: bodyStr,
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "unavailable" }));
    }
    return;
  }

  if (pathname === "/api/kill-switches") {
    const callerStaff = String(req.headers["x-ssra-staff-id"] ?? "").trim();
    const allowedSet = method === "POST" ? ALLOWED_CONSOLE_WRITE_STAFF : ALLOWED_CONSOLE_READ_STAFF;
    if (!allowedSet.has(callerStaff)) {
      res.writeHead(403, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: "STAFF_AUTHORIZATION_REQUIRED" }));
      return;
    }
    try {
      const bodyStr = method === "POST" ? await readConsoleBody(req) : undefined;
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/admin/kill-switches`, {
        method,
        headers: {
          Accept: "application/json",
          ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
          "X-SSRA-Staff-Id": callerStaff,
          traceparent,
        },
        body: bodyStr,
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "unavailable" }));
    }
    return;
  }

  if (isGetOrHead && pathname === "/v1/runtime/stack-status") {
    try {
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/runtime/stack-status`, {
        headers: { Accept: "application/json", traceparent },
        signal: AbortSignal.timeout(15_000),
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "unavailable" }));
    }
    return;
  }

  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...secHeaders });
  res.end(renderOpsDashboardHtml(pathname, nonce));
});

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-console listening on http://${HOSTNAME}:${PORT}\n`);
});
