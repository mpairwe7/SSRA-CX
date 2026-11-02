# Hardened Multi-Stage Container for SSRA Assist Unified Space Runtime (CIS Docker Benchmark v1.7)
FROM node:24.19.0-bookworm-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df AS node_runtime
RUN mkdir -p /opt/node-libs && cp -a /usr/lib/*/libstdc++.so.6* /opt/node-libs/

FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime

LABEL org.opencontainers.image.title="ssra-cx-space" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /opt/node-libs/ /usr/local/lib/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    SSRA_HF_SPACE_EMBED=1 \
    SSRA_RUNTIME_MODE=production \
    NODE_ENV=production \
    HOSTNAME="0.0.0.0" \
    PORT=7860 \
    INTERNAL_API_URL="http://127.0.0.1:8000" \
    INTERNAL_RUNTIME_URL="http://127.0.0.1:8001" \
    PYTHONPATH="/app/libs/ssra_core/src:/app/libs/ssra_security/src:/app/libs/ssra_rules/src:/app/libs/ssra_llm/src:/app/libs/ssra_mcp/src:/app/libs/ssra_adapters/src:/app/libs/ssra_testing/src:/app/mcp-servers/knowledge/src:/app/mcp-servers/tax-facts/src:/app/mcp-servers/official-channels/src:/app/mcp-servers/taxpayer/src:/app/mcp-servers/ledger/src:/app/mcp-servers/payments-info/src:/app/mcp-servers/tcc/src:/app/mcp-servers/customs/src:/app/mcp-servers/cases/src:/app/mcp-servers/appointments/src:/app/mcp-servers/notifications/src:/app/services/api/src:/app/services/agent-runtime/src:/app/services/channel-gateway/src:/app/services/voice/src:/app/services/workers/src"

RUN ldconfig && \
    node --version && \
    groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra && \
    pip install --no-cache-dir "fastapi==0.139.2" "uvicorn==0.54.0" "pydantic==2.14.0" "pydantic-settings==2.15.0" "pyyaml==6.0.2" "langgraph==1.2.14" "httpx==0.28.1" "jsonschema==4.25.1" "sqlalchemy==2.1.4" "structlog==26.1.0" "stamina==26.1.0" "tenacity==9.2.1" "orjson==3.13.0" "cryptography==50.0.2"

WORKDIR /app
COPY --chown=10001:10001 package.json pnpm-lock.yaml pnpm-workspace.yaml pyproject.toml uv.lock ./
COPY --chown=10001:10001 ai ./ai
COPY --chown=10001:10001 knowledge ./knowledge
COPY --chown=10001:10001 libs ./libs
COPY --chown=10001:10001 mcp-servers ./mcp-servers
COPY --chown=10001:10001 services ./services
COPY --chown=10001:10001 packages ./packages
COPY --chown=10001:10001 apps/web ./apps/web
COPY --chown=10001:10001 apps/console ./apps/console

USER 10001:10001
EXPOSE 7860
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/healthz')"]
CMD ["sh", "-c", "uvicorn ssra_api.main:app --host 127.0.0.1 --port 8000 --no-access-log & API_PID=$!; uvicorn ssra_runtime.main:app --host 127.0.0.1 --port 8001 --no-access-log & RT_PID=$!; node apps/web/server.js & WEB_PID=$!; trap 'kill -TERM $API_PID $RT_PID $WEB_PID 2>/dev/null || true; wait $API_PID $RT_PID $WEB_PID 2>/dev/null || true; exit 0' TERM INT; wait $WEB_PID; STATUS=$?; kill -TERM $API_PID $RT_PID 2>/dev/null || true; wait $API_PID $RT_PID 2>/dev/null || true; exit $STATUS"]
