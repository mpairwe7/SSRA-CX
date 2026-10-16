// SSRA Assist Hand-Written PWA Service Worker (Section 9.2, ADR-011)
// Security Invariant: Caches ONLY immutable T0 public assets and FAQ shell.
// NEVER caches /api/* BFF responses or authenticated T1-T3 taxpayer data.

const CACHE_NAME = "ssra-assist-public-shell-v2026.10.1";
const PUBLIC_SHELL_URLS = ["/en", "/pga", "/ar", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PUBLIC_SHELL_URLS)));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Never cache API, BFF streams, or account routes
  if (
    event.request.method !== "GET" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.includes("/account")
  ) {
    return;
  }
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
