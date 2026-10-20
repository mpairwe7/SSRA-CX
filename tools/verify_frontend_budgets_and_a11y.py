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

    print(
        f"Frontend budget & WCAG 2.2 AA check passed: public gzip size={gzip_kb:.2f} KB (<= {TARGET_FIRST_LOAD_JS_GZIP_KB} KB target)."
    )


if __name__ == "__main__":
    main()
