#!/usr/bin/env python3
"""OpenAPI 3.1 contract snapshot & breaking-change verifier (`oasdiff` CI gate — Section 10.4)."""

from __future__ import annotations

import json
from pathlib import Path

from ssra_api import create_api_app

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "services" / "api" / "openapi.json"


def main() -> None:
    if not SNAPSHOT_PATH.exists():
        raise SystemExit("ERROR: services/api/openapi.json snapshot is missing. Run `task gen`.")

    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    live = create_api_app().openapi()

    assert committed.get("openapi") == "3.1.0", "OpenAPI version must be 3.1.0"
    committed_paths = set(committed.get("paths", {}).keys())
    live_paths = set(live.get("paths", {}).keys())

    removed_paths = committed_paths - live_paths
    if removed_paths:
        raise SystemExit(f"BREAKING API CHANGE DETECTED: Removed paths {sorted(removed_paths)}")

    if json.dumps(committed, sort_keys=True) != json.dumps(live, sort_keys=True):
        raise SystemExit(
            "OpenAPI 3.1 snapshot drift detected in services/api/openapi.json. Run `task gen`."
        )

    print(
        f"OpenAPI 3.1 contract check passed ({len(live_paths)} paths verified, 0 breaking changes)."
    )


if __name__ == "__main__":
    main()
