# Hardened Multi-Stage Python 3.14 Container for SSRA Assist Agent Runtime (CIS Docker Benchmark v1.7)
FROM python:3.14.7-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="ssra-agent-runtime" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PORT=8001 \
    PYTHONPATH="/app/libs/ssra_core/src:/app/libs/ssra_security/src:/app/libs/ssra_rules/src:/app/libs/ssra_llm/src:/app/libs/ssra_mcp/src:/app/libs/ssra_adapters/src:/app/libs/ssra_testing/src:/app/mcp-servers/knowledge/src:/app/mcp-servers/tax-facts/src:/app/mcp-servers/official-channels/src:/app/mcp-servers/taxpayer/src:/app/mcp-servers/ledger/src:/app/mcp-servers/payments-info/src:/app/mcp-servers/tcc/src:/app/mcp-servers/customs/src:/app/mcp-servers/cases/src:/app/mcp-servers/appointments/src:/app/mcp-servers/notifications/src:/app/services/agent-runtime/src:/app/services/voice/src:/app/services/workers/src"

RUN groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra && \
    pip install --no-cache-dir "fastapi==0.139.2" "uvicorn==0.54.0" "pydantic==2.14.0" "pydantic-settings==2.15.0" "pyyaml==6.0.2" "langgraph==1.2.14" "httpx==0.28.1" "jsonschema==4.25.1" "sqlalchemy==2.1.4" "structlog==26.1.0" "stamina==26.1.0" "tenacity==9.2.1" "orjson==3.13.0" cryptography

WORKDIR /app
COPY --chown=10001:10001 pyproject.toml uv.lock ./
COPY --chown=10001:10001 ai ./ai
COPY --chown=10001:10001 knowledge ./knowledge
COPY --chown=10001:10001 libs ./libs
COPY --chown=10001:10001 mcp-servers ./mcp-servers
COPY --chown=10001:10001 services/agent-runtime ./services/agent-runtime
COPY --chown=10001:10001 services/voice ./services/voice
COPY --chown=10001:10001 services/workers ./services/workers

USER 10001:10001
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz')"]
CMD ["uvicorn", "ssra_runtime.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
