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
