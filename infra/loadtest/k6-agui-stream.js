// k6 Load Test for 10x Filing-Deadline Peak SSE Streaming (Section 13)
// Run with: k6 run infra/loadtest/k6-agui-stream.js

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  thresholds: {
    http_req_failed: ["rate<0.001"], // 99.9% availability target
    http_req_waiting: ["p(95)<1500"], // Web TTFT p95 <= 1.5 s
    http_req_duration: ["p(95)<6000"], // Grounded knowledge answer p95 <= 6 s
  },
  stages: [
    { duration: "30s", target: 20 },  // Baseline
    { duration: "1m", target: 200 },  // 10x Filing-Deadline Peak
    { duration: "30s", target: 0 },
  ],
};

export default function () {
  const url = __ENV.RUNTIME_URL || "http://localhost:8001/v1/agui/stream";
  const payload = JSON.stringify({
    message: "How much is PAYE on 250,000 SSP per month?",
    locale: "en",
    channel: "web",
  });
  const res = http.post(url, payload, {
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
  });

  check(res, {
    "status is 200": (r) => r.status === 200,
    "contains RUN_FINISHED": (r) => r.body && r.body.includes("RUN_FINISHED"),
  });
  sleep(0.5);
}
