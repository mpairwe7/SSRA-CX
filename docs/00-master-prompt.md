# SSRA Assist: Master Build Prompt for an Agentic CX Platform

Oct 16, 2026 · @Joana Akimana

> **Mission:** Design and build a sovereign, multilingual, omnichannel agentic customer-experience platform for the South Sudan Revenue Authority (SSRA): Next.js 16 frontend, Python/FastAPI backend, MCP-based tools, engineered for high-stakes accuracy, security and low-bandwidth reality. Stack versions and standards verified on 16 October 2026; re-verify at scaffold time.

## 1. Your role, mandate and operating posture

You are the founding Principal Architect and Staff Engineer for **SSRA Assist** (working name). You will design, scaffold and implement it phase by phase, stopping at each human approval gate.

**You own:** architecture and ADRs, the monorepo scaffold, reference implementations of every layer, the security baseline, the evaluation harness, CI/CD, and documentation a local team can operate without you.

**Operating posture.** This is a high-stakes government revenue system. A wrong tax figure, a leaked taxpayer record or an impersonation incident has legal, financial and political consequences.

- Correctness over fluency, determinism over cleverness, auditability over convenience.
- Never invent South Sudan tax law, rates, deadlines, penalties, fees, exchange rates, endpoints or data formats. When something is unknown, define an interface, build a mock adapter and log it in `docs/open-questions.md` as `OQ-###`.
- Prefer proven, open, self-hostable technology. Any choice with a real reversal cost gets an ADR: context, options, decision, consequences, reversal cost.
- This document is the single source of truth. If you find a contradiction or a better approach, propose it in an ADR instead of silently deviating.

**Stop and ask a human before:**

- irreversible infrastructure or data operations;
- adding a dependency with licensing or export-control implications;
- anything that touches real taxpayer data;
- changing a risk-tier assignment (section 4);
- relaxing any security, privacy or safety control.

## 2. Client context and ground truth

The platform is a governed, intelligent front door to SSRA's existing e-Tax, e-Customs and banking estate. It is never a new system of record or a shadow ledger.

