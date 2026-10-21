# Hardened Node 24 Alpine Container for SSRA Assist Taxpayer Web PWA (CIS Docker Benchmark v1.7)
FROM node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS runtime

LABEL org.opencontainers.image.title="ssra-web" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ARG NEXT_PUBLIC_API_URL=http://localhost:18000
ARG INTERNAL_API_URL=http://ssra-api:8000
ARG INTERNAL_RUNTIME_URL=http://ssra-agent-runtime:8001

ENV NODE_ENV=production \
    HOSTNAME="0.0.0.0" \
    PORT=3000 \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    INTERNAL_API_URL=$INTERNAL_API_URL \
    INTERNAL_RUNTIME_URL=$INTERNAL_RUNTIME_URL

RUN addgroup -g 10001 -S ssra && \
    adduser -u 10001 -S ssra -G ssra

WORKDIR /app
COPY --chown=10001:10001 package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY --chown=10001:10001 packages ./packages
COPY --chown=10001:10001 apps/web ./apps/web

USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
CMD ["node", "apps/web/server.js"]
