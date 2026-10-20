/**
 * Production Node.js HTTP & BFF Server for SSRA Assist Taxpayer Web PWA (`apps/web/server.js`).
 *
 * Enforces:
 * - Per-request cryptographic nonce CSP (`'nonce-...'`, `'strict-dynamic'`, `worker-src 'self'`)
 * - Government security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`)
 * - Internal Docker network BFF proxying to `INTERNAL_API_URL` (`ssra-api:8000`) and `INTERNAL_RUNTIME_URL` (`ssra-agent-runtime:8001`)
 */

import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number.parseInt(process.env.PORT ?? "3000", 10);
const HOSTNAME = process.env.HOSTNAME ?? "0.0.0.0";
const INTERNAL_API_URL = (process.env.INTERNAL_API_URL ?? "http://ssra-api:8000").replace(
  /\/$/,
  "",
);
const INTERNAL_RUNTIME_URL = (
  process.env.INTERNAL_RUNTIME_URL ?? "http://ssra-agent-runtime:8001"
).replace(/\/$/, "");

const SUPPORTED_LOCALES = new Set(["en", "pga", "ar", "din", "nus", "bfa", "zne", "shk"]);

function buildSecurityHeaders(nonce) {
  return {
    "Content-Security-Policy": `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; connect-src 'self'; img-src 'self' data:; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
    "X-Nonce": nonce,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(self), camera=()",
    "Cache-Control": "private, no-cache, no-store, must-revalidate",
  };
}

function renderPwaShellHtml(locale, nonce) {
  const dir = locale === "ar" ? "rtl" : "ltr";
  return `<!DOCTYPE html>
<html lang="${locale}" dir="${dir}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>SSRA Assist — South Sudan Revenue Authority Taxpayer Portal</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <style nonce="${nonce}">
    :root {
      --bg: oklch(98.5% 0.004 250);
      --fg: oklch(18% 0.02 250);
      --brand: oklch(42% 0.14 250);
      --surface: oklch(100% 0 0);
      --border: oklch(88% 0.01 250);
    }
    body { margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); min-height: 100dvh; display: flex; flex-direction: column; }
    header { background: var(--brand); color: #fff; padding: 1rem 1.25rem; display: flex; justify-content: space-between; align-items: center; }
    main { max-width: 52rem; width: 100%; margin: 1.5rem auto; padding: 0 1rem; flex: 1; box-sizing: border-box; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1rem; }
    .banner { background: oklch(94% 0.05 85); border-left: 4px solid oklch(65% 0.16 70); padding: 0.75rem 1rem; border-radius: 0.5rem; margin-bottom: 1rem; font-size: 0.92rem; }
  </style>
</head>
<body>
  <header>
    <strong>SSRA Assist (NRA South Sudan)</strong>
    <span>Locale: ${locale.toUpperCase()}</span>
  </header>
  <main>
    <div class="banner" role="status">
      <strong>March 2026 Cash-Free Directive:</strong> All SSRA tax payments are processed exclusively through <a href="https://etax.nra.gov.ss/">https://etax.nra.gov.ss/</a> and designated commercial banks. Never pay cash to an individual collector.
    </div>
    <section class="card" aria-label="SSRA Assist Taxpayer Chat">
      <h1>SSRA Assist — Grounded Tax, TIN, TCC &amp; Customs Guidance</h1>
      <p>Ask in English (<code>en</code>), Juba Arabic (<code>pga</code>), Arabic (<code>ar</code>), or Dinka (<code>din</code>).</p>
    </section>
  </main>
</body>
</html>`;
}

async function readRequestBody(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > 1_048_576) {
      throw new Error("PAYLOAD_TOO_LARGE");
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8");
}

const server = http.createServer(async (req, res) => {
  const nonce = crypto.randomBytes(16).toString("base64");
  const secHeaders = buildSecurityHeaders(nonce);
  const urlObj = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
  const pathname = urlObj.pathname;

  if (req.method === "GET" && (pathname === "/healthz" || pathname === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json", ...secHeaders });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "ssra-web",
        internal_api_url: INTERNAL_API_URL,
        internal_runtime_url: INTERNAL_RUNTIME_URL,
      }),
    );
    return;
  }

  if (req.method === "GET" && pathname === "/manifest.webmanifest") {
    res.writeHead(200, { "Content-Type": "application/manifest+json", ...secHeaders });
    res.end(
      JSON.stringify({
        name: "SSRA Assist — South Sudan Revenue Authority",
        short_name: "SSRA Assist",
        start_url: "/en",
        display: "standalone",
        background_color: "#f8fafc",
        theme_color: "#0f3d75",
      }),
    );
    return;
  }

  if (req.method === "GET" && pathname === "/sw.js") {
    const swPath = path.join(__dirname, "public", "sw.js");
    const swContent = fs.existsSync(swPath)
      ? fs.readFileSync(swPath, "utf-8")
      : "self.addEventListener('install', () => self.skipWaiting());";
    res.writeHead(200, {
      "Content-Type": "application/javascript; charset=utf-8",
      ...secHeaders,
    });
    res.end(swContent);
    return;
  }

  if (req.method === "GET" && pathname === "/api/status") {
    try {
      const upstream = await fetch(`${INTERNAL_API_URL}/v1/admin/public-status`, {
        headers: { Accept: "application/json" },
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { "Content-Type": "application/json", ...secHeaders });
      res.end(text);
    } catch {
      res.writeHead(503, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ status: "degraded", service: "ssra-web" }));
    }
    return;
  }

  if (req.method === "POST" && (pathname === "/api/turns" || pathname === "/api/chat/stream")) {
    try {
      const bodyStr = await readRequestBody(req);
      const targetPath = pathname === "/api/chat/stream" ? "/v1/agui/stream" : "/v1/turns";
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}${targetPath}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(req.headers["x-ssra-subject-ref"]
            ? { "X-SSRA-Subject-Ref": String(req.headers["x-ssra-subject-ref"]) }
            : {}),
        },
        body: bodyStr,
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        ...secHeaders,
      });
      res.end(text);
    } catch (err) {
      const code = err instanceof Error && err.message === "PAYLOAD_TOO_LARGE" ? 413 : 502;
      res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: code === 413 ? "PAYLOAD_TOO_LARGE" : "UPSTREAM_ERROR" }));
    }
    return;
  }

  const seg = pathname.split("/").filter(Boolean)[0] ?? "en";
  const locale = SUPPORTED_LOCALES.has(seg) ? seg : "en";
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...secHeaders });
  res.end(renderPwaShellHtml(locale, nonce));
});

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-web listening on http://${HOSTNAME}:${PORT}\n`);
});
