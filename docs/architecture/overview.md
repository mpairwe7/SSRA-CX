# SSRA Assist — Architecture Overview (C4 Levels 1–3)

**Status:** Draft (Phase 0 Planning — Awaiting Gate 0 Approval)  
**Date:** 2026-10-16  
**Source of Truth:** [`docs/00-master-prompt.md`](../00-master-prompt.md)

---

## 1. Executive Summary & Architectural Posture

**SSRA Assist** is a sovereign, multilingual, omnichannel agentic customer-experience (CX) platform for the **South Sudan Revenue Authority (SSRA)** (formerly the National Revenue Authority, NRA; both names are treated as synonyms across search, content, and intent detection).

It operates strictly as a **governed, intelligent front door** to SSRA's existing e-Tax (`etax.nra.gov.ss`), e-Customs (`OQ-002`), National eServices single window, and Bank of South Sudan (BoSS) banking estate. It is **never** a system of record or a shadow ledger, and it **never** executes payments, refunds, transfers, waivers, penalty remissions, or legal rulings.

### Non-Negotiable Architectural Invariants

1. **Grounded or Silent:** Every factual claim cites an SSRA-approved source (`KnowledgeSnapshot` version, document, section anchor, and effective date). Insufficient evidence triggers abstention and a human handoff offer.
2. **Numbers Come from Tools:** Tax rates, thresholds, deadlines (`Africa/Juba`, UTC+02:00), penalties, balances, and official BoSS exchange rates originate exclusively from deterministic MCP tools (`tax_facts` or authenticated ledger tools). The `numeric_provenance` output validator blocks any numeric claim not traceable to a tool result or cited Tax Fact.
3. **Risk-Tiered Autonomy (T0–T4):** Risk tier is assigned deterministically from `ai/policies/risk-tiers.yaml` by intent and tool—never by the LLM—and enforced at both the `policy_gate` node (OPA) and `agentgateway`.
4. **Single Governed Egress (`agentgateway`):** Every LLM inference request, MCP tool invocation (stateless revision `2026-07-28`), and future A2A v1.0 message transits `agentgateway` with mTLS, OAuth 2.1 RFC 8693 token exchange, per-tool authorization, spend caps, and hash-chained WORM audit logging.
5. **Subject Binding & Zero Trust for Model Arguments:** Identity proofing occurs outside the LLM in the `deterministic_router`. Verified identity is bound to the conversation thread as an opaque `subject_ref` and propagated via RFC 8693 token exchange. Adapters enforce ownership server-side and never trust TIN or identity arguments emitted by a model.
6. **Sovereign & Low-Bandwidth First:** Hosted in-country at the National Communication Authority (NCA) data centre (`OQ-003`) on Kubernetes (RKE2/k3s) using open-weight models (vLLM/SGLang). Designed for 2G/intermittent mobile networks, low-end Android and feature phones, and multilingual inclusivity (`en`, `pga`, `ar` RTL in Phase 1; `din`, `nus`, `bfa`, `zne`, `shk` in Phase 4).

---

## 2. Twelve-Layer Reference Architecture

Every request traverses a strict top-to-bottom pipeline so channels are isolated from intelligence, and intelligence is isolated from systems of record:

| # | Layer | Components | Primary Responsibility |
|---|---|---|---|
| 1 | **Channels** | Web PWA, WhatsApp Business Platform, SMS, USSD, Voice/IVR, Staff Console | Reach taxpayers and staff on the devices and networks they have |
| 2 | **Edge** | CDN, WAF, DDoS & bot defence (ALTCHA PoW), TLS 1.3 | Absorb network/application abuse and terminate TLS 1.3 at the perimeter |
| 3 | **Experience (BFF)** | `apps/web`, `apps/console` (Next.js 16.3.x, `proxy.ts`, Server Components) | Render UI, enforce nonce CSP & Trusted Types, manage `httpOnly` sessions, proxy AG-UI SSE |
| 4 | **Channel Gateway** | `services/channel-gateway` (FastAPI) | Verify webhook signatures, deduplicate deliveries, map sessions, normalise to CloudEvents 1.0 |
| 5 | **Agent Runtime** | `services/agent-runtime` (FastAPI + LangGraph 1.2.x) | Execute deterministic 11-node conversation graph, guardrails, interrupts, and AG-UI streaming |
| 6 | **AI Gateway** | `agentgateway` (1.x) | Single egress for LLM, MCP (`2026-07-28`), and future A2A (`1.0`); OPA policy, token exchange, spend caps, audit |
| 7 | **Domain Tools** | `mcp-servers/*` (Python MCP `2026-07-28` Streamable HTTP) | Expose one governed, schema-validated business capability per tool |
| 8 | **Integration** | `libs/ssra_adapters` (Anti-Corruption Layer) | Adapt e-Tax, e-Customs, BoSS/banks, mobile money, SMS/USSD aggregators, National eServices |
| 9 | **Data** | PostgreSQL 18 + pgvector 0.8+, Valkey 8, S3/MinIO (WORM), NATS JetStream, Temporal | Persist transactional state, hybrid vectors/FTS, caches, objects, event streams, durable workflows |
| 10 | **AI Services** | vLLM / SGLang, Embedding & Reranker servers, ASR/TTS (Whisper / Omnilingual ASR), Guard models | Sovereign in-country inference and speech processing |
| 11 | **Security** | Keycloak (OAuth 2.1 / WebAuthn), OpenBao (Transit KMS/HSM), OPA, cert-manager, mTLS mesh, SIEM | Identity, secrets/encryption, policy-as-code, zero-trust transport, security monitoring |
| 12 | **Platform** | Kubernetes (RKE2/k3s), Argo CD + Rollouts, OpenTofu, Harbor, Kyverno, CloudNativePG, Velero, OTel + LGTM + Langfuse | Provision, verify supply chain (SLSA L3 / Cosign), deploy progressively, observe, and recover |

---

## 3. C4 Level 1 — System Context

### 3.1 Context Description

At the System Context level, **SSRA Assist** sits between two primary user groups (**Taxpayers & Trade Actors** and **SSRA Staff**) and SSRA's authoritative external systems (**National e-Tax System**, **e-Customs Platform**, **Bank of South Sudan & Commercial Banks**, **National eServices Single Window**, and **Telecom / Messaging Aggregators**).

