# Hardened Multi-Stage Python 3.14 Container for SSRA Assist Agent Runtime (CIS Docker Benchmark v1.7)
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="ssra-agent-runtime" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PORT=8001

RUN groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra

WORKDIR /app
COPY --chown=10001:10001 pyproject.toml uv.lock ./
COPY --chown=10001:10001 ai ./ai
COPY --chown=10001:10001 knowledge ./knowledge
COPY --chown=10001:10001 libs ./libs
COPY --chown=10001:10001 mcp-servers ./mcp-servers
COPY --chown=10001:10001 services/agent-runtime ./services/agent-runtime

USER 10001:10001
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz')"]
CMD ["uvicorn", "ssra_runtime.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
