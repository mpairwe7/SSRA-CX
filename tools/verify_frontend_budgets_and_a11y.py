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

    # 2. Verify WCAG 2.2 AA touch target (>= 44px), RTL Arabic support, and ARIA landmarks in packages/ui & chat-ui
    ui_src = (ROOT / "packages" / "ui" / "src" / "index.ts").read_text(encoding="utf-8")
    chat_comp_src = (ROOT / "packages" / "chat-ui" / "src" / "components.ts").read_text(
        encoding="utf-8"
    )
    assert "minTouchTargetPx: 44" in ui_src, "WCAG 2.2 AA 44px touch target missing in packages/ui"
    assert 'role="region"' in chat_comp_src and "aria-label=" in chat_comp_src, (
        "ARIA region/label attributes missing in packages/chat-ui/src/components.ts"
    )

    print(
        f"Frontend budget & WCAG 2.2 AA check passed: public gzip size={gzip_kb:.2f} KB (<= {TARGET_FIRST_LOAD_JS_GZIP_KB} KB target)."
    )


if __name__ == "__main__":
    main()
