/**
 * Production Node.js HTTP & BFF Server for SSRA Assist Staff, Admin & Auditor Console (`apps/console/server.js`).
 *
 * Uses the unified `FinalYearProject`-inspired Operations Console & `.staff-rail` Sidebar design system
 * (`packages/ui/ops-console.js`).
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

function buildConsoleHeaders(nonce) {
  return {
    "Content-Security-Policy": `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; connect-src 'self'; frame-ancestors 'none'`,
    "X-Nonce": nonce,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Cache-Control": "private, no-cache, no-store, must-revalidate",
  };
}

const server = http.createServer(async (req, res) => {
  const nonce = crypto.randomBytes(16).toString("base64");
  const secHeaders = buildConsoleHeaders(nonce);
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

  const isGetOrHead = req.method === "GET" || req.method === "HEAD";

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
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/analytics/cx-scorecard`);
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
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/runtime/stack-status`);
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
