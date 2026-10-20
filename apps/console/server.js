/**
 * Production Node.js HTTP & BFF Server for SSRA Assist Staff, Admin & Auditor Console (`apps/console/server.js`).
 */

import crypto from "node:crypto";
import http from "node:http";

const PORT = Number.parseInt(process.env.PORT ?? "3001", 10);
const HOSTNAME = process.env.HOSTNAME ?? "0.0.0.0";
const INTERNAL_API_URL = (process.env.INTERNAL_API_URL ?? "http://ssra-api:8000").replace(
  /\/$/,
  "",
);
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

function renderConsoleWorkbenchHtml(pathname, nonce) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SSRA Assist — Staff, Admin &amp; Auditor Console</title>
  <style nonce="${nonce}">
    body { margin: 0; font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; min-height: 100dvh; display: flex; flex-direction: column; }
    nav { background: #1e293b; padding: 0.85rem 1.25rem; display: flex; gap: 1rem; align-items: center; border-bottom: 1px solid #334155; }
    nav a { color: #93c5fd; text-decoration: none; font-weight: 600; }
    main { max-width: 68rem; width: 100%; margin: 1.5rem auto; padding: 0 1rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: 1rem; box-sizing: border-box; }
    .panel { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }
    pre { background: #0f172a; padding: 0.75rem; border-radius: 0.5rem; overflow-x: auto; font-size: 0.85rem; }
  </style>
</head>
<body>
  <nav aria-label="SSRA Console Role Navigation">
    <strong>SSRA Assist Console</strong>
    <a href="/queue">Staff Queue (ssra_staff)</a>
    <a href="/admin">Admin Control Plane (ssra_admin)</a>
    <a href="/auditor">Forensic Replay &amp; Scorecard (ssra_auditor)</a>
  </nav>
  <main id="ssra-console-root" data-route="${pathname}">
    <section class="panel" aria-label="Omnichannel Staff Queue &amp; Maker-Checker">
      <h2>Staff Queue &amp; Copilot Inbox</h2>
      <p>Route: <code>${pathname}</code> — RLS-scoped officer takeover, cited reply drafts, and T3 two-officer maker-checker review.</p>
    </section>
    <section class="panel" aria-label="2026 Agentic CX Scorecard">
      <h2>Live Agentic CX Scorecard</h2>
      <pre id="ssra-scorecard-view">Loading /api/scorecard...</pre>
    </section>
  </main>
  <script nonce="${nonce}">
    fetch("/api/scorecard")
      .then((r) => r.json())
      .then((d) => {
        const el = document.getElementById("ssra-scorecard-view");
        if (el) el.textContent = JSON.stringify(d, null, 2);
      })
      .catch(() => {});
  </script>
</body>
</html>`;
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

  if (req.method === "GET" && (pathname === "/healthz" || pathname === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json", ...secHeaders });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "ssra-console",
        internal_api_url: INTERNAL_API_URL,
      }),
    );
    return;
  }

  if (req.method === "GET" && pathname === "/api/scorecard") {
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

  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...secHeaders });
  res.end(renderConsoleWorkbenchHtml(pathname, nonce));
});

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-console listening on http://${HOSTNAME}:${PORT}\n`);
});
