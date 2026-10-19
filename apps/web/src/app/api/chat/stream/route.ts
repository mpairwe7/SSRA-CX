/**
 * BFF AG-UI SSE Stream Proxy (`apps/web/src/app/api/chat/stream/route.ts` — Section 9.1, 9.4, 16).
 *
 * Ensures OAuth 2.1 tokens and internal runtime URLs never reach browser JavaScript.
 */

import type { LocaleCode } from "@ssra/contracts";

export interface BffStreamProxyInput {
  readonly message: string;
  readonly locale: LocaleCode;
  readonly threadId?: string;
  readonly lowDataMode?: boolean;
  readonly lastEventId?: string;
  readonly traceparent?: string;
  readonly confirmationToken?: string;
  readonly idempotencyKey?: string;
  readonly runtimeBaseUrl?: string;
}

/**
 * Build the upstream `/v1/agui/stream` request descriptor with `Last-Event-ID`, `traceparent`, and confirmation tokens.
 */
export function buildRuntimeStreamRequest(input: BffStreamProxyInput): {
  readonly url: string;
  readonly method: "POST";
  readonly headers: Record<string, string>;
  readonly body: string;
} {
  const base = (input.runtimeBaseUrl ?? "http://localhost:8001").replace(/\/$/, "");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (input.lastEventId) {
    headers["Last-Event-ID"] = input.lastEventId.trim();
  }
  if (input.traceparent) {
    headers.traceparent = input.traceparent.trim();
  }
  return {
    url: `${base}/v1/agui/stream`,
    method: "POST",
    headers,
    body: JSON.stringify({
      message: input.message,
      locale: input.locale,
      channel: "web",
      thread_id: input.threadId ?? null,
      low_data_mode: input.lowDataMode ?? false,
      confirmation_token: input.confirmationToken ?? null,
      idempotency_key: input.idempotencyKey ?? null,
    }),
  };
}

/**
 * Next.js App Router POST handler validating incoming BFF chat stream requests and forwarding to agent-runtime.
 */
export async function POST(
  request: Request,
  fetcher: typeof fetch = globalThis.fetch,
): Promise<Response> {
  const raw = (await request.json()) as Record<string, unknown>;
  const message = typeof raw.message === "string" ? raw.message.trim() : "";
  if (!message) {
    return new Response(JSON.stringify({ error: "MESSAGE_REQUIRED" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
  const locale = (typeof raw.locale === "string" ? raw.locale : "en") as LocaleCode;
  const lastEventId =
    request.headers.get("Last-Event-ID") ??
    (typeof raw.lastEventId === "string" ? raw.lastEventId : undefined);
  const traceparent =
    request.headers.get("traceparent") ??
    (typeof raw.traceparent === "string" ? raw.traceparent : undefined);

  const built = buildRuntimeStreamRequest({
    message,
    locale,
    ...(typeof raw.threadId === "string" ? { threadId: raw.threadId } : {}),
    ...(typeof raw.lowDataMode === "boolean" ? { lowDataMode: raw.lowDataMode } : {}),
    ...(lastEventId ? { lastEventId } : {}),
    ...(traceparent ? { traceparent } : {}),
    ...(typeof raw.confirmationToken === "string"
      ? { confirmationToken: raw.confirmationToken }
      : {}),
    ...(typeof raw.idempotencyKey === "string" ? { idempotencyKey: raw.idempotencyKey } : {}),
  });
  return fetcher(built.url, {
    method: built.method,
    headers: built.headers,
    body: built.body,
  });
}
