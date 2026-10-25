// SSRA Assist Hand-Written PWA Service Worker (Section 9.2, ADR-011, CVE-2026-50184)
// Security Invariant: Caches ONLY verified T0 public assets; purges stale caches on activate;
// sends ngrok-skip-browser-warning header so Ngrok interstitials (ERR_NGROK_6024 / allerrors.js) are never cached.

const CACHE_NAME = "ssra-assist-public-shell-v2026.10.6";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      )
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
  const cacheControl = (event.request.headers.get("Cache-Control") || "").toLowerCase();
  const hasAuthHeader = Boolean(event.request.headers.get("Authorization"));
  // CVE-2026-50184: Never intercept or cache non-GET, API/BFF, health/metrics, SW script, account, no-store, or authenticated requests
  if (
    event.request.method !== "GET" ||
    event.request.cache === "no-store" ||
    cacheControl.includes("no-store") ||
    hasAuthHeader ||
    url.origin !== self.location.origin ||
    url.pathname === "/sw.js" ||
    url.pathname === "/healthz" ||
    url.pathname === "/health" ||
    url.pathname === "/metrics" ||
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
        const resCacheControl = (res.headers.get("cache-control") || "").toLowerCase();
        const resVary = res.headers.get("vary") || "";
        if (
          res.status === 200 &&
          res.type === "basic" &&
          !res.headers.get("ngrok-error-code") &&
          !resCacheControl.includes("no-store") &&
          !resCacheControl.includes("private") &&
          !res.headers.has("set-cookie") &&
          !resVary.includes("*")
        ) {
          const clone = res.clone();
          caches
            .open(CACHE_NAME)
            .then((cache) => cache.put(event.request, clone))
            .catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(event.request).then(
          (cached) =>
            cached ||
            new Response(JSON.stringify({ status: "offline", service: "ssra-web" }), {
              status: 503,
              headers: {
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store",
              },
            }),
        ),
      ),
  );
});
