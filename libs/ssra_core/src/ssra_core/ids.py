"""RFC 9562 UUIDv7 generator for time-ordered database keys and correlation IDs."""

from __future__ import annotations

import os
import time
import uuid


def new_uuid7(timestamp_ms: int | None = None) -> uuid.UUID:
    """Generate a time-ordered UUIDv7 per RFC 9562."""
    ts_ms = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    if ts_ms < 0 or ts_ms >= (1 << 48):
        raise ValueError("timestamp_ms out of 48-bit range")

    rand_bytes = os.urandom(10)
    rand_a = int.from_bytes(rand_bytes[:2], "big") & 0x0FFF
    rand_b = int.from_bytes(rand_bytes[2:], "big") & ((1 << 62) - 1)

    uuid_int = (ts_ms & ((1 << 48) - 1)) << 80
    uuid_int |= 0x7 << 76  # version 7
    uuid_int |= rand_a << 64
    uuid_int |= 0b10 << 62  # RFC 9562 variant
    uuid_int |= rand_b
    return uuid.UUID(int=uuid_int)


def new_id(prefix: str) -> str:
    """Generate a prefixed UUIDv7 string (e.g., 'thr_0192...')."""
    clean_prefix = prefix.strip("_")
    return f"{clean_prefix}_{new_uuid7()}"
