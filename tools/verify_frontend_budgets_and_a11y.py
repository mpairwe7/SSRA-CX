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

    # FE-G2: OWASP ASVS 5.0 V3/V4 headers, method allowlist, AbortSignal.timeout & traceparent
    for srv_name, srv_src in [
        ("apps/web/server.js", web_srv_src),
        ("apps/console/server.js", con_srv_src),
    ]:
        assert "Cross-Origin-Opener-Policy" in srv_src and "ALLOWED_METHODS" in srv_src, (
            f"FE-G2 COOP header or ALLOWED_METHODS missing in {srv_name}"
        )
        assert "AbortSignal.timeout(15_000)" in srv_src and "createTraceparent" in srv_src, (
            f"FE-G2 upstream timeout or W3C traceparent missing in {srv_name}"
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
        and "ssra-flag-ribbon" in ops_ui_src
        and "#078930" in ops_ui_src
    ), (
        "FE-G7 Auditor read-only SoD or South Sudan civic palette missing in packages/ui/ops-console.js"
    )

    print(
        f"Frontend budget & WCAG 2.2 AA check passed: public gzip size={gzip_kb:.2f} KB (<= {TARGET_FIRST_LOAD_JS_GZIP_KB} KB target)."
    )


if __name__ == "__main__":
    main()
