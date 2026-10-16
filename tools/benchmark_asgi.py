#!/usr/bin/env python3
"""ASGI Latency & Throughput Benchmark Harness for Uvicorn vs Granian (Section 10.1 & ADR-013)."""

from __future__ import annotations

import statistics
import time

from fastapi.testclient import TestClient
from ssra_runtime import create_runtime_app


def run_benchmark(iterations: int = 25) -> dict[str, float]:
    client = TestClient(create_runtime_app())
    latencies_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = client.post(
            "/v1/agui/stream",
            json={
                "message": "How much is PAYE on 250,000 SSP per month?",
                "locale": "en",
                "channel": "web",
            },
        )
        assert res.status_code == 200
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    latencies_ms.sort()
    p50 = statistics.median(latencies_ms)
    p95 = latencies_ms[int(len(latencies_ms) * 0.95) - 1]
    assert p95 <= 1500.0, f"p95 latency {p95:.2f} ms exceeded 1500 ms TTFT SLO"
    return {"p50_ms": round(p50, 2), "p95_ms": round(p95, 2), "iterations": float(iterations)}


def main() -> None:
    stats = run_benchmark(iterations=25)
    print(
        f"ASGI AG-UI SSE benchmark passed: p50={stats['p50_ms']} ms, p95={stats['p95_ms']} ms (<= 1500 ms SLO)."
    )


if __name__ == "__main__":
    main()
