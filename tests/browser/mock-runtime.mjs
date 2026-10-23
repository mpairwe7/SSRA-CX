import http from "node:http";

const HOSTNAME = "127.0.0.1";
const PORT = Number.parseInt(process.env.PORT ?? "3101", 10);
const MAX_BODY_BYTES = 65_536;
const requests = [];

function sendJson(res, status, body) {
  res.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
  });
  res.end(JSON.stringify(body));
}

const SYNTHETIC_CITATION = {
  doc_title: "Synthetic Test Document",
  effective_from: "2000-01-01",
  id: "cit_synthetic",
  section_anchor: "Synthetic-Section-1",
  snapshot_version: "synthetic-0",
  url: "https://example.invalid/synthetic",
};

function syntheticAnswer(overrides = {}) {
  return {
    affective_state: { recommended_tone: "de_escalate_synthetic" },
    answer: {
      abstained: false,
      citations: [],
      is_estimate: false,
      segments: [{ text: "Synthetic scenario response." }],
      ui_component: null,
    },
    citations: [],
    intent: { intent: "synthetic_intent_slug" },
    outcome_verified: true,
    pending_confirmation: null,
    thread_id: "browser-test-thread",
    tier: "T0",
    ...overrides,
  };
}

function syntheticCard(name, props, extra = {}) {
  return syntheticAnswer({
    answer: {
      abstained: false,
      citations: [],
      is_estimate: false,
      segments: [{ text: "Synthetic scenario response." }],
      ui_component: { name, props },
      ...extra,
    },
  });
}

// Scenario replies keyed by the synthetic message text. Values are placeholders, not tax facts.
const SCENARIOS = {
  "synthetic-scenario:handoff-reason-only": () => [200, syntheticCard("HandoffCard", { reason: "SYNTHETIC_REASON" })],
  "synthetic-scenario:partial-personal-card": () => [
    200,
    syntheticCard("BalanceCard", { total_outstanding_ssp: "1" }),
  ],
  "synthetic-scenario:unregistered-card": () => [
    200,
    syntheticCard("SyntheticUnregisteredCard", { prn: "SYNTHETIC-REF" }),
  ],
  "synthetic-scenario:pending-confirmation": () => [
    200,
    syntheticAnswer({
      pending_confirmation: {
        idempotency_key: "synthetic-idempotency",
        summary_text: "Synthetic action summary",
        token: "synthetic-confirmation",
        tool: "synthetic.tool",
      },
      tier: "T2",
    }),
  ],
  "synthetic-scenario:estimate-with-source": () => [
    200,
    syntheticCard(
      "CalculatorForm",
      { calculator_type: "PAYE", estimated_tax_ssp: "111", gross_monthly_ssp: "999", is_estimate: true },
      { citations: [SYNTHETIC_CITATION], is_estimate: true },
    ),
  ],
  "synthetic-scenario:estimate-without-source": () => [
    200,
    syntheticCard(
      "CalculatorForm",
      { calculator_type: "PAYE", estimated_tax_ssp: "111", gross_monthly_ssp: "999", is_estimate: true },
      { is_estimate: true },
    ),
  ],
  "synthetic-scenario:unavailable": () => [503, { detail: "Synthetic unavailable detail" }],
  "synthetic-scenario:rate-limited": () => [
    429,
    { status: 429, title: "Synthetic rate limit" },
    { "Retry-After": "7" },
  ],
  "synthetic-scenario:html-error": () => [500, "<html><body>Synthetic error page</body></html>"],
};

async function readJson(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) {
      throw new Error("PAYLOAD_TOO_LARGE");
    }
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

const server = http.createServer(async (req, res) => {
  const method = String(req.method ?? "GET").toUpperCase();
  const pathname = new URL(req.url ?? "/", `http://${HOSTNAME}`).pathname;

  if (method === "GET" && pathname === "/healthz") {
    sendJson(res, 200, { status: "ok", service: "ssra-browser-test-runtime" });
    return;
  }

  if (pathname === "/test/requests") {
    if (method === "DELETE") {
      requests.length = 0;
      sendJson(res, 204, {});
      return;
    }
    if (method === "GET") {
      sendJson(res, 200, requests);
      return;
    }
  }

  if (method === "POST" && pathname === "/v1/turns") {
    try {
      const body = await readJson(req);
      requests.push({
        body,
        headers: {
          authorization: req.headers.authorization ?? null,
          subject_ref: req.headers["x-subject-ref"] ?? null,
          traceparent: req.headers.traceparent ?? null,
        },
      });
      if (body.message === "synthetic-scenario:slow") {
        await new Promise((resolve) => setTimeout(resolve, 3_000));
      }
      if (body.message === "synthetic-scenario:drop-connection") {
        req.socket.destroy();
        return;
      }
      const scenario = SCENARIOS[body.message];
      if (scenario) {
        const [status, payload, headers = {}] = scenario();
        if (typeof payload === "string") {
          res.writeHead(status, { "Cache-Control": "no-store", "Content-Type": "text/html", ...headers });
          res.end(payload);
        } else {
          res.writeHead(status, {
            "Cache-Control": "no-store",
            "Content-Type": "application/json; charset=utf-8",
            ...headers,
          });
          res.end(JSON.stringify(payload));
        }
        return;
      }
      sendJson(res, 200, {
        affective_state: { recommended_tone: "standard_clear" },
        answer: {
          abstained: false,
          citations: [],
          is_estimate: false,
          segments: [{ text: "Synthetic browser verification response." }],
          ui_component: null,
        },
        citations: [],
        intent: { intent: "general_information" },
        outcome_verified: true,
        pending_confirmation: null,
        thread_id: typeof body.thread_id === "string" ? body.thread_id : "browser-test-thread",
        tier: "T0",
      });
    } catch {
      sendJson(res, 400, { error: "INVALID_TEST_RUNTIME_REQUEST" });
    }
    return;
  }

  sendJson(res, 404, { error: "NOT_FOUND" });
});

server.listen(PORT, HOSTNAME, () => {
  process.stdout.write(`ssra-browser-test-runtime listening on http://${HOSTNAME}:${PORT}\n`);
});

function stopServer() {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1_000).unref();
}

process.once("SIGINT", stopServer);
process.once("SIGTERM", stopServer);
