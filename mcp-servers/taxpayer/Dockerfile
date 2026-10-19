# Hardened Python 3.14 Container for SSRA MCP Server — taxpayer (CIS Docker Benchmark v1.7)
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="ssra-mcp-taxpayer" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PORT=8104

RUN groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra

WORKDIR /app
COPY --chown=10001:10001 . /app

USER 10001:10001
EXPOSE 8104
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8104/healthz')"]
CMD ["uvicorn", "ssra_mcp_taxpayer.server:app", "--host", "0.0.0.0", "--port", "8104", "--no-access-log"]
