# ADR-005: AG-UI Streaming Protocol and Allow-Listed Generative UI Registry

- **Status:** Proposed
- **Date:** 2026-10-16
- **Deciders:** Founding Principal Architect / Staff Engineer, SSRA Technical Lead
- **Reversal Cost:** Medium
- **References:** [`docs/00-master-prompt.md`](../00-master-prompt.md) Sections 5, 6.1, 9.1–9.5, 10.1, 11, Appendix A

---

## 1. Problem Statement

How do we stream real-time agent text, tool progress, citations, confirmation prompts, and structured UI cards to low-bandwidth Web PWA and Staff Console clients while guaranteeing that the model can never inject arbitrary HTML, CSS, or JavaScript into the browser?

## 2. Context

Taxpayers in South Sudan frequently connect over high-latency, intermittent 2G/3G mobile connections where perceived responsiveness (Web TTFT p95 ≤ 1.5 s) and resumable streams are critical. At the same time, complex tax interactions—such as inspecting a PAYE breakdown, viewing a filing timeline, verifying official payment instructions, or confirming a `T2`/`T3` action—are much clearer for varying-literacy users when presented as clear, accessible, icon-supported UI cards (`en`, `pga`, and RTL `ar`) rather than dense paragraphs. However, allowing an LLM to emit raw HTML/Markdown with embedded scripts or arbitrary component trees creates severe XSS and UI-spoofing risks (e.g., rendering a fake payment account card).

## 3. Options Considered

1. **Plain REST JSON Request/Response:** Simple, but blocks the UI for 4–8 seconds until full generation and output guard checks complete, failing the 1.5 s p95 TTFT target and breaking on flaky mobile connections.
2. **Custom WebSocket Protocol + Raw HTML/MDX Streaming from the Model:** Bi-directional, but WebSockets are harder to proxy/cache across corporate and mobile middleboxes than HTTP/2 or HTTP/3 SSE, and model-emitted HTML/MDX violates our untrusted-output security posture.
3. **AG-UI Protocol over Resumable SSE + Strict Allow-Listed, Zod-Validated Generative UI Registry (Selected):** Uses the standard AG-UI event stream (`ag-ui-protocol` `1.0.0` in Python, `@ag-ui/client` & `@ag-ui/core` `1.0.2` in TypeScript) over Server-Sent Events proxied through the Next.js 16 BFF, paired with a closed registry of seven React components validated by Zod 4.

## 4. Decision

We adopt Option 3:

1. **AG-UI over SSE Transport (`services/agent-runtime` ↔ `apps/web` & `apps/console`):**
   - `services/agent-runtime` exposes an AG-UI SSE endpoint (`streaming/agui.py`) emitting typed lifecycle events: run start, tool-progress chips (`ToolCallStart`/`ToolCallEnd`), text delta chunks (released after sentence/segment guard checks), structured citations, interrupt confirmation requests, generative UI component descriptors, and run completion with `Last-Event-ID` cursor support for stream resumption.
   - `apps/web` and `apps/console` proxy the stream through `/api/chat/stream` (BFF pattern) so internal runtime URLs and session credentials never reach browser JavaScript.
2. **Closed Generative UI Component Registry (`packages/chat-ui`):**
   - The agent may only request UI rendering by referencing one of the seven allow-listed component names and passing structured JSON props:
     1. `BalanceCard`
     2. `FilingStatusTimeline`
     3. `PaymentInstructionsCard`
     4. `CalculatorForm`
     5. `CitationList`
     6. `ConfirmActionSheet`
     7. `HandoffCard`
   - Every component's props are validated on both the backend (Pydantic v2) and the client (Zod `4.6.5`).
   - **Safe Fallback:** If the agent requests an unknown component name, if Zod validation fails, or if the user has enabled **2G Text-Only / Low-Data Mode**, `packages/chat-ui` deterministically renders the plain-text segments and citations instead.
   - **Hard Prohibition:** The LLM never emits HTML, CSS, or JavaScript; strict Nonce CSP and `Trusted-Types` headers in `proxy.ts` enforce this in the browser.

## 5. Consequences

- **Positive:**
  - Meets the ≤ 1.5 s TTFT target over standard HTTP/2 and HTTP/3 SSE, works seamlessly through CDNs and mobile proxies, and degrades gracefully to text-only on 2G.
  - Eliminates generative-UI XSS and spoofing vectors: numeric fields rendered in `BalanceCard`, `PaymentInstructionsCard`, or `CalculatorForm` are guaranteed by `numeric_provenance` to match verified MCP tool artifacts.
- **Negative / Trade-offs:**
  - Adding a new interactive card type requires a code change and PR review in `packages/chat-ui` and `packages/contracts` rather than a prompt-only change—which is an intentional security feature for a government revenue system.

## 6. Reversal Cost & Migration Path

- **Reversal Cost:** Medium. The AG-UI transport adapter (`streaming/agui.py` and `packages/chat-ui`) is cleanly separated from the LangGraph state machine (`Answer` schema), allowing transport upgrades without modifying domain subgraphs.
