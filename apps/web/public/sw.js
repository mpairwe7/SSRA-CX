// SSRA Assist Hand-Written PWA Service Worker (Section 9.2, ADR-011, CVE-2026-50184)
// Security Invariant: Caches ONLY immutable T0 public assets and FAQ shell.
// NEVER caches /api/*, /v1/*, Authorization/session requests, no-store requests, or T1-T3 data.

const CACHE_NAME = "ssra-assist-public-shell-v2026.10.2";
const PUBLIC_SHELL_URLS = [
  "/en",
  "/pga",
  "/ar",
  "/din",
  "/nus",
  "/bfa",
  "/zne",
  "/shk",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PUBLIC_SHELL_URLS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      ),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SSRA_LOGOUT_PURGE") {
    event.waitUntil(
      caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key)))),
    );
  }
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const cacheControl = event.request.headers.get("Cache-Control") || "";
  const hasAuthHeader = Boolean(event.request.headers.get("Authorization"));
  // CVE-2026-50184: Never intercept or cache non-GET, API/BFF, account, no-store, or authenticated requests
  if (
    event.request.method !== "GET" ||
    event.request.cache === "no-store" ||
    cacheControl.includes("no-store") ||
    hasAuthHeader ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/v1/") ||
    url.pathname.includes("/account")
  ) {
    return;
  }
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
