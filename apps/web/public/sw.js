// SSRA Assist Hand-Written PWA Service Worker (Section 9.2, ADR-011, CVE-2026-50184)
// Security Invariant: Caches ONLY verified T0 public assets; purges stale caches on activate;
// sends ngrok-skip-browser-warning header so Ngrok interstitials (ERR_NGROK_6024 / allerrors.js) are never cached.

const CACHE_NAME = "ssra-assist-public-shell-v2026.10.4";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
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
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/v1/") ||
    url.pathname.includes("/account")
  ) {
    return;
  }

  // Network-first with ngrok-skip-browser-warning header so ERR_NGROK_6024 is never served or cached
  const reqHeaders = new Headers(event.request.headers);
  reqHeaders.set("ngrok-skip-browser-warning", "true");
  const netReq = new Request(event.request.url, {
    method: "GET",
    headers: reqHeaders,
    credentials: "same-origin",
  });

  event.respondWith(
    fetch(netReq)
      .then((res) => {
        if (res.ok && !res.headers.get("ngrok-error-code")) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(event.request)),
  );
});
