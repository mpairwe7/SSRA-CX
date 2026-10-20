# SSRA Assist — 1,000-Scenario Complex Multimodal (`TTT`, `STT`, `TTS`) Live Ngrok Stress & Load Report

- **Date:** 2026-10-21
- **Live Ngrok Endpoint:** `https://<redacted-ngrok-tunnel>`
- **Total Complex Scenarios Formulated & Executed:** `1000` (`340 en`, `330 ar/pga`, `330 din`)
- **Total Conversational Turns Executed:** `1060`
- **Total Live HTTP Requests Over Ngrok:** `1059`
- **Overall Scenario Pass / Accuracy Rate:** **`100.0%`** (`1000/1000`)
- **Intent & Objective Identification Accuracy:** **`100.0%`**
- **Issue Resolution & Autonomous Goal Completion Rate:** **`100.0%`**
- **Emotional Intelligence (`EQ`) Accuracy:** **`100.0%`**
- **Statutory Numeric Provenance & Spoken Figure Fidelity:** **`100.0%`**
- **4-Tier Cognitive Memory Hydration & Qdrant Sync:** `2/2` (`230` Qdrant vector points indexed at peak)
- **Right-to-Erasure Verification (In-Memory + Qdrant):** `2/2` (`0` residual points)

## 1. Performance, Throughput & Conversational Rate Metrics (Live Ngrok HTTPS)

| Metric | Value |
|---|---|
| Concurrency (Persistent TLS Keep-Alive Workers) | `16` |
| Total Wall-Clock Duration | `32.45 s` |
| Scenario Throughput | `30.81 scenarios/sec` |
| Conversational Rate (Turns / sec) | `32.66 turns/sec` (`1959.8 turns/min`) |
| HTTP Request Rate Over Ngrok | `32.63 req/sec` |
| Latency `p50` (Median) | `430.46 ms` |
| Latency `p90` | `576.58 ms` |
| Latency `p95` | `883.47 ms` |
| Latency `p99` | `1084.13 ms` |
| Latency Mean | `465.11 ms` |

## 2. Accuracy & Latency by Language Family (`en`, `ar`/`pga`, `din`)

| Language Family | Scenarios | Passed | Accuracy | Mean Latency (`ms`) |
|---|---|---|---|---|
| `en` | `340` | `340` | **`100.0%`** | `469.71 ms` |
| `ar` | `330` | `330` | **`100.0%`** | `443.58 ms` |
| `din` | `330` | `330` | **`100.0%`** | `481.89 ms` |

## 3. Accuracy & Latency by Modality (`TTT`, `STT`, `TTS`)

| Modality | Scenarios | Passed | Accuracy | Mean Latency (`ms`) |
|---|---|---|---|---|
| `TTT` | `400` | `400` | **`100.0%`** | `546.39 ms` |
| `STT` | `300` | `300` | **`100.0%`** | `414.61 ms` |
| `TTS` | `300` | `300` | **`100.0%`** | `407.24 ms` |

## 4. Accuracy by Functional, Long-Horizon, EQ & Security Category

| Category | Scenarios | Passed | Accuracy |
|---|---|---|---|
| `AUTHENTICATED_T1_SELF_SERVICE` | `100` | `100` | **`100.0%`** |
| `FUZZY_GROUPED_TIN_AND_FILING` | `24` | `24` | **`100.0%`** |
| `FUZZY_SECURITY_HOMOGLYPH_INJECTION` | `27` | `27` | **`100.0%`** |
| `FUZZY_SECURITY_MULTILINGUAL_INJECTION` | `25` | `25` | **`100.0%`** |
| `FUZZY_SECURITY_SUBJECT_SMUGGLE` | `24` | `24` | **`100.0%`** |
| `LONG_HORIZON_COMPOUND_PLANNER` | `100` | `100` | **`100.0%`** |
| `LONG_HORIZON_WORKFLOW_DELEGATION` | `100` | `100` | **`100.0%`** |
| `MULTILINGUAL_TCC_JOURNEY` | `100` | `100` | **`100.0%`** |
| `MULTIMODAL_EQ_DEESCALATION` | `49` | `49` | **`100.0%`** |
| `MULTIMODAL_EQ_ESCALATION` | `51` | `51` | **`100.0%`** |
| `OFFICIAL_CHANNEL_VERIFICATION` | `100` | `100` | **`100.0%`** |
| `STATUTORY_NUMERIC_PAYE` | `100` | `100` | **`100.0%`** |
| `STATUTORY_NUMERIC_WHT` | `100` | `100` | **`100.0%`** |
| `T4_AND_OOS_GOVERNANCE_GATE` | `100` | `100` | **`100.0%`** |
