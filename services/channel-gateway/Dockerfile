# Hardened Multi-Stage Python 3.14 Container for SSRA Assist Channel Gateway (CIS Docker Benchmark v1.7)
FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime

LABEL org.opencontainers.image.title="ssra-channel-gateway" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PORT=8002 \
    PYTHONPATH="/app/libs/ssra_core/src:/app/libs/ssra_security/src:/app/libs/ssra_rules/src:/app/libs/ssra_testing/src:/app/services/channel-gateway/src"

RUN groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra && \
    pip install --no-cache-dir "fastapi==0.139.2" "uvicorn==0.54.0" "pydantic==2.14.0" "pydantic-settings==2.15.0" "pyyaml==6.0.2" "httpx==0.28.1" "jsonschema==4.25.1" "structlog==26.1.0" "stamina==26.1.0" "tenacity==9.2.1" "orjson==3.13.0" "cryptography==50.0.2"

WORKDIR /app
COPY --chown=10001:10001 pyproject.toml uv.lock ./
COPY --chown=10001:10001 ai ./ai
COPY --chown=10001:10001 libs ./libs
COPY --chown=10001:10001 services/channel-gateway ./services/channel-gateway

USER 10001:10001
EXPOSE 8002
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/healthz')"]
CMD ["uvicorn", "ssra_channel_gateway.main:app", "--host", "0.0.0.0", "--port", "8002", "--no-access-log"]
