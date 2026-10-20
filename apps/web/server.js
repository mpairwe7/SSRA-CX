/**
 * Production Node.js HTTP & BFF Server for SSRA Assist Taxpayer Web PWA (`apps/web/server.js`).
 *
 * Enforces:
 * - Fixed-base URL parsing (`new URL(req.url, "http://127.0.0.1")`) with `400` malformed-target handling
 * - Per-request cryptographic nonce CSP (`'nonce-...'`, `'strict-dynamic'`, `worker-src 'self'`)
 * - Incremental AG-UI SSE chunk streaming (`upstream.body` with `AbortController` on client disconnect)
 * - Zero-trust BFF subject stripping (`auth_level: "ANONYMOUS"`, `subject_ref: null` for unverified browser calls)
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
const VALID_HOST_RE = /^[A-Za-z0-9.[\]:-]+$/;

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
    .chat-log { min-height: 12rem; border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.75rem; margin-bottom: 0.75rem; background: var(--bg); white-space: pre-wrap; }
    form { display: flex; gap: 0.5rem; }
    textarea { flex: 1; min-height: 2.75rem; padding: 0.5rem; border: 1px solid var(--border); border-radius: 0.5rem; font: inherit; }
    button { min-height: 2.75rem; padding: 0.5rem 1rem; background: var(--brand); color: #fff; border: none; border-radius: 0.5rem; cursor: pointer; font-weight: 600; }
  </style>
</head>
<body>
  <header>
    <strong>SSRA Assist (NRA South Sudan)</strong>
    <span id="ssra-snapshot-badge">Locale: ${locale.toUpperCase()}</span>
  </header>
  <main id="ssra-app-root" data-locale="${locale}">
    <section class="card" aria-label="SSRA Assist Taxpayer Chat">
      <h1>SSRA Assist — Grounded Tax, TIN, TCC &amp; Customs Guidance</h1>
      <div id="ssra-chat-messages" class="chat-log" role="log" aria-live="polite">Ask a question in English (en), Juba Arabic (pga), Arabic (ar), or Dinka (din).</div>
      <form id="ssra-chat-form">
        <label for="ssra-chat-input" class="sr-only">Your question</label>
        <textarea id="ssra-chat-input" name="message" required placeholder="e.g. How much is PAYE on 250,000 SSP per month?"></textarea>
        <button type="submit" id="ssra-chat-submit">Send</button>
      </form>
    </section>
  </main>
  <script nonce="${nonce}">
    (() => {
      const form = document.getElementById("ssra-chat-form");
      const input = document.getElementById("ssra-chat-input");
      const log = document.getElementById("ssra-chat-messages");
      const root = document.getElementById("ssra-app-root");
      const locale = root?.dataset.locale || "en";
      form?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;
        log.textContent = "Checking official SSRA knowledge snapshot...";
        const res = await fetch("/api/turns", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, locale, channel: "web" }),
        });
        const data = await res.json();
        const segs = data?.answer?.segments?.map((s) => s.text).join(" ") || JSON.stringify(data);
        log.textContent = segs;
      });
    })();
  </script>
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

function sanitizeBrowserTurnBody(rawBodyStr) {
  const parsed = JSON.parse(rawBodyStr);
  return JSON.stringify({
    message: typeof parsed.message === "string" ? parsed.message : "",
    locale: typeof parsed.locale === "string" ? parsed.locale : "en",
    channel: "web",
    thread_id: typeof parsed.thread_id === "string" ? parsed.thread_id : null,
    low_data_mode: Boolean(parsed.low_data_mode),
    auth_level: "ANONYMOUS",
    subject_ref: null,
  });
}

const server = http.createServer(async (req, res) => {
  const nonce = crypto.randomBytes(16).toString("base64");
  const secHeaders = buildSecurityHeaders(nonce);
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

  if (req.method === "POST" && pathname === "/api/turns") {
    try {
      const safeBody = sanitizeBrowserTurnBody(await readRequestBody(req));
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/turns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: safeBody,
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        ...secHeaders,
      });
      res.end(text);
    } catch (err) {
      const code =
        err instanceof Error && err.message === "PAYLOAD_TOO_LARGE"
          ? 413
          : err instanceof SyntaxError
            ? 400
            : 502;
      res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
      res.end(JSON.stringify({ error: "BFF_TURN_PROXY_ERROR" }));
    }
    return;
  }

  if (req.method === "POST" && pathname === "/api/chat/stream") {
    const ac = new AbortController();
    req.on("close", () => ac.abort());
    try {
      const safeBody = sanitizeBrowserTurnBody(await readRequestBody(req));
      const upstream = await fetch(`${INTERNAL_RUNTIME_URL}/v1/agui/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: safeBody,
        signal: ac.signal,
      });
      res.writeHead(upstream.status, {
        "Content-Type": upstream.headers.get("content-type") ?? "text/event-stream",
        "X-Accel-Buffering": "no",
        ...secHeaders,
      });
      if (upstream.body) {
        for await (const chunk of upstream.body) {
          if (res.destroyed) {
            break;
          }
          res.write(chunk);
        }
      }
      res.end();
    } catch (err) {
      if (!res.headersSent) {
        const code =
          err instanceof Error && err.message === "PAYLOAD_TOO_LARGE"
            ? 413
            : err instanceof SyntaxError
              ? 400
              : 502;
        res.writeHead(code, { "Content-Type": "application/json", ...secHeaders });
        res.end(JSON.stringify({ error: "BFF_STREAM_PROXY_ERROR" }));
      } else {
        res.end();
      }
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
