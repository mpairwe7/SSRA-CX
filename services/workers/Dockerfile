# Hardened Multi-Stage Python 3.14 Container for SSRA Assist Temporal Workers (CIS Docker Benchmark v1.7)
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="ssra-workers" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

RUN groupadd --gid 10001 ssra && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin --no-create-home ssra

WORKDIR /app
COPY --chown=10001:10001 pyproject.toml uv.lock ./
COPY --chown=10001:10001 libs ./libs
COPY --chown=10001:10001 services/workers ./services/workers

USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-m", "ssra_workers"]
CMD ["python3", "-m", "ssra_workers"]
