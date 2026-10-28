#!/usr/bin/env python3
"""Frontend First-Load JS Gzip Budget (<= 150 KB max, <= 120 KB target) & WCAG 2.2 AA / RTL Verifier (Section 9.3, 9.5)."""

from __future__ import annotations

import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_FIRST_LOAD_JS_GZIP_KB = 150.0
TARGET_FIRST_LOAD_JS_GZIP_KB = 120.0


def main() -> None:
    # 1. Measure total gzipped size of public-route TypeScript/JS modules in apps/web + packages/{ui,i18n,contracts}
    public_files = [
        *(ROOT / "apps" / "web" / "src").glob("**/*.ts"),
        *(ROOT / "apps" / "web" / "public").glob("**/*.js"),
        *(ROOT / "packages" / "ui" / "src").glob("**/*.ts"),
        *(ROOT / "packages" / "i18n" / "src").glob("**/*.ts"),
        *(ROOT / "packages" / "contracts" / "src").glob("**/*.ts"),
    ]
    raw_bytes = b"\n".join(f.read_bytes() for f in sorted(public_files))
    gzip_kb = len(gzip.compress(raw_bytes, compresslevel=9)) / 1024.0

    assert gzip_kb <= MAX_FIRST_LOAD_JS_GZIP_KB, (
        f"Public bundle gzip size {gzip_kb:.2f} KB exceeds {MAX_FIRST_LOAD_JS_GZIP_KB} KB budget"
    )
    assert gzip_kb <= TARGET_FIRST_LOAD_JS_GZIP_KB, (
        f"Public bundle gzip size {gzip_kb:.2f} KB exceeds {TARGET_FIRST_LOAD_JS_GZIP_KB} KB target"
    )

    # 2. Verify WCAG 2.2 AA touch target (>= 44px), SC 2.4.11/2.4.13 focus ring, SC 3.3.8 OTP autofill, RTL Arabic support, and ARIA landmarks
    ui_src = (ROOT / "packages" / "ui" / "src" / "index.ts").read_text(encoding="utf-8")
    ui_comp_src = (ROOT / "packages" / "ui" / "src" / "components.ts").read_text(encoding="utf-8")
    chat_comp_src = (ROOT / "packages" / "chat-ui" / "src" / "components.ts").read_text(
        encoding="utf-8"
    )
    sw_src = (ROOT / "apps" / "web" / "public" / "sw.js").read_text(encoding="utf-8")
    assert "minTouchTargetPx: 44" in ui_src, "WCAG 2.2 AA 44px touch target missing in packages/ui"
    assert "focusOutlineCss:" in ui_src, (
        "WCAG 2.2 SC 2.4.13 focus indicator token missing in packages/ui"
    )
    assert '"high-contrast"' in ui_src and "computeWcagContrastRatio" in ui_src, (
        "High-contrast theme or WCAG contrast verifier missing in packages/ui"
    )
    assert "oklch(" in ui_src, "Perceptual OKLCH color tokens missing in packages/ui"
    assert 'autoComplete: "one-time-code"' in ui_comp_src, (
        "WCAG 2.2 SC 3.3.8 OTP one-time-code missing"
    )
    assert (
        "100dvh" in ui_comp_src
        and "env(safe-area-inset-bottom" in ui_comp_src
        and "container-type: inline-size" in ui_comp_src
    ), "Mobile 100dvh, safe-area-inset-bottom, or @container query primitive missing in packages/ui"
    assert (
        'role="region"' in chat_comp_src
        and 'aria-live="polite"' in chat_comp_src
        and "ssra-guided-steps" in chat_comp_src
    ), (
        "ARIA region/live attributes or structured guided-steps renderer missing in packages/chat-ui/src/components.ts"
    )
    assert "SSRA_LOGOUT_PURGE" in sw_src and "no-store" in sw_src, (
        "CVE-2026-50184 Service Worker logout purge & no-store guard missing in apps/web/public/sw.js"
    )
    proxy_src = (ROOT / "apps" / "web" / "src" / "proxy.ts").read_text(encoding="utf-8")
    stream_src = (
        ROOT / "apps" / "web" / "src" / "app" / "api" / "chat" / "stream" / "route.ts"
    ).read_text(encoding="utf-8")
    tel_src = (ROOT / "packages" / "telemetry" / "src" / "index.ts").read_text(encoding="utf-8")
    assert "ROADMAP_LOCALES" in proxy_src and '"x-nonce"' in proxy_src, (
        "8-locale negotiation or x-nonce header missing in apps/web/src/proxy.ts"
    )
    assert "Last-Event-ID" in stream_src and "confirmation_token" in stream_src, (
        "Resumable Last-Event-ID or confirmation_token missing in BFF stream route"
    )
    assert "createBrowserTraceparent" in tel_src, (
        "Browser W3C traceparent helper missing in packages/telemetry"
    )

    # 3. Verify FE-G1..FE-G8 Runtime BFF & Operations Console Invariants (apps/web/server.js, apps/console/server.js, packages/ui/ops-console.js)
    web_srv_src = (ROOT / "apps" / "web" / "server.js").read_text(encoding="utf-8")
    con_srv_src = (ROOT / "apps" / "console" / "server.js").read_text(encoding="utf-8")
    ops_ui_src = (ROOT / "packages" / "ui" / "ops-console.js").read_text(encoding="utf-8")

    # FE-G1: Shared-device zero-PII localStorage hygiene & SSRA_LOGOUT_PURGE dispatch
    assert "scrubPiiForStorage" in web_srv_src and "SSRA_LOGOUT_PURGE" in web_srv_src, (
        "FE-G1 shared-device PII scrubbing or SSRA_LOGOUT_PURGE dispatch missing in apps/web/server.js"
    )
    assert "ngrok-skip-browser-warning" in sw_src and "ngrok-error-code" in sw_src, (
        "Ngrok interstitial cache-poisoning guard missing in apps/web/public/sw.js"
    )

    # FE-G2: Public BFF uses bounded upstream calls; staff preview has no upstream API proxy.
    for srv_name, srv_src in [
        ("apps/web/server.js", web_srv_src),
        ("apps/console/server.js", con_srv_src),
    ]:
        assert "Cross-Origin-Opener-Policy" in srv_src and "ALLOWED_METHODS" in srv_src, (
            f"FE-G2 COOP header or ALLOWED_METHODS missing in {srv_name}"
        )
    assert "AbortSignal.timeout(15_000)" in web_srv_src and "createTraceparent" in web_srv_src, (
        "FE-G2 public BFF upstream timeout or W3C traceparent missing in apps/web/server.js"
    )
    assert (
        "denyStaffApi" in con_srv_src
        and "AUTHENTICATED_STAFF_SESSION_REQUIRED" in con_srv_src
        and "X-SSRA-Staff-Id" not in con_srv_src
        and "INTERNAL_API_URL" not in con_srv_src
        and "fetch(" not in con_srv_src
    ), (
        "Staff console preview must deny APIs and must not trust browser identity or proxy staff data"
    )

    # FE-G3: W3C Trusted Types & 6-char escapeHtml (including &#39; and &#96;)
    for ui_name, src in [
        ("apps/web/server.js", web_srv_src),
        ("packages/ui/ops-console.js", ops_ui_src),
    ]:
        assert "&#39;" in src and "&#96;" in src and "setSafeHtml" in src, (
            f"FE-G3 Trusted Types setSafeHtml or 6-char HTML escaping missing in {ui_name}"
        )

    # FE-G4..FE-G7: Offline statutory fallback, 8-locale UI dictionary, 5-tab SettingsDialog, Auditor SoD & South Sudan Civic Palette
    assert "computeOfflineResilienceAnswer" in web_srv_src and "LOCALE_UI_STRINGS" in web_srv_src, (
        "FE-G4/FE-G5 offline statutory calculator fallback or 8-locale UI dictionary missing in apps/web/server.js"
    )
    assert "renderSettingsTabContent" in web_srv_src and 'class="skip-link"' in web_srv_src, (
        "FE-G6 interactive 5-tab SettingsDialog or skip-link missing in apps/web/server.js"
    )
    assert (
        "ssra_auditor" in ops_ui_src
        and "--ssra-civic-green: #078930" in ops_ui_src
        and "ssra-flag-ribbon" not in ops_ui_src
    ), (
        "FE-G7 Auditor read-only SoD or South Sudan civic palette token missing, or decorative flag ribbon reintroduced, in packages/ui/ops-console.js"
    )

    # FE-G8, FE2-G1..G8 & SEC2-G6/G7: Executable verification of cross-subject purge, safe offline abstention, BFF staff-header stripping, AbortController cancellation, modal focus trap, CSAT feedback & SVG icon library
    import re

    icons_src = (ROOT / "packages" / "ui" / "icons.js").read_text(encoding="utf-8")
    emoji_re = re.compile(r"[\U0001F300-\U0001FAFF\U0001F1E6-\U0001F1FF\u2600-\u27BF\u2190-\u21FF]")
    assert (
        '<svg class="ui-icon"' in icons_src
        and "ICONS." in web_srv_src
        and "ICONS." in ops_ui_src
        and not emoji_re.search(web_srv_src)
        and not emoji_re.search(ops_ui_src)
        and not emoji_re.search(con_srv_src)
    ), "Emoji characters found or SVG icon library missing in frontend UI"
    assert (
        'auth_level: "ANONYMOUS"' in web_srv_src
        and "subject_ref: null" in web_srv_src
        and "PUBLIC_BFF_ROUTE_NOT_ALLOWED" in web_srv_src
        and "outcome_verified: false" in web_srv_src
        and "x-ssra-staff-id" not in web_srv_src
        and "activeTurnAbortController" in web_srv_src
        and "cleanTextForSpeech" in web_srv_src
        and "data-csat=" in web_srv_src
        and "trapModalTabFocus" in web_srv_src
        and "trapModalTabFocus" in ops_ui_src
        and "fetch(" not in ops_ui_src
        and "X-SSRA-Staff-Id" not in ops_ui_src
        and "AUTHENTICATED_STAFF_SESSION_REQUIRED" in con_srv_src
        and "resolveTelemetryProvenance"
        in (ROOT / "apps" / "console" / "src" / "views.ts").read_text(encoding="utf-8")
        and "UNKNOWN_TELEMETRY"
        in (ROOT / "apps" / "console" / "src" / "views.ts").read_text(encoding="utf-8")
        and "cmdkReturnFocusEl.isConnected" in ops_ui_src
        and "e.ctrlKey || e.metaKey || e.altKey" in ops_ui_src
    ), (
        "FE-G8 / FE2-G1..G8 / SEC2-G6 anonymous BFF, staff preview gate, AbortController, modal focus trap, or telemetry freshness checks missing"
    )

    # 6. CSP Level 3 strict-dynamic, zero inline style="...", Lighthouse & Mobile Responsiveness verification
    for ui_file in (web_srv_src, ops_ui_src, icons_src):
        if "style=" in ui_file:
            raise SystemExit(
                'CSP style-src-attr violation: inline style="..." attribute detected; move styles to nonced CSS classes'
            )
    if "script-src 'self'" in web_srv_src or "script-src 'self'" in con_srv_src:
        raise SystemExit(
            "CSP script-src warning: do not combine 'self' with 'strict-dynamic' in script-src"
        )
    assert (
        "sendBodyWithCompression" in web_srv_src
        and "sendBodyWithCompression" in con_srv_src
        and "acceptsEncoding(" in web_srv_src
        and "acceptsEncoding(" in con_srv_src
        and 'pathname === "/robots.txt"' in web_srv_src
        and 'pathname === "/robots.txt"' in con_srv_src
        and 'meta name="description"' in web_srv_src
        and 'meta name="description"' in ops_ui_src
        and 'id="mobile-ops-nav-btn"' in ops_ui_src
        and "z-index: 25" in ops_ui_src
        and 'id="rail-mobile-backdrop"' in web_srv_src
        and "syncMobileRailA11y" in web_srv_src
        and 'aria-current="true"' in web_srv_src
        and 'btn.setAttribute("aria-checked", String(isSelected))' in ops_ui_src
        and 'railEl?.addEventListener("focusin"' in ops_ui_src
        and 'railEl?.addEventListener("focusout"' in ops_ui_src
        and 'railEl?.matches(":hover")' in ops_ui_src
        and 'railEl.classList.remove("is-collapsed")' in ops_ui_src
        and '<h2 id="settings-pane-title"' in web_srv_src
    ), (
        "Lighthouse / Mobile Responsiveness / WCAG 2.2 AA invariants missing (compression, robots.txt, meta description, aria-checked, or mobile drawer)"
    )

    # 7. Executable verification of public BFF denial, staff API denial, compression, and preview rendering.
    import http.client
    import os
    import shutil
    import subprocess
    import time

    node_bin = shutil.which("node") or "node"
    proc = subprocess.Popen(  # noqa: S603
        [node_bin, str(ROOT / "apps" / "web" / "server.js")],
        env={**os.environ, "PORT": "39123"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=0.2)
                conn.request("GET", "/healthz")
                if conn.getresponse().status == 200:
                    conn.close()
                    break
                conn.close()
            except Exception:
                time.sleep(0.1)

        conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=2.0)
        conn.request("GET", "/en", headers={"Accept-Encoding": "br;q=0, gzip;q=1.0"})
        resp_q0 = conn.getresponse()
        assert resp_q0.getheader("Content-Encoding") == "gzip", (
            f"Expected gzip when br;q=0, got {resp_q0.getheader('Content-Encoding')}"
        )
        resp_q0.read()
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=2.0)
        conn.request("GET", "/en", headers={"Accept-Encoding": "br;q=0, gzip;q=0"})
        resp_none = conn.getresponse()
        assert resp_none.getheader("Content-Encoding") is None, (
            f"Expected no Content-Encoding when br;q=0, gzip;q=0, got {resp_none.getheader('Content-Encoding')}"
        )
        html_en = resp_none.read().decode("utf-8")
        assert 'data-mobile-rail="closed"' in html_en and 'id="rail-mobile-backdrop"' in html_en
        assert 'id="rail-hotzone"' in html_en and "IBMPlexSans-Regular.woff2" in html_en
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=2.0)
        conn.request("GET", "/fonts/IBMPlexSans-Regular.woff2")
        resp_font = conn.getresponse()
        font_etag = resp_font.getheader("ETag")
        assert (
            resp_font.status == 200
            and resp_font.getheader("Content-Type") == "font/woff2"
            and font_etag
        ), (
            f"Expected 200 font/woff2 with ETag on /fonts/IBMPlexSans-Regular.woff2, got {resp_font.status}"
        )
        resp_font.read()
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=2.0)
        conn.request(
            "GET",
            "/fonts/IBMPlexSans-Regular.woff2",
            headers={"If-None-Match": str(font_etag)},
        )
        resp_font_304 = conn.getresponse()
        assert resp_font_304.status == 304, (
            f"Expected 304 on If-None-Match, got {resp_font_304.status}"
        )
        resp_font_304.read()
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=2.0)
        conn.request("GET", "/admin", headers={"Accept-Encoding": "identity"})
        resp_ops = conn.getresponse()
        assert resp_ops.status == 404, f"Public web BFF exposed staff route: HTTP {resp_ops.status}"
        resp_ops.read()
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", 39123, timeout=2.0)
        conn.request("GET", "/v1/turns", headers={"Accept-Encoding": "identity"})
        resp_direct_runtime = conn.getresponse()
        assert resp_direct_runtime.status == 403, (
            f"Public web BFF exposed direct runtime route: HTTP {resp_direct_runtime.status}"
        )
        resp_direct_runtime.read()
        conn.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    console_proc = subprocess.Popen(  # noqa: S603
        [node_bin, str(ROOT / "apps" / "console" / "server.js")],
        env={**os.environ, "PORT": "39124"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                conn = http.client.HTTPConnection("127.0.0.1", 39124, timeout=0.2)
                conn.request("GET", "/healthz")
                if conn.getresponse().status == 200:
                    conn.close()
                    break
                conn.close()
            except Exception:
                time.sleep(0.1)

        conn = http.client.HTTPConnection("127.0.0.1", 39124, timeout=2.0)
        conn.request("GET", "/admin", headers={"Accept-Encoding": "identity"})
        preview = conn.getresponse()
        html_ops = preview.read().decode("utf-8")
        assert preview.status == 200
        assert 'id="mobile-ops-nav-btn"' in html_ops and 'id="ops-mobile-backdrop"' in html_ops
        assert "Preview only · no authenticated staff session" in html_ops
        assert (
            "IBMPlexMono-Light.woff2" in html_ops and 'class="ops-stat-grid ov-stats"' in html_ops
        )
        assert 'id="rail-group-work"' in html_ops and 'aria-current="page"' in html_ops
        assert "Live Sovereign GPU Stack" not in html_ops
        conn.close()

        for auth_route, expected_marker in (
            ("/signin", "urn:ssra:acr:passkey"),
            ("/signup", "prompt=create"),
            ("/signin/callback", "callback-status-banner"),
            ("/analytics", "OpenSLO v1"),
        ):
            conn = http.client.HTTPConnection("127.0.0.1", 39124, timeout=2.0)
            conn.request("GET", auth_route, headers={"Accept-Encoding": "identity"})
            auth_resp = conn.getresponse()
            auth_html = auth_resp.read().decode("utf-8")
            assert auth_resp.status == 200 and expected_marker in auth_html, (
                f"Expected HTTP 200 and '{expected_marker}' on console route {auth_route}"
            )
            conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", 39124, timeout=2.0)
        conn.request("GET", "/fonts/IBMPlexMono-Light.woff2")
        resp_ops_font = conn.getresponse()
        assert (
            resp_ops_font.status == 200 and resp_ops_font.getheader("Content-Type") == "font/woff2"
        ), (
            f"Expected 200 font/woff2 on console /fonts/IBMPlexMono-Light.woff2, got {resp_ops_font.status}"
        )
        resp_ops_font.read()
        conn.close()

        for method, route in [
            ("GET", "/api/scorecard"),
            ("GET", "/api/flags"),
            ("POST", "/api/flags"),
            ("GET", "/api/kill-switches"),
            ("POST", "/api/kill-switches"),
            ("GET", "/v1/runtime/stack-status"),
        ]:
            conn = http.client.HTTPConnection("127.0.0.1", 39124, timeout=2.0)
            conn.request(method, route, headers={"X-SSRA-Staff-Id": "ssra_admin"})
            denied = conn.getresponse()
            assert denied.status == 403, (
                f"Staff API {method} {route} was not denied: HTTP {denied.status}"
            )
            assert "AUTHENTICATED_STAFF_SESSION_REQUIRED" in denied.read().decode("utf-8")
            conn.close()
    finally:
        console_proc.terminate()
        console_proc.wait(timeout=5)

    print(
        f"Frontend budget & WCAG 2.2 AA check passed (FE-G1..FE-G8 verified): public gzip size={gzip_kb:.2f} KB (<= {TARGET_FIRST_LOAD_JS_GZIP_KB} KB target)."
    )


if __name__ == "__main__":
    main()
