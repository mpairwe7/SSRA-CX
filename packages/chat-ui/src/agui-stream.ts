/**
 * Resumable AG-UI SSE Stream Client & Parser (`packages/chat-ui/src/agui-stream.ts` — Section 9.3, 11, ADR-005).
 */

export type AguiEventType =
  | "RUN_STARTED"
  | "TOOL_CALL_START"
  | "TOOL_CALL_END"
  | "TEXT_MESSAGE_START"
  | "TEXT_MESSAGE_CONTENT"
  | "TEXT_MESSAGE_END"
  | "CUSTOM"
  | "RUN_FINISHED";

export interface ParsedAguiSseEvent {
  readonly id: string;
  readonly type: AguiEventType;
  readonly payload: Record<string, unknown>;
}

/**
 * Parse an AG-UI Server-Sent Events (SSE) stream with resumable `afterEventId` cursor and corruption detection.
 * Stops advancing the resume cursor at the first corrupt/truncated frame so no event gap is skipped.
 */
export function parseAguiSseStream(
  rawSseBody: string,
  options?: { readonly afterEventId?: string },
): {
  readonly events: ParsedAguiSseEvent[];
  readonly lastEventId: string | null;
  readonly accumulatedText: string;
  readonly corrupted: boolean;
} {
  const blocks = rawSseBody.split("\n\n").filter((b) => b.trim().length > 0);
  const allEvents: ParsedAguiSseEvent[] = [];
  let corrupted = false;

  for (const block of blocks) {
    let id = "";
    let dataLine = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("id:")) {
        id = line.slice(3).trim();
      } else if (line.startsWith("data:")) {
        dataLine = line.slice(5).trim();
      }
    }
    if (!dataLine) {
      continue;
    }
    try {
      const parsed = JSON.parse(dataLine) as Record<string, unknown>;
      const type = parsed.type as AguiEventType;
      allEvents.push({ id, type, payload: parsed });
    } catch {
      // Stop before advancing lastEventId past a corrupt or truncated SSE frame so callers can resume from the last valid event
      corrupted = true;
      break;
    }
  }

  let startIndex = 0;
  if (options?.afterEventId) {
    const foundIdx = allEvents.findIndex((e) => e.id === options.afterEventId);
    if (foundIdx >= 0) {
      startIndex = foundIdx + 1;
    }
  }

  const events = allEvents.slice(startIndex);
  const lastEventId = allEvents.length > 0 ? (allEvents[allEvents.length - 1]?.id ?? null) : null;
  const accumulatedText = events
    .filter((e) => e.type === "TEXT_MESSAGE_CONTENT" && typeof e.payload.delta === "string")
    .map((e) => e.payload.delta as string)
    .join(" ");

  return {
    events,
    lastEventId,
    accumulatedText,
    corrupted,
  };
}
