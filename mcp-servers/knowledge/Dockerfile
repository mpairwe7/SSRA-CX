# Hardened Python 3.14 Container for SSRA MCP Server — knowledge (CIS Docker Benchmark v1.7)
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="ssra-mcp-knowledge" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PORT=8101

RUN groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra

WORKDIR /app
COPY --chown=10001:10001 . /app

USER 10001:10001
EXPOSE 8101
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8101/healthz')"]
CMD ["uvicorn", "ssra_mcp_knowledge.server:app", "--host", "0.0.0.0", "--port", "8101", "--no-access-log"]
