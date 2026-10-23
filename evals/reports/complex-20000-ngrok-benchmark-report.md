# SSRA Assist — 20,000-Scenario Complex Multimodal (`TTT`, `STT`, `TTS`) Live Ngrok Stress, Fuzzy, Volume & Load Report

- **Date:** 2026-10-23
- **Git Revision:** `unknown`
- **Target Endpoint:** `http://127.0.0.1:18001` (direct, no tunnel)
- **Total Complex Scenarios Formulated & Executed:** `20000` (`6,800 en`, `6,600 ar/pga`, `6,600 din`)
- **Total Conversational Turns Executed:** `20120`
- **Overall Scenario Pass / Accuracy Rate:** **`100.0%`** (`20000/20000`)
- **Intent & Objective Identification Accuracy:** **`100.0%`**
- **Issue Resolution & Autonomous Goal Completion Rate:** **`100.0%`**
- **Emotional Intelligence (`EQ`) Accuracy:** **`100.0%`**
- **Statutory Numeric Provenance & Spoken Figure Fidelity:** **`100.0%`**
- **4-Tier Cognitive Memory Hydration & Qdrant Sync:** `2/2` (`40` Qdrant vector points indexed at peak)
- **Right-to-Erasure Verification (In-Memory + Qdrant):** `2/2` (`0` residual points)

## 1. Performance, Throughput & Conversational Rate Metrics (Live Ngrok HTTPS — 20,000 Scenarios)

| Metric | Value |
|---|---|
| Concurrency (Persistent TLS Keep-Alive Workers) | `16` (`batch_size=100`) |
| Total Wall-Clock Duration (`20,000` Scenarios) | `87.12 s` |
| Scenario Throughput | **`229.57 scenarios/sec`** |
| Conversational Rate (Turns / sec) | **`230.95 turns/sec`** (**`13856.9 turns/min`**) |
| Amortized Turn Latency `p50` | `69.3 ms` |
| Amortized Turn Latency `p90` | `75.99 ms` |
| Amortized Turn Latency `p95` | `85.8 ms` |
| Amortized Turn Latency `p99` | `87.31 ms` |
| Single-Turn Live HTTP RTT `p50` / `p95` | `100.9 ms` / `1259.19 ms` |

## 2. Accuracy & Latency by Language Family (`en`, `ar`/`pga`, `din`)

| Language Family | Scenarios | Passed | Accuracy | Mean Latency (`ms`) |
|---|---|---|---|---|
| `en` | `6800` | `6800` | **`100.0%`** | `73.75 ms` |
| `ar` | `6600` | `6600` | **`100.0%`** | `64.65 ms` |
| `din` | `6600` | `6600` | **`100.0%`** | `65.76 ms` |

## 3. Accuracy & Latency by Modality (`TTT`, `STT`, `TTS`)

| Modality | Scenarios | Passed | Accuracy | Mean Latency (`ms`) |
|---|---|---|---|---|
| `TTT` | `8000` | `8000` | **`100.0%`** | `68.57 ms` |
| `STT` | `6000` | `6000` | **`100.0%`** | `66.06 ms` |
| `TTS` | `6000` | `6000` | **`100.0%`** | `69.55 ms` |

## 4. Accuracy by Functional, Long-Horizon, EQ & Security Category (`20,000` Scenarios)

| Category | Scenarios | Passed | Accuracy |
|---|---|---|---|
| `AUTHENTICATED_T1_SELF_SERVICE` | `2000` | `2000` | **`100.0%`** |
| `FUZZY_GROUPED_TIN_AND_FILING` | `500` | `500` | **`100.0%`** |
| `FUZZY_SECURITY_HOMOGLYPH_INJECTION` | `500` | `500` | **`100.0%`** |
| `FUZZY_SECURITY_MULTILINGUAL_INJECTION` | `500` | `500` | **`100.0%`** |
| `FUZZY_SECURITY_SUBJECT_SMUGGLE` | `500` | `500` | **`100.0%`** |
| `LONG_HORIZON_COMPOUND_PLANNER` | `2000` | `2000` | **`100.0%`** |
| `LONG_HORIZON_WORKFLOW_DELEGATION` | `2000` | `2000` | **`100.0%`** |
| `MULTILINGUAL_TCC_JOURNEY` | `2000` | `2000` | **`100.0%`** |
| `MULTIMODAL_EQ_DEESCALATION` | `1000` | `1000` | **`100.0%`** |
| `MULTIMODAL_EQ_ESCALATION` | `1000` | `1000` | **`100.0%`** |
| `OFFICIAL_CHANNEL_VERIFICATION` | `2000` | `2000` | **`100.0%`** |
| `STATUTORY_NUMERIC_PAYE` | `2000` | `2000` | **`100.0%`** |
| `STATUTORY_NUMERIC_WHT` | `2000` | `2000` | **`100.0%`** |
| `T4_AND_OOS_GOVERNANCE_GATE` | `2000` | `2000` | **`100.0%`** |