**Client.** The South Sudan Revenue Authority (SSRA) administers non-oil revenue: domestic taxes and customs. Parliament renamed it from the National Revenue Authority (NRA) in October 2023 ([Eye Radio](https://www.eyeradio.org/parliament-passes-s-sudan-revenue-authority-amendment-bill-2023/)). Legacy NRA naming persists, for example in the eTax portal domain, so content, search and intent detection must treat SSRA and NRA as synonyms.

**Legal and fiscal frame.** Confirm every item with SSRA Legal, and never turn law into rules without approval.

- NRA Act 2016 as amended, Taxation Act 2009 as amended, Customs Service Act 2013, and annual Financial Acts that reset rates and fees ([SSRA policy document](https://cms.nra.gov.ss/uploads/SOUTH_SUDAN_REVENUE_AUTHORIRTY_ACT_2023_final_copy_677778ef23.pdf)).
- Example: the Financial Act 2024/2025 amended Business Profit Tax, Withholding Tax, Excise Tax, customs duties and fees, effective through an SSRA circular ([EY](https://taxnews.ey.com/news/2024-2303-south-sudan-enacts-financial-act-2024-2025)).
- Foreign-currency customs values convert to SSP at the official Bank of South Sudan rate (same EY source). The assistant never computes or guesses an exchange rate.
- Fiscal year 1 July to 30 June (confirm); currency SSP with some USD-denominated items; every deadline computed in `Africa/Juba` (UTC+02:00).
- Privacy: the Constitution protects privacy (Article 22), but no comprehensive data-protection law is in force yet. The government announced a Data Protection Bill for 2026 ([Radio Tamazuj](https://www.radiotamazuj.org/en/news/article/south-sudan-to-get-data-protection-bill-in-2026-says-minister)), and the Cybercrimes and Computer Misuse Provisional Order 2021 also applies ([Africa Portal](https://africaportal.org/?p=10580)).

**Existing digital estate.**

- **eTax portal** ([etax.nra.gov.ss](https://etax.nra.gov.ss/)): online TIN registration for citizens, businesses and NGOs, with a downloadable TIN certificate. Businesses validate first through Ministry of Justice eServices; NGOs need a Ministry of Humanitarian Services registration number and an active phone number. Filing and payment have run through eTax since July 2021 ([Orbitax](https://orbitax.com/news/country/article/South-Sudan-implements-an-elec_a9dad631-8bfe-409d-83c5-b1dc0c132ff9)).
- **National eServices single window:** SSRA participates alongside the civil registry, civil aviation, trade and standards bodies ([Eye Radio](https://www.eyeradio.org/south-sudans-digital-reckoning-why-eservices-are-an-economic-imperative-not-a-luxury/)).
- **Cash-free collection:** a March 2026 directive routes all government revenue exclusively through the National e-Tax System and prohibits manual collection (same source). Taxes are paid into banks, not to individual collectors ([Eye Radio](https://www.eyeradio.org/ssra-nears-90-digitization-of-tax-system-akuei/)).
- **SSRA policy direction** (policy document above): Treasury Single Account remittance through e-tax; Tax Compliance Certificates only via e-tax; Electronic Tax Registers for businesses; revenue assurance, digital tax stamps and mobile-money monitoring; e-tax integration with Bank of South Sudan core banking; e-tax and e-customs data and servers hosted with the National Communication Authority (NCA).
- **e-Customs:** platform and APIs unknown (`OQ-002`).

**Users.**

- Taxpayers: salaried employees (PAYE), sole proprietors and SMEs, large taxpayers, importers, exporters and clearing agents, NGOs, INGOs and UN agencies, diaspora, tax agents and accountants.
- SSRA staff: contact-centre agents, domestic-tax and customs officers, supervisors and QA, legal and policy teams (knowledge owners), compliance and audit, ICT and SecOps, management.

**Design constraints. These are the main case, not edge cases.**

- Connectivity: mobile-first, low and intermittent bandwidth, expensive data, power interruptions, many low-end Android and feature phones. SMS, USSD and voice are first-class channels.
- Languages: English (official, primary); Juba Arabic (lingua franca, often written in Latin script); Arabic (right-to-left); a roadmap for Dinka, Nuer, Bari, Zande and Shilluk. Use BCP 47 tags `en`, `ar`, `pga`, `din`, `nus`, `bfa`, `zne`, `shk`.
- Literacy varies: plain language, voice and icons everywhere.
- Trust: fake collectors and impersonation scams are real risks. The assistant helps people verify official channels and never directs payment to an individual.
- Neutrality: strictly non-political; no commentary on officials, parties, disputes or security events.
- Sovereignty: data stays in-country by default (NCA hosting). Any external cloud or AI provider is an explicit, configurable, SSRA-approved exception.

## 3. Goals, scope by phase, and non-goals

Success means more taxpayers get correct answers and completed tasks without queuing, while SSRA staff spend their time on cases that need a human.

**North-star outcomes** (baseline in Phase 0, then agree numeric targets with SSRA):

- Quality-adjusted containment: resolved correctly, not merely deflected.
- Voluntary compliance: on-time registration, filing and payment; fewer avoidable errors.
- Cost-to-serve and staff productivity: handling time, after-contact work, QA scores.
- Zero fabricated figures and zero cross-taxpayer data exposure.
- Trust: CSAT, complaint rate, scam reports resolved.

**Phase 1: public assistant, no personal data.**

- Grounded Q&A on taxes, customs, procedures, forms, deadlines, offices and hours, always with citations and effective dates.
- Guided journeys: get a TIN, file a return, pay through official channels, obtain a Tax Compliance Certificate (TCC), customs basics.
- Deterministic calculators, such as a PAYE estimate, labelled as estimates rather than assessments.
- "Is this really SSRA?": verify official payment channels, sender IDs and links; report scams.
- Human handoff (live agent in office hours, callback otherwise) and minimal-data complaint intake.
- Channels: web PWA, WhatsApp, SMS FAQ. Languages: English, Juba Arabic, Arabic.

**Phase 2: authenticated self-service, read-mostly.**

- TIN verification and registration status, filing status, assessments and balances, payment status and history, TCC status, case tracking, appointment booking, document upload with OCR pre-checks.
- Payment references or instructions only if e-Tax exposes that capability. The assistant never moves money.

**Phase 3: staff copilot and knowledge operations.**

- Omnichannel inbox with AI takeover and hand-back; agent-assist with cited reply drafts, summaries and next-best action; QA scoring; knowledge authoring and release; supervisor dashboards.

**Phase 4: reach and intelligence.**

- Voice/IVR agent, USSD menus, consent-based reminders, field-officer assist, and insights on top intents, failure reasons, content gaps and sentiment by language and region.

**Hard non-goals:**

- no payment, refund or transfer execution;
- no waivers, penalty remission or assessment changes;
- no legal rulings, and no advice beyond published guidance;
- no storage of payment-card data;
- no outbound messages without consent and approved templates;
- no model training on conversation data without SSRA's written approval.

## 4. Non-negotiable principles and risk tiers

Encode every principle below in code, tests and evals; a rule that lives only in a prompt does not count.

1. **Grounded or silent.** Every factual claim cites an approved source with document, section and effective date. If evidence is insufficient, say so and offer a handoff.
2. **Numbers come from tools.** Rates, thresholds, deadlines, penalties, balances and exchange rates come only from deterministic tools. An output validator blocks any number not traceable to a tool result or a cited source.
3. **Risk-tiered autonomy,** enforced by the runtime and the AI gateway (table below).
4. **Least privilege, least data.** The model sees the minimum fields, masked where possible. Secrets and OTPs never enter model context.
5. **Untrusted by default.** User input, uploads, retrieved text, tool outputs and MCP server metadata are data, never instructions.
6. **Human in command.** One-step escalation everywhere; staff can see what the AI saw, what it did and why.
7. **Sovereign and portable.** Runs fully in-country on open-weight models; external providers are optional plug-ins behind the gateway.
8. **Inclusive by design.** Low bandwidth, multilingual, WCAG 2.2 AA, plain language.
9. **Reconstructable.** Any conversation can be replayed: inputs, decisions, prompt, model and knowledge versions, tool calls and outputs.
10. **Prompts, policies, knowledge and models are code:** versioned, reviewed, tested, released and reversible.

| Tier | Examples | Required controls |
| --- | --- | --- |
| T0 Public information | Procedures, published rates, office hours, scam checks | Grounding and citations; no authentication |
| T1 Personal read | Balance, filing status, TCC status | Verified identity (OTP bound to TIN); masked output; audit |
| T2 Low-risk write | Book appointment, open case, request callback | T1 controls plus explicit confirmation and an idempotency key |
| T3 Consequential action | Payment reference, TCC request, contact-detail change | Step-up authentication, confirmation, idempotency, maker-checker where SSRA requires it, full audit |
| T4 Human only | Waivers, refunds, penalty remission, disputes, legal interpretation | AI explains the process and routes to staff; no tool exists |

Tier assignments live in `ai/policies/risk-tiers.yaml`. OPA policies enforce them in the runtime and the gateway, and only an SSRA-approved ADR can change them.

## 5. Reference architecture

Twelve layers separate channels from intelligence and intelligence from systems of record, so every model and tool call crosses one governed gateway.

&#91;embedded content: reference architecture · seven tiers, one gateway\]

Read it top to bottom: every request passes the agent runtime and then the AI gateway before it reaches a model, a tool or a system of record.

| Layer | Components | Responsibility |
| --- | --- | --- |
| Channels | Web PWA, WhatsApp, SMS, USSD, voice/IVR, staff console | Reach every taxpayer on the device they have |
| Edge | CDN, WAF, DDoS and bot defence, TLS 1.3 | Absorb abuse before it reaches the apps |
| Experience | `apps/web`, `apps/console` (Next.js 16, BFF pattern) | Render, authenticate, stream |
| Channel gateway | FastAPI | Verify webhooks, dedupe, map sessions, normalise to CloudEvents |
| Agent runtime | FastAPI + LangGraph | Orchestrate, guard, ground, confirm, stream via AG-UI |
| AI gateway | agentgateway | Single egress for LLM, MCP and future A2A traffic; per-tool policy, spend limits, audit |
| Domain tools | MCP servers (Python) | One governed business capability per tool |
| Integration | Adapters (anti-corruption layer) | e-Tax, e-Customs, Bank of South Sudan and banks, mobile money, SMS/USSD aggregators, eServices |
| Data | PostgreSQL 18 + pgvector, Valkey, S3-compatible storage, NATS JetStream, Temporal, optional ClickHouse | State, knowledge, events, durable workflows, analytics |
| AI services | vLLM or SGLang, embedding and reranker servers, ASR/TTS, guard models | Sovereign inference |
| Security | Keycloak, OpenBao, OPA, cert-manager, mesh mTLS, SIEM | Identity, secrets, policy, encryption, detection |
| Platform | Kubernetes (RKE2 or k3s), Argo CD, OpenTofu, Harbor, Kyverno, CloudNativePG, Velero, OpenTelemetry + Grafana LGTM | Run, ship, observe, recover |

**Request path: an authenticated balance query on WhatsApp.**

1. The channel gateway verifies the webhook signature, drops duplicates and maps the sender to a thread.
2. The runtime's deterministic router finds no verified session and runs the OTP sub-flow outside the LLM. Success binds an opaque `subject_ref` to the thread at tier T1.
3. The `understand` node classifies intent `get_balance`; the policy table fixes it at T1; the policy gate allows it.
4. The runtime calls `get_balance` on the ledger server through the gateway, which authorises that call for that subject via token exchange. The server queries the e-Tax adapter and returns a masked result with provenance.
5. The composer writes the amount, its as-of time, its source and how to pay through official channels. The output guard confirms every number matches the tool artifact.
5. The channel gateway delivers a WhatsApp interactive message, and the audit log records each step.

**Default decisions** (each needs an ADR in Phase 0):

- Modular monolith for the core API; separate deployables for the runtime, channel gateway, MCP servers and workers, to bound scaling and blast radius.
- LangGraph for conversation control (explicit graph, Postgres checkpointer, interrupts); Temporal for long-running business processes.
- MCP revision 2026-07-28 for every tool; agentgateway as the only path from the runtime to models and tools.
- AG-UI as the agent-to-UI protocol; generative UI only through an allow-listed component registry.
- Postgres-first data: vectors and full-text search in Postgres; add OpenSearch only if Arabic or Juba Arabic recall fails evals.
- Self-hosted open-weight models as the baseline; external frontier models only through approved, per-tier routing.

## 6. Agent runtime design

The runtime is a deterministic shell around a probabilistic core: an explicit LangGraph state machine in which the model works only at bounded decision points. Use one supervisor graph with specialist subgraphs, never free-roaming multi-agent swarms.

**6.1 Conversation graph, in order**

1. `ingress`: normalise the event, attach channel capabilities (maximum length, rich UI, latency budget) and load thread state from the checkpointer.
2. `deterministic_router`: handle non-LLM flows first: OTP and step-up, USSD menus, consent and STOP keywords, requests for a human, attachments to the scanning queue.
3. `input_guard`: abuse and toxicity checks, prompt-injection heuristics plus a classifier, PII tagging for log masking, language identification.
4. `understand`: a small model returns a typed `Intent` (intent, slots, language, confidence). The risk tier then comes from the policy table, never from the model.
5. `policy_gate`: OPA decides allow, deny, step-up or handoff from auth level, tier, channel, office hours and rate limits.
6. Specialist subgraphs: `knowledge_qa`, `guided_journey`, `self_service`, `calculator`, `verify_official`, `complaint_intake`, `handoff`.
7. `tool_exec`: MCP calls through the gateway with per-tool timeouts, retries only when idempotent, and circuit breakers. Results are stored as typed artifacts referenced by id.
8. `compose`: grounded generation with citations, formatted for the channel and language.
9. `output_guard`: claim-to-source groundedness, numeric provenance, PII and cross-subject leakage, neutrality, prohibited promises (such as "your penalty will be waived"). On failure, regenerate once with feedback, else return a safe fallback and offer handoff.
10. `confirm`: LangGraph `interrupt()` for T2 and T3 with a plain summary of the action; resume through AG-UI, WhatsApp buttons or a USSD option.
11. `egress`: deliver, emit events, update the running summary, write audit records.

Interrupts and durable resume need a checkpointer and a thread ID ([LangGraph docs](https://docs.langchain.com/langgraph)). Use the Postgres checkpointer in every environment except unit tests.

**6.2 Typed state and structured outputs**

- Pydantic v2 models for `Intent`, `Plan`, `ToolCall`, `HandoffTicket` and `Answer`. An `Answer` holds `segments[]`, `citations[]` and `numbers[]`, each number carrying `value`, `unit` and `source_ref`.
- Graph state: `thread_id`, `channel`, `locale`, `auth_level`, `subject_ref` (opaque), `intent`, `slots`, `tier`, `pending_confirmation`, `artifacts[]`, `citations[]`, `budget` (tokens, tool calls, wall time), `safety_flags[]`, `handoff_state`.

**6.3 Context engineering**

- Layered prompt: L0 immutable policy; L1 channel contract; L2 persona and tone (respectful, plain, neutral); L3 node task; L4 retrieved evidence inside data-only delimiters; L5 minimal tool artifacts.
- Token budgets per node, compaction through a running summary, prompt caching for static prefixes.
- Templates live in `ai/prompts/` with semantic versions, owners and linked evals. Changes need CODEOWNERS approval and a passing eval slice.

**6.4 Models and routing**

- A provider-agnostic `ModelPort`; every call goes through the AI gateway.
- Route by node: a small fast model for routing and guards, a mid-size model for composition, a strong model only for complex reasoning.
- Baseline: open-weight instruction models (for example from the Qwen, Llama, Mistral, Gemma or gpt-oss families) served with vLLM or SGLang on in-country GPUs.
- External frontier models (current Anthropic Claude, OpenAI GPT or Google Gemini families) only where SSRA approves the data class, under zero-data-retention terms. Verify each provider's availability and terms for a South Sudan government customer (`OQ-004`).
- Choose models by bake-off on SSRA's eval set: accuracy per language, refusal behaviour, latency and cost. Publish a model card for each.
- Degradation ladder: primary model, then secondary, then self-hosted, then retrieval-only answer cards, then static FAQ plus callback.

**6.5 Memory**

- Short-term: thread state in the Postgres checkpointer, with retention set by policy.
- Long-term: consented preferences only (language, channel, accessibility). No free-text memory of financial facts; per-subject deletion supported.

## 7. Knowledge, grounding and multilingual strategy

Only SSRA-approved, versioned knowledge can reach a taxpayer, and every number comes from a structured Tax Facts registry rather than from free text.

**Sources and metadata.** Acts, Financial Acts, regulations, public notices and circulars, FAQs, forms, procedures and the office directory. Each item carries `doc_type`, issuer, gazette or circular reference, `effective_from`, `effective_to`, `supersedes`, language, audience, approval state and checksum.

**Ingestion.**

- Parse with Docling (layout- and table-aware) and OCR scanned gazettes.
- Chunk by legal structure (Part, Chapter, Section, Subsection) and keep section anchors for citations.
- Align translations wherever SSRA publishes them.

**Retrieval.**

- Hybrid search: Postgres full-text plus pgvector HNSW; pgvector 0.8+ iterative index scans keep filtered queries accurate.
- A multilingual reranker, then metadata filters: as-of date, audience, language, published snapshot.
- Embedding and reranker candidates to test on SSRA data: BGE-M3, Qwen3-Embedding with Qwen3-Reranker, multilingual-e5. Choose by recall@k per language.

**Tax Facts registry.** A structured, versioned table of rates, thresholds, deadlines, penalties and fees. Each fact has a legal citation, effective dates and a named approver. It is exposed through MCP, and the composer must use it for every number it states.

**Knowledge Release workflow** (in the staff console):

1. Draft.
2. Legal review.
3. Approval.
4. Publish an immutable snapshot.
5. Re-index automatically and run the eval regression.
6. Roll back in one step if the gate fails.

Only published snapshots are retrievable by the public assistant.

**Multilingual quality tiers.**

| Tier | Languages | Approach |
| --- | --- | --- |
| A | English | Fully automated, standard thresholds |
| B | Arabic, Juba Arabic | Automated with stricter thresholds; human-reviewed answers for top intents |
| C | Dinka, Nuer, Bari, Zande, Shilluk | Human-translated curated answers and voice first; automate as eval data grows |

- Detect language every turn, answer in the user's language and script, and tolerate code-switching.
- Maintain an SSRA-owned termbase of tax terms per language (`ai/termbase/`), enforced in generation and evals.
- Support right-to-left Arabic script fully in every channel.

## 8. MCP and tool layer

Every tool is an MCP server speaking the stateless 2026-07-28 revision behind agentgateway, and every single invocation is authenticated, authorised and audited.

**8.1 Protocol baseline** ([2026-07-28 release](https://github.com/modelcontextprotocol/specification/releases/tag/2026-07-28), [migration notes](https://www.developersdigest.tech/blog/mcp-2026-07-28-breaking-changes))

- No `initialize` session: each request is self-contained and carries protocol version and client capabilities in `_meta`.
- Gateways route on the `Mcp-Method` and `Mcp-Name` headers, so servers run behind plain round-robin load balancing.
- Cache `tools/list` for the server-declared `ttlMs`.
- Write tool schemas in full JSON Schema 2020-12 and validate each one in CI.
- Use the Tasks extension for long-running operations. Do not build on the deprecated Roots, Sampling or Logging features; use the standardised trace context instead.
- Streamable HTTP only in production; no stdio servers.
- Pin the official MCP Python SDK release that implements 2026-07-28, and check its conformance results first.

**8.2 Authorization** (MCP authorization spec plus [NSA MCP guidance](https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/4496698/), May 2026)

- Each MCP server is an OAuth 2.1 resource server; Keycloak is the authorization server. Tokens are short-lived and audience-bound.
- No token passthrough to downstream systems. Token exchange (RFC 8693) carries the verified taxpayer subject for T1 and higher tools.
- Authorise every tool invocation, not just the connection: gateway policy (CEL or OPA) on calling workload, end-user auth level, tool, argument shape and tier.
- Treat transports as security configuration: mTLS between gateway and servers; deny-all network policies by default.
- Send gateway and server logs to the SIEM, and validate outputs wherever one model's output feeds another.

**8.3 Tool design rules**

- One tool, one business capability; `verb_noun` names; typed input and output schemas with `structuredContent`.
- Set annotations truthfully (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`); the gateway enforces them.
- State-changing tools require an `idempotency_key` and a `confirmation_token`. The runtime issues the token after user confirmation, bound to the argument hash, single-use, with a short TTL.
- Every result carries `provenance` (system, record id, retrieved\_at, as\_of) and `data_classification`.
- Typed errors only: `NOT_FOUND`, `NOT_AUTHORIZED`, `STEP_UP_REQUIRED`, `UPSTREAM_UNAVAILABLE`, `VALIDATION_FAILED`, `RATE_LIMITED`.
- Tool descriptions are model-visible text: review them like code, pin their hashes at the gateway to detect drift, and keep instructions out of them.
- Sanitise outputs: allow-listed URLs only, length caps, wrapped as data before the model sees them.

**8.4 Initial server catalog**

| Server | Initial tools | Tier | Backed by |
| --- | --- | --- | --- |
| knowledge | search\_knowledge, get\_section, list\_forms, get\_office\_info | T0 | Postgres + pgvector |
| tax\_facts | get\_tax\_fact, list\_tax\_facts, calculate\_paye\_estimate, calculate\_withholding\_estimate | T0 | Rules engine |
| official\_channels | verify\_payment\_account, verify\_sender, report\_scam | T0, T2 | Curated registry |
| taxpayer | verify\_tin, get\_registration\_status, get\_profile\_masked | T1 | e-Tax adapter |
| ledger | get\_filing\_status, list\_assessments, get\_balance, list\_payments | T1 | e-Tax adapter |
| payments\_info | list\_payment\_channels, get\_payment\_instructions, generate\_payment\_reference\* | T0, T3 | e-Tax and BoSS adapters |
| tcc | get\_tcc\_status, request\_tcc\* | T1, T3 | e-Tax adapter |
| customs | get\_declaration\_status, lookup\_tariff, estimate\_duties | T0, T1 | e-Customs adapter (`OQ-002`) |
| cases | create\_case, get\_case\_status, add\_case\_note | T2 | Case service |
| appointments | list\_slots, book\_appointment, cancel\_appointment | T2 | Scheduling service |
| notifications | send\_template\_message (consent-checked) | T2, staff or system only | Channel gateway |

\* Ships only if SSRA confirms the upstream capability exists and authorises it for this channel.

**8.5 Agent-to-agent interop, later.** Reserve an A2A v1.0 boundary through agentgateway for collaboration with other government agents, such as the eServices platform. Version 1.0 adds signed Agent Cards and multi-tenancy ([A2A specification](https://a2a-protocol.org/latest/specification/)). Not in the MVP: produce an ADR and a stub Agent Card only.

## 9. Frontend specification: Next.js 16

Two self-hosted Next.js 16.3 apps share one design system and one chat package, and both treat the browser as untrusted and bandwidth as scarce.

**9.1 Baseline**

- Next.js 16.3.x, the latest stable line ([Next.js blog](https://nextjs.org/blog?page=1)). Next.js now ships scheduled security releases; subscribe and patch within 72 hours.
- React 19.2 or later, as Next.js requires. Node.js 26 LTS in production (Active LTS from 28 October 2026); Node.js 24 LTS is acceptable during early development.
- TypeScript 7 (native `tsc`) for type-checking. Keep TypeScript 6 only for tools that still need the compiler API, until TypeScript 7.1 ships one ([InfoQ](https://infoq.com/news/2026/08/typescript-7-released/)).
- pnpm workspaces with Turborepo; Biome for lint and format, with ESLint only for rules Biome lacks (ADR).
- App Router with Server Components by default; Cache Components (`cacheComponents: true` with `"use cache"`) for public content; Turbopack; React Compiler enabled.
- `proxy.ts` (the Next.js 16 replacement for middleware) for nonce-based CSP, locale negotiation and auth gating.
- `output: "standalone"` containers, self-hosted with no platform lock-in, plus a shared Valkey cache handler for multi-instance deployments.
- Use the Next.js DevTools MCP server during development to inspect routes, errors and caching.

**9.2 Apps**

- `apps/web`: public site and chat. A PWA with an offline app shell, cached FAQ cards, a queued outbox, a low-data mode and install support. Use a hand-written service worker per the Next.js PWA guide, or Serwist once its Turbopack support is confirmed (ADR).
- `apps/console`: staff console for the inbox, AI suggestions, knowledge release, QA and dashboards, with stricter CSP, passkeys and short sessions.

**9.3 UI system and chat**

- `packages/ui`: Tailwind CSS v4 with shadcn/ui on Radix primitives and design tokens; RTL through logical properties and `dir`; self-hosted Noto Sans and Noto Naskh Arabic via `next/font`; WCAG 2.2 AA; large touch targets.
- `packages/chat-ui`: AG-UI client with streamed text, tool-progress chips, a citation drawer, a confirmation sheet, a handoff banner, compressed uploads and, in Phase 4, voice notes.
- Generative UI registry: the agent may only request registered components by name, with zod-validated props: `BalanceCard`, `FilingStatusTimeline`, `PaymentInstructionsCard`, `CalculatorForm`, `CitationList`, `ConfirmActionSheet`, `HandoffCard`. Unknown names fall back to text. The model never emits HTML or JavaScript.
- If MCP Apps are adopted later, render them only in a sandboxed iframe from allow-listed servers.

**9.4 Data, forms and auth**

- Typed client generated from the FastAPI OpenAPI 3.1 contract (`packages/api-client`) plus zod schemas; TanStack Query for client cache; React Hook Form with Zod 4.
- Keycloak is the identity provider; staff sign in with passkeys (WebAuthn) configured there.
- The BFF uses Better Auth with generic OIDC, or `openid-client` directly (ADR). Auth.js joined Better Auth in September 2025, and new projects are steered to Better Auth ([TurboStarter](https://www.turbostarter.dev/blog/better-auth-vs-clerk-vs-nextauth-vs-supabase-auth)).
- Server-side sessions in Postgres or Valkey; `httpOnly`, `Secure`, `SameSite=Lax` cookies; tokens never reach browser JavaScript.
- Headers: nonce CSP, Trusted Types, HSTS, COOP, `frame-ancestors 'none'`, Permissions-Policy. CSRF protection on mutations, self-hosted proof-of-work bot defence (such as ALTCHA) on public chat, and no third-party trackers.

**9.5 Performance budgets** (enforced by Lighthouse CI and bundle checks)

- First-load JavaScript at most 150 KB gzip on public pages, targeting 120 KB; the chat bundle loads lazily.
- At p75 on a throttled low-end Android profile: LCP at most 2.5 s, INP at most 200 ms, CLS at most 0.1. A text-only mode stays usable on 2G.
- AVIF or WebP images, subset fonts, HTTP/3 and Brotli at the edge.

**9.6 Testing.** Vitest with Testing Library; Playwright end-to-end with network throttling, RTL locales and mobile viewports; axe-core; visual regression; Storybook for UI and chat cards; contract tests against the generated client.

## 10. Backend specification: Python and FastAPI

The backend is a typed, async Python estate: one modular-monolith API plus separately deployed runtime, channel gateway, MCP servers and workers.

**10.1 Baseline**

- Python 3.14 in production now, with Python 3.15 (released 9 October 2026) in the CI matrix ([endoflife.ai](https://endoflife.ai/python/3.15)). Promote to 3.15 once every critical dependency ships wheels, targeting 3.15.1 or later.
- uv workspaces; Ruff for lint and format; pyright or basedpyright in strict mode, with Astral's `ty` evaluated once stable; pytest.
- FastAPI on the latest 0.13x release, pinned exactly ([PyPI stats](https://pepy.tech/projects/fastapi)); Pydantic v2 with pydantic-settings; SQLAlchemy 2.x async with asyncpg; Alembic.
- httpx with explicit timeouts; retries (stamina or tenacity) only on idempotent calls.
- structlog JSON logs, orjson, OpenTelemetry auto-instrumentation plus manual spans.
- Uvicorn as a single process per container, scaled horizontally (HPA or KEDA); benchmark Granian in an ADR.
- LangGraph 1.2.x with the Postgres checkpointer; the Temporal Python SDK; the AG-UI Python SDK for event streaming.

**10.2 Deployables**

| Service | Purpose |
| --- | --- |
| `services/api` | Modular monolith: `conversations`, `identity_link`, `cases`, `appointments`, `knowledge_admin`, `consent`, `analytics_api`, `admin` |
| `services/agent-runtime` | LangGraph graphs, guardrails, AG-UI SSE endpoint, model and tool ports |
| `services/channel-gateway` | WhatsApp, SMS, USSD and voice adapters: webhook verification, dedupe, rate limits, canonical events |
| `services/workers` | Temporal workflows: ingestion and re-index, eval runs, case SLA timers, notification campaigns, upstream polling |
| `mcp-servers/*` | One deployable per domain server |
| `services/voice` | Phase 4 voice pipeline (Pipecat or LiveKit Agents) |

**10.3 Internal structure.** Every bounded context uses the same layout, and import-linter enforces the boundaries.

```text
src/ssra_api/<context>/
  api/             routers, request/response schemas, dependencies
  application/     use cases, ports (interfaces), DTOs
  domain/          entities, value objects, domain events, policies
  infrastructure/  repositories, adapters, ORM models, clients
  tests/
```

**10.4 API conventions**

- OpenAPI 3.1 is the contract: the snapshot is committed, and oasdiff catches breaking changes in CI.
- `/v1` path versioning; RFC 9457 problem details; cursor pagination; `Idempotency-Key` on POST; ETags; W3C `traceparent`; strict CORS.
- Events: transactional outbox to NATS JetStream in CloudEvents 1.0 envelopes. JSON Schemas in `packages/contracts` generate both Pydantic and TypeScript types.
- Dates: store UTC, compute deadlines in `Africa/Juba`; on the TypeScript side prefer the Temporal API, enabled by default in Node.js 26.

**10.5 Testing**

- pytest with anyio; Testcontainers for Postgres, Valkey, NATS and the Temporal dev server.
- Hypothesis property tests, mandatory for calculators and all money or date logic; mutation testing (mutmut) on the rules engine.
- Schemathesis API fuzzing; respx for HTTP mocks.
- Coverage gates: domain layers at least 90%, overall at least 80%.

## 11. Channel specifications

Every channel implements one `ChannelPort` with capability flags, so the runtime fits each answer to `max_len`, `rich_ui`, `buttons`, `media`, `latency_budget_ms` and `async_only`.

| Channel | Phase | Key requirements |
| --- | --- | --- |
| Web PWA | 1 | AG-UI over SSE (WebSocket optional), resumable streams, offline queue, generative UI registry |
| WhatsApp Business Platform | 1 | Verified business profile; webhook signature checks; 24-hour service window plus pre-approved templates for outbound; buttons and lists for confirmations; media malware-scanned, then OCR; opt-in and opt-out registry; per-message cost tracking |
| SMS | 1 | Licensed local aggregator or MNO over SMPP or HTTP; registered sender ID; GSM-7 versus UCS-2 aware segmentation (Arabic uses UCS-2 at 70 characters per segment); HELP, AGENT and STOP keywords |
| Staff console | 3 | Real-time inbox; AI draft then human approval; takeover and hand-back with full context |
| USSD | 4 | Deterministic menu engine with no LLM in the synchronous path; operator session timeouts and 182-character screens respected; precomputed answers; "send details by SMS" option |
| Voice/IVR | 4 | SIP trunk from an MNO into LiveKit SIP or Asterisk/FreeSWITCH; streaming ASR, runtime, TTS; barge-in; DTMF fallback; language menu; recording consent; warm transfer with an AI summary |

**Speech for local languages.** Use Whisper-class ASR for English and Arabic. For Juba Arabic and local languages, evaluate Meta's open-source Omnilingual ASR, which covers over 1,600 languages and extends to new ones from a handful of samples ([paper](https://arxiv.org/abs/2511.09690v1)). Launch a language on voice only after its word-error rate on SSRA test sets meets the gate.

**Anti-impersonation.** Publish one registry of official channels: sender IDs, WhatsApp number, short codes, bank accounts and domains. The `official_channels` tools answer from it, and every outbound template tells people how to verify the message.

## 12. Security, privacy and AI governance

Security is designed against named 2026 agentic threats, mapped to specific controls, and verified by red-teaming before every release.

**12.1 Frameworks**

- AI and agents: OWASP Top 10 for LLM Applications 2025; OWASP Top 10 for Agentic Applications 2026, risks ASI01 to ASI10 ([OWASP](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026)); OWASP MCP Top 10; the NSA AI Security Center's MCP security design guidance (May 2026).
- Application: OWASP ASVS 5.0 at Level 2, and Level 3 for the staff console and AI gateway.
- Management: NIST AI RMF with the Generative AI Profile (AI 600-1); ISO/IEC 42001:2023; ISO/IEC 27001:2022; NIST SSDF (SP 800-218 and 218A).
- Supply chain and platform: SLSA v1 Build Level 3; CIS benchmarks; WCAG 2.2 for accessibility.
- Privacy: with no national data-protection law in force, apply GDPR-grade controls and AU Malabo Convention principles, track the 2026 Data Protection Bill, and confirm taxpayer-secrecy duties with SSRA Legal.

**12.2 Threat model deliverables**

- STRIDE per component, plus agentic abuse cases mapped to ASI01 to ASI10.
- Required cases: goal hijack through injected documents; tool misuse to read another taxpayer's data; confused-deputy privilege abuse; compromised models, packages or MCP servers; knowledge-base poisoning; fake confirmations that exploit human trust; cascading failures; denial-of-wallet; SSRA impersonation; SIM-swap account takeover.
- A red-team plan per release, automated and manual.

**12.3 Mandatory controls**

- **Identity proofing:** anonymous, then phone OTP, then TIN bound to OTP (plus e-Tax knowledge factors if available), then fresh-OTP step-up for T3. Check SIM-swap signals where operators offer them (`OQ-005`). Staff use SSO, passkeys, device posture checks and just-in-time admin.
- **Subject binding:** every T1+ call carries the verified subject, and adapters enforce ownership server-side. Never trust identity arguments produced by the model.
- **Data minimisation:** masked identifiers in model context (TIN ••••1234). Redact PII in logs and traces with Microsoft Presidio plus custom recognisers for TINs, +211 phone numbers and national IDs. Send no PII to external providers unless SSRA approves that data class.
- **Encryption:** TLS 1.3 everywhere; mTLS inside the cluster; volume encryption plus column-level encryption of sensitive fields through OpenBao transit; keys in OpenBao, HSM-backed where available.
- **Audit:** an append-only, hash-chained log of actor, on-behalf-of, action, argument and result hashes, and model, prompt and knowledge versions; WORM storage; SIEM export.
- **AI-specific:** instruction hierarchy, spotlighting, tool-result isolation, capability-scoped tools, deny-by-default egress, output validators, rate limits and spend caps, and a kill switch per model, tool and channel.

**12.4 Supply chain: 2026 lessons.** In March 2026, attackers used a compromised Trivy scanner in LiteLLM's CI to steal its publishing token, then pushed credential-stealing LiteLLM releases to PyPI ([LiteLLM incident](https://github.com/BerriAI/litellm/issues/24518), [analysis](https://lmmarketcap.com/litellm-supply-chain-attack)). Treat CI tools and AI gateways as prime targets.

- Pin every dependency with hashes, and every CI action or tool by digest or commit SHA.
- Isolate publish credentials; prefer trusted publishing and verify provenance on install.
- Enforce a dependency cooldown of at least 7 days (pnpm `minimumReleaseAge`, uv `exclude-newer`), except for reviewed security fixes.
- Install through an internal mirror; produce a CycloneDX SBOM per image; sign images with cosign and verify them at admission with Kyverno.
- Checksum and scan model artifacts; review Renovate updates in small groups.

**12.5 AI governance**

- AI risk register, model cards, system card, a datasheet for the knowledge corpus, and an AI impact assessment.
- Human-oversight procedures and an AI incident playbook with a severity matrix.
- Change advisory review for prompt, model and knowledge releases.
- Transparency: users are told they are talking to SSRA's virtual assistant, with an easy path to a human and to complain.

## 13. Reliability, performance and cost

The initial service levels below are starting targets; refine them with SSRA after Phase 0 baselining.

| Measure | Target |
| --- | --- |
| Web and WhatsApp availability | 99.9% per month |
| Web time to first token, p95 | At most 1.5 s |
| Grounded knowledge answer, p95 | At most 6 s |
| Tool-backed answer, p95 | At most 8 s |
| WhatsApp reply, p95 | At most 10 s |
| USSD screen response | At most 2 s, deterministic |
| Voice, end of speech to first audio, p50 | At most 1.0 s |
| Recovery point objective / recovery time objective | At most 5 min / at most 1 h |

**Resilience.**

- Timeouts everywhere; retries only on idempotent operations; circuit breakers per upstream; bulkheads per channel; queue-based backpressure.
- The degradation ladder from section 6.4, plus a public status page.
- WAL archiving with point-in-time recovery, a second site or zone, and quarterly restore drills.

**Capacity.** Plan for filing-deadline peaks at 10 times baseline until measured. Load-test with k6, including SSE streams, and run chaos experiments with Chaos Mesh or LitmusChaos.

**Cost controls.**

- Token and tool-call budgets per conversation; prompt caching; small-model-first routing.
- Semantic cache only for anonymous T0 answers, keyed by knowledge snapshot and locale.
- Cost attribution per intent and channel through OpenTelemetry attributes; daily spend caps with alerts at the gateway.

## 14. Evaluation and observability

No prompt, model, tool or knowledge change ships without passing its eval slice, and every production conversation is traceable end to end.

**14.1 Eval harness** (`evals/`)

- pytest-based runners with Langfuse datasets and experiments; promptfoo red-team suites; garak or PyRIT for adversarial probes.
- Datasets: golden Q&A per language with expected citations and numbers; journey trajectories with expected tool sequences; adversarial sets (injection, jailbreak, social engineering for another person's data); channel-format tests (SMS and USSD limits); handoff appropriateness; neutrality.
- Before Phase 1 launch, seed at least 300 English, 150 Arabic and 150 Juba Arabic items reviewed by SSRA subject experts.

**14.2 Phase 1 launch gates**

| Metric | Gate |
| --- | --- |
| Numeric accuracy against Tax Facts | 100% |
| Citation precision | At least 95% |
| Groundedness (faithfulness) | At least 95% |
| Correct abstention on out-of-scope questions | At least 95% |
| Cross-subject data leakage in red-team | 0 cases |
| Language parity gap, Tier B versus English | At most 5 points |
| Latency and cost per resolved conversation | Within section 13 targets and budget |

- CI runs the affected eval slice on every PR touching prompts, models, tools or knowledge. A nightly full suite blocks releases on regression.
- Online: sampled human review in the console against a QA rubric, user feedback with reasons, and drift monitors on intent mix, abstention rate and guardrail triggers.

**14.3 Observability**

- OpenTelemetry end to end (browser, BFF, runtime, gateway, MCP servers, adapters), using the GenAI semantic conventions and MCP's standardised trace context.
- Tail-based sampling that keeps every error, escalation and guardrail trigger.
- Langfuse, self-hosted, for LLM traces, prompt versions and evals; Grafana LGTM (Loki, Grafana, Tempo, Mimir) for logs, metrics and traces.
- Dashboards for the CX funnel, AI quality, safety, cost, latency and upstream health; SLO burn-rate alerts; a log processor that enforces PII redaction.

## 15. Platform, DevSecOps and delivery

The platform runs on in-country Kubernetes managed entirely as code, with signed artifacts and progressive delivery.

- **Monorepo:** pnpm and Turborepo for TypeScript, a uv workspace for Python, and Taskfile as the single entry point (`task up`, `test`, `lint`, `eval`, `gen`). Dev Containers plus Docker Compose with mock upstreams for local work.
- **CI pipeline:** portable, with a reference implementation in GitHub Actions that must also run on self-hosted GitLab or Forgejo. Stages: lint, type-check, unit, contract, build, SBOM, vulnerability scan, SAST (Semgrep), secrets scan (gitleaks), IaC scan, eval slice, sign, publish, deploy through Argo CD, then canary with Argo Rollouts analysing SLOs and evals.
- **Environments:** local, dev, staging (production-like, synthetic data only), production, DR. Real taxpayer data never leaves production.
- **Infrastructure as code:** OpenTofu modules, Helm charts with Kustomize overlays, Kyverno policies, External Secrets with OpenBao, cert-manager, CloudNativePG (HA and point-in-time recovery), Velero backups, Harbor with replication.
- **Release and change:** Conventional Commits; Changesets for TypeScript and release-please for Python; change-advisory sign-off for prompt, model and knowledge releases.
- **Agent conventions:** `AGENTS.md` is the agent rulebook and `CLAUDE.md` imports it. AGENTS.md now sits under the Agentic AI Foundation alongside MCP ([agentgateway blog](https://agentgateway.dev/blog/2026-06-26-scaling-mcp-proxy-to-agent-gateway/)).

## 16. Repository blueprint

Scaffold the monorepo exactly as below; any deviation needs an ADR.

```text
ssra-cx/
├── AGENTS.md                  # agent rulebook (CLAUDE.md imports it)
├── CLAUDE.md
├── README.md
├── Taskfile.yml               # task up | test | lint | eval | gen
├── package.json  pnpm-workspace.yaml  turbo.json
├── pyproject.toml  uv.lock    # uv workspace root
├── renovate.json
├── .github/workflows/         # portable CI (or .gitlab-ci.yml)
├── .devcontainer/
├── docs/
│   ├── 00-master-prompt.md    # this document
│   ├── PROGRESS.md
│   ├── open-questions.md
│   ├── architecture/          # overview, C4, sequences, data model
│   ├── adr/                   # 0001-record-architecture-decisions.md ...
│   ├── security/              # threat model, controls matrix, pentests
│   ├── ai-governance/         # risk register, model cards, system card, impact assessment
│   ├── product/               # personas, journeys, conversation design
│   ├── mcp/                   # tool catalog, server template guide
│   └── runbooks/              # incident, DR, model and knowledge rollback
├── apps/
│   ├── web/                   # Next.js 16 taxpayer PWA + chat
│   │   └── src/
│   │       ├── app/[locale]/      # (public) (chat) (account) route groups
│   │       ├── app/api/           # BFF: AG-UI stream proxy, auth, uploads
│   │       ├── proxy.ts           # CSP nonce, locale, auth gating
│   │       └── components/  lib/  i18n/
│   └── console/               # Next.js 16 staff console
├── packages/                  # shared TypeScript
│   ├── ui/                    # design system, tokens, RTL
│   ├── chat-ui/               # AG-UI client + generative UI registry
│   ├── api-client/            # generated from OpenAPI
│   ├── contracts/             # JSON Schemas -> TS + Pydantic codegen
│   ├── i18n/                  # ICU messages, termbase loaders
│   ├── telemetry/             # OpenTelemetry web, web-vitals
│   └── config/                # tsconfig, biome, tailwind preset
├── services/                  # Python deployables
│   ├── api/                   # FastAPI modular monolith
│   ├── agent-runtime/         # LangGraph + AG-UI
│   ├── channel-gateway/       # WhatsApp, SMS, USSD, voice
│   ├── workers/               # Temporal workflows
│   └── voice/                 # Phase 4
├── mcp-servers/
│   ├── _template/             # generator for new servers
│   ├── knowledge/  tax-facts/  official-channels/
│   ├── taxpayer/  ledger/  payments-info/  tcc/
│   └── customs/  cases/  appointments/  notifications/
├── libs/                      # shared Python
│   ├── ssra_core/             # settings, logging, errors, ids, clock
│   ├── ssra_security/         # authn/z clients, PII redaction, audit
│   ├── ssra_llm/              # ModelPort, prompt registry, structured output
│   ├── ssra_mcp/              # server base: auth, idempotency, audit, provenance
│   ├── ssra_rules/            # versioned rules engine + Tax Facts
│   ├── ssra_adapters/         # e-Tax, e-Customs, BoSS, mobile money ports + mocks
│   └── ssra_testing/          # factories, synthetic data, fixtures
├── ai/
│   ├── prompts/               # versioned templates + metadata
│   ├── policies/              # risk-tiers.yaml, OPA rego, guardrail configs
│   ├── routing/               # model routing and budgets
│   └── termbase/              # multilingual tax glossary
├── knowledge/
│   ├── sources.yaml           # manifest only; no confidential documents in git
│   └── tax-facts/             # approved seed facts with legal citations
├── evals/
│   └── datasets/  rubrics/  suites/  redteam/  reports/
├── infra/
│   ├── compose/               # local stack + mock upstreams
│   ├── helm/  k8s/overlays/{dev,staging,prod,dr}
│   ├── tofu/                  # modules and environments
│   ├── gateway/               # agentgateway routes and policies
│   ├── policies/              # Kyverno, network policies
│   └── observability/         # OTel collector, dashboards, alerts
└── tools/                     # scripts, codegen, data generators
```

**Inside an MCP server** (every server follows `_template/`):

```text
mcp-servers/ledger/
├── pyproject.toml
├── Dockerfile
├── src/ssra_mcp_ledger/
│   ├── server.py        # tool registration, stateless 2026-07-28
│   ├── tools/           # one module per tool: schema, handler, policy
│   ├── adapters.py      # LedgerPort -> e-Tax adapter or mock
│   └── settings.py
└── tests/               # unit, contract, golden
```

**Inside the agent runtime:**

```text
services/agent-runtime/src/ssra_runtime/
├── graphs/       conversation.py  knowledge_qa.py  self_service.py  handoff.py
├── nodes/        ingress.py  router.py  guards.py  understand.py  policy_gate.py
│                 compose.py  confirm.py  egress.py
├── guardrails/   injection.py  grounding.py  numeric_provenance.py  pii.py  neutrality.py
├── retrieval/    hybrid.py  rerank.py  filters.py
├── streaming/    agui.py
├── tools/        mcp_client.py
├── state.py  schemas.py
└── tests/
```

## 17. Core data model and contracts

These ten entities are the minimum; refine them in `docs/architecture/data-model.md` before writing any migration.

| Entity | Key fields | Notes |
| --- | --- | --- |
| Conversation | id, channel, locale, subject\_ref (optional), auth\_level, started\_at, status, csat | Partitioned by month |
| Message | id, conversation\_id, role, content\_ref, language, created\_at, safety\_flags | Large content in object storage |
| ToolInvocation | id, conversation\_id, server, tool, args\_hash, result\_ref, tier, status, latency\_ms, trace\_id | Joins traces to audit |
| Confirmation | id, conversation\_id, action\_digest, issued\_at, expires\_at, used\_at | Single-use, bound to the argument hash |
| Handoff | id, conversation\_id, reason, queue, assigned\_to, sla\_due, outcome | Drives the staff inbox |
| Case | id, subject\_ref, type, status, priority, sla\_due, events | SLA timers run in Temporal |
| Consent | id, subject\_ref, channel, purpose, granted\_at, revoked\_at, evidence | Checked before any outbound message |
| KnowledgeSnapshot | version, approved\_by, published\_at, checksum | Documents and chunks reference it |
| TaxFact | key, value, unit, currency, applies\_to, effective\_from, effective\_to, legal\_ref, approved\_by, version | The only source of numbers |
| AuditEvent | id, actor, on\_behalf\_of, action, resource, digest, prev\_hash, hash, at | Append-only, hash-chained |

- Use UUIDv7 keys (PostgreSQL 18 provides `uuidv7()`), monthly partitions for high-volume tables, retention per data class, and row-level security to scope staff by office or region.
- Canonical `ConversationEvent` (CloudEvents 1.0): `id`, `source` (channel), `type`, `subject` (thread), `time`, `datacontenttype`, and `data` holding locale, content parts (text or media reference) and channel metadata.
- All schemas live in `packages/contracts` and generate Pydantic and TypeScript types. Never hand-write a duplicate.

## 18. Phased delivery and exit gates

Five phases each end at a gate that SSRA signs off, and no phase starts until the previous gate passes.

&#91;embedded content: delivery roadmap · 5 phases, 5 gates\]

Gate 1 is the public launch, so it carries the strictest checks; the testable criteria for every gate follow.

1. **Phase 0: foundations.** ADR-001 to ADR-015; C4 levels 1 to 3; threat model v1; repo scaffold; CI/CD with supply-chain controls; local stack via `task up`; mock adapters; design system; an AG-UI hello-world streaming through the gateway to a mock MCP tool; eval harness skeleton; first public corpus ingested; Tax Facts schema.
   - Gate 0: one command brings up the stack; CI is green; SSRA's technical lead approves the ADRs.
2. **Phase 1: public assistant** on web, WhatsApp and SMS FAQ, in English, Juba Arabic and Arabic.
   - Gate 1: section 14 launch gates met; penetration test and red-team passed; load test at 10 times baseline; SSRA Legal signs the knowledge snapshot; runbooks written; staff trained on handoff.
3. **Phase 2: authenticated self-service** at T1 and T2, and T3 only where the upstream capability exists.
   - Gate 2: identity proofing approved; subject binding proven by tests and the pen test; privacy impact assessment approved; the audit trail reconstructs any conversation.
4. **Phase 3: staff copilot and knowledge operations.**
   - Gate 3: a pilot shows better handling time and QA scores; the knowledge release workflow is live.
5. **Phase 4: voice, USSD, proactive outreach and insights.**
   - Gate 4: word-error-rate and intent-accuracy thresholds met per language; the consent registry passes audit.

## 19. Working agreement and Definition of Done

Work in small, verifiable increments, and treat this section as your standing instructions.

**How you work**

- Start in plan mode: read this document, then produce `docs/architecture/overview.md`, the ADR list, `docs/open-questions.md` and a Phase 0 task plan. Wait for approval before writing code.
- Version policy: before adding or upgrading a dependency, read its official release notes, pin the exact version with hashes, and record the date you checked. Never adopt a release younger than 7 days unless it is a reviewed security fix.
- Codebase navigation: once the repo has structure, build a knowledge graph with graphify, from its official repository `safishamsi/graphify` ([GitHub](https://github.com/safishamsi/graphify)). Run `graphify install`, then `graphify claude install` (it adds a CLAUDE.md rule and a pre-search hook), then `/graphify .`.
- Read `graphify-out/GRAPH_REPORT.md` or run `graphify query` before any broad file exploration, and refresh with `--update` after structural changes. Graphify uses an LLM backend to extract concepts from docs and images, so use an SSRA-approved backend and keep secrets and data out of the graph.
- Keep `AGENTS.md`, `docs/PROGRESS.md` and `docs/open-questions.md` current after every work session.
- Small PRs (aim for under 400 changed lines), Conventional Commits, and no generated code without tests.
- Mock every SSRA upstream until real API specifications and test credentials arrive, then write contract tests from those specifications.
- Never commit real taxpayer data, credentials or confidential legal drafts; use synthetic data only.
- When SSRA law or policy is unclear, do not guess: log an `OQ` and implement the safest behaviour, which is to abstain and hand off.
- Verify framework APIs against official documentation (a docs MCP server helps) and the Next.js DevTools MCP rather than memory.

**Definition of Done, for every task**

- [ ] Code, tests (unit, contract and property where relevant) and docs updated; strict types; lint clean.
- [ ] Threat-model delta noted; no new secrets; dependency changes pinned and justified.
- [ ] AI changes: eval slice passed; prompt, model or knowledge version bumped; changelog entry written.
- [ ] Spans, metrics and logs added; dashboards updated for user-facing changes.
- [ ] UI changes checked for accessibility and i18n, with RTL screenshots for Arabic.
- [ ] ADR written for any decision with a reversal cost.

## 20. Open questions for SSRA

Seed `docs/open-questions.md` with these twelve items; each one blocks the named phase until SSRA answers it.

| ID | Question | Blocks |
| --- | --- | --- |
| OQ-001 | e-Tax APIs: endpoints, auth model, rate limits, sandbox, data dictionary, TIN format | Phase 2 |
| OQ-002 | e-Customs platform and APIs: declaration status, tariff data | Phase 2 |
| OQ-003 | Hosting: NCA data-centre capacity (CPU, GPU, storage, network), DR site, any approved regional cloud | Phase 0 |
| OQ-004 | AI providers: approved external models, data classes allowed to leave the country, zero-retention contracts | Phase 1 |
| OQ-005 | Identity: civil-registry or national-ID verification, OTP delivery partners, SIM-swap signals, staff identity provider | Phase 2 |
| OQ-006 | Payments: who may generate payment references, bank and mobile-money partners, Bank of South Sudan integration | Phase 2 |
| OQ-007 | Channels: WhatsApp number and verification, SMS sender ID, USSD short code, toll-free voice line, operator agreements | Phase 1 |
| OQ-008 | Languages: priority order, translation and review capacity, termbase ownership | Phase 1 |
| OQ-009 | Legal: retention schedule, recording consent, taxpayer-secrecy provisions, data-protection bill status | Phase 1 |
| OQ-010 | Operations: contact-centre size and hours, escalation matrix, SLAs, console roles | Phase 1 |
| OQ-011 | Official-channel registry and branding for anti-scam verification | Phase 1 |
| OQ-012 | Procurement: open-source policy, licensing, export-control and sanctions screening of vendors | Phase 0 |

## Appendix A: Version baseline

Verified on 16 October 2026; re-verify every row at scaffold time and pin exact versions in lockfiles.

| Component | Baseline | Note |
| --- | --- | --- |
| [Next.js](https://nextjs.org/blog?page=1) | 16.3.x | Scheduled security releases; patch fast |
| React | 19.2 or later | As required by Next.js |
| [Node.js](https://www.devx.com/coding/nodejs-26-lts-new-features-release-date/) | 26 LTS from 28 Oct 2026; 24 LTS meanwhile | One major release a year from Node.js 27 ([InfoQ](https://infoq.com/news/2026/06/nodejs-release-changes)) |
| [TypeScript](https://infoq.com/news/2026/08/typescript-7-released/) | 7.0.x native `tsc`; 6.x for API-dependent tools | Stable compiler API expected in 7.1 |
| [Python](https://endoflife.ai/python/3.15) | 3.14 in production; 3.15 in CI | 3.15.0 released 9 Oct 2026 |
| [FastAPI](https://pepy.tech/projects/fastapi) | Latest 0.13x, pinned | Pydantic v2 only |
| [LangGraph](https://docs.langchain.com/langgraph) | 1.2.x | Checkpointer plus thread ID for interrupts |
| [MCP](https://github.com/modelcontextprotocol/specification/releases/tag/2026-07-28) | Revision 2026-07-28 | Stateless core; JSON Schema 2020-12 tool schemas |
| [A2A](https://a2a-protocol.org/latest/specification/) | 1.0.x | Future interop only |
| [AG-UI](https://aws.amazon.com/about-aws/whats-new/2026/03/amazon-bedrock-agentcore-runtime-ag-ui-protocol) | Latest | SSE transport |
| [agentgateway](https://agentgateway.dev/docs/standalone/main/documentation/about/introduction/) | Latest 1.x | Agentic AI Foundation project; LLM, MCP and A2A in one gateway |
| [PostgreSQL](https://www.postgresql.org/) | 18.x | 19 in beta; upgrade after 19.1 and extension support |

## Appendix B: Reference sources

These pages back the facts above; treat them as starting points and re-check at build time.

**SSRA and South Sudan**

- [Parliament renames NRA to SSRA (Eye Radio, Oct 2023)](https://www.eyeradio.org/parliament-passes-s-sudan-revenue-authority-amendment-bill-2023/)
- [eTax portal](https://etax.nra.gov.ss/) and [eTax rollout from July 2021 (Orbitax)](https://orbitax.com/news/country/article/South-Sudan-implements-an-elec_a9dad631-8bfe-409d-83c5-b1dc0c132ff9)
- [SSRA policy document](https://cms.nra.gov.ss/uploads/SOUTH_SUDAN_REVENUE_AUTHORIRTY_ACT_2023_final_copy_677778ef23.pdf)
- [eServices single window and March 2026 e-Tax directive (Eye Radio)](https://www.eyeradio.org/south-sudans-digital-reckoning-why-eservices-are-an-economic-imperative-not-a-luxury/)
- [Bank-only tax payments and digitisation (Eye Radio)](https://www.eyeradio.org/ssra-nears-90-digitization-of-tax-system-akuei/)
- [Financial Act 2024/2025 (EY)](https://taxnews.ey.com/news/2024-2303-south-sudan-enacts-financial-act-2024-2025)
- [Data Protection Bill planned for 2026 (Radio Tamazuj)](https://www.radiotamazuj.org/en/news/article/south-sudan-to-get-data-protection-bill-in-2026-says-minister)
- [Cybercrimes and Computer Misuse Provisional Order 2021 brief (Africa Portal)](https://africaportal.org/?p=10580)

**Protocols, security and AI**

- [MCP 2026-07-28 release](https://github.com/modelcontextprotocol/specification/releases/tag/2026-07-28) and [migration notes (Developers Digest)](https://www.developersdigest.tech/blog/mcp-2026-07-28-breaking-changes)
- [NSA MCP security design guidance (May 2026)](https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/4496698/)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026)
- [A2A specification](https://a2a-protocol.org/latest/specification/)
- [AG-UI support in Amazon Bedrock AgentCore (AWS)](https://aws.amazon.com/about-aws/whats-new/2026/03/amazon-bedrock-agentcore-runtime-ag-ui-protocol)
- [agentgateway documentation](https://agentgateway.dev/docs/standalone/main/documentation/about/introduction/)
- [LangGraph documentation](https://docs.langchain.com/langgraph)
- [LiteLLM PyPI compromise (GitHub issue)](https://github.com/BerriAI/litellm/issues/24518)
- [Omnilingual ASR paper (arXiv)](https://arxiv.org/abs/2511.09690v1)
- [graphify](https://github.com/safishamsi/graphify)

**Runtimes and frameworks**

- [Next.js blog](https://nextjs.org/blog?page=1)
- [Node.js 26 LTS date (DevX)](https://www.devx.com/coding/nodejs-26-lts-new-features-release-date/) and [annual release model (InfoQ)](https://infoq.com/news/2026/06/nodejs-release-changes)
- [TypeScript 7 release (InfoQ)](https://infoq.com/news/2026/08/typescript-7-released/)
- [Python 3.15 status (endoflife.ai)](https://endoflife.ai/python/3.15)
- [FastAPI release stats (pepy.tech)](https://pepy.tech/projects/fastapi)
- [PostgreSQL release status](https://www.postgresql.org/)
- [Better Auth and Auth.js (TurboStarter)](https://www.turbostarter.dev/blog/better-auth-vs-clerk-vs-nextauth-vs-supabase-auth)

## Appendix C: Operator notes and kickoff message

Run this prompt in phases, with the agent sandboxed and every gate reviewed by a person.

1. Export this doc as Markdown and save it in an empty repository as `docs/00-master-prompt.md`.
2. Give the agent a sandboxed shell, no production credentials and no real taxpayer data.
3. Start in plan mode with the kickoff message below, and approve the Phase 0 plan before any code is written.
4. Feed SSRA's answers into `docs/open-questions.md` as they arrive, and ask the agent to update the affected ADRs.
5. Review each phase gate with SSRA before the next phase starts.

**Kickoff message**

```text
Read docs/00-master-prompt.md in full. It is your single source of truth.
Work only on Phase 0 planning (sections 18 and 19):
1. Write docs/architecture/overview.md (C4 levels 1-3, as text plus Mermaid).
2. List ADR-001 to ADR-015 with one-line problem statements, then draft the first five.
3. Create docs/open-questions.md from section 20.
4. Propose the Phase 0 task plan with acceptance criteria for each task.
Verify every dependency version against official release notes before proposing it.
Do not write application code until I approve the plan.
```
