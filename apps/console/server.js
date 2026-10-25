/**
 * Non-operational prototype preview server for the SSRA Assist Staff Console (`apps/console/server.js`).
 *
 * Serves the preview shell with security headers. Staff data and action routes are denied until
 * server-verified identity, role mapping, and audited API authorization are implemented.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";
import { renderOpsDashboardHtml } from "../../packages/ui/ops-console.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FONTS_DIR = path.resolve(__dirname, "../../packages/ui/fonts");
const ALLOWED_FONT_FILES = new Set([
  "IBMPlexSans-Regular.woff2",
  "IBMPlexSans-Medium.woff2",
  "IBMPlexSans-SemiBold.woff2",
  "IBMPlexMono-Light.woff2",
  "IBMPlexMono-Regular.woff2",
]);
const FONT_CACHE = new Map();
for (const fontName of ALLOWED_FONT_FILES) {
  const fontPath = path.join(FONTS_DIR, fontName);
  if (fs.existsSync(fontPath)) {
    const buffer = fs.readFileSync(fontPath);
    const etag = `"${crypto.createHash("sha256").update(buffer).digest("hex").slice(0, 32)}"`;
    FONT_CACHE.set(fontName, { buffer, etag, byteLength: String(buffer.byteLength) });
  }
}

const PORT = Number.parseInt(process.env.PORT ?? "3001", 10);
const HOSTNAME = process.env.HOSTNAME ?? "0.0.0.0";
const VALID_HOST_RE = /^[A-Za-z0-9.[\]:-]+$/;
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "OPTIONS"]);
function denyStaffApi(res, secHeaders) {
  res.writeHead(403, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    ...secHeaders,
  });
  res.end(JSON.stringify({ error: "AUTHENTICATED_STAFF_SESSION_REQUIRED" }));
}

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

function buildConsoleHeaders(nonce) {
  return {
    "Content-Security-Policy": `default-src 'self'; script-src 'nonce-${nonce}' 'strict-dynamic'; style-src 'self' 'nonce-${nonce}'; font-src 'self' data:; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; require-trusted-types-for 'script'; trusted-types ssra-ops-html`,
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

function acceptsEncoding(acceptEncHeader, targetCoding) {
  let explicitQ = null;
  let wildcardQ = null;
  for (const part of String(acceptEncHeader ?? "").split(",")) {
    const [rawName, ...params] = part.trim().split(";");
    const name = rawName.trim().toLowerCase();
    if (!name) continue;
    let q = 1;
    for (const p of params) {
      const [k, v] = p.split("=");
      if (k && k.trim().toLowerCase() === "q" && v !== undefined) {
        const parsed = Number.parseFloat(v.trim());
        q = Number.isFinite(parsed) ? parsed : 0;
      }
    }
    if (name === targetCoding) {
      explicitQ = q;
    } else if (name === "*") {
      wildcardQ = q;
    }
  }
  if (explicitQ !== null) return explicitQ > 0;
  if (wildcardQ !== null) return wildcardQ > 0;
  return false;
}

function sendBodyWithCompression(req, res, statusCode, headers, bodyStr) {
  const isHead = String(req.method ?? "GET").toUpperCase() === "HEAD";
  const acceptEnc = String(req.headers["accept-encoding"] ?? "");
  const buf = Buffer.from(bodyStr, "utf-8");
  if (buf.length > 512 && acceptsEncoding(acceptEnc, "br")) {
    const compressed = zlib.brotliCompressSync(buf, {
      // Quality 5 measured smaller than quality 4 (which was larger than gzip level 6) for about 0.5 ms more CPU.
      params: {
        [zlib.constants.BROTLI_PARAM_QUALITY]: 5,
        [zlib.constants.BROTLI_PARAM_SIZE_HINT]: buf.length,
      },
    });
    res.writeHead(statusCode, {
      ...headers,
      "Content-Encoding": "br",
      "Content-Length": String(compressed.byteLength),
      Vary: "Accept-Encoding",
    });
    res.end(isHead ? undefined : compressed);
    return;
  }
  if (buf.length > 512 && acceptsEncoding(acceptEnc, "gzip")) {
    const compressed = zlib.gzipSync(buf, { level: 6 });
    res.writeHead(statusCode, {
      ...headers,
      "Content-Encoding": "gzip",
      "Content-Length": String(compressed.byteLength),
      Vary: "Accept-Encoding",
    });
    res.end(isHead ? undefined : compressed);
    return;
  }
  res.writeHead(statusCode, {
    ...headers,
    "Content-Length": String(buf.byteLength),
  });
  res.end(isHead ? undefined : buf);
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
  if (isGetOrHead && pathname === "/robots.txt") {
    res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8", ...secHeaders });
    res.end("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /v1/\n");
    return;
  }

  if (isGetOrHead && pathname.startsWith("/fonts/")) {
    const fontName = pathname.slice("/fonts/".length);
    const cached = FONT_CACHE.get(fontName);
    if (cached) {
      const fontHeaders = {
        ...secHeaders,
        "Content-Type": "font/woff2",
        "Cache-Control": "public, max-age=31536000, immutable",
        ETag: cached.etag,
      };
      if (req.headers["if-none-match"] === cached.etag) {
        res.writeHead(304, fontHeaders);
        res.end();
        return;
      }
      res.writeHead(200, {
        ...fontHeaders,
        "Content-Length": cached.byteLength,
      });
      res.end(method === "HEAD" ? undefined : cached.buffer);
      return;
    }
    res.writeHead(404, { "Content-Type": "application/json", ...secHeaders });
    res.end(method === "HEAD" ? undefined : JSON.stringify({ error: "FONT_NOT_FOUND" }));
    return;
  }

  if (isGetOrHead && (pathname === "/healthz" || pathname === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json", ...secHeaders });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "ssra-console-preview",
      }),
    );
    return;
  }

  if (pathname === "/api/scorecard") {
    denyStaffApi(res, secHeaders);
    return;
  }

  if (pathname === "/api/flags") {
    denyStaffApi(res, secHeaders);
    return;
  }

  if (pathname === "/api/kill-switches") {
    denyStaffApi(res, secHeaders);
    return;
  }

  if (pathname === "/v1/runtime/stack-status") {
    denyStaffApi(res, secHeaders);
    return;
  }

  if (method === "POST" && pathname === "/api/auth/backchannel-logout") {
    try {
      const rawBody = await readConsoleBody(req);
      const tokenParam = rawBody.startsWith("{")
        ? String(JSON.parse(rawBody).logout_token ?? "")
        : String(new URLSearchParams(rawBody).get("logout_token") ?? "");
      const parts = tokenParam.trim().split(".");
      if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) {
        res.writeHead(400, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
          ...secHeaders,
        });
        res.end(JSON.stringify({ error: "UNSIGNED_OR_MALFORMED_LOGOUT_JWT" }));
        return;
      }
      const hdr = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf-8"));
      const pld = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"));
      const verifyKey = process.env.KEYCLOAK_LOGOUT_VERIFY_KEY ?? "";
      const expectedSig = verifyKey
        ? crypto.createHmac("sha256", verifyKey).update(`${parts[0]}.${parts[1]}`).digest()
        : Buffer.alloc(0);
      const actualSig = Buffer.from(parts[2], "base64url");
      const sigOk =
        Boolean(verifyKey) &&
        expectedSig.length === actualSig.length &&
        crypto.timingSafeEqual(expectedSig, actualSig);
      const nowSec = Math.floor(Date.now() / 1000);
      if (
        !sigOk ||
        !["ES256", "RS256", "PS256", "EdDSA"].includes(hdr?.alg) ||
        pld?.iss !== "https://sso.ssra.gov.ss/realms/ssra" ||
        pld?.aud !== "ssra-staff-console" ||
        pld?.nonce !== undefined ||
        typeof pld?.jti !== "string" ||
        typeof pld?.iat !== "number" ||
        typeof pld?.exp !== "number" ||
        nowSec > pld.exp ||
        Math.abs(nowSec - pld.iat) > 120 ||
        !pld?.events?.["http://schemas.openid.net/event/backchannel-logout"] ||
        (!pld?.sid && !pld?.sub)
      ) {
        res.writeHead(400, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
          ...secHeaders,
        });
        res.end(JSON.stringify({ error: "INVALID_BACKCHANNEL_LOGOUT_CLAIMS" }));
        return;
      }
      res.writeHead(200, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "Clear-Site-Data": '"cache", "cookies", "storage"',
        ...secHeaders,
      });
      res.end(JSON.stringify({ status: "logged_out", client_id: "ssra-staff-console" }));
    } catch {
      res.writeHead(400, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        ...secHeaders,
      });
      res.end(JSON.stringify({ error: "INVALID_BACKCHANNEL_LOGOUT_REQUEST" }));
    }
    return;
  }

  sendBodyWithCompression(
    req,
    res,
    200,
    { "Content-Type": "text/html; charset=utf-8", ...secHeaders },
    renderOpsDashboardHtml(pathname, nonce),
  );
});

server.headersTimeout = 15_000;
server.requestTimeout = 35_000;
server.keepAliveTimeout = 5_000;

function shutdownConsoleGracefully() {
  server.closeIdleConnections?.();
  const forceTimer = setTimeout(() => process.exit(0), 2_000);
  forceTimer.unref?.();
  server.close(() => process.exit(0));
}
process.on("SIGTERM", shutdownConsoleGracefully);
process.on("SIGINT", shutdownConsoleGracefully);

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-console listening on http://${HOSTNAME}:${PORT}\n`);
});