- **Taxpayers** interact via Web PWA (`apps/web`), WhatsApp, SMS, USSD, or Voice/IVR in English (`en`), Juba Arabic (`pga`), Arabic (`ar`), and national languages (`din`, `nus`, `bfa`, `zne`, `shk`) to ask grounded tax/customs questions, run deterministic tax estimates, verify official SSRA channels/accounts against scammers, check their own T1 balances/filings/TCC status (after OTP + TIN verification), and book appointments or open cases (T2).
- **SSRA Staff** (Contact-Centre Agents, Tax/Customs Officers, Supervisors/QA, Legal & Policy Knowledge Owners, ICT/SecOps) use the **Staff Console** (`apps/console`) with WebAuthn passkeys to handle escalated conversations, review AI-drafted cited responses, author/approve/publish immutable `KnowledgeSnapshot` and `TaxFact` releases, and monitor quality and security.
- **External Systems of Record** remain the sole authority for taxpayer registration, assessments, ledger balances, payment references, customs declarations, and exchange rates.

### 3.2 C4 Level 1 Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph Users["Users (South Sudan & Diaspora)"]
        Taxpayer["👤 Taxpayer / Importer / NGO / Tax Agent\n(Web PWA, WhatsApp, SMS, USSD, Voice/IVR)\nLanguages: en, pga, ar, din, nus, bfa, zne, shk"]
        Agent["👤 SSRA Contact-Centre Agent & Officer\n(Staff Console — Inbox, Handoffs, Cases)"]
        Legal["👤 SSRA Legal & Policy Team\n(Staff Console — Knowledge & Tax Facts Approval)"]
        Supervisor["👤 SSRA Supervisor, QA & SecOps\n(Dashboards, QA Rubrics, Audit & SIEM)"]
    end

    subgraph SovereignBoundary["NCA Sovereign Hosting Boundary (Juba, South Sudan)"]
        SSRAAssist["🏛️ SSRA Assist Platform\nSovereign Omnichannel Agentic CX Platform\n(Next.js 16, FastAPI, LangGraph, agentgateway, MCP 2026-07-28)"]
    end

    subgraph ExternalEstate["SSRA & National Digital Estate (Systems of Record)"]
        ETax["🏦 SSRA National e-Tax System\n(etax.nra.gov.ss)\nTIN, Filings, Assessments, Ledger, TCC"]
        ECustoms["🛃 SSRA e-Customs Platform\n(OQ-002)\nDeclarations, Tariffs, Duties"]
        BoSS["💱 Bank of South Sudan (BoSS) & Commercial Banks\nOfficial FX Rates, TSA Payment Channels"]
        EServices["🪪 National eServices Single Window\nMoJ Business Registry, NGOs, Civil Registry"]
    end

    subgraph TelecomAndCloud["Telecom & Optional External Providers"]
        Telco["📱 Telecom & Messaging Providers\nWhatsApp Business API, Licensed SMS/SMPP, USSD Gateway, SIP Trunk"]
        ExtLLM["☁️ Approved External Frontier LLM (Optional, OQ-004)\nT0-Only / Zero-Data-Retention behind agentgateway"]
    end

    Taxpayer <-->|"HTTPS (Web PWA)"| SSRAAssist
    Taxpayer <-->|"WhatsApp / SMS / USSD / Voice"| Telco
    Telco <-->|"Signed Webhooks / SMPP / SIP"| SSRAAssist

    Agent <-->|"HTTPS + Passkey (WebAuthn)"| SSRAAssist
    Legal <-->|"HTTPS + Passkey (WebAuthn)"| SSRAAssist
    Supervisor <-->|"HTTPS + Passkey (WebAuthn)"| SSRAAssist

    SSRAAssist <-->|"mTLS / REST / SOAP via Anti-Corruption Adapters"| ETax
    SSRAAssist <-->|"mTLS via Customs Adapter (OQ-002)"| ECustoms
    SSRAAssist <-->|"Official FX & Channel Verification"| BoSS
    SSRAAssist <-->|"Identity / Registration Verification & Future A2A"| EServices
    SSRAAssist -.->|"Gated Egress (Only if OQ-004 Approved)"| ExtLLM
