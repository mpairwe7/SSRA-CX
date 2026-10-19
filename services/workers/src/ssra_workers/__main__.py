"""Runnable entrypoint for `python -m ssra_workers`."""

from __future__ import annotations

import json

from ssra_workers import get_worker_health_status


def main() -> int:
    print(json.dumps(get_worker_health_status(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
