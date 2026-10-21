# Hardened Node 24 Alpine Container for SSRA Assist Staff Console (CIS Docker Benchmark v1.7)
FROM node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS runtime

LABEL org.opencontainers.image.title="ssra-console" \
      org.opencontainers.image.vendor="South Sudan Revenue Authority (SSRA)" \
      org.opencontainers.image.source="https://github.com/mpairwe7/SSRA-CX"

ARG INTERNAL_API_URL=http://ssra-api:8000

ENV NODE_ENV=production \
    HOSTNAME="0.0.0.0" \
    PORT=3001 \
    INTERNAL_API_URL=$INTERNAL_API_URL

RUN addgroup -g 10001 -S ssra && \
    adduser -u 10001 -S ssra -G ssra

WORKDIR /app
COPY --chown=10001:10001 package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY --chown=10001:10001 packages ./packages
COPY --chown=10001:10001 apps/console ./apps/console

USER 10001:10001
EXPOSE 3001
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3001/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
CMD ["node", "apps/console/server.js"]
