# SSRA Assist — 20,000-Scenario Complex Multimodal (`TTT`, `STT`, `TTS`) Live Ngrok Stress, Fuzzy, Volume & Load Report

- **Date:** 2026-10-21
- **Git Revision:** `884b622`
- **Live Ngrok Endpoint:** `https://<redacted-ngrok-tunnel>`
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
| Total Wall-Clock Duration (`20,000` Scenarios) | `75.78 s` |
| Scenario Throughput | **`263.92 scenarios/sec`** |
| Conversational Rate (Turns / sec) | **`265.51 turns/sec`** (**`15930.4 turns/min`**) |
| Amortized Turn Latency `p50` | `56.35 ms` |
| Amortized Turn Latency `p90` | `68.02 ms` |
| Amortized Turn Latency `p95` | `71.82 ms` |
| Amortized Turn Latency `p99` | `93.22 ms` |
| Single-Turn Ngrok HTTPS RTT `p50` / `p95` | `651.84 ms` / `1327.98 ms` |

## 2. Accuracy & Latency by Language Family (`en`, `ar`/`pga`, `din`)

| Language Family | Scenarios | Passed | Accuracy | Mean Latency (`ms`) |
|---|---|---|---|---|
| `en` | `6800` | `6800` | **`100.0%`** | `67.45 ms` |
| `ar` | `6600` | `6600` | **`100.0%`** | `60.01 ms` |
| `din` | `6600` | `6600` | **`100.0%`** | `41.21 ms` |

## 3. Accuracy & Latency by Modality (`TTT`, `STT`, `TTS`)

| Modality | Scenarios | Passed | Accuracy | Mean Latency (`ms`) |
|---|---|---|---|---|
| `TTT` | `8000` | `8000` | **`100.0%`** | `67.28 ms` |
| `STT` | `6000` | `6000` | **`100.0%`** | `49.59 ms` |
| `TTS` | `6000` | `6000` | **`100.0%`** | `48.49 ms` |

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
