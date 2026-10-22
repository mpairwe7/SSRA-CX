import http from "node:http";

const HOSTNAME = "127.0.0.1";
const PORT = 3101;
const MAX_BODY_BYTES = 65_536;
const requests = [];

function sendJson(res, status, body) {
  res.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
  });
  res.end(JSON.stringify(body));
}

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