```

---

## 4. C4 Level 2 — Container Architecture

### 4.1 Container Inventory & Responsibilities

Inside the **SSRA Assist** boundary on NCA Kubernetes (RKE2/k3s), the platform is decomposed into independently scalable containers with strict network policies (deny-all by default, mTLS between all internal workloads):

1. **Edge & Ingress (`Edge WAF / Envoy / Ingress`):** Terminates TLS 1.3, enforces WAF rules, DDoS rate limits, and ALTCHA proof-of-work bot verification on public endpoints.
2. **Taxpayer Web PWA (`apps/web` — Next.js 16.3.x standalone):** Public knowledge portal, deterministic calculators, official-channel verifier, and AG-UI chat client. Uses `proxy.ts` for nonce CSP, locale routing (`en`, `pga`, `ar`), and BFF session cookies backed by Valkey.
3. **Staff Console (`apps/console` — Next.js 16.3.x standalone):** Omnichannel agent inbox, AI suggestion review, human takeover/hand-back, Knowledge & Tax Facts release workflow (Draft → Legal Review → Approval → Immutable Publish → Eval Gate → Rollback), and QA/supervisor dashboards. Protected by Keycloak OIDC + WebAuthn passkeys and ASVS 5.0 L3 controls.
4. **Channel Gateway (`services/channel-gateway` — FastAPI):** Terminates webhooks and operator links for WhatsApp Business Platform, SMS (SMPP/HTTP), USSD, and Voice/IVR (`services/voice` in Phase 4). Verifies HMAC signatures, deduplicates message IDs in Valkey, enforces per-sender rate limits, tracks GSM-7 vs. UCS-2 segmentation, and normalises inbound/outbound traffic into `ConversationEvent` (CloudEvents 1.0).
5. **Core API Modular Monolith (`services/api` — FastAPI 0.13x):** Houses eight bounded contexts (`conversations`, `identity_link`, `cases`, `appointments`, `knowledge_admin`, `consent`, `analytics_api`, `admin`), enforcing clean hexagonal boundaries via `import-linter` and publishing domain events via a transactional outbox to NATS JetStream.
6. **Agent Runtime (`services/agent-runtime` — FastAPI + LangGraph 1.2.x):** Stateless worker pool executing the 11-node deterministic supervisor graph and specialist subgraphs, persisting thread checkpoints in PostgreSQL 18, enforcing input/output guardrails (including Presidio PII redaction and numeric provenance), and streaming AG-UI events over SSE.
7. **AI Gateway (`agentgateway` 1.x):** The **only** egress path from `services/agent-runtime` to LLMs, MCP servers, and future A2A peers. Enforces OPA policies on `(caller, subject_ref, auth_level, tool, tier, args_shape)`, performs OAuth 2.1 RFC 8693 token exchange with Keycloak, pins tool description hashes, tracks token/cost budgets, and emits immutable audit records.
8. **Domain MCP Servers (`mcp-servers/*` — Python MCP SDK `2026-07-28`):** Eleven stateless Streamable HTTP servers (`knowledge`, `tax-facts`, `official-channels`, `taxpayer`, `ledger`, `payments-info`, `tcc`, `customs`, `cases`, `appointments`, `notifications`), routed by `agentgateway` via `Mcp-Method` and `Mcp-Name` headers.
9. **Background Workers (`services/workers` — Temporal Python SDK):** Executes durable workflows for Docling document ingestion & legal-structure chunking, embedding/reranking index builds, eval regression suites on knowledge publish, case SLA timers, and consent-checked notification campaigns.
10. **Sovereign AI Inference (`AI Services`):** In-country GPU/CPU inference pods running vLLM/SGLang (open-weight instruction models), embedding/reranker services (BGE-M3 / Qwen3-Embedding + Qwen3-Reranker), guard classifiers, and ASR/TTS (Whisper + Meta Omnilingual ASR in Phase 4).
11. **Data & Messaging Stores:**
    - **PostgreSQL 18 + pgvector 0.8+ (CloudNativePG HA):** Primary relational store (`uuidv7()` keys, monthly partitions, RLS by office/region), hybrid FTS + HNSW vector index with iterative scans, LangGraph checkpointer, and hash-chained `AuditEvent` table.
    - **Valkey 8:** BFF session store, webhook deduplication, rate-limit counters, Next.js shared cache handler, and T0 anonymous semantic cache.
    - **S3-Compatible Object Storage (MinIO / Ceph):** Source legal documents, malware-scanned media attachments, and WORM-locked audit archives.
    - **NATS JetStream:** Event bus for CloudEvents 1.0 (`ConversationEvent`, domain events from transactional outbox).
    - **Temporal Server:** Durable execution engine for `services/workers`.
12. **Security & Observability Plane:** Keycloak (OAuth 2.1 / OIDC / RFC 8693 Token Exchange), OpenBao (secrets + transit encryption), OPA (policy sidecars/service), OpenTelemetry Collector, Langfuse (self-hosted LLM traces & evals), and Grafana LGTM + SIEM.

### 4.2 C4 Level 2 Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph Clients["External Clients & Channels"]
        Browser["🌐 Taxpayer Browser / Mobile PWA"]
        StaffBrowser["🖥️ SSRA Staff Browser (Passkey)"]
        WAGateway["📱 WhatsApp / SMS / USSD / SIP Providers"]
    end

    subgraph EdgeLayer["Layer 2: Edge"]
        WAF["🛡️ CDN + WAF + TLS 1.3 + ALTCHA Bot Defence"]
    end

    subgraph ExperienceLayer["Layer 3 & 4: Experience (BFF) & Channel Gateway"]
        WebPWA["📦 apps/web\nNext.js 16.3.x BFF & PWA\n(proxy.ts, AG-UI SSE Proxy)"]
        ConsoleApp["📦 apps/console\nNext.js 16.3.x Staff Console\n(Inbox, Knowledge Release, QA)"]
        ChanGW["📦 services/channel-gateway\nFastAPI Webhook/SMPP/USSD Normaliser\n(CloudEvents 1.0)"]
    end

    subgraph CoreAndRuntime["Layer 5: Core Services & Agent Runtime"]
        CoreAPI["📦 services/api\nFastAPI Modular Monolith\n(conversations, identity_link, cases,\nappointments, knowledge_admin, consent)"]
        Runtime["📦 services/agent-runtime\nFastAPI + LangGraph 1.2.x\n(11-Node Graph, Guardrails, AG-UI SSE)"]
        Workers["📦 services/workers\nTemporal Worker Service\n(Docling Ingestion, Evals, SLA Timers)"]
    end

    subgraph GovernanceGateway["Layer 6: Governed AI & Tool Egress"]
        AgentGW["🚦 agentgateway 1.x\nSingle LLM / MCP / A2A Egress\n(OPA Policy, RFC 8693 Token Exchange,\nTool Hash Pinning, Spend Caps)"]
    end

    subgraph DomainTools["Layer 7 & 8: Stateless MCP Servers (2026-07-28) & Anti-Corruption Adapters"]
        MCP_T0["🔧 T0 MCP Servers\nknowledge | tax-facts | official-channels"]
        MCP_T1["🔐 T1 MCP Servers\ntaxpayer | ledger | customs"]
        MCP_T2_T3["✍️ T2/T3 MCP Servers\ncases | appointments | payments-info | tcc | notifications"]
        Adapters["🔌 libs/ssra_adapters\ne-Tax | e-Customs | BoSS | Telco Ports & Mocks"]
    end

    subgraph SovereignAI["Layer 10: Sovereign AI Services (In-Country GPU/CPU)"]
        vLLM["🧠 vLLM / SGLang\nOpen-Weight Instruction Models"]
        Embed["🔎 Embedding & Reranker\n(BGE-M3 / Qwen3)"]
        GuardModels["🛡️ Guard & Language ID Models\n+ Presidio Redactor"]
    end

    subgraph DataAndSecurity["Layer 9, 11 & 12: Data, Security & Observability"]
        PG[("🐘 PostgreSQL 18 + pgvector 0.8+\n(Entities, Chunks, Checkpoints, Hash Audit)")]
        Valkey[("⚡ Valkey 8\n(Sessions, Dedupe, Rate Limits, Cache)")]
        ObjStore[("🪣 S3 Object Store\n(Docs, Media, WORM Audit Archive)")]
        NATS[["📨 NATS JetStream + Temporal Server"]]
        SecPlane["🔑 Keycloak (OAuth 2.1) + OpenBao (KMS) + OPA"]
        ObsPlane["📊 OTel Collector + Self-Hosted Langfuse + Grafana LGTM + SIEM"]
    end

    subgraph Upstreams["SSRA Systems of Record"]
        SOR["🏦 e-Tax | e-Customs | BoSS | eServices"]
    end

    Browser --> WAF
    StaffBrowser --> WAF
    WAGateway --> WAF

    WAF --> WebPWA
    WAF --> ConsoleApp
    WAF --> ChanGW

    WebPWA <-->|"REST / OpenAPI 3.1"| CoreAPI
    WebPWA <-->|"AG-UI over SSE"| Runtime
    ConsoleApp <-->|"REST / OpenAPI 3.1"| CoreAPI
    ConsoleApp <-->|"Agent Assist / Inbox SSE"| Runtime
    ChanGW <-->|"CloudEvents / Internal API"| Runtime
    ChanGW <-->|"Consent & Delivery State"| CoreAPI

    CoreAPI <--> PG
    CoreAPI <--> Valkey
    CoreAPI <--> ObjStore
    CoreAPI <--> NATS
    Workers <--> NATS
    Workers <--> PG
    Workers <--> ObjStore

    Runtime <-->|"Checkpoints & State"| PG
    Runtime <-->|"Guard & Redaction"| GuardModels
    Runtime -->|"All Model & Tool Calls (mTLS)"| AgentGW

    AgentGW <-->|"AuthZ & Token Exchange"| SecPlane
    AgentGW -->|"OpenAI-Compatible API"| vLLM
    AgentGW -->|"Embedding / Rerank"| Embed
    AgentGW -->|"Mcp-Method / Mcp-Name (mTLS)"| MCP_T0
    AgentGW -->|"Mcp-Method / Mcp-Name + Subject Token"| MCP_T1
    AgentGW -->|"Mcp-Method / Mcp-Name + Confirm Token"| MCP_T2_T3

    MCP_T0 <--> PG
    MCP_T1 --> Adapters
    MCP_T2_T3 --> Adapters
    MCP_T2_T3 --> CoreAPI
    Adapters <--> SOR

    Runtime -.-> ObsPlane
    AgentGW -.-> ObsPlane
    CoreAPI -.-> ObsPlane
```

---

## 5. C4 Level 3 — Component Architecture

We detail Level 3 components for the four most critical containers in the request path:
1. **`services/agent-runtime`** (LangGraph deterministic shell + guardrails + AG-UI streaming)
2. **`services/api`** (FastAPI modular monolith & hexagonal bounded contexts)
3. **`mcp-servers/*`** (Stateless `2026-07-28` MCP server internal architecture)
4. **`apps/web`** (Next.js 16.3.x taxpayer PWA, BFF, and Generative UI registry)

---

### 5.1 C4 Level 3 — `services/agent-runtime` (`ssra_runtime`)

#### Component Responsibilities

`services/agent-runtime` is a deterministic state machine built on LangGraph `1.2.x` where LLM calls occur only inside bounded nodes (`understand` and `compose`) and every transition is governed by deterministic code and OPA policy:

1. **AG-UI & Internal Event Ingress (`streaming/agui.py`, `nodes/ingress.py`):** Accepts SSE connections from `apps/web` / `apps/console` or `ConversationEvent` payloads from `services/channel-gateway`. Attaches `ChannelCapabilities` (`max_len`, `rich_ui`, `buttons`, `media`, `latency_budget_ms`, `async_only`) and hydrates `ConversationState` from the PostgreSQL checkpointer by `thread_id`.
2. **Deterministic Router (`nodes/router.py`):** Intercepts non-LLM flows before any model is invoked:
   - OTP challenge/verification and TIN binding (`identity_link` service)
   - USSD menu state transitions (synchronous deterministic path, <2 s)
   - `STOP`, `HELP`, and `AGENT` keywords (immediate consent update or human handoff)
   - Media attachment quarantine to malware-scan + OCR pipeline
3. **Input Guard (`nodes/guards.py`, `guardrails/injection.py`, `guardrails/pii.py`):** Runs language identification (`en`, `pga`, `ar`, `din`, `nus`, `bfa`, `zne`, `shk`), prompt-injection heuristics + classifier, toxicity/abuse filter, and Presidio PII tagging (+211 phones, TINs, national IDs) so logs and traces are masked before storage.
4. **Understand Node (`nodes/understand.py`):** Uses a small, fast model via `ModelPort` (`agentgateway`) with structured output (`Intent` Pydantic v2 schema) to extract `intent`, `slots`, `language`, and `confidence`. Looks up the immutable risk tier (`T0`–`T4`) from `ai/policies/risk-tiers.yaml`—never from the model.
5. **Policy Gate (`nodes/policy_gate.py`):** Evaluates OPA policy (`ai/policies/*.rego`) against `(auth_level, tier, channel, office_hours, rate_limits, safety_flags)` to return one of: `ALLOW`, `DENY`, `STEP_UP_AUTH`, or `HANDOFF`. `T4` intents (`waiver`, `refund`, `penalty_remission`, `dispute`, `legal_ruling`) deterministically route to `handoff` after explaining the official process.
6. **Specialist Subgraphs (`graphs/*.py`):**
   - `knowledge_qa`: Hybrid retrieval (`retrieval/hybrid.py`, `rerank.py`, `filters.py`) via `knowledge` and `tax-facts` MCP servers.
   - `guided_journey`: Step-by-step procedural wizards (TIN registration, e-Tax filing, bank payment, TCC application, customs basics).
   - `calculator`: Invokes deterministic `tax-facts` MCP tools (`calculate_paye_estimate`, `calculate_withholding_estimate`) and labels output explicitly as an estimate.
   - `verify_official`: Invokes `official-channels` MCP tools (`verify_payment_account`, `verify_sender`, `report_scam`) against the anti-impersonation registry.
   - `self_service`: Authenticated `T1`/`T2`/`T3` flows (`taxpayer`, `ledger`, `tcc`, `customs`, `appointments`, `cases`).
   - `complaint_intake` & `handoff`: Minimal-data complaint capture and warm transfer to `services/api` (`Handoff` queue).
7. **Confirmation Interrupt Node (`nodes/confirm.py`):** For `T2` and `T3` state-changing tools, calls LangGraph `interrupt()` with a plain-language action summary and argument digest. When the user confirms via AG-UI `ConfirmActionSheet`, WhatsApp interactive button, or USSD option, issues a short-lived, single-use `confirmation_token` bound to `args_hash` and `idempotency_key`.
8. **Tool Execution Client (`tools/mcp_client.py`):** Invokes MCP servers exclusively through `agentgateway` using stateless MCP `2026-07-28` (`Mcp-Method`, `Mcp-Name`, W3C `traceparent`), enforcing per-tool timeouts, idempotent-only retries, and circuit breakers. Stores tool outputs as typed `Artifact` records referenced by ID.
9. **Compose Node (`nodes/compose.py`):** Assembles the layered prompt (`L0` immutable policy → `L1` channel contract → `L2` persona/tone → `L3` node task → `L4` spotlighted data-only evidence → `L5` minimal tool artifacts), enforces the `ai/termbase/` glossary, and produces a structured `Answer` (`segments[]`, `citations[]`, `numbers[]`, optional registered UI component request).
10. **Output Guard (`guardrails/grounding.py`, `numeric_provenance.py`, `neutrality.py`):** Validates:
    - **Numeric provenance:** Every number in `segments[]` and `numbers[]` matches a `TaxFact` or `Artifact` from the current turn (`100%` gate).
    - **Citation precision & groundedness:** Every claim maps to a published `KnowledgeSnapshot` section or tool provenance.
    - **Cross-subject & PII check:** No unmasked TINs or other-subject data.
    - **Neutrality & non-promise check:** Blocks political commentary or prohibited promises (e.g., *"your penalty will be waived"*).
    - On failure: regenerates at most once with validator feedback; if still failing, emits a safe abstention fallback and offers human handoff.
11. **Egress Node (`nodes/egress.py`):** Streams final AG-UI events or dispatches channel reply, updates running thread summary, writes hash-chained `AuditEvent`, and records OTel GenAI spans.

#### C4 Level 3 Diagram — `services/agent-runtime` (Mermaid)

```mermaid
flowchart TB
    subgraph AgentRuntime["services/agent-runtime (ssra_runtime)"]
        Ingress["1. nodes/ingress.py\nNormalise Event + Attach ChannelCapabilities\nLoad Checkpoint by thread_id"]
        DetRouter["2. nodes/router.py\nDeterministic Router\n(OTP/Step-Up, USSD, STOP/HELP/AGENT, Malware Scan)"]
        InputGuard["3. nodes/guards.py + guardrails/injection.py\nLanguage ID, Injection Classifier,\nAbuse Check, Presidio PII Tagging"]
        Understand["4. nodes/understand.py\nStructured Intent Extraction (Pydantic v2)\n+ Deterministic Tier Lookup (risk-tiers.yaml)"]
        PolicyGate["5. nodes/policy_gate.py\nOPA Policy Evaluation\n(allow | deny | step_up | handoff)"]

        subgraph Subgraphs["6. Specialist Subgraphs (graphs/)"]
            SG_QA["knowledge_qa.py\nHybrid Search + Tax Facts"]
            SG_Journey["guided_journey.py\nTIN / Filing / Payment / TCC"]
            SG_Calc["calculator.py\nPAYE & WHT Estimates"]
            SG_Verify["verify_official.py\nAnti-Scam & Official Channels"]
            SG_Self["self_service.py\nT1/T2/T3 Authenticated Flows"]
            SG_Handoff["complaint_intake.py & handoff.py\nEscalation & Callback"]
        end

        ConfirmNode["7a. nodes/confirm.py\nLangGraph interrupt() for T2/T3\nIssues Single-Use confirmation_token"]
        ToolExec["7b. tools/mcp_client.py\nStateless MCP 2026-07-28 Client\nTimeouts, Idempotent Retries, Artifact Store"]
        Compose["8. nodes/compose.py\nLayered Prompt (L0-L5) + Termbase\nStructured Answer + UI Component Request"]
        OutputGuard["9. guardrails/\ngrounding.py | numeric_provenance.py\npii.py | neutrality.py\n(1x Retry -> Safe Fallback + Handoff)"]
        Egress["10. nodes/egress.py + streaming/agui.py\nAG-UI SSE Stream / Channel Egress\nSummary Compaction + AuditEvent"]
    end

    PGCheck[("PostgreSQL 18\nLangGraph Checkpointer")]
    OPASvc["OPA Policy Engine\n(risk-tiers.yaml + Rego)"]
    Gateway["agentgateway 1.x\n(Models & MCP Servers)"]

    Ingress <--> PGCheck
    Ingress --> DetRouter
    DetRouter -->|"Non-LLM OTP / USSD / STOP"| Egress
    DetRouter -->|"Standard Turn"| InputGuard
    InputGuard --> Understand
    Understand <-->|"Small Model via ModelPort"| Gateway
    Understand --> PolicyGate
    PolicyGate <--> OPASvc

    PolicyGate -->|"allow (T0)"| SG_QA
    PolicyGate -->|"allow (T0)"| SG_Journey
    PolicyGate -->|"allow (T0)"| SG_Calc
    PolicyGate -->|"allow (T0/T2)"| SG_Verify
    PolicyGate -->|"allow (T1/T2/T3)"| SG_Self
    PolicyGate -->|"handoff / T4 / step_up"| SG_Handoff

    SG_QA --> ToolExec
    SG_Journey --> ToolExec
    SG_Calc --> ToolExec
    SG_Verify --> ConfirmNode
    SG_Self --> ConfirmNode

    ConfirmNode <-->|"Persist Interrupt"| PGCheck
    ConfirmNode -->|"Confirmed / Read-Only"| ToolExec
    ToolExec <-->|"Mcp-Method / Mcp-Name"| Gateway
    ToolExec --> Compose
    SG_Handoff --> Compose

    Compose <-->|"Mid Model via ModelPort"| Gateway
    Compose --> OutputGuard
    OutputGuard -->|"Regenerate Once (if failed)"| Compose
    OutputGuard -->|"Pass or Safe Abstention"| Egress
```

---

### 5.2 C4 Level 3 — `services/api` (Modular Monolith) & `mcp-servers/*`

#### Component Responsibilities

`services/api` is structured into eight strict hexagonal bounded contexts under `src/ssra_api/<context>/`, enforced by `import-linter` so no context may import another context's `infrastructure/` or `api/` internals:

1. **`conversations`:** Manages `Conversation`, `Message`, `ToolInvocation`, `Confirmation`, and `Handoff` lifecycle; exposes inbox APIs for `apps/console`.
2. **`identity_link`:** Executes deterministic OTP issuance/verification, binds verified TINs to opaque `subject_ref` identifiers, and coordinates RFC 8693 token exchange claims with Keycloak.
3. **`cases`:** Manages taxpayer inquiries, complaints, and scam reports (`Case`), emitting events to Temporal for SLA tracking.
4. **`appointments`:** Manages office slot inventory and booking (`book_appointment`, `cancel_appointment`) across SSRA offices in `Africa/Juba` time.
5. **`knowledge_admin`:** Implements the 6-step Knowledge & Tax Facts Release Workflow (`Draft` → `Legal Review` → `Approval` → `Publish Immutable Snapshot` → `Auto Re-index & Eval Gate` → `One-Step Rollback`).
6. **`consent`:** Maintains the immutable opt-in/opt-out `Consent` ledger checked before any outbound WhatsApp template or SMS notification is sent.
7. **`analytics_api`:** Serves aggregated, de-identified CX funnel, containment, language parity, and content-gap metrics.
8. **`admin`:** Manages official-channel registry entries, kill switches per model/tool/channel, and hash-chained `AuditEvent` verification.

Each MCP server in `mcp-servers/<domain>/` follows `mcp-servers/_template/` and uses `libs/ssra_mcp` to enforce:
- Stateless MCP `2026-07-28` request validation (`_meta` protocol version, `Mcp-Method`, `Mcp-Name`)
- OAuth 2.1 audience-bound JWT verification and `subject_ref` extraction
- Single-use `confirmation_token` + `idempotency_key` enforcement for `T2`/`T3` write tools
- Provenance envelope (`system`, `record_id`, `retrieved_at`, `as_of`, `data_classification`) and typed errors (`NOT_FOUND`, `NOT_AUTHORIZED`, `STEP_UP_REQUIRED`, `UPSTREAM_UNAVAILABLE`, `VALIDATION_FAILED`, `RATE_LIMITED`).

#### C4 Level 3 Diagram — `services/api` & `mcp-servers/*` (Mermaid)

```mermaid
flowchart LR
    subgraph ModularMonolith["services/api (src/ssra_api/)"]
        direction TB
        API_Router["FastAPI /v1 Routers\n(OpenAPI 3.1, RFC 9457, Idempotency-Key, traceparent)"]
        subgraph Contexts["Hexagonal Bounded Contexts (import-linter enforced)"]
            C_Conv["conversations"]
            C_Id["identity_link"]
            C_Cases["cases"]
            C_Appt["appointments"]
            C_Know["knowledge_admin"]
            C_Consent["consent"]
            C_Analytics["analytics_api"]
            C_Admin["admin (Kill Switches & Audit)"]
        end
        Outbox["Transactional Outbox Publisher\n(CloudEvents 1.0 -> NATS JetStream)"]
        API_Router --> Contexts
        Contexts --> Outbox
    end

    subgraph MCPServerTemplate["mcp-servers/<domain> (Stateless 2026-07-28)"]
        direction TB
        MCPHttp["Streamable HTTP Endpoint\n(server.py — Mcp-Method / Mcp-Name)"]
        MCPBase["libs/ssra_mcp Middleware\nOAuth 2.1 Audience Check, Subject Binding,\nConfirmation Token & Idempotency, Audit"]
        ToolHandler["tools/<verb_noun>.py\nJSON Schema 2020-12 Validation\n+ Provenance Envelope"]
        PortAdapter["adapters.py (libs/ssra_adapters)\nAnti-Corruption Port -> Real or Mock Upstream"]
        MCPHttp --> MCPBase --> ToolHandler --> PortAdapter
    end

    PG[("PostgreSQL 18\n(UUIDv7, RLS, Partitions)")]
    ETaxAdapter["e-Tax / e-Customs / BoSS\n(Mock in Phase 0/1)"]

    Contexts --> PG
    PortAdapter --> PG
    PortAdapter --> ETaxAdapter
```

---

### 5.3 C4 Level 3 — `apps/web` & `packages/chat-ui` (Frontend Experience)

#### Component Responsibilities

1. **`src/proxy.ts` (Next.js 16 Proxy):** Generates per-request cryptographic CSP nonces, negotiates locale (`en`, `pga`, `ar` with `dir="rtl"`), enforces security headers (`Trusted-Types`, `HSTS`, `COOP`, `frame-ancestors 'none'`), and gates `/[locale]/(account)/*` routes.
2. **Public Route Group (`app/[locale]/(public)/`):** Uses Next.js 16 Cache Components (`"use cache"`) for ultra-fast, low-bandwidth delivery (<120 KB gzip target) of tax guides, office directory, deterministic PAYE/WHT calculator forms, and the *"Is this really SSRA?"* official-channel verifier.
3. **Chat & Account Route Groups (`app/[locale]/(chat)/`, `app/[locale]/(account)/`):** Lazy-loads `packages/chat-ui` (AG-UI SSE client, offline outbox queue, citation drawer, low-data text-only toggle).
4. **Generative UI Registry (`packages/chat-ui/src/registry/`):** Maps allow-listed component names from the agent (`BalanceCard`, `FilingStatusTimeline`, `PaymentInstructionsCard`, `CalculatorForm`, `CitationList`, `ConfirmActionSheet`, `HandoffCard`) through strict Zod 4 prop schemas. Unknown component names or invalid props safely fall back to plain text. The model never emits raw HTML or JS.
5. **BFF Route Handlers (`app/api/`):** Terminates OIDC (`openid-client` / Better Auth) with Keycloak, manages `httpOnly` session cookies in Valkey, verifies ALTCHA proof-of-work challenges, and proxies resumable AG-UI SSE streams to `services/agent-runtime`.

---

## 6. Key End-to-End Request Sequences

### 6.1 Sequence 1: Phase 0 / Phase 1 Grounded Tax Q&A + Deterministic Calculator (Web PWA, Tier T0)

```mermaid
sequenceDiagram
    autonumber
    actor User as Taxpayer (Web PWA)
    participant Web as apps/web (BFF & proxy.ts)
    participant RT as services/agent-runtime (LangGraph)
    participant GW as agentgateway 1.x
    participant MCP_TF as mcp-servers/tax-facts
    participant MCP_KN as mcp-servers/knowledge
    participant LLM as Sovereign vLLM (ModelPort)

    User->>Web: "How much is PAYE on 250,000 SSP per month and when is it due?"
    Web->>RT: POST /v1/agui/stream (SSE, locale=en, auth_level=anonymous)
    RT->>RT: 1. ingress -> 2. deterministic_router -> 3. input_guard (Presidio + Injection Check)
    RT->>GW: 4. understand (Small Model: structured Intent)
    GW->>LLM: ChatCompletions (JSON Schema: Intent)
    LLM-->>GW: Intent(intent="calculate_paye", slots={gross_monthly_ssp: 250000}, confidence=0.98)
    GW-->>RT: Intent + Lookup risk-tiers.yaml -> Tier T0
    RT->>RT: 5. policy_gate (OPA: T0 anonymous on web -> ALLOW)
    RT-->>Web: AG-UI Event: ToolCallStart("calculate_paye_estimate", "search_knowledge")
    par Deterministic Calculation & Legal Citation Retrieval
        RT->>GW: 7. MCP Call (Mcp-Name: tax-facts, tool: calculate_paye_estimate)
        GW->>MCP_TF: POST /mcp (stateless 2026-07-28)
        MCP_TF-->>GW: Structured Artifact (tax_ssp, effective_rate, brackets_ref, citation="Taxation Act 2009 / Financial Act 2024-2025", as_of="2026-10-16")
        GW-->>RT: Artifact #1 (tax_facts)
    and
        RT->>GW: 7. MCP Call (Mcp-Name: knowledge, tool: search_knowledge)
        GW->>MCP_KN: POST /mcp (query="PAYE monthly filing deadline")
        MCP_KN-->>GW: Chunk Artifact (snapshot_v="2026.10.1", section="Part IV Sec 18", deadline_rule)
        GW-->>RT: Artifact #2 (knowledge)
    end
    RT->>GW: 8. compose (Layered Prompt L0-L5 + Artifacts #1 & #2)
    GW->>LLM: Generate structured Answer(segments, citations, numbers, ui_component="CalculatorForm")
    LLM-->>GW: Structured Answer
    GW-->>RT: Structured Answer
    RT->>RT: 9. output_guard (numeric_provenance verifies every number in Answer == Artifact #1/#2; grounding check)
    RT-->>Web: 10. AG-UI SSE: TextStream + CitationList + CalculatorForm (Zod-validated)
    Web-->>User: Renders answer with legal citation, effective date, "Estimate Only" badge, and official e-Tax payment notice
```

### 6.2 Sequence 2: Authenticated Balance Query on WhatsApp (Tier T1)

```mermaid
sequenceDiagram
    autonumber
    actor User as Taxpayer (WhatsApp)
    participant CGW as services/channel-gateway
    participant RT as services/agent-runtime
    participant ID as services/api (identity_link)
    participant GW as agentgateway + Keycloak
    participant Ledger as mcp-servers/ledger
    participant ETax as e-Tax Adapter (Mock/Real)

    User->>CGW: WhatsApp Message: "Check my tax balance"
    CGW->>CGW: Verify X-Hub-Signature-256, Dedupe in Valkey, Normalise to CloudEvents 1.0
    CGW->>RT: POST /v1/events (ConversationEvent)
    RT->>RT: 1. ingress loads thread state (auth_level=anonymous)
    RT->>ID: 2. deterministic_router triggers OTP + TIN verification sub-flow (outside LLM)
    ID-->>User: WhatsApp OTP Challenge -> User verifies OTP bound to TIN
    ID-->>RT: Thread bound to opaque subject_ref="sub_0192..." at auth_level=T1_VERIFIED
    RT->>GW: 3. understand -> Intent="get_balance" -> Policy table fixes Tier=T1
    RT->>RT: 4. policy_gate (OPA confirms T1_VERIFIED >= T1 -> ALLOW)
    RT->>GW: 5. MCP Call: ledger.get_balance (with caller token + subject_ref context)
    GW->>GW: Keycloak OAuth 2.1 RFC 8693 Token Exchange (audience=mcp-ledger, sub=sub_0192...)
    GW->>Ledger: POST /mcp (Mcp-Name: ledger, Bearer <exchanged_token>)
    Ledger->>ETax: get_balance(subject_ref="sub_0192...") [Server-side ownership enforced]
    ETax-->>Ledger: Balance(tin_masked="••••1234", amount_ssp=1450000, as_of="2026-10-16T08:00:00Z")
    Ledger-->>GW: Structured Result + Provenance
    GW-->>RT: Artifact #1
    RT->>GW: 6. compose grounded response + official e-Tax payment channel instructions
    RT->>RT: 7. output_guard verifies 1,450,000 SSP == Artifact #1 and TIN is masked (••••1234)
    RT->>CGW: 8. egress -> WhatsApp interactive reply + hash-chained AuditEvent written
    CGW-->>User: Delivers WhatsApp message with balance, as-of timestamp, and etax.nra.gov.ss guidance
```

---

## 7. Security, Sovereignty & Trust Boundaries

1. **Public Internet / Telecom Perimeter → Edge Layer:** Untrusted traffic. Protected by TLS 1.3, WAF, rate limiting, webhook HMAC verification, and ALTCHA proof-of-work bot defence.
2. **Experience / Channel Gateway → Agent Runtime:** Internal cluster network with mTLS. User text, uploaded documents, and webhook payloads are tagged as **untrusted data** (`L4` spotlighting delimiters) and never interpolated into `L0`–`L3` system instructions.
3. **Agent Runtime → `agentgateway`:** Single egress choke point enforced by Kubernetes `NetworkPolicy` (the runtime pod has zero network routes to LLMs, MCP servers, or external networks except via `agentgateway`).
4. **`agentgateway` → Domain MCP Servers:** mTLS + OAuth 2.1 audience-scoped JWTs + RFC 8693 subject tokens + single-use confirmation tokens for `T2`/`T3`.
5. **MCP Servers → Systems of Record (`libs/ssra_adapters`):** Anti-corruption layer with circuit breakers, strict timeouts, idempotency keys, and server-side ownership checks. No LLM or user token is ever passed through to e-Tax or e-Customs.

---

## 8. Architecture Decision Records (ADR-001 to ADR-015)

Full index and problem statements are maintained in [`docs/adr/README.md`](../adr/README.md):

| ADR | Title | One-Line Problem Statement | Status |
|---|---|---|---|
| [ADR-001](../adr/0001-record-architecture-decisions.md) | Record Architecture Decisions | How do we govern, document, and evaluate the reversal cost of architectural decisions across SSRA Assist? | Proposed (Drafted) |
| [ADR-002](../adr/0002-service-decomposition-and-modular-monolith.md) | Service Decomposition & Modular Monolith | How do we partition backend responsibilities to balance operational simplicity for SSRA's local team with blast-radius isolation for AI and channels? | Proposed (Drafted) |
| [ADR-003](../adr/0003-orchestration-langgraph-and-temporal.md) | Dual Orchestration: LangGraph & Temporal | How do we separate low-latency, interruptible conversational control flow from long-running, durable background business processes? | Proposed (Drafted) |
| [ADR-004](../adr/0004-mcp-2026-07-28-and-agentgateway-egress.md) | Stateless MCP 2026-07-28 & `agentgateway` Single Egress | How do we expose domain tools and govern all model/tool traffic with zero-trust authorization, auditability, and horizontal scalability? | Proposed (Drafted) |
| [ADR-005](../adr/0005-ag-ui-streaming-and-generative-ui-registry.md) | AG-UI Streaming Protocol & Allow-Listed Generative UI Registry | How do we stream rich, interactive agent responses to low-bandwidth clients without exposing browsers to model-generated HTML/JS injection? | Proposed (Drafted) |
| [ADR-006](../adr/0006-postgresql-18-pgvector-hybrid-retrieval.md) | PostgreSQL 18 + pgvector 0.8+ Hybrid Retrieval | How do we store operational state, checkpoints, and multilingual legal embeddings in one sovereign database before introducing external search engines? | Proposed (Drafted) |
| [ADR-007](../adr/0007-sovereign-model-hosting-and-tiered-routing.md) | Sovereign Open-Weight Model Hosting & Tiered Routing | How do we run LLM inference in-country on NCA infrastructure with a deterministic degradation ladder and strictly gated external fallbacks? | Proposed (Drafted) |
| [ADR-008](../adr/0008-risk-tiered-autonomy-subject-binding-and-opa.md) | Risk-Tiered Autonomy (T0–T4), Subject Binding & OPA Policy Gate | How do we guarantee in code and policy that the assistant cannot leak cross-taxpayer data or execute unauthorized actions? | Proposed (Drafted) |
| [ADR-009](../adr/0009-deterministic-tax-facts-registry-and-numeric-provenance.md) | Deterministic Tax Facts Registry & Numeric Provenance Guard | How do we ensure 100% numeric accuracy on South Sudan tax rates, thresholds, deadlines, and calculations with zero hallucinated figures? | Proposed (Drafted) |
| [ADR-010](../adr/0010-nextjs-16-typescript-7-turborepo-and-biome.md) | Next.js 16.3.x, TypeScript 7, Turborepo & Biome Frontend Stack | How do we build and type-check two secure, low-bandwidth Next.js 16 applications sharing one RTL-ready design system? | Proposed (Drafted) |
| [ADR-011](../adr/0011-low-bandwidth-taxpayer-pwa-and-service-worker.md) | Low-Bandwidth Taxpayer PWA & Service Worker Strategy | How do we deliver an offline-capable, 2G-resilient PWA under Next.js 16 and Turbopack within a 150 KB gzip first-load budget? | Proposed (Drafted) |
| [ADR-012](../adr/0012-bff-authentication-keycloak-passkeys-and-sessions.md) | BFF Authentication with Keycloak OIDC, Passkeys & Server Sessions | How do we authenticate taxpayers (OTP+TIN) and staff (WebAuthn passkeys) while keeping all OAuth tokens out of browser JavaScript? | Proposed (Drafted) |
| [ADR-013](../adr/0013-python-314-315-fastapi-and-asgi-server.md) | Python 3.14/3.15 Workspace, FastAPI 0.13x & ASGI Server Selection | How do we standardise the Python monorepo toolchain (`uv`, Ruff, basedpyright) and evaluate Uvicorn vs. Granian for container deployments? | Proposed (Drafted) |
| [ADR-014](../adr/0014-future-a2a-v1-interoperability-boundary.md) | Future Agent-to-Agent (A2A v1.0) Interoperability Boundary | How do we reserve a governed boundary for future multi-agency collaboration with South Sudan's National eServices platform? | Proposed (Drafted) |
| [ADR-015](../adr/0015-supply-chain-hardening-and-sovereign-gitops.md) | Supply-Chain Hardening (SLSA L3, 7-Day Cooldown) & Sovereign GitOps | How do we defend CI/CD, dependencies, and container images against 2026-class supply-chain compromises (such as the March 2026 LiteLLM/Trivy incident)? | Proposed (Drafted) |
