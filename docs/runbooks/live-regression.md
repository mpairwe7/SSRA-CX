# Live Regression on the GPU Profile

## Purpose

Run regression tests against a running SSRA Assist stack, after a merge or before a demonstration, in three layers: the deployed public BFF and staff preview, the Core API and agent runtime, and the 1,000-scenario benchmark. This runbook covers the local GPU Compose profile in reference mode. It does not authorize a production deployment, staff operations, or the use of taxpayer data.

## Preconditions

1. You are on an up-to-date `main` in the checkout that holds the `.env` used by Compose. Do not print or copy that file.
2. The GPUs named in `infra/compose/docker-compose.gpu.yml` (`SUNFLOWER_GPU_ID`, `REASONER_GPU_ID`, `ORPHEUS_GPU_ID`, `SSRA_GPU_DEVICE_ID`) are idle. Check with `nvidia-smi` before you start. Another workload must not share them.
3. The profile's host ports are free: `3032`, `3033`, `3034`, `8011`, `8012`, `8083`, `18000`, `18001`, `18100`, `25432`, `26333`, and `26379`.
4. Other sessions may use the same host and stack. Before you stop or rebuild containers you did not start, check `docker ps` and coordinate.
5. Use a local `TMPDIR` for browser tools (see [the browser-flow runbook](./browser-flow-assurance.md)).

## Start or refresh the stack

```bash
docker compose -f infra/compose/docker-compose.gpu.yml up -d --build --wait
docker compose -f infra/compose/docker-compose.gpu.yml ps
```

After a merge that changes only the web or staff servers, rebuild only those services:

```bash
docker compose -f infra/compose/docker-compose.gpu.yml up -d --build --no-deps --wait ssra-frontend ssra-console
```

Confirm that the running files match the checkout, for example `docker exec ssra-frontend sha256sum /app/apps/web/server.js` against `sha256sum apps/web/server.js`. Note that `infra/compose/docker-compose.gpu.yml` mounts `apps/web`, `apps/console`, `packages`, `libs`, `services/*`, `mcp-servers`, `ai`, and `knowledge` read-only with source-scoped live-watch (`uvicorn --reload-dir /app/libs/*/src --reload-dir /app/services/*/src` and `node --watch apps/*/server.js`) so source edits hot-reload cleanly while Turborepo `.turbo/*.log` and test runs never trigger spurious container restarts.

## Layer 1: public BFF and staff preview

`ssra-frontend` publishes port `3032` for a public tunnel and `3033` on loopback. Run against the public tunnel URL when one is configured, otherwise against `http://127.0.0.1:3033`:

```bash
LIVE_WEB_URL=https://<tunnel-host> LIVE_CONSOLE_URL=http://127.0.0.1:3034 \
  node tools/live_frontend_regression.mjs > live-frontend.json
```

The script checks security headers, `/healthz`, locale fallback, denial of `/v1/*` and staff paths, `400` for malformed input, and that forged identity stays anonymous. It then asks eight public questions (TIN steps, PAYE, WHT, a phishing URL, the official portal, a personal balance, an out-of-scope request, and Juba Arabic) and checks that each is answered with no invented defaults, no internal telemetry, and no estimate without an approved source. Finally it checks the announcer, the thread identifier, Arabic RTL, and the staff preview's heading, capability claims, combobox, and API denial. The exit code is non-zero if any check fails. It retries a navigation only on Chromium's `ERR_NETWORK_CHANGED`, which Docker interface changes can trigger, and records how many retries it made.

## Layer 2: Core API and agent runtime

```bash
uv run python tools/smoke_test_stack.py \
  --api-url http://127.0.0.1:18000 --runtime-url http://127.0.0.1:18001 --qdrant-url http://127.0.0.1:26333
```

The suite expects the governed fail-closed statuses: `503` for public status and the CX scorecard, and `403` for staff takeover, hand-back, and feature flags, even with an `X-SSRA-Staff-Id` header. These statuses match `services/api/tests/test_route_matrix.py`. Never change these expectations to `200` to get a passing run.

Without URLs, the same suite runs in-process. `task up` sets `SSRA_RUNTIME_MODE=reference` for that run only.

## Layer 3: 1,000-scenario benchmark

```bash
uv run python tools/run_1000_complex_ngrok_benchmark.py --ngrok-url http://127.0.0.1:18001
```

The benchmark posts to `/v1/turns`, which the public BFF denies, so run it against the runtime directly or through a tunnel that points at the runtime. The report records the run date in `Africa/Juba` and whether a tunnel was used. It overwrites `evals/reports/complex-1000-ngrok-benchmark-report.*`; commit those files only as deliberate evidence. Its `STT` and `TTS` scenarios are simulated: they send text and use synthetic word-error-rate evidence, and no audio is transcribed or synthesized. Never cite them as ASR, TTS, or voice-launch evidence.

## Evidence

Record the commit, the stack state, and each layer's result in `docs/audit/`. The [2026-10-23 live regression record](../audit/live-regression-2026-10-23.md) is an example. A passing live run is reference evidence, not production readiness.
